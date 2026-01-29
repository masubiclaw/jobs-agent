#!/usr/bin/env python3
"""
Compare base model vs fine-tuned model on real job matches.

Usage:
    python scripts/compare_models.py              # Compare on 5 random jobs
    python scripts/compare_models.py --limit 10   # Compare on 10 jobs
"""

import argparse
import csv
import re
import sys
import subprocess
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def run_mlx_model(prompt: str, adapter_path: str = None, max_tokens: int = 300) -> tuple[int, str]:
    """
    Run mlx_lm.generate and extract score.
    
    Returns:
        Tuple of (score, raw_output)
    """
    cmd = [
        "mlx_lm.generate",
        "--model", "mlx-community/gemma-2-9b-it-4bit",
        "--max-tokens", str(max_tokens),
        "--prompt", prompt,
    ]
    
    if adapter_path:
        cmd.extend(["--adapter-path", adapter_path])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr
        
        # Extract the generated text (between ========== markers)
        match = re.search(r'={10,}\n(.*?)={10,}', output, re.DOTALL)
        if match:
            generated = match.group(1).strip()
        else:
            generated = output
        
        # Extract score
        score_match = re.search(r'score[:\s]*(\d+)', generated.lower())
        if score_match:
            score = int(score_match.group(1))
            score = max(0, min(100, score))
        else:
            # Try to find percentage
            pct_match = re.search(r'(\d+)%', generated)
            if pct_match:
                score = int(pct_match.group(1))
                score = max(0, min(100, score))
            else:
                score = None
        
        return score, generated
        
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT"
    except Exception as e:
        return None, f"ERROR: {e}"


def create_prompt(job: dict) -> str:
    """Create a prompt for job matching."""
    return f"""<start_of_turn>user
Analyze how well this candidate matches the job. Be calibrated - most jobs should score 20-60%.

CANDIDATE PROFILE:
- Skills: Python, Machine Learning, TensorFlow, Deep Learning, Java, Scala, NLP
- Target Roles: Principal Software Engineer, ML Engineer, Engineering Manager
- Experience: 10+ years in software engineering and ML

JOB POSTING:
- Title: {job.get('title', 'Unknown')}
- Company: {job.get('company', 'Unknown')}
- Location: {job.get('location', 'Unknown')}

JOB DESCRIPTION (excerpt):
{job.get('description', 'No description')[:1500]}

Provide a score (0-100) and brief assessment.
<end_of_turn>
<start_of_turn>model
[llm_analysis]
score:"""


def main():
    parser = argparse.ArgumentParser(description="Compare base vs fine-tuned model")
    parser.add_argument("--limit", type=int, default=5, help="Number of jobs to test")
    parser.add_argument("--adapter-path", type=str, 
                        default="models/job-matcher-lora/adapters",
                        help="Path to fine-tuned adapter")
    args = parser.parse_args()

    # Load labeled data
    csv_path = Path("data/labeled_matches.csv")
    if not csv_path.exists():
        print(f"❌ Labeled data not found: {csv_path}")
        sys.exit(1)
    
    jobs = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            human_score = row.get('human_score', '').strip()
            if human_score:
                try:
                    row['human_score'] = int(human_score)
                    jobs.append(row)
                except ValueError:
                    pass
    
    if not jobs:
        print("❌ No jobs with human scores found")
        sys.exit(1)
    
    # Select jobs to test
    import random
    random.seed(42)
    test_jobs = random.sample(jobs, min(args.limit, len(jobs)))
    
    print(f"🔬 Comparing models on {len(test_jobs)} jobs\n")
    print("=" * 80)
    
    results = []
    
    for i, job in enumerate(test_jobs, 1):
        title = job.get('title', 'Unknown')[:40]
        company = job.get('company', 'Unknown')[:20]
        human = job['human_score']
        
        print(f"\n[{i}/{len(test_jobs)}] {title} @ {company}")
        print(f"    Human score: {human}%")
        
        prompt = create_prompt(job)
        
        # Run base model
        print(f"    Running base model...", end=" ", flush=True)
        base_score, base_output = run_mlx_model(prompt, adapter_path=None)
        print(f"→ {base_score}%" if base_score else "→ ERROR")
        
        # Run fine-tuned model
        print(f"    Running fine-tuned...", end=" ", flush=True)
        tuned_score, tuned_output = run_mlx_model(prompt, adapter_path=args.adapter_path)
        print(f"→ {tuned_score}%" if tuned_score else "→ ERROR")
        
        # Calculate errors
        base_error = abs(base_score - human) if base_score else None
        tuned_error = abs(tuned_score - human) if tuned_score else None
        
        if base_error is not None and tuned_error is not None:
            if tuned_error < base_error:
                print(f"    ✅ Fine-tuned closer (error: {tuned_error} vs {base_error})")
            elif tuned_error > base_error:
                print(f"    ❌ Base closer (error: {base_error} vs {tuned_error})")
            else:
                print(f"    ➖ Same error ({base_error})")
        
        results.append({
            'title': title,
            'human': human,
            'base': base_score,
            'tuned': tuned_score,
            'base_error': base_error,
            'tuned_error': tuned_error,
        })
    
    # Summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    
    valid_results = [r for r in results if r['base_error'] is not None and r['tuned_error'] is not None]
    
    if valid_results:
        avg_base_error = sum(r['base_error'] for r in valid_results) / len(valid_results)
        avg_tuned_error = sum(r['tuned_error'] for r in valid_results) / len(valid_results)
        
        tuned_wins = sum(1 for r in valid_results if r['tuned_error'] < r['base_error'])
        base_wins = sum(1 for r in valid_results if r['base_error'] < r['tuned_error'])
        ties = len(valid_results) - tuned_wins - base_wins
        
        print(f"\nAverage Error:")
        print(f"  Base model:      {avg_base_error:.1f} points")
        print(f"  Fine-tuned:      {avg_tuned_error:.1f} points")
        
        improvement = ((avg_base_error - avg_tuned_error) / avg_base_error * 100) if avg_base_error > 0 else 0
        print(f"  Improvement:     {improvement:+.1f}%")
        
        print(f"\nHead-to-head:")
        print(f"  Fine-tuned wins: {tuned_wins}")
        print(f"  Base wins:       {base_wins}")
        print(f"  Ties:            {ties}")
        
        if avg_tuned_error < avg_base_error:
            print(f"\n✅ Fine-tuned model is better!")
        else:
            print(f"\n⚠️  Base model performed better on this sample")
    else:
        print("❌ No valid comparisons")


if __name__ == "__main__":
    main()
