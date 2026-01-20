#!/usr/bin/env python3
"""
Rebuild all job matches from scratch with two-pass matching.

Clears existing matches and re-analyzes all cached jobs.
Useful when profile changes or matching algorithm is updated.

Supports:
- Pass 1 only (keyword, fast)
- Two-pass with LLM (slower but thorough)
- Checkpoint/resume for LLM pass

Usage:
    python scripts/rebuild_all_matches.py              # Keyword only (fast)
    python scripts/rebuild_all_matches.py --llm        # With LLM (slow)
    python scripts/rebuild_all_matches.py --resume     # Resume LLM pass
    python scripts/rebuild_all_matches.py --limit 100  # Process 100 jobs
"""

import argparse
import sys
import time
import logging
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild all job matches with two-pass matching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fast keyword-only rebuild
  python scripts/rebuild_all_matches.py
  
  # Two-pass with LLM (thorough, ~3-5s/job)
  python scripts/rebuild_all_matches.py --llm
  
  # Resume interrupted LLM rebuild
  python scripts/rebuild_all_matches.py --llm --resume
"""
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit jobs (0=all)")
    parser.add_argument("--llm", action="store_true", help="Run Pass 2 LLM analysis (~3-5s/job)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint (with --llm)")
    parser.add_argument("--fetch", action="store_true", help="Fetch descriptions from URLs")
    parser.add_argument("--keep-cache", action="store_true", help="Don't clear existing matches first")
    args = parser.parse_args()

    # Import after path setup
    from job_agent_coordinator.sub_agents.job_matcher.agent import (
        analyze_job_match,
        batch_match,
        MatchingProgress,
    )
    from job_agent_coordinator.tools.job_cache import get_cache

    cache = get_cache()
    
    # Clear existing matches unless --keep-cache or --resume
    if not args.keep_cache and not args.resume:
        existing = len(cache._matches)
        if existing > 0:
            logger.info(f"🗑️  Clearing {existing} existing matches...")
            cache.clear_matches()
        
        # Clear checkpoint too
        progress = MatchingProgress()
        progress.clear()
    
    # Get all jobs
    limit = args.limit if args.limit > 0 else 10000
    jobs = cache.list_all(limit=limit)
    
    logger.info("=" * 70)
    logger.info(f"🔄 REBUILDING ALL MATCHES")
    logger.info(f"   Jobs: {len(jobs)}")
    logger.info(f"   Pass 1 (keyword): always")
    logger.info(f"   Pass 2 (LLM): {'yes (~3-5s/job)' if args.llm else 'no'}")
    logger.info(f"   Fetch descriptions: {'yes' if args.fetch else 'no'}")
    if args.resume:
        progress = MatchingProgress()
        summary = progress.get_summary()
        logger.info(f"   Resume: from checkpoint ({summary.get('completed', 0)} already done)")
    logger.info("=" * 70)
    logger.info("")
    
    start_time = time.time()
    
    if args.llm:
        # Use batch_match for LLM with checkpoint support
        def on_progress(completed, total, result):
            kw = result.get("keyword_score", 0)
            llm = result.get("llm_score")
            combined = result.get("combined_score", kw)
            llm_str = f"llm={llm}%" if llm is not None else "llm=pending"
            
            elapsed = time.time() - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / rate if rate > 0 else 0
            pct = (completed / total * 100) if total > 0 else 0
            
            # Log every job completion
            logger.info(f"   ✅ [{completed}/{total}] ({pct:.1f}%) kw={kw}% {llm_str} combined={combined}% | {elapsed:.0f}s elapsed, ~{eta:.0f}s remaining")
        
        result = batch_match(
            jobs=jobs,
            run_llm=True,
            resume=args.resume,
            batch_size=10,
            on_progress=on_progress,
        )
        
        results = {
            "strong": result["strong"],
            "good": result["good"],
            "partial": result["partial"],
            "weak": result["weak"],
            "excluded": result["excluded"],
            "error": result["errors"],
        }
    else:
        # Simple loop for keyword-only
        results = {"strong": 0, "good": 0, "partial": 0, "weak": 0, "excluded": 0, "error": 0}
        
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
                    use_cache=True,
                    fetch_description=args.fetch,
                    run_llm=False,
                )
                
                level = result.get("match_level", "error")
                results[level] = results.get(level, 0) + 1
                
                if (i + 1) % 50 == 0:
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
    
    stats = cache.stats()
    logger.info(f"💾 Cache: {stats['total_jobs']} jobs, {stats['total_matches']} matches")


if __name__ == "__main__":
    main()
