#!/usr/bin/env python3
"""
Run job matching on all cached jobs.

Usage:
    python scripts/run_job_matcher.py              # Match all jobs
    python scripts/run_job_matcher.py --limit 10   # Match first 10 jobs
    python scripts/run_job_matcher.py --min-score 60  # Show only 60%+ matches
"""

import argparse
import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.sub_agents.job_matcher.agent import analyze_job_match
from job_agent_coordinator.tools.job_cache import get_cache


def main():
    parser = argparse.ArgumentParser(description="Run job matching on cached jobs")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of jobs to process (0=all)")
    parser.add_argument("--min-score", type=int, default=0, help="Only show matches with score >= this")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show progress for each job")
    parser.add_argument("--skip-cached", action="store_true", help="Skip jobs already matched")
    parser.add_argument("--fetch-descriptions", action="store_true", help="Fetch job descriptions from URLs if missing")
    parser.add_argument("--no-fetch", action="store_true", help="Disable fetching descriptions (faster but less accurate)")
    args = parser.parse_args()
    
    # Default: fetch descriptions if not already cached
    fetch_desc = not args.no_fetch

    cache = get_cache()
    limit = args.limit if args.limit > 0 else 10000
    jobs = cache.list_all(limit=limit)

    print("=" * 70)
    print(f"BATCH JOB MATCHING - {len(jobs)} jobs")
    print(f"  Fetch descriptions: {'yes (slower but more accurate)' if fetch_desc else 'no (faster)'}")
    print("=" * 70)

    results = {"strong": [], "good": [], "partial": [], "weak": [], "excluded": [], "error": []}
    start_time = time.time()
    skipped = 0

    for i, job in enumerate(jobs):
        try:
            # Check if already cached
            if args.skip_cached:
                existing = cache.get_match(job.get("id", ""))
                if existing:
                    skipped += 1
                    continue

            result = analyze_job_match(
                job_title=job["title"],
                company=job["company"],
                job_description=job.get("description", ""),
                location=job.get("location", ""),
                salary_info=str(job.get("salary", "")),
                job_url=job.get("url", ""),
                job_id=job.get("id", ""),  # Pass cached job ID for consistency
                fetch_description=fetch_desc,  # Fetch description if missing and URL exists
            )

            level = result.get("match_level", "error")
            score = result.get("match_score", 0)
            from_cache = result.get("from_cache", False)

            results[level].append({
                "title": job["title"][:50],
                "company": job["company"][:25],
                "score": score,
                "cached": from_cache,
                "url": job.get("url", ""),
            })

            if args.verbose:
                cache_indicator = "📦" if from_cache else "🆕"
                print(f"  {cache_indicator} {score}% - {job['title'][:40]} @ {job['company'][:20]}")

            # Progress every 50 jobs
            if not args.verbose and (i + 1) % 50 == 0:
                elapsed = time.time() - start_time
                print(f"  Processed {i + 1}/{len(jobs)} jobs ({elapsed:.1f}s)")

        except Exception as e:
            results["error"].append({"title": job["title"][:40], "error": str(e)[:50]})

    elapsed = time.time() - start_time
    print()
    print("=" * 70)
    print(f"COMPLETE! Processed {len(jobs)} jobs in {elapsed:.1f}s")
    if skipped:
        print(f"Skipped {skipped} already-cached jobs")
    print("=" * 70)
    print()
    print("📊 SUMMARY:")
    print(f"  🟢 Strong (80%+): {len(results['strong'])}")
    print(f"  🟢 Good (60-79%): {len(results['good'])}")
    print(f"  🟡 Partial (40-59%): {len(results['partial'])}")
    print(f"  🔴 Weak (<40%): {len(results['weak'])}")
    print(f"  ⛔ Excluded: {len(results['excluded'])}")
    print(f"  ❌ Errors: {len(results['error'])}")
    print()

    # Filter by min score
    min_score = args.min_score

    # Show top matches
    if results["strong"]:
        filtered = [m for m in results["strong"] if m["score"] >= min_score]
        if filtered:
            print("🏆 STRONG MATCHES (80%+):")
            for m in filtered[:15]:
                print(f"  {m['score']}% - {m['title']} @ {m['company']}")
            print()

    if results["good"]:
        filtered = [m for m in sorted(results["good"], key=lambda x: x["score"], reverse=True) if m["score"] >= min_score]
        if filtered:
            print("✅ GOOD MATCHES (60-79%):")
            for m in filtered[:15]:
                print(f"  {m['score']}% - {m['title']} @ {m['company']}")
            print()

    # Show cache stats
    stats = cache.stats()
    print(f"💾 Cache: {stats['total_jobs']} jobs, {stats['total_matches']} matches cached")


if __name__ == "__main__":
    main()
