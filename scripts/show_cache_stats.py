#!/usr/bin/env python3
"""
Show job cache statistics.

Usage:
    python scripts/show_cache_stats.py
    python scripts/show_cache_stats.py --matches    # Show match statistics
    python scripts/show_cache_stats.py --companies  # Show all companies
"""

import argparse
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.tools.job_cache import get_cache


def main():
    parser = argparse.ArgumentParser(description="Show job cache statistics")
    parser.add_argument("--matches", "-m", action="store_true", help="Show match statistics")
    parser.add_argument("--companies", "-c", action="store_true", help="Show all companies")
    parser.add_argument("--top", type=int, default=10, help="Number of top items to show")
    args = parser.parse_args()

    cache = get_cache()
    stats = cache.stats()

    print("=" * 60)
    print("📦 JOB CACHE STATISTICS")
    print("=" * 60)
    print(f"Total jobs:    {stats['total_jobs']}")
    print(f"Total matches: {stats['total_matches']}")
    print(f"Vector count:  {stats['vector_count']}")
    print(f"Cache dir:     {stats['cache_dir']}")
    print(f"Created:       {stats.get('created', 'N/A')}")
    print(f"Last updated:  {stats.get('last_updated', 'N/A')}")
    print()

    print("📊 By Platform:")
    for platform, count in stats["platforms"].items():
        print(f"  {platform}: {count}")
    print()

    limit = args.top if not args.companies else 100
    print(f"🏢 Top {limit} Companies:")
    for company, count in stats["top_companies"][:limit]:
        print(f"  {company}: {count}")
    print()

    if args.matches and stats["total_matches"] > 0:
        match_stats = stats.get("match_stats", {})
        print("=" * 60)
        print("🎯 MATCH STATISTICS")
        print("=" * 60)
        print(f"Total matches:  {match_stats.get('total_matches', 0)}")
        print(f"Average score:  {match_stats.get('avg_score', 0):.1f}%")
        print(f"Max score:      {match_stats.get('max_score', 0)}%")
        print(f"Min score:      {match_stats.get('min_score', 0)}%")
        print()
        print("Level distribution:")
        for level, count in match_stats.get("level_distribution", {}).items():
            emoji = "🟢" if level in ("strong", "good") else "🟡" if level == "partial" else "🔴"
            print(f"  {emoji} {level}: {count}")
        print()

        # Show top matches
        matches = cache.list_matches(min_score=60, limit=args.top)
        if matches:
            print(f"🏆 Top {args.top} Matches (60%+):")
            for m in matches:
                job = cache.get(m.get("job_id", ""))
                if job:
                    print(f"  {m['match_score']}% - {job['title'][:40]} @ {job['company'][:20]}")


if __name__ == "__main__":
    main()
