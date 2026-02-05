#!/usr/bin/env python3
"""
Run job scraper to fetch jobs from configured sources.

Supports checkpointing - if interrupted, run with --resume to continue.
Automatically filters out companies in your profile's exclusion list.

Usage:
    python scripts/run_job_scraper.py                    # Show available sources
    python scripts/run_job_scraper.py --source Boeing    # Scrape single source
    python scripts/run_job_scraper.py --category Aerospace  # Scrape category
    python scripts/run_job_scraper.py --all              # Scrape all sources (SLOW!)
    python scripts/run_job_scraper.py --all --workers 5  # Parallel scrape (FAST!)
    python scripts/run_job_scraper.py --max-sources 5    # Scrape first 5 sources
    python scripts/run_job_scraper.py --resume           # Resume interrupted scrape
    python scripts/run_job_scraper.py --status           # Show checkpoint status
    python scripts/run_job_scraper.py --exclude "Amazon,Meta"  # Override exclusions
    python scripts/run_job_scraper.py --no-exclude       # Disable exclusion filtering
"""

import argparse
import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.tools.job_links_scraper import (
    get_links_summary,
    scrape_single_source,
    scrape_job_links,
    ScrapingProgress,
)
from job_agent_coordinator.tools.job_cache import get_cache
from job_agent_coordinator.tools.profile_store import get_store


def show_checkpoint_status():
    """Show current checkpoint status."""
    progress = ScrapingProgress()
    summary = progress.get_summary()
    
    print("=" * 70)
    print("CHECKPOINT STATUS")
    print("=" * 70)
    
    if summary["status"] == "idle":
        print("📭 No active checkpoint")
        print("   Start a new scrape with --all, --category, or --max-sources")
    elif summary["status"] == "complete":
        print("✅ Last scrape completed")
        print(f"   Sources: {summary['completed']}/{summary['total_sources']}")
        print(f"   Jobs found: {summary['jobs_found']}")
        print(f"   Jobs cached: {summary['jobs_cached']}")
        print(f"   Started: {summary['started_at']}")
        print(f"   Finished: {summary['updated_at']}")
    else:
        print("⏸️  Scrape in progress (interrupted)")
        print(f"   Sources: {summary['completed']}/{summary['total_sources']}")
        print(f"   Jobs found so far: {summary['jobs_found']}")
        print(f"   Jobs cached so far: {summary['jobs_cached']}")
        print(f"   Started: {summary['started_at']}")
        print(f"   Last update: {summary['updated_at']}")
        print()
        print("   💡 Run with --resume to continue")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape jobs from configured sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show available sources and categories
  python scripts/run_job_scraper.py
  
  # Scrape a single source
  python scripts/run_job_scraper.py --source Boeing
  
  # Scrape a category
  python scripts/run_job_scraper.py --category Aerospace
  
  # Scrape all (with checkpointing)
  python scripts/run_job_scraper.py --all
  
  # Resume interrupted scrape
  python scripts/run_job_scraper.py --resume
  
  # Check status
  python scripts/run_job_scraper.py --status
"""
    )
    parser.add_argument("--source", "-s", type=str, help="Scrape a single source by name")
    parser.add_argument("--category", "-c", type=str, help="Scrape all sources in a category")
    parser.add_argument("--all", action="store_true", help="Scrape ALL sources (takes 10-20 min!)")
    parser.add_argument("--max-sources", type=int, default=0, help="Limit number of sources to scrape")
    parser.add_argument("--delay", type=int, default=2, help="Delay between requests (seconds)")
    parser.add_argument("--no-pagination", action="store_true", help="Don't follow pagination links")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--status", action="store_true", help="Show checkpoint status")
    parser.add_argument("--clear", action="store_true", help="Clear checkpoint and start fresh")
    parser.add_argument("--force", "-f", action="store_true", help="Force scrape even if already scraped today")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show progress for each source")
    parser.add_argument("--exclude", type=str, help="Companies to exclude (comma-separated), overrides profile")
    parser.add_argument("--no-exclude", action="store_true", help="Disable exclusion filtering")
    parser.add_argument("--workers", "-w", type=int, default=5, help="Parallel workers (default: 5)")
    args = parser.parse_args()
    
    # Load exclusions from profile or command line
    exclusions = []
    if not args.no_exclude:
        if args.exclude:
            exclusions = [c.strip().lower() for c in args.exclude.split(",") if c.strip()]
        else:
            # Auto-load from profile
            context = get_store().get_search_context()
            exclusions = [c.lower() for c in context.get("excluded_companies", [])]

    # Handle --status
    if args.status:
        show_checkpoint_status()
        return

    # Handle --clear
    if args.clear:
        progress = ScrapingProgress()
        progress.clear()
        print("✅ Checkpoint cleared")
        return

    # Handle --resume without other args
    if args.resume and not args.category and not args.all and not args.max_sources:
        # Resume previous scrape
        progress = ScrapingProgress()
        summary = progress.get_summary()
        if summary["status"] == "idle":
            print("❌ No checkpoint to resume. Start a new scrape first.")
            return
        if summary["status"] == "complete":
            print("✅ Previous scrape already complete. Use --clear to start fresh.")
            return
        # Resume with same settings
        args.all = True  # Will skip already-done sources

    # Show summary if no action specified
    if not args.source and not args.category and not args.all and not args.max_sources:
        summary = get_links_summary()
        print("=" * 70)
        print("JOB SOURCES SUMMARY")
        print("=" * 70)
        print(summary["toon_report"])
        print()
        print("Usage examples:")
        print("  python scripts/run_job_scraper.py --source Boeing")
        print("  python scripts/run_job_scraper.py --category Aerospace")
        print("  python scripts/run_job_scraper.py --max-sources 5")
        print("  python scripts/run_job_scraper.py --all  # Takes 10-20 min!")
        print("  python scripts/run_job_scraper.py --resume  # Continue interrupted")
        print("  python scripts/run_job_scraper.py --status  # Check progress")
        return

    cache = get_cache()
    initial_count = len(cache.list_all(limit=10000))
    start_time = time.time()

    print("=" * 70)
    print("JOB SCRAPER")
    print("=" * 70)
    print(f"📦 Initial cache: {initial_count} jobs")
    if args.resume:
        print("📥 Mode: RESUME from checkpoint")
    if args.workers > 1:
        print(f"⚡ Parallel mode: {args.workers} workers")
    if exclusions and not args.no_exclude:
        print(f"🚫 Excluding companies: {', '.join(exclusions)}")
    print()

    # Progress callback for verbose mode
    def on_progress(completed, total, source_result):
        if args.verbose:
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / rate if rate > 0 else 0
            name = source_result.get("name", "?")
            jobs = source_result.get("jobs_found", 0)
            cached = source_result.get("jobs_cached", 0)
            status = "✅" if source_result.get("success") else "❌"
            print(f"   {status} [{completed}/{total}] {name}: {jobs} found, {cached} cached (~{eta:.0f}s remaining)")

    if args.source:
        # Check if source is excluded
        if exclusions and any(exc in args.source.lower() for exc in exclusions):
            print(f"❌ Source '{args.source}' matches exclusion list. Skipping.")
            print(f"   Use --no-exclude to override.")
            return
        
        # Scrape single source (no checkpointing for single source)
        print(f"🕷️  Scraping source: {args.source}")
        if args.force:
            print("   (force mode: ignoring same-day cache)")
        print("-" * 70)
        result = scrape_single_source(
            source_name=args.source,
            cache_results=True,
            force=args.force,
        )
    elif args.category or args.all or args.max_sources:
        # Scrape multiple sources with checkpointing
        categories = args.category if args.category else ""
        max_sources = args.max_sources if args.max_sources > 0 else 0
        
        if args.resume:
            print("📥 Resuming from checkpoint...")
        elif args.all:
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
            resume=args.resume,
            skip_same_day=not args.force,
            on_progress=on_progress if args.verbose else None,
            workers=args.workers,
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
        if result.get("resumed_sources", 0) > 0:
            print(f"⏭️  Sources resumed: {result.get('resumed_sources', 0)}")
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
