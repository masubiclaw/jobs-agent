#!/usr/bin/env python3
"""
Search job aggregators (Indeed, LinkedIn, Glassdoor, ZipRecruiter) using JobSpy.

Usage:
    python scripts/run_jobspy_search.py "software engineer" "Seattle, WA"
    python scripts/run_jobspy_search.py "ML engineer" "Remote" --results 50
    python scripts/run_jobspy_search.py "data scientist" "San Francisco" --sites indeed,glassdoor
    python scripts/run_jobspy_search.py "engineer" "Seattle" --exclude "Amazon,Microsoft"
"""

import argparse
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.tools.jobspy_tools import search_jobs_with_jobspy, JOBSPY_AVAILABLE
from job_agent_coordinator.tools.job_cache import get_cache


def main():
    parser = argparse.ArgumentParser(
        description="Search job aggregators using JobSpy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_jobspy_search.py "software engineer" "Seattle, WA"
  python scripts/run_jobspy_search.py "ML engineer" "Remote" --results 50
  python scripts/run_jobspy_search.py "data scientist" "Bay Area" --sites indeed,glassdoor
  python scripts/run_jobspy_search.py "engineer" "Seattle" --exclude "Amazon,Microsoft,Boeing"
  python scripts/run_jobspy_search.py "manager" "NYC" --hours 72  # Last 3 days only
"""
    )
    parser.add_argument("search_term", type=str, help="Job search term (e.g., 'software engineer')")
    parser.add_argument("location", type=str, help="Location (e.g., 'Seattle, WA' or 'Remote')")
    parser.add_argument("--results", "-n", type=int, default=25, help="Number of results (default: 25)")
    parser.add_argument("--sites", "-s", type=str, default="indeed,linkedin", 
                        help="Sites to search: indeed,linkedin,glassdoor,zip_recruiter (default: indeed,linkedin)")
    parser.add_argument("--exclude", "-x", type=str, default="", 
                        help="Comma-separated companies to exclude (e.g., 'Amazon,Microsoft')")
    parser.add_argument("--hours", type=int, default=168, help="Max hours old (default: 168 = 7 days)")
    parser.add_argument("--no-cache", action="store_true", help="Don't cache results")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full job details")
    args = parser.parse_args()

    if not JOBSPY_AVAILABLE:
        print("❌ JobSpy not installed!")
        print("   Install with: pip install python-jobspy")
        sys.exit(1)

    cache = get_cache()
    initial_count = len(cache.list_all(limit=10000))

    print("=" * 70)
    print("JOBSPY SEARCH")
    print("=" * 70)
    print(f"🔍 Search: '{args.search_term}'")
    print(f"📍 Location: {args.location}")
    print(f"🌐 Sites: {args.sites}")
    print(f"📊 Results: {args.results}")
    print(f"⏰ Max age: {args.hours} hours ({args.hours // 24} days)")
    if args.exclude:
        print(f"🚫 Excluding: {args.exclude}")
    print("=" * 70)
    print()

    result = search_jobs_with_jobspy(
        search_term=args.search_term,
        location=args.location,
        results_wanted=args.results,
        hours_old=args.hours,
        sites=args.sites,
        exclude_companies=args.exclude,
    )

    if result.get("success"):
        jobs = result.get("jobs", [])
        print(f"✅ Found {len(jobs)} jobs")
        print()

        if jobs:
            # Group by platform
            by_platform = {}
            for job in jobs:
                p = job.get("platform", "unknown")
                by_platform[p] = by_platform.get(p, 0) + 1
            
            print("📊 By Platform:")
            for platform, count in sorted(by_platform.items(), key=lambda x: -x[1]):
                print(f"   {platform}: {count}")
            print()

            # Show jobs
            print("📋 JOBS:")
            print("-" * 70)
            for i, job in enumerate(jobs, 1):
                title = job.get("title", "Unknown")[:45]
                company = job.get("company", "Unknown")[:20]
                location = job.get("location", "")[:20]
                salary = job.get("salary", "")
                platform = job.get("platform", "")
                url = job.get("url", "")

                print(f"{i:2}. {title}")
                print(f"    📍 {company} | {location} | {platform}")
                if salary and salary != "Not disclosed":
                    print(f"    💰 {salary}")
                if args.verbose and url:
                    print(f"    🔗 {url}")
                print()

        # Cache stats
        if not args.no_cache:
            final_count = len(cache.list_all(limit=10000))
            new_jobs = final_count - initial_count
            print("-" * 70)
            print(f"💾 Cache: {final_count} jobs (+{new_jobs} new)")
    else:
        print(f"❌ Search failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
