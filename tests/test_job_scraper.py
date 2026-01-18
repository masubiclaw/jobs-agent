"""Tests for the job links scraper tool."""

import sys
import os
import logging
import time

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Suppress noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

from job_agent_coordinator.tools.job_links_scraper import (
    parse_markdown_links,
    get_links_summary,
    scrape_webpage,
    scrape_single_source,
    scrape_job_links,
    SCRAPER_MODEL,
)
from job_agent_coordinator.tools.job_cache import get_cache


def test_parse_markdown_links():
    """Test parsing links from the markdown file."""
    print("\n" + "=" * 60)
    print("TEST: Parse Markdown Links")
    print("=" * 60)
    
    links = parse_markdown_links()
    
    if not links:
        print("❌ No links found")
        return False
    
    print(f"✅ Found {len(links)} links")
    
    categories = {}
    for link in links:
        cat = link["category"]
        categories.setdefault(cat, []).append(link["name"])
    
    print(f"\n📁 Categories ({len(categories)}):")
    for cat, sources in categories.items():
        print(f"  • {cat}: {len(sources)} sources")
    
    return True


def test_get_links_summary():
    """Test getting a summary without scraping."""
    print("\n" + "=" * 60)
    print("TEST: Get Links Summary")
    print("=" * 60)
    
    result = get_links_summary()
    
    if not result.get("success"):
        print(f"❌ Failed: {result.get('error')}")
        return False
    
    print(f"✅ Summary generated")
    print(f"   Total sources: {result['total_sources']}")
    print(f"   Categories: {list(result['categories'].keys())}")
    
    return True


def test_scrape_single_webpage():
    """Test scraping a single webpage."""
    print("\n" + "=" * 60)
    print("TEST: Scrape Single Webpage")
    print("=" * 60)
    
    test_url = "https://www.anthropic.com/jobs"
    
    print(f"📡 Scraping: {test_url}")
    result = scrape_webpage(test_url)
    
    if not result:
        print("❌ Scraping failed")
        return False
    
    print(f"✅ Scraped successfully")
    print(f"   Title: {result['title'][:50]}...")
    print(f"   Text length: {len(result['text'])} chars")
    
    return True


def test_scrape_single_source():
    """Test scraping a single source by name."""
    print("\n" + "=" * 60)
    print(f"TEST: Scrape Single Source (using {SCRAPER_MODEL})")
    print("=" * 60)
    
    result = scrape_single_source("Anthropic", cache_results=True)
    
    if not result.get("success"):
        print(f"❌ Failed: {result.get('error')}")
        return False
    
    print(f"✅ Scraped {result['source']}")
    print(f"   Category: {result['category']}")
    print(f"   Jobs found: {result['jobs_found']}")
    print(f"   Jobs cached: {result.get('jobs_cached', 0)}")
    print(f"   Duplicates: {result.get('duplicates_skipped', 0)}")
    
    if result.get("jobs"):
        print("\n📋 Sample jobs:")
        for job in result["jobs"][:5]:
            print(f"   • {job.get('title', 'N/A')[:40]}")
            print(f"     📍 {job.get('location', 'N/A')}")
    
    return True


def test_scrape_category():
    """Test scraping an entire category."""
    print("\n" + "=" * 60)
    print("TEST: Scrape Category (Tech)")
    print("=" * 60)
    
    result = scrape_job_links(
        categories="Tech",
        cache_results=True,
        delay_seconds=2
    )
    
    if not result.get("success"):
        print(f"❌ Failed: {result.get('error')}")
        return False
    
    print(f"✅ Scraping complete")
    print(f"   Jobs found: {result['jobs_found']}")
    print(f"   Jobs cached: {result.get('jobs_cached', 0)}")
    print(f"   Sources scraped: {result['sources_scraped']}")
    print(f"   Time: {result['elapsed_seconds']}s")
    
    if result.get("summary"):
        print(f"\n{result['summary']}")
    
    return True


def test_cache_stats():
    """Show current cache statistics."""
    print("\n" + "=" * 60)
    print("TEST: Cache Statistics")
    print("=" * 60)
    
    stats = get_cache().stats()
    
    print(f"📊 Job Cache Stats:")
    print(f"   Total jobs: {stats.get('total_jobs', 0)}")
    print(f"   Cache dir: {stats.get('cache_dir', 'N/A')}")
    print(f"   Vector search: {stats.get('vector_search', False)}")
    
    if stats.get("platforms"):
        print(f"\n📁 By platform:")
        for platform, count in stats["platforms"].items():
            print(f"   • {platform}: {count}")
    
    if stats.get("top_companies"):
        print(f"\n🏢 Top companies:")
        for company, count in stats["top_companies"][:5]:
            print(f"   • {company}: {count}")
    
    return True


def test_full_scrape():
    """Scrape ALL sources and cache locally - FULL TEST."""
    print("\n" + "=" * 60)
    print("TEST: Scrape ALL Sources (Full Crawl)")
    print("=" * 60)
    
    initial_stats = get_cache().stats()
    initial_count = initial_stats.get("total_jobs", 0)
    print(f"📊 Initial cache: {initial_count} jobs")
    
    start = time.time()
    result = scrape_job_links(cache_results=True, delay_seconds=2)
    elapsed = time.time() - start
    
    if not result.get("success"):
        print(f"❌ Failed: {result.get('error')}")
        return False
    
    final_stats = get_cache().stats()
    final_count = final_stats.get("total_jobs", 0)
    
    print(f"\n✅ FULL CRAWL COMPLETE")
    print(f"   Total time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"   Jobs found: {result['jobs_found']}")
    print(f"   Jobs cached: {result.get('jobs_cached', 0)}")
    print(f"   Cache total: {final_count}")
    
    if result.get("summary"):
        print(f"\n{result['summary']}")
    
    return True


def run_quick_tests():
    """Run quick tests (no full scraping)."""
    results = []
    
    results.append(("Parse Markdown", test_parse_markdown_links()))
    results.append(("Links Summary", test_get_links_summary()))
    results.append(("Scrape Webpage", test_scrape_single_webpage()))
    results.append(("Cache Stats", test_cache_stats()))
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test job links scraper")
    parser.add_argument("--full", action="store_true", help="Scrape ALL sources")
    parser.add_argument("--category", type=str, help="Scrape specific category")
    parser.add_argument("--source", type=str, help="Scrape single source by name")
    parser.add_argument("--quick", action="store_true", help="Quick tests only (default)")
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"🕷️  JOB LINKS SCRAPER TESTS (model: {SCRAPER_MODEL})")
    print("=" * 60)
    
    if args.source:
        test_scrape_single_source()
        test_cache_stats()
    
    elif args.category:
        print(f"\n🎯 Scraping category: {args.category}")
        result = scrape_job_links(categories=args.category, cache_results=True, delay_seconds=2)
        if result.get("summary"):
            print(result["summary"])
        test_cache_stats()
    
    elif args.full:
        print("\n⚠️  FULL SCRAPE MODE - This will take 10-20 minutes")
        confirm = input("Continue? (y/N): ")
        if confirm.lower() == 'y':
            test_full_scrape()
        else:
            print("Cancelled.")
    
    else:
        print("\n📋 Running quick tests...")
        results = run_quick_tests()
        
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        for name, passed in results:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {status}: {name}")
        
        print(f"\nTotal: {sum(1 for _, p in results if p)}/{len(results)} passed")
        print("\n💡 Options:")
        print("   --source 'Boeing'  : Scrape one source")
        print("   --category 'Tech'  : Scrape one category")
        print("   --full             : Scrape ALL sources")
