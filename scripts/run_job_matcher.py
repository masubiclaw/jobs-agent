#!/usr/bin/env python3
"""
Run two-pass job matching on cached jobs.

Pass 1 (fast): Keyword/regex analysis (~0.01s/job)
Pass 2 (slow): LLM holistic analysis (~3-5s/job)

Supports checkpoint/resume for long-running LLM passes.

Usage:
    python scripts/run_job_matcher.py              # Keyword-only (fast)
    python scripts/run_job_matcher.py --llm        # Two-pass with LLM (slow)
    python scripts/run_job_matcher.py --resume     # Resume interrupted LLM pass
    python scripts/run_job_matcher.py --limit 50   # Process first 50 jobs
"""

import argparse
import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.sub_agents.job_matcher.agent import (
    analyze_job_match,
    batch_match,
    MatchingProgress,
)
from job_agent_coordinator.tools.job_cache import get_cache


def main():
    parser = argparse.ArgumentParser(
        description="Run two-pass job matching on cached jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fast keyword-only matching
  python scripts/run_job_matcher.py
  
  # Two-pass with LLM analysis (slow but thorough)
  python scripts/run_job_matcher.py --llm
  
  # Resume interrupted LLM pass
  python scripts/run_job_matcher.py --llm --resume
  
  # Process specific number of jobs
  python scripts/run_job_matcher.py --limit 100 --llm
"""
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit number of jobs (0=all)")
    parser.add_argument("--min-score", type=int, default=0, help="Only show matches with score >= this")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show each job as processed")
    parser.add_argument("--llm", action="store_true", help="Run Pass 2 LLM analysis (slower, ~3-5s/job)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint (requires --llm)")
    parser.add_argument("--clear-progress", action="store_true", help="Clear checkpoint and start fresh")
    parser.add_argument("--fetch", action="store_true", help="Fetch missing job descriptions from URLs")
    parser.add_argument("--no-cache", action="store_true", help="Don't use cached results")
    args = parser.parse_args()

    cache = get_cache()
    limit = args.limit if args.limit > 0 else 10000
    jobs = cache.list_all(limit=limit)

    # Check progress if resuming
    progress = MatchingProgress()
    if args.clear_progress:
        progress.clear()
        print("🗑️ Cleared checkpoint progress")

    if args.resume and not args.llm:
        print("⚠️ --resume only works with --llm flag")
        return

    print("=" * 70)
    print(f"TWO-PASS JOB MATCHING")
    print(f"  Jobs: {len(jobs)}")
    print(f"  Pass 1 (keyword): always")
    print(f"  Pass 2 (LLM): {'yes (~3-5s/job)' if args.llm else 'no (use --llm to enable)'}")
    if args.resume:
        summary = progress.get_summary()
        print(f"  Resume: from checkpoint ({summary.get('completed', 0)} already done)")
    print("=" * 70)
    print()

    results = {"strong": [], "good": [], "partial": [], "weak": [], "excluded": [], "error": []}
    start_time = time.time()

    def on_progress(completed, total, result):
        if args.verbose:
            kw = result.get("keyword_score", 0)
            llm = result.get("llm_score")
            combined = result.get("combined_score", kw)
            llm_str = f" llm={llm}%" if llm is not None else ""
            title = result.get("job_id", "unknown")[:12]
            print(f"  [{completed}/{total}] kw={kw}%{llm_str} combined={combined}% - {title}")

    if args.llm:
        # Use batch_match for checkpoint support
        batch_result = batch_match(
            jobs=jobs,
            run_llm=True,
            resume=args.resume,
            batch_size=10,
            on_progress=on_progress if args.verbose else None,
        )
        
        results["strong"] = batch_result["results"]["strong"]
        results["good"] = batch_result["results"]["good"]
        results["partial"] = batch_result["results"]["partial"]
        results["weak"] = batch_result["results"]["weak"]
        results["excluded"] = batch_result["results"]["excluded"]
        results["error"] = batch_result["results"]["error"]
    else:
        # Simple loop for keyword-only
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
                    use_cache=not args.no_cache,
                    fetch_description=args.fetch,
                    run_llm=False,
                )

                level = result.get("match_level", "error")
                kw_score = result.get("keyword_score", 0)
                combined = result.get("combined_score", kw_score)

                results[level].append({
                    "title": job["title"][:50],
                    "company": job["company"][:25],
                    "keyword_score": kw_score,
                    "llm_score": result.get("llm_score"),
                    "combined_score": combined,
                    "url": job.get("url", ""),
                })

                if args.verbose:
                    cached = "📦" if result.get("from_cache") else "🆕"
                    print(f"  {cached} kw={kw_score}% - {job['title'][:40]}")

                if not args.verbose and (i + 1) % 100 == 0:
                    elapsed = time.time() - start_time
                    print(f"  Processed {i + 1}/{len(jobs)} ({elapsed:.1f}s)")

            except Exception as e:
                results["error"].append({"title": job["title"][:40], "error": str(e)[:50]})

    elapsed = time.time() - start_time

    # Summary
    print()
    print("=" * 70)
    print(f"COMPLETE! {len(jobs)} jobs in {elapsed:.1f}s")
    print("=" * 70)
    print()
    print("📊 MATCH DISTRIBUTION:")
    print(f"  🟢 Strong (80%+):    {len(results['strong'])}")
    print(f"  🟢 Good (60-79%):    {len(results['good'])}")
    print(f"  🟡 Partial (40-59%): {len(results['partial'])}")
    print(f"  🔴 Weak (<40%):      {len(results['weak'])}")
    print(f"  ⛔ Excluded:         {len(results['excluded'])}")
    print(f"  ❌ Errors:           {len(results['error'])}")
    print()

    # Top matches
    min_score = args.min_score
    all_good = results["strong"] + results["good"]
    if all_good:
        filtered = sorted(
            [m for m in all_good if m.get("combined_score", m.get("keyword_score", 0)) >= min_score],
            key=lambda x: x.get("combined_score", x.get("keyword_score", 0)),
            reverse=True
        )
        if filtered:
            print("🏆 TOP MATCHES:")
            for m in filtered[:20]:
                kw = m.get("keyword_score", 0)
                llm = m.get("llm_score")
                combined = m.get("combined_score", kw)
                llm_str = f" llm={llm}%" if llm is not None else ""
                print(f"  {combined}% (kw={kw}%{llm_str}) - {m['title'][:35]} @ {m['company'][:15]}")
            print()

    # Cache stats
    stats = cache.stats()
    print(f"💾 Cache: {stats['total_jobs']} jobs, {stats['total_matches']} matches")


if __name__ == "__main__":
    main()
