#!/usr/bin/env python3
"""
Show top job matches with links.

Usage:
    python scripts/show_top_matches.py              # Show matches >= 70%
    python scripts/show_top_matches.py --min 50     # Show matches >= 50%
    python scripts/show_top_matches.py --limit 10   # Limit to 10 results
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.tools.job_cache import get_cache


def main():
    parser = argparse.ArgumentParser(description="Show top job matches with links")
    parser.add_argument("--min", type=int, default=70, help="Minimum score (default: 70)")
    parser.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    args = parser.parse_args()

    cache = get_cache()
    matches = cache.list_matches(min_score=args.min, limit=args.limit)
    jobs = {j['id']: j for j in cache.list_all(limit=10000)}

    print("=" * 80)
    print(f"TOP MATCHES (score >= {args.min}%)")
    print("=" * 80)
    print(f"Found: {len(matches)} matches\n")

    for i, m in enumerate(matches, 1):
        job_id = m.get("job_id", "")
        job = jobs.get(job_id, {})
        
        score = m.get("combined_score", m.get("keyword_score", m.get("match_score", 0)))
        kw = m.get("keyword_score", 0)
        llm = m.get("llm_score")
        
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        location = job.get("location", "")
        url = job.get("url", "")
        
        llm_str = f" | llm={llm}%" if llm is not None else ""
        
        print(f"{i}. [{score}%] {title}")
        print(f"   Company: {company}")
        if location:
            print(f"   Location: {location}")
        print(f"   Scores: kw={kw}%{llm_str}")
        if url:
            print(f"   Link: {url}")
        else:
            print(f"   Link: (not available)")
        print()

    if not matches:
        print(f"No matches found with score >= {args.min}%")


if __name__ == "__main__":
    main()
