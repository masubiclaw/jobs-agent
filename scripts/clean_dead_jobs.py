#!/usr/bin/env python3
"""
Clean up expired or dead jobs from the cache.

Removes jobs with:
- Missing or empty URLs
- URLs that return 404/410 (optionally, with --check-urls)
- Jobs older than a specified number of days (optionally, with --older-than)

Usage:
    python scripts/clean_dead_jobs.py                    # Remove jobs with no URLs
    python scripts/clean_dead_jobs.py --check-urls       # Also check if URLs are still valid
    python scripts/clean_dead_jobs.py --older-than 14    # Remove jobs older than 14 days
    python scripts/clean_dead_jobs.py --dry-run          # Preview what would be removed
"""

import argparse
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def check_url_alive(url: str, timeout: int = 5) -> bool:
    """Check if a URL is still accessible (returns 2xx/3xx status)."""
    if not url:
        return False
    
    try:
        import requests
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        # 2xx and 3xx are OK, 404/410 are dead
        return response.status_code < 400
    except Exception:
        # Connection error, timeout, etc. - assume dead
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Clean up expired or dead jobs from the cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/clean_dead_jobs.py                    # Remove jobs with no URLs
  python scripts/clean_dead_jobs.py --check-urls       # Also validate URLs (slower)
  python scripts/clean_dead_jobs.py --older-than 14    # Remove jobs older than 14 days
  python scripts/clean_dead_jobs.py --dry-run          # Preview without removing
  python scripts/clean_dead_jobs.py --check-urls --dry-run  # Check URLs, preview only
"""
    )
    parser.add_argument("--check-urls", action="store_true", 
                        help="Validate URLs are still accessible (slower, uses HTTP HEAD)")
    parser.add_argument("--older-than", type=int, default=0,
                        help="Remove jobs older than N days (0 = don't filter by age)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be removed without actually removing")
    parser.add_argument("--threads", type=int, default=10,
                        help="Number of threads for URL checking (default: 10)")
    parser.add_argument("--timeout", type=int, default=5,
                        help="URL check timeout in seconds (default: 5)")
    args = parser.parse_args()
    
    from job_agent_coordinator.tools.job_cache import get_cache
    
    cache = get_cache()
    all_jobs = cache.list_all(limit=100000)
    
    print("=" * 70)
    print("CLEAN DEAD JOBS")
    print("=" * 70)
    print(f"📊 Total jobs in cache: {len(all_jobs)}")
    print(f"🔍 Check URLs: {'yes' if args.check_urls else 'no'}")
    print(f"📅 Older than: {args.older_than} days" if args.older_than else "📅 Age filter: disabled")
    print(f"🏃 Mode: {'DRY RUN (no changes)' if args.dry_run else 'LIVE (will remove jobs)'}")
    print("=" * 70)
    print()
    
    # Categorize jobs
    no_url_jobs = []
    old_jobs = []
    dead_url_jobs = []
    
    cutoff_date = None
    if args.older_than > 0:
        cutoff_date = datetime.now() - timedelta(days=args.older_than)
    
    # Pass 1: Find jobs with no URLs and old jobs
    print("🔍 Scanning jobs...")
    for job in all_jobs:
        url = job.get("url", "").strip()
        
        # Check for missing URL
        if not url:
            no_url_jobs.append(job)
            continue
        
        # Check for age (if enabled)
        if cutoff_date:
            added_at = job.get("added_at") or job.get("scraped_at")
            if added_at:
                try:
                    if isinstance(added_at, str):
                        # Parse ISO format
                        job_date = datetime.fromisoformat(added_at.replace("Z", "+00:00").split("+")[0])
                    else:
                        job_date = added_at
                    
                    if job_date < cutoff_date:
                        old_jobs.append(job)
                        continue
                except Exception:
                    pass  # Can't parse date, skip age check
    
    print(f"   📭 Jobs with no URL: {len(no_url_jobs)}")
    if cutoff_date:
        print(f"   📅 Jobs older than {args.older_than} days: {len(old_jobs)}")
    
    # Pass 2: Check URLs (if enabled)
    if args.check_urls:
        # Get jobs that have URLs and aren't already flagged
        flagged_ids = {j["id"] for j in no_url_jobs + old_jobs}
        jobs_to_check = [j for j in all_jobs if j["id"] not in flagged_ids and j.get("url")]
        
        print(f"\n🌐 Checking {len(jobs_to_check)} URLs (this may take a while)...")
        
        start_time = time.time()
        checked = 0
        
        def check_job_url(job):
            url = job.get("url", "")
            alive = check_url_alive(url, timeout=args.timeout)
            return job, alive
        
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            futures = {executor.submit(check_job_url, job): job for job in jobs_to_check}
            
            for future in as_completed(futures):
                job, alive = future.result()
                checked += 1
                
                if not alive:
                    dead_url_jobs.append(job)
                
                if checked % 50 == 0 or checked == len(jobs_to_check):
                    elapsed = time.time() - start_time
                    rate = checked / elapsed if elapsed > 0 else 0
                    eta = (len(jobs_to_check) - checked) / rate if rate > 0 else 0
                    print(f"   [{checked}/{len(jobs_to_check)}] {len(dead_url_jobs)} dead URLs found ({elapsed:.0f}s elapsed, ~{eta:.0f}s remaining)")
        
        print(f"   🔗 Dead URLs found: {len(dead_url_jobs)}")
    
    # Combine all jobs to remove
    to_remove = []
    seen_ids = set()
    
    for job in no_url_jobs + old_jobs + dead_url_jobs:
        if job["id"] not in seen_ids:
            to_remove.append(job)
            seen_ids.add(job["id"])
    
    print()
    print("=" * 70)
    print(f"📋 SUMMARY: {len(to_remove)} jobs to remove")
    print("=" * 70)
    
    if not to_remove:
        print("✅ No dead jobs found! Cache is clean.")
        return
    
    # Show breakdown
    print(f"   📭 No URL: {len(no_url_jobs)}")
    if args.older_than:
        print(f"   📅 Too old: {len(old_jobs)}")
    if args.check_urls:
        print(f"   🔗 Dead URL: {len(dead_url_jobs)}")
    print()
    
    # Show sample of jobs to remove
    print("📋 Sample jobs to remove:")
    print("-" * 70)
    for job in to_remove[:10]:
        title = job.get("title", "Unknown")[:40]
        company = job.get("company", "Unknown")[:20]
        reason = []
        if job in no_url_jobs:
            reason.append("no URL")
        if job in old_jobs:
            reason.append("old")
        if job in dead_url_jobs:
            reason.append("dead URL")
        print(f"   • {title} @ {company} ({', '.join(reason)})")
    
    if len(to_remove) > 10:
        print(f"   ... and {len(to_remove) - 10} more")
    print()
    
    # Remove jobs (or preview)
    if args.dry_run:
        print("🏃 DRY RUN - No jobs removed. Run without --dry-run to remove.")
    else:
        print(f"🗑️  Removing {len(to_remove)} jobs...")
        removed = 0
        for job in to_remove:
            if cache.remove(job["id"]):
                removed += 1
        
        # Also clear matches for removed jobs
        for job in to_remove:
            cache.clear_matches(job["id"])
        
        print(f"✅ Removed {removed} jobs from cache")
        
        # Show updated stats
        stats = cache.stats()
        print(f"\n💾 Cache now: {stats['total_jobs']} jobs, {stats['total_matches']} matches")


if __name__ == "__main__":
    main()
