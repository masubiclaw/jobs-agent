#!/usr/bin/env python3
"""
Export job matches for human labeling (Phase 1.1 of fine-tuning pipeline).

Exports jobs and their match results to CSV for manual review and labeling.
Focus on edge cases where LLM might need calibration.

Usage:
    python scripts/export_for_labeling.py                    # Export all matches
    python scripts/export_for_labeling.py --min 40 --max 80  # Export partial matches (best for labeling)
    python scripts/export_for_labeling.py --limit 100        # Limit to 100 jobs
    python scripts/export_for_labeling.py --output data/my_labels.csv
"""

import argparse
import csv
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.tools.job_cache import get_cache
from job_agent_coordinator.tools.profile_store import get_store


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", " ").strip()
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def extract_llm_assessment(toon_report: str) -> str:
    """Extract assessment from LLM TOON report."""
    if not toon_report:
        return ""
    
    # Look for assessment line in llm_analysis section
    lines = toon_report.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith("assessment:"):
            return line.split(":", 1)[1].strip()
    return ""


def main():
    parser = argparse.ArgumentParser(description="Export job matches for labeling")
    parser.add_argument("--min", type=int, default=0, help="Minimum score to include (default: 0)")
    parser.add_argument("--max", type=int, default=100, help="Maximum score to include (default: 100)")
    parser.add_argument("--limit", type=int, default=500, help="Max jobs to export (default: 500)")
    parser.add_argument("--output", type=str, default="data/labeled_matches.csv", help="Output CSV path")
    parser.add_argument("--include-excluded", action="store_true", help="Include excluded companies")
    parser.add_argument("--prioritize-edge-cases", action="store_true", default=True,
                        help="Prioritize jobs where keyword and LLM scores differ significantly")
    args = parser.parse_args()

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load data
    cache = get_cache()
    store = get_store()
    
    # Get profile summary
    profile = store.get_active()
    if not profile:
        print("❌ No active profile found. Create one first.")
        sys.exit(1)
    
    profile_summary = f"{profile.get('name', 'Unknown')}: {', '.join(s.get('name', '') for s in profile.get('skills', [])[:10])}"
    prefs = profile.get("preferences", {})
    target_roles = ", ".join(prefs.get("target_roles", []))
    
    # Get all matches
    all_matches = cache.list_matches(min_score=0, limit=10000)
    jobs = {j['id']: j for j in cache.list_all(limit=10000)}
    
    print(f"📊 Found {len(all_matches)} total matches, {len(jobs)} jobs")

    # Filter and prepare data
    export_data = []
    
    for m in all_matches:
        job_id = m.get("job_id", "")
        job = jobs.get(job_id)
        
        if not job:
            continue
        
        # Skip excluded unless requested
        if m.get("match_level") == "excluded" and not args.include_excluded:
            continue
        
        # Get scores
        keyword_score = m.get("keyword_score", 0)
        llm_score = m.get("llm_score")
        combined_score = m.get("combined_score", keyword_score)
        
        # Filter by score range
        if combined_score < args.min or combined_score > args.max:
            continue
        
        # Calculate score divergence (for prioritization)
        score_divergence = abs(keyword_score - llm_score) if llm_score is not None else 0
        
        export_data.append({
            "job_id": job_id,
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "url": job.get("url", ""),
            "platform": job.get("platform", ""),
            "description": truncate_text(job.get("description", ""), 1500),
            "keyword_score": keyword_score,
            "llm_score": llm_score if llm_score is not None else "",
            "combined_score": combined_score,
            "match_level": m.get("match_level", ""),
            "matching_skills": ", ".join(m.get("matching_skills", [])[:8]),
            "missing_skills": ", ".join(m.get("missing_skills", [])[:6]),
            "llm_assessment": extract_llm_assessment(m.get("toon_report", "")),
            "score_divergence": score_divergence,
            # Profile context
            "profile_summary": profile_summary,
            "target_roles": target_roles,
            # Empty columns for labeling
            "human_score": "",
            "fit_category": "",  # excellent, good, partial, poor
            "notes": "",
        })
    
    # Sort: prioritize edge cases (high score divergence) if requested
    if args.prioritize_edge_cases:
        # Sort by score divergence desc, then combined score desc
        export_data.sort(key=lambda x: (-x["score_divergence"], -x["combined_score"]))
    else:
        # Sort by combined score desc
        export_data.sort(key=lambda x: -x["combined_score"])
    
    # Limit results
    export_data = export_data[:args.limit]
    
    if not export_data:
        print(f"❌ No matches found in score range {args.min}-{args.max}%")
        sys.exit(1)

    # Write CSV
    fieldnames = [
        "job_id", "title", "company", "location", "url", "platform",
        "description", "keyword_score", "llm_score", "combined_score",
        "match_level", "matching_skills", "missing_skills", "llm_assessment",
        "score_divergence", "profile_summary", "target_roles",
        "human_score", "fit_category", "notes"
    ]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(export_data)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"EXPORT SUMMARY")
    print(f"{'='*60}")
    print(f"📁 Output: {output_path}")
    print(f"📊 Exported: {len(export_data)} jobs")
    print(f"📏 Score range: {args.min}-{args.max}%")
    
    # Score distribution
    scores = [d["combined_score"] for d in export_data]
    if scores:
        print(f"\n📈 Score distribution:")
        print(f"   80-100% (excellent): {sum(1 for s in scores if s >= 80)}")
        print(f"   60-79%  (good):      {sum(1 for s in scores if 60 <= s < 80)}")
        print(f"   40-59%  (partial):   {sum(1 for s in scores if 40 <= s < 60)}")
        print(f"   0-39%   (poor):      {sum(1 for s in scores if s < 40)}")
    
    # Edge case count
    edge_cases = sum(1 for d in export_data if d["score_divergence"] >= 15)
    if edge_cases:
        print(f"\n⚠️  Edge cases (keyword vs LLM differ by 15+): {edge_cases}")
        print(f"   These are the best candidates for labeling!")
    
    print(f"\n📝 Next steps:")
    print(f"   1. Open {output_path} in Excel/Google Sheets")
    print(f"   2. Fill in 'human_score' (0-100) for each job")
    print(f"   3. Optionally set 'fit_category': excellent, good, partial, poor")
    print(f"   4. Add notes for edge cases")
    print(f"   5. Run: python scripts/import_labels.py --input {output_path}")


if __name__ == "__main__":
    main()
