#!/usr/bin/env python3
"""
Run job scraper to fetch jobs from configured sources.

Usage:
    python scripts/run_job_scraper.py                    # Show available sources
    python scripts/run_job_scraper.py --source Boeing    # Scrape single source
    python scripts/run_job_scraper.py --category Aerospace  # Scrape category
    python scripts/run_job_scraper.py --all              # Scrape all sources (SLOW!)
    python scripts/run_job_scraper.py --max-sources 5    # Scrape first 5 sources
"""

import argparse
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.tools.job_links_scraper import (
    get_links_summary,
    scrape_single_source,
    scrape_job_links,
)
from job_agent_coordinator.tools.job_cache import get_cache


def main():
    parser = argparse.ArgumentParser(description="Scrape jobs from configured sources")
    parser.add_argument("--source", "-s", type=str, help="Scrape a single source by name")
    parser.add_argument("--category", "-c", type=str, help="Scrape all sources in a category")
    parser.add_argument("--all", action="store_true", help="Scrape ALL sources (takes 10-20 min!)")
    parser.add_argument("--max-sources", type=int, default=0, help="Limit number of sources to scrape")
    parser.add_argument("--delay", type=int, default=2, help="Delay between requests (seconds)")
    parser.add_argument("--no-pagination", action="store_true", help="Don't follow pagination links")
    args = parser.parse_args()

    # Show summary if no action specified
    if not args.source and not args.category and not args.all and not args.max_sources:
        summary = get_links_summary()
        print("=" * 70)
        print("JOB SOURCES SUMMARY")
        print("=" * 70)
        print(summary["toon_summary"])
        print()
        print("Usage examples:")
        print("  python scripts/run_job_scraper.py --source Boeing")
        print("  python scripts/run_job_scraper.py --category Aerospace")
        print("  python scripts/run_job_scraper.py --max-sources 5")
        print("  python scripts/run_job_scraper.py --all  # Takes 10-20 min!")
        return

    cache = get_cache()
    initial_count = len(cache.list_all(limit=10000))

    print("=" * 70)
    print("JOB SCRAPER")
    print("=" * 70)
    print(f"📦 Initial cache: {initial_count} jobs")
    print()

    if args.source:
        # Scrape single source
        print(f"🕷️  Scraping source: {args.source}")
        print("-" * 70)
        result = scrape_single_source(
            source_name=args.source,
            cache_results=True,
            delay_seconds=args.delay,
        )
    elif args.category or args.all or args.max_sources:
        # Scrape multiple sources
        categories = args.category if args.category else None
        max_sources = args.max_sources if args.max_sources > 0 else None
        
        if args.all:
            print("🕷️  Scraping ALL sources (this will take 10-20 minutes!)")
        elif categories:
            print(f"🕷️  Scraping category: {categories}")
        elif max_sources:
            print(f"🕷️  Scraping first {max_sources} sources")
        print("-" * 70)
        
        result = scrape_job_links(
            categories=categories,
            max_sources=max_sources,
            cache_results=True,
            delay_seconds=args.delay,
            follow_pagination=not args.no_pagination,
        )

    # Show results
    print()
    print("=" * 70)
    if result.get("success"):
        print("✅ SCRAPE COMPLETE!")
        print("=" * 70)
        print(f"📊 Jobs found: {result.get('jobs_found', 0)}")
        print(f"💾 Jobs cached: {result.get('jobs_cached', 0)}")
        print(f"🔄 Duplicates: {result.get('duplicates_skipped', 0)}")
        print(f"📡 Sources scraped: {result.get('sources_scraped', 0)}")
        print(f"❌ Sources failed: {result.get('sources_failed', 0)}")
        print(f"⏱️  Time: {result.get('elapsed_seconds', 0)}s")
        print()

        # Final cache count
        final_count = len(cache.list_all(limit=10000))
        print(f"📦 Final cache: {final_count} jobs (+{final_count - initial_count} new)")
        print()

        if result.get("toon_report"):
            print("📝 TOON Report:")
            print("-" * 70)
            print(result["toon_report"])
    else:
        print("❌ SCRAPE FAILED")
        print("=" * 70)
        print(f"Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
