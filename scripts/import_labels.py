#!/usr/bin/env python3
"""
Import human labels and create training data for LoRA fine-tuning (Phase 1.3).

Reads the labeled CSV and converts to instruction-following JSONL format
suitable for fine-tuning with mlx-lm, unsloth, or similar tools.

Usage:
    python scripts/import_labels.py                              # Use default labeled_matches.csv
    python scripts/import_labels.py --input data/my_labels.csv   # Use custom input
    python scripts/import_labels.py --train-split 0.8            # 80% train, 20% eval
"""

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.tools.job_cache import get_cache
from job_agent_coordinator.tools.profile_store import get_store


def load_labels(input_path: Path) -> List[Dict[str, Any]]:
    """Load labeled data from CSV."""
    labeled = []
    
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip rows without human_score
            human_score = row.get("human_score", "").strip()
            if not human_score:
                continue
            
            try:
                score = int(human_score)
                if not (0 <= score <= 100):
                    print(f"⚠️  Skipping invalid score {score} for {row.get('job_id', 'unknown')}")
                    continue
            except ValueError:
                print(f"⚠️  Skipping non-numeric score '{human_score}' for {row.get('job_id', 'unknown')}")
                continue
            
            labeled.append({
                "job_id": row.get("job_id", ""),
                "title": row.get("title", ""),
                "company": row.get("company", ""),
                "location": row.get("location", ""),
                "description": row.get("description", ""),
                "profile_summary": row.get("profile_summary", ""),
                "target_roles": row.get("target_roles", ""),
                "matching_skills": row.get("matching_skills", ""),
                "missing_skills": row.get("missing_skills", ""),
                "human_score": score,
                "fit_category": row.get("fit_category", "").strip() or determine_category(score),
                "notes": row.get("notes", ""),
                "keyword_score": int(row.get("keyword_score", 0) or 0),
                "llm_score": int(row.get("llm_score")) if row.get("llm_score") else None,
            })
    
    return labeled


def determine_category(score: int) -> str:
    """Determine fit category from score."""
    if score >= 80:
        return "excellent"
    elif score >= 60:
        return "good"
    elif score >= 40:
        return "partial"
    return "poor"


def create_training_example(
    job: Dict[str, Any],
    profile: Dict[str, Any],
    include_keyword_context: bool = True
) -> Dict[str, str]:
    """
    Create a single training example in instruction-following format.
    
    The format matches the LLM prompt structure from agent.py.
    """
    # Build profile text
    skills = [s.get("name", "") for s in profile.get("skills", [])]
    prefs = profile.get("preferences", {})
    
    profile_text = f"""CANDIDATE PROFILE:
- Name: {profile.get('name', 'Unknown')}
- Location: {profile.get('location', 'Not specified')}
- Skills: {', '.join(skills[:20])}
- Target Roles: {', '.join(prefs.get('target_roles', []))}
- Target Locations: {', '.join(prefs.get('target_locations', []))}
- Remote Preference: {prefs.get('remote_preference', 'hybrid')}
- Salary Range: {prefs.get('salary_min', 0)} - {prefs.get('salary_max', 0)} if both else 'Not specified'
- Summary: {profile.get('resume', {}).get('summary', 'Not provided')[:400]}"""

    # Include keyword analysis context if available
    keyword_context = ""
    if include_keyword_context and job.get("matching_skills"):
        keyword_context = f"""
KEYWORD ANALYSIS (Pass 1):
- Keyword Score: {job.get('keyword_score', 'N/A')}%
- Matching Skills: {job.get('matching_skills', '')}
- Missing Skills: {job.get('missing_skills', '')}
"""

    # Truncate description
    desc = job.get("description", "No description provided")[:6000]
    
    # Build instruction (matches agent.py prompt)
    instruction = f"""Analyze how well this candidate matches the job. Provide a holistic assessment.

{profile_text}
{keyword_context}
JOB POSTING:
- Title: {job['title']}
- Company: {job['company']}
- Location: {job.get('location', 'Not specified')}

JOB DESCRIPTION:
{desc}

SCORING (be thoughtful and realistic):
- 85-100%: Excellent fit - exceeds most requirements
- 70-84%: Good fit - meets core requirements
- 50-69%: Partial fit - some alignment, notable gaps
- 30-49%: Stretch - significant gaps
- 0-29%: Poor fit - major misalignment

OUTPUT EXACTLY IN THIS FORMAT:
[llm_analysis]
score: [NUMBER between 0-100]%
assessment: [2-3 sentence holistic evaluation citing specific job requirements and candidate qualifications]

[key_strengths]
- [strength 1 with evidence]
- [strength 2 with evidence]
- [strength 3 with evidence]

[concerns]
- [concern 1 and how to address]
- [concern 2 and how to address]

[recommendations]
1. [specific application advice]
2. [interview prep suggestion]
3. [skill to emphasize or develop]

Output ONLY the TOON format above, no other text."""

    # Build expected output (ground truth from human label)
    human_score = job["human_score"]
    category = job["fit_category"]
    notes = job.get("notes", "")
    
    # Generate assessment based on category
    if category == "excellent":
        assessment = f"Strong alignment with job requirements. Candidate's background in {job.get('matching_skills', 'relevant skills')[:50]} directly addresses core needs."
    elif category == "good":
        assessment = f"Good fit with most requirements met. Skills in {job.get('matching_skills', 'relevant areas')[:50]} are valuable, with minor gaps that can be addressed."
    elif category == "partial":
        assessment = f"Partial alignment - some relevant experience but notable gaps. {job.get('missing_skills', 'Key requirements')[:50]} would need to be developed."
    else:  # poor
        assessment = f"Limited alignment with job requirements. Significant gaps in {job.get('missing_skills', 'required areas')[:50]} make this a stretch role."
    
    if notes:
        assessment = f"{assessment} {notes[:100]}"
    
    # Build strengths based on matching skills
    matching = job.get("matching_skills", "").split(", ")[:3]
    strengths = [f"- Experience with {s}" for s in matching if s] or ["- Relevant background"]
    
    # Build concerns based on missing skills
    missing = job.get("missing_skills", "").split(", ")[:2]
    concerns = [f"- Gap in {s}: consider highlighting related experience" for s in missing if s] or ["- None identified"]
    
    # Build recommendations
    if human_score >= 70:
        recommendations = [
            "1. Apply with confidence - strong fit",
            "2. Emphasize relevant project experience",
            "3. Research company culture for interview prep"
        ]
    elif human_score >= 50:
        recommendations = [
            "1. Tailor resume to address specific requirements",
            f"2. Prepare to discuss how you'd fill gaps in {missing[0] if missing else 'required areas'}",
            "3. Highlight transferable skills from similar work"
        ]
    else:
        recommendations = [
            "1. Consider if this role aligns with career goals",
            "2. May require significant upskilling",
            "3. Look for similar roles with lower requirements"
        ]
    
    output = f"""[llm_analysis]
score: {human_score}%
assessment: {assessment}

[key_strengths]
{chr(10).join(strengths)}

[concerns]
{chr(10).join(concerns)}

[recommendations]
{chr(10).join(recommendations)}"""

    return {
        "instruction": instruction,
        "input": "",  # Input is embedded in instruction for this format
        "output": output,
        # Metadata (not used in training, but useful for debugging)
        "_job_id": job["job_id"],
        "_human_score": human_score,
        "_original_llm_score": job.get("llm_score"),
        "_keyword_score": job.get("keyword_score"),
    }


def main():
    parser = argparse.ArgumentParser(description="Import labels and create training data")
    parser.add_argument("--input", type=str, default="data/labeled_matches.csv", help="Input CSV path")
    parser.add_argument("--output-dir", type=str, default="data", help="Output directory")
    parser.add_argument("--train-split", type=float, default=0.8, help="Train/eval split ratio (default: 0.8)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for split")
    parser.add_argument("--format", choices=["alpaca", "sharegpt", "raw"], default="alpaca",
                        help="Output format: alpaca (instruction/input/output), sharegpt (conversations), raw")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        print(f"   Run: python scripts/export_for_labeling.py first")
        sys.exit(1)

    # Load labels
    print(f"📂 Loading labels from: {input_path}")
    labeled = load_labels(input_path)
    
    if not labeled:
        print("❌ No valid labeled examples found!")
        print("   Make sure to fill in 'human_score' column (0-100)")
        sys.exit(1)
    
    print(f"✅ Loaded {len(labeled)} labeled examples")

    # Load profile for context
    store = get_store()
    profile = store.get_active()
    if not profile:
        print("❌ No active profile found")
        sys.exit(1)
    
    # Get full job descriptions from cache
    cache = get_cache()
    jobs = {j['id']: j for j in cache.list_all(limit=10000)}
    
    # Enrich labeled data with full descriptions if truncated
    for item in labeled:
        job = jobs.get(item["job_id"])
        if job and len(job.get("description", "")) > len(item.get("description", "")):
            item["description"] = job["description"]

    # Create training examples
    print(f"🔄 Creating training examples...")
    examples = []
    for item in labeled:
        example = create_training_example(item, profile)
        examples.append(example)
    
    # Shuffle and split
    random.seed(args.seed)
    random.shuffle(examples)
    
    split_idx = int(len(examples) * args.train_split)
    train_examples = examples[:split_idx]
    eval_examples = examples[split_idx:]
    
    # Save based on format
    if args.format == "alpaca":
        # Standard Alpaca format (works with most fine-tuning tools)
        train_file = output_dir / "train.jsonl"
        eval_file = output_dir / "eval.jsonl"
        
        with open(train_file, "w") as f:
            for ex in train_examples:
                # Remove metadata for training
                clean = {k: v for k, v in ex.items() if not k.startswith("_")}
                f.write(json.dumps(clean) + "\n")
        
        with open(eval_file, "w") as f:
            for ex in eval_examples:
                clean = {k: v for k, v in ex.items() if not k.startswith("_")}
                f.write(json.dumps(clean) + "\n")
        
        print(f"📁 Saved training data:")
        print(f"   {train_file} ({len(train_examples)} examples)")
        print(f"   {eval_file} ({len(eval_examples)} examples)")
    
    elif args.format == "sharegpt":
        # ShareGPT conversation format (works with some tools)
        train_file = output_dir / "train_sharegpt.json"
        eval_file = output_dir / "eval_sharegpt.json"
        
        def to_sharegpt(ex):
            return {
                "conversations": [
                    {"from": "human", "value": ex["instruction"]},
                    {"from": "gpt", "value": ex["output"]}
                ]
            }
        
        with open(train_file, "w") as f:
            json.dump([to_sharegpt(ex) for ex in train_examples], f, indent=2)
        
        with open(eval_file, "w") as f:
            json.dump([to_sharegpt(ex) for ex in eval_examples], f, indent=2)
        
        print(f"📁 Saved ShareGPT format:")
        print(f"   {train_file} ({len(train_examples)} examples)")
        print(f"   {eval_file} ({len(eval_examples)} examples)")
    
    else:  # raw
        # Raw format with all metadata
        all_file = output_dir / "training_data_raw.json"
        with open(all_file, "w") as f:
            json.dump({
                "train": train_examples,
                "eval": eval_examples,
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "total_examples": len(examples),
                    "train_count": len(train_examples),
                    "eval_count": len(eval_examples),
                    "profile_id": profile.get("id"),
                }
            }, f, indent=2)
        print(f"📁 Saved raw format: {all_file}")

    # Print statistics
    print(f"\n{'='*60}")
    print("TRAINING DATA STATISTICS")
    print(f"{'='*60}")
    print(f"Total labeled: {len(examples)}")
    print(f"Train set: {len(train_examples)} ({args.train_split*100:.0f}%)")
    print(f"Eval set: {len(eval_examples)} ({(1-args.train_split)*100:.0f}%)")
    
    # Score distribution
    scores = [ex["_human_score"] for ex in examples]
    print(f"\nScore distribution (human labels):")
    print(f"   Excellent (80-100): {sum(1 for s in scores if s >= 80)}")
    print(f"   Good (60-79):       {sum(1 for s in scores if 60 <= s < 80)}")
    print(f"   Partial (40-59):    {sum(1 for s in scores if 40 <= s < 60)}")
    print(f"   Poor (0-39):        {sum(1 for s in scores if s < 40)}")
    
    # Score correction analysis
    corrections = []
    for ex in examples:
        if ex["_original_llm_score"] is not None:
            diff = ex["_human_score"] - ex["_original_llm_score"]
            corrections.append(diff)
    
    if corrections:
        avg_correction = sum(corrections) / len(corrections)
        print(f"\nLLM Score Corrections:")
        print(f"   Average correction: {avg_correction:+.1f} points")
        print(f"   Human scored higher: {sum(1 for c in corrections if c > 5)}")
        print(f"   Human scored lower:  {sum(1 for c in corrections if c < -5)}")
        print(f"   Close agreement (±5): {sum(1 for c in corrections if -5 <= c <= 5)}")

    print(f"\n📝 Next steps:")
    print(f"   1. Review the training data in {output_dir}/")
    print(f"   2. Run: python scripts/train_lora.py --data {output_dir}")


if __name__ == "__main__":
    main()
