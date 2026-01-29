#!/usr/bin/env python3
"""
Fetch job descriptions from URLs and update the cache.

Many jobs are cached with just titles/metadata. This script fetches
the full descriptions from job posting URLs.

Usage:
    python scripts/fetch_descriptions.py              # Fetch all missing descriptions
    python scripts/fetch_descriptions.py --limit 50   # Limit to 50 jobs
    python scripts/fetch_descriptions.py --force      # Re-fetch even if description exists
"""

import argparse
import re
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ Missing dependencies. Run: pip install requests beautifulsoup4")
    sys.exit(1)

from job_agent_coordinator.tools.job_cache import get_cache

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
REQUEST_TIMEOUT = 15


def fetch_description(url: str) -> tuple[str, str]:
    """
    Fetch job description from URL.
    
    Returns:
        Tuple of (description, error_message)
    """
    if not url:
        return "", "no URL"
    
    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove noise
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            element.decompose()
        
        # Try common job description selectors
        selectors = [
            "#content", ".content", ".job-description", "#job-description",
            ".description", "#description", ".job-details", "#job-details",
            "#jobDescriptionText", "article", "main", "[role='main']",
            ".posting-requirements", ".job-posting", ".vacancy-description",
        ]
        
        content = None
        for selector in selectors:
            try:
                el = soup.select_one(selector)
                if el:
                    text = el.get_text(separator=" ", strip=True)
                    if len(text) > 200:
                        content = text
                        break
            except:
                continue
        
        # Fallback to body
        if not content:
            body = soup.find("body")
            content = body.get_text(separator=" ", strip=True) if body else ""
        
        # Clean up whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Truncate very long content
        content = content[:10000]
        
        if len(content) < 100:
            return "", "content too short"
        
        return content, ""
        
    except requests.exceptions.Timeout:
        return "", "timeout"
    except requests.exceptions.HTTPError as e:
        return "", f"HTTP {e.response.status_code}"
    except Exception as e:
        return "", str(e)[:50]


def main():
    parser = argparse.ArgumentParser(description="Fetch job descriptions from URLs")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of jobs to fetch")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if description exists")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent workers (default: 5)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests (default: 0.5s)")
    args = parser.parse_args()

    cache = get_cache()
    jobs = cache.list_all(limit=10000)
    
    # Filter jobs needing descriptions
    if args.force:
        jobs_to_fetch = [j for j in jobs if j.get("url")]
    else:
        jobs_to_fetch = [j for j in jobs if j.get("url") and len(j.get("description", "")) < 100]
    
    if args.limit:
        jobs_to_fetch = jobs_to_fetch[:args.limit]
    
    print(f"📊 Total jobs in cache: {len(jobs)}")
    print(f"🔍 Jobs needing descriptions: {len(jobs_to_fetch)}")
    
    if not jobs_to_fetch:
        print("✅ All jobs already have descriptions!")
        return
    
    print(f"🚀 Fetching with {args.workers} workers...")
    print()
    
    success_count = 0
    error_count = 0
    errors = []
    
    def process_job(job):
        """Fetch and return result."""
        time.sleep(args.delay)  # Rate limiting
        desc, error = fetch_description(job.get("url", ""))
        return job, desc, error
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_job, job): job for job in jobs_to_fetch}
        
        for i, future in enumerate(as_completed(futures), 1):
            job, desc, error = future.result()
            job_id = job.get("id", "unknown")
            title = job.get("title", "Unknown")[:40]
            
            if desc and len(desc) >= 100:
                # Update job in cache
                cache._jobs[job_id]["description"] = desc
                success_count += 1
                print(f"[{i}/{len(jobs_to_fetch)}] ✅ {title}: {len(desc)} chars")
            else:
                error_count += 1
                errors.append((title, error))
                print(f"[{i}/{len(jobs_to_fetch)}] ❌ {title}: {error}")
    
    # Save updated cache
    if success_count > 0:
        cache._save_jobs()
        print(f"\n💾 Saved {success_count} descriptions to cache")
    
    # Summary
    print(f"\n{'='*60}")
    print("FETCH SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed: {error_count}")
    
    if errors:
        print(f"\nCommon errors:")
        error_types = {}
        for title, err in errors:
            error_types[err] = error_types.get(err, 0) + 1
        for err, count in sorted(error_types.items(), key=lambda x: -x[1])[:5]:
            print(f"  - {err}: {count}")
    
    if success_count > 0:
        print(f"\n📝 Next steps:")
        print(f"   1. Re-export for labeling: python scripts/export_for_labeling.py")
        print(f"   2. The new export will include full descriptions")


if __name__ == "__main__":
    main()
