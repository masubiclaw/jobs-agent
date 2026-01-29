#!/usr/bin/env python3
"""
Evaluate fine-tuned job matcher model against base model.

Compares LLM scores from the fine-tuned MLX model against:
1. Human-labeled scores (if available)
2. Ollama base model scores

Usage:
    python scripts/eval_fine_tuned.py              # Run evaluation
    python scripts/eval_fine_tuned.py --limit 20   # Limit to 20 jobs
    python scripts/eval_fine_tuned.py --verbose    # Show per-job results
"""

import os
import sys
import json
import argparse
import statistics
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set environment before importing agent modules
os.environ.setdefault("MLX_MODEL_PATH", "models/job-matcher-lora/fused_model")


def load_eval_data():
    """Load evaluation data from data/eval.jsonl."""
    eval_path = Path("data/eval.jsonl")
    if not eval_path.exists():
        print(f"Error: {eval_path} not found. Run import_labels.py first.")
        sys.exit(1)
    
    data = []
    with open(eval_path) as f:
        for line in f:
            data.append(json.loads(line))
    return data


def load_labeled_data():
    """Load human-labeled data from CSV."""
    import csv
    csv_path = Path("data/labeled_matches.csv")
    if not csv_path.exists():
        return {}
    
    labels = {}
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            job_id = row.get("job_id")
            human_score = row.get("human_score")
            if job_id and human_score:
                try:
                    labels[job_id] = int(human_score)
                except ValueError:
                    pass
    return labels


def extract_job_details(entry):
    """Extract job details from eval entry instruction."""
    # The instruction field contains the full prompt including job details
    instruction = entry.get("instruction", "")
    
    # Parse the structured instruction
    job_title = ""
    company = ""
    description = ""
    
    # Extract from JOB POSTING section
    if "- Title:" in instruction:
        import re
        title_match = re.search(r"- Title:\s*(.+)", instruction)
        if title_match:
            job_title = title_match.group(1).strip()
    
    if "- Company:" in instruction:
        import re
        company_match = re.search(r"- Company:\s*(.+)", instruction)
        if company_match:
            company = company_match.group(1).strip()
    
    # Extract job description
    if "JOB DESCRIPTION:" in instruction:
        desc_start = instruction.find("JOB DESCRIPTION:") + len("JOB DESCRIPTION:")
        desc_end = instruction.find("SCORING (be thoughtful")
        if desc_end == -1:
            desc_end = len(instruction)
        description = instruction[desc_start:desc_end].strip()[:2000]
    
    return {
        "job_title": job_title,
        "company": company,
        "description": description,
    }


def extract_expected_score(entry):
    """Extract expected score from output field."""
    output = entry.get("output", "")
    import re
    match = re.search(r'score:\s*(\d+)%?', output)
    if match:
        return int(match.group(1))
    return None


def run_mlx_inference(job_title, company, description, profile):
    """Run inference with MLX model."""
    # Import here to ensure environment is set before module loads
    import importlib
    import job_agent_coordinator.sub_agents.job_matcher.agent as agent_module
    
    # Set the module-level variable directly
    agent_module.USE_MLX_MODEL = True
    
    result = agent_module.llm_match(
        job_title=job_title,
        company=company,
        job_description=description,
        location="",
        salary_info="",
        job_url="",
        profile=profile,
    )
    return result.get("llm_score")


def run_ollama_inference(job_title, company, description, profile):
    """Run inference with Ollama base model."""
    import job_agent_coordinator.sub_agents.job_matcher.agent as agent_module
    
    # Set the module-level variable directly
    agent_module.USE_MLX_MODEL = False
    
    result = agent_module.llm_match(
        job_title=job_title,
        company=company,
        job_description=description,
        location="",
        salary_info="",
        job_url="",
        profile=profile,
    )
    return result.get("llm_score")


def calculate_metrics(predictions, ground_truth):
    """Calculate evaluation metrics."""
    errors = []
    abs_errors = []
    
    for pred, truth in zip(predictions, ground_truth):
        if pred is not None and truth is not None:
            error = pred - truth
            errors.append(error)
            abs_errors.append(abs(error))
    
    if not abs_errors:
        return {}
    
    return {
        "count": len(abs_errors),
        "mae": statistics.mean(abs_errors),
        "median_ae": statistics.median(abs_errors),
        "mean_error": statistics.mean(errors),  # Positive = overestimates
        "std_error": statistics.stdev(errors) if len(errors) > 1 else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate fine-tuned job matcher model")
    parser.add_argument("--limit", type=int, help="Limit evaluation to N jobs")
    parser.add_argument("--verbose", action="store_true", help="Show per-job results")
    parser.add_argument("--skip-ollama", action="store_true", help="Skip Ollama comparison")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Fine-Tuned Model Evaluation")
    print("=" * 60)
    
    # Load data
    eval_data = load_eval_data()
    human_labels = load_labeled_data()
    
    if args.limit:
        eval_data = eval_data[:args.limit]
    
    print(f"\nLoaded {len(eval_data)} evaluation examples")
    print(f"Human labels available: {len(human_labels)}")
    
    # Create a test profile
    from job_agent_coordinator.tools.profile_store import get_store
    store = get_store()
    profiles = store.list_profiles()
    if not profiles:
        print("Error: No profiles found. Import a profile first.")
        sys.exit(1)
    profile_id = profiles[0].get("id")
    profile = store.get(profile_id)
    
    # Normalize profile - skills may be dicts with 'name' key
    if profile.get("skills") and isinstance(profile["skills"][0], dict):
        profile["skills"] = [s.get("name", str(s)) for s in profile["skills"]]
    
    print(f"Using profile: {profile.get('name', profile_id)}")
    
    # Run evaluations
    mlx_scores = []
    ollama_scores = []
    expected_scores = []
    
    print("\nRunning evaluation...")
    print("-" * 60)
    
    for i, entry in enumerate(eval_data):
        job_details = extract_job_details(entry)
        expected = extract_expected_score(entry)
        
        if args.verbose:
            print(f"\n[{i+1}/{len(eval_data)}] {job_details['job_title'][:40]} @ {job_details['company'][:20]}")
        else:
            print(f"\r  Progress: {i+1}/{len(eval_data)}", end="", flush=True)
        
        # MLX inference
        mlx_score = run_mlx_inference(
            job_details["job_title"],
            job_details["company"],
            job_details["description"],
            profile
        )
        mlx_scores.append(mlx_score)
        
        # Ollama inference (optional)
        if not args.skip_ollama:
            ollama_score = run_ollama_inference(
                job_details["job_title"],
                job_details["company"],
                job_details["description"],
                profile
            )
            ollama_scores.append(ollama_score)
        
        expected_scores.append(expected)
        
        if args.verbose:
            print(f"  Expected: {expected}%, MLX: {mlx_score}%", end="")
            if not args.skip_ollama:
                print(f", Ollama: {ollama_score}%")
            else:
                print()
    
    if not args.verbose:
        print()
    
    # Calculate metrics
    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    
    # MLX vs Expected
    mlx_metrics = calculate_metrics(mlx_scores, expected_scores)
    print(f"\nMLX Fine-Tuned vs Expected (Human-Labeled):")
    print(f"  Samples: {mlx_metrics.get('count', 0)}")
    print(f"  Mean Absolute Error: {mlx_metrics.get('mae', 0):.1f}%")
    print(f"  Median Absolute Error: {mlx_metrics.get('median_ae', 0):.1f}%")
    print(f"  Mean Error (bias): {mlx_metrics.get('mean_error', 0):+.1f}%")
    
    # Ollama vs Expected
    if not args.skip_ollama and ollama_scores:
        ollama_metrics = calculate_metrics(ollama_scores, expected_scores)
        print(f"\nOllama Base vs Expected (Human-Labeled):")
        print(f"  Samples: {ollama_metrics.get('count', 0)}")
        print(f"  Mean Absolute Error: {ollama_metrics.get('mae', 0):.1f}%")
        print(f"  Median Absolute Error: {ollama_metrics.get('median_ae', 0):.1f}%")
        print(f"  Mean Error (bias): {ollama_metrics.get('mean_error', 0):+.1f}%")
        
        # Comparison
        print(f"\nImprovement:")
        mae_diff = ollama_metrics.get('mae', 0) - mlx_metrics.get('mae', 0)
        print(f"  MAE Reduction: {mae_diff:.1f}% ({mae_diff/ollama_metrics.get('mae', 1)*100:.0f}% improvement)")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
