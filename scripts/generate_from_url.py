#!/usr/bin/env python3
"""
Generate resume and cover letter from job posting URL(s).

Fetches job details from any URL (Indeed, LinkedIn, Glassdoor, etc.) using
Playwright and generates tailored PDF documents.

Usage:
    python scripts/generate_from_url.py "https://www.indeed.com/viewjob?jk=abc123"
    python scripts/generate_from_url.py URL1 URL2 URL3
    python scripts/generate_from_url.py URL --type resume
    python scripts/generate_from_url.py URL --no-cache --dry-run
"""

import argparse
import sys
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def process_single_url(
    url: str,
    doc_type: str,
    profile: Dict[str, Any],
    cache: Any,
    resume_tools: Any,
    no_cache: bool,
    dry_run: bool,
    fetch_job_from_url: callable,
    detect_job_site: callable,
) -> Tuple[bool, Optional[Dict[str, Any]], List[Tuple[str, str]]]:
    """
    Process a single URL and generate documents.
    
    Returns:
        Tuple of (success, job_data, generated_files)
    """
    print()
    print("-" * 70)
    site = detect_job_site(url)
    print(f"🌐 {site.capitalize()}: {url[:65]}...")
    print("-" * 70)
    
    # Step 1: Check if job is already cached
    existing = cache.get_by_url(url)
    if existing:
        job = existing
        job_id = existing.get('id')
        print(f"   💾 Found in cache (ID: {job_id})")
        print(f"   ✅ {job.get('title', 'Unknown')} @ {job.get('company', 'Unknown')}")
        print(f"      📍 {job.get('location', 'Not specified')}")
        
        if dry_run:
            print("   🏃 DRY RUN - skipping document generation")
            return True, job, []
    else:
        # Step 2: Fetch job details from URL
        print("   📋 Fetching job details from web...")
        job = fetch_job_from_url(url)
        
        if not job:
            print("   ❌ Failed to fetch job details")
            return False, None, []
        
        print(f"   ✅ {job.get('title', 'Unknown')} @ {job.get('company', 'Unknown')}")
        print(f"      📍 {job.get('location', 'Not specified')}")
        
        # Dry run - just show extracted info
        if dry_run:
            print("   🏃 DRY RUN - skipping document generation")
            return True, job, []
        
        # Step 3: Add to cache
        job_id = hashlib.md5(job.get('url', '').encode()).hexdigest()[:12]
        
        if not no_cache:
            if cache.add(job):
                print(f"   💾 Cached (ID: {job_id})")
                cache._save_jobs()
        else:
            job['id'] = job_id
            cache.add(job)
    
    # Step 3: Generate documents
    generated_files = []
    
    try:
        if doc_type in ["resume", "both"]:
            print("   📄 Generating resume...")
            result = resume_tools.generate_resume(job_id, profile.get('id', ''))
            if "pdf_path:" in result:
                for line in result.split('\n'):
                    if line.strip().startswith('pdf_path:'):
                        pdf_path = line.split(':', 1)[1].strip()
                        generated_files.append(("Resume", pdf_path))
                        break
            print("   ✅ Resume done")
        
        if doc_type in ["cover-letter", "both"]:
            print("   📄 Generating cover letter...")
            result = resume_tools.generate_cover_letter(job_id, profile.get('id', ''))
            if "pdf_path:" in result:
                for line in result.split('\n'):
                    if line.strip().startswith('pdf_path:'):
                        pdf_path = line.split(':', 1)[1].strip()
                        generated_files.append(("Cover Letter", pdf_path))
                        break
            print("   ✅ Cover letter done")
            
    except Exception as e:
        print(f"   ❌ Error generating documents: {e}")
        if no_cache:
            cache.remove(job_id)
        return False, job, generated_files
    
    # Cleanup if --no-cache
    if no_cache:
        cache.remove(job_id)
    
    return True, job, generated_files


def main():
    parser = argparse.ArgumentParser(
        description="Generate resume and cover letter from job posting URL(s)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single URL
  python scripts/generate_from_url.py "https://www.indeed.com/viewjob?jk=abc123"
  
  # Multiple URLs
  python scripts/generate_from_url.py URL1 URL2 URL3
  
  # Options
  python scripts/generate_from_url.py URL --type resume
  python scripts/generate_from_url.py URL --type cover-letter
  python scripts/generate_from_url.py URL --dry-run
  python scripts/generate_from_url.py URL --no-cache
  python scripts/generate_from_url.py URL --profile justin_masui
"""
    )
    parser.add_argument("urls", nargs='+', help="Job posting URL(s) (Indeed, LinkedIn, Glassdoor, etc.)")
    parser.add_argument("--type", choices=["resume", "cover-letter", "both"], 
                        default="both", help="Document type to generate (default: both)")
    parser.add_argument("--profile", help="Profile ID to use (default: first profile)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Don't add jobs to cache after fetching")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and extract job details without generating documents")
    parser.add_argument("--max-critiques", type=int, default=3,
                        help="Maximum critique iterations (default: 3)")
    args = parser.parse_args()
    
    from job_agent_coordinator.tools.url_job_fetcher import fetch_job_from_url, detect_job_site
    from job_agent_coordinator.tools.job_cache import get_cache
    from job_agent_coordinator.tools.profile_store import get_store
    from job_agent_coordinator.tools import resume_tools
    
    print("=" * 70)
    print("GENERATE DOCUMENTS FROM URL")
    print("=" * 70)
    print(f"📋 URLs to process: {len(args.urls)}")
    print(f"📄 Document Type: {args.type}")
    print(f"💾 Cache Jobs: {'no' if args.no_cache else 'yes'}")
    print(f"🏃 Mode: {'DRY RUN' if args.dry_run else 'GENERATE'}")
    print("=" * 70)
    
    # Load profile
    store = get_store()
    profiles = store.list_profiles()
    
    if not profiles:
        print("\n❌ No profiles found. Create a profile first:")
        print("   python scripts/add_profile.py")
        sys.exit(1)
    
    if args.profile:
        profile = store.get(args.profile)
        if not profile:
            print(f"\n❌ Profile not found: {args.profile}")
            print("   Available profiles:", [p.get('id') for p in profiles])
            sys.exit(1)
    else:
        profile = store.get(profiles[0].get('id'))
    
    print(f"\n👤 Using profile: {profile.get('name', profile.get('id'))}")
    
    # Set max iterations
    resume_tools.set_max_iterations(args.max_critiques)
    
    # Get cache
    cache = get_cache()
    
    # Process each URL
    results = []  # List of (url, success, job, files)
    
    for i, url in enumerate(args.urls):
        print(f"\n[{i+1}/{len(args.urls)}]", end="")
        
        success, job, files = process_single_url(
            url=url,
            doc_type=args.type,
            profile=profile,
            cache=cache,
            resume_tools=resume_tools,
            no_cache=args.no_cache,
            dry_run=args.dry_run,
            fetch_job_from_url=fetch_job_from_url,
            detect_job_site=detect_job_site,
        )
        
        results.append((url, success, job, files))
    
    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    successful = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]
    
    print(f"✅ Successful: {len(successful)}/{len(results)}")
    if failed:
        print(f"❌ Failed: {len(failed)}/{len(results)}")
    print()
    
    if successful:
        print("📋 Processed jobs:")
        for url, success, job, files in successful:
            if job:
                print(f"   • {job.get('title', 'Unknown')[:40]} @ {job.get('company', 'Unknown')[:20]}")
                for doc_type, path in files:
                    print(f"     📄 {doc_type}: {Path(path).name}")
        print()
    
    if failed:
        print("❌ Failed URLs:")
        for url, success, job, files in failed:
            print(f"   • {url[:60]}...")
        print()
    
    # Exit with error if any failed
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
