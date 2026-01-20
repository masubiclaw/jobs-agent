#!/usr/bin/env python3
"""
Rebuild all job matches from scratch.

This clears existing matches and re-analyzes all cached jobs.
Useful when profile changes or matching algorithm is updated.

Usage:
    python scripts/rebuild_all_matches.py                    # Rebuild all
    python scripts/rebuild_all_matches.py --fetch            # Fetch descriptions from URLs
    python scripts/rebuild_all_matches.py --limit 100        # Process only 100 jobs
"""

import argparse
import sys
import time
import logging
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Rebuild all job matches")
    parser.add_argument("--limit", type=int, default=0, help="Limit jobs to process (0=all)")
    parser.add_argument("--fetch", action="store_true", help="Fetch job descriptions from URLs (slower)")
    parser.add_argument("--keep-cache", action="store_true", help="Don't clear existing matches first")
    args = parser.parse_args()

    # Import after path setup
    from job_agent_coordinator.sub_agents.job_matcher.agent import analyze_job_match
    from job_agent_coordinator.tools.job_cache import get_cache

    cache = get_cache()
    
    # Clear existing matches unless --keep-cache
    if not args.keep_cache:
        existing = len(cache._matches)
        if existing > 0:
            logger.info(f"🗑️  Clearing {existing} existing matches...")
            cache.clear_matches()
    
    # Get all jobs
    limit = args.limit if args.limit > 0 else 10000
    jobs = cache.list_all(limit=limit)
    
    logger.info("=" * 70)
    logger.info(f"🔄 REBUILDING MATCHES - {len(jobs)} jobs")
    logger.info(f"   Fetch descriptions: {'yes' if args.fetch else 'no'}")
    logger.info("=" * 70)
    
    results = {"strong": 0, "good": 0, "partial": 0, "weak": 0, "excluded": 0, "error": 0}
    start_time = time.time()
    
    for i, job in enumerate(jobs):
        try:
            result = analyze_job_match(
                job_title=job["title"],
                company=job["company"],
                job_description=job.get("description", ""),
                location=job.get("location", ""),
                salary_info=str(job.get("salary", "")),
                job_url=job.get("url", ""),
                job_id=job.get("id", ""),
                use_cache=True,  # Will cache the new result
                fetch_description=args.fetch,
            )
            
            level = result.get("match_level", "error")
            score = result.get("match_score", 0)
            results[level] = results.get(level, 0) + 1
            
            # Progress indicator
            if (i + 1) % 25 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(jobs) - i - 1) / rate if rate > 0 else 0
                logger.info(f"   [{i+1}/{len(jobs)}] {elapsed:.0f}s elapsed, ~{eta:.0f}s remaining")
            
        except Exception as e:
            results["error"] += 1
            logger.warning(f"   ❌ Error matching {job['title'][:30]}: {e}")
    
    elapsed = time.time() - start_time
    
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"✅ COMPLETE! Rebuilt {len(jobs)} matches in {elapsed:.1f}s")
    logger.info("=" * 70)
    logger.info("")
    logger.info("📊 MATCH DISTRIBUTION:")
    logger.info(f"   🟢 Strong (80%+):    {results.get('strong', 0):4d}")
    logger.info(f"   🟢 Good (60-79%):    {results.get('good', 0):4d}")
    logger.info(f"   🟡 Partial (40-59%): {results.get('partial', 0):4d}")
    logger.info(f"   🔴 Weak (<40%):      {results.get('weak', 0):4d}")
    logger.info(f"   ⛔ Excluded:         {results.get('excluded', 0):4d}")
    logger.info(f"   ❌ Errors:           {results.get('error', 0):4d}")
    logger.info("")
    
    # Show cache stats
    stats = cache.stats()
    logger.info(f"💾 Cache now has {stats['total_jobs']} jobs, {stats['total_matches']} matches")


if __name__ == "__main__":
    main()
