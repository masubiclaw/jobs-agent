#!/usr/bin/env python3
"""
Generate resume and cover letter PDFs for a job.

Usage:
    python scripts/generate_documents.py --job-id abc123 --type resume
    python scripts/generate_documents.py --job-id abc123 --type cover-letter
    python scripts/generate_documents.py --job-id abc123 --type both
    python scripts/generate_documents.py --list  # List available jobs
    python scripts/generate_documents.py --top 5  # Generate for top 5 matched jobs
"""

import argparse
import sys
import logging
import re
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.tools.resume_tools import (
    generate_resume,
    generate_cover_letter,
    generate_application_package,
    set_max_iterations,
)
from job_agent_coordinator.tools.job_cache import get_cache

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Output directory for generated documents
GENERATED_DOCS_DIR = Path(__file__).parent.parent / "generated_documents"


def list_jobs(min_score: int = 60, limit: int = 20):
    """List available jobs with match scores."""
    cache = get_cache()
    matches = cache.list_matches(min_score=min_score, limit=limit)
    jobs = {j['id']: j for j in cache.list_all(limit=10000)}
    
    print("=" * 80)
    print(f"AVAILABLE JOBS (score >= {min_score}%)")
    print("=" * 80)
    print(f"Found: {len(matches)} matches\n")
    
    for i, m in enumerate(matches, 1):
        job_id = m.get("job_id", "")
        job = jobs.get(job_id, {})
        
        score = m.get("combined_score", m.get("keyword_score", 0))
        title = job.get("title", "Unknown")[:40]
        company = job.get("company", "Unknown")[:20]
        
        print(f"{i:2}. [{score:3}%] {title}")
        print(f"    Company: {company}")
        print(f"    Job ID: {job_id}")
        print()


def _sanitize_company_name(company: str) -> str:
    """Sanitize company name to match PDF filename format."""
    return re.sub(r'[^\w\s-]', '', company).replace(' ', '').replace('.', '')


def _check_existing_docs(company: str, doc_type: str) -> Dict[str, bool]:
    """Check if documents already exist for a company."""
    sanitized = _sanitize_company_name(company)
    existing = {"resume": False, "cover_letter": False}
    
    if not GENERATED_DOCS_DIR.exists():
        return existing
    
    for pdf in GENERATED_DOCS_DIR.glob(f"{sanitized}_*_resume.pdf"):
        existing["resume"] = True
    for pdf in GENERATED_DOCS_DIR.glob(f"{sanitized}_*_coverletter.pdf"):
        existing["cover_letter"] = True
    
    return existing


def generate_for_top_jobs(
    top_n: int,
    doc_type: str,
    min_score: int = 60,
    profile_id: str = "",
    skip_existing: bool = True,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Generate documents for top N matched jobs.
    
    Args:
        top_n: Number of top jobs to process
        doc_type: Type of document ('resume', 'cover-letter', 'both')
        min_score: Minimum match score filter
        profile_id: Profile ID (uses first profile if empty)
        skip_existing: Skip jobs that already have generated documents
        dry_run: Preview mode - show what would be generated without doing it
    
    Returns:
        Summary dict with success/failure counts and details
    """
    cache = get_cache()
    matches = cache.list_matches(min_score=min_score, limit=top_n)
    jobs = {j['id']: j for j in cache.list_all(limit=10000)}
    
    print("=" * 80)
    print(f"BATCH DOCUMENT GENERATION - Top {top_n} Jobs")
    print("=" * 80)
    print(f"Document type: {doc_type}")
    print(f"Min score: {min_score}%")
    print(f"Skip existing: {skip_existing}")
    print(f"Dry run: {dry_run}")
    print(f"Found: {len(matches)} matching jobs")
    print("=" * 80)
    print()
    
    results = {
        "total": len(matches),
        "processed": 0,
        "skipped": 0,
        "success": 0,
        "failed": 0,
        "details": []
    }
    
    for i, match in enumerate(matches, 1):
        job_id = match.get("job_id", "")
        job = jobs.get(job_id, {})
        
        if not job:
            logger.warning(f"Job {job_id} not found in cache, skipping")
            results["skipped"] += 1
            continue
        
        score = match.get("combined_score", match.get("keyword_score", 0))
        company = job.get("company", "Unknown")
        title = job.get("title", "Unknown")
        
        # Check for existing documents
        existing = _check_existing_docs(company, doc_type)
        
        should_skip = False
        skip_reason = ""
        
        if skip_existing:
            if doc_type == "resume" and existing["resume"]:
                should_skip = True
                skip_reason = "resume exists"
            elif doc_type == "cover-letter" and existing["cover_letter"]:
                should_skip = True
                skip_reason = "cover letter exists"
            elif doc_type == "both" and existing["resume"] and existing["cover_letter"]:
                should_skip = True
                skip_reason = "both documents exist"
        
        # Print progress
        status_prefix = "[DRY RUN] " if dry_run else ""
        if should_skip:
            print(f"{status_prefix}[{i}/{len(matches)}] SKIP: {company[:25]} - {title[:35]} ({score}%)")
            print(f"         Reason: {skip_reason}")
            results["skipped"] += 1
            results["details"].append({
                "job_id": job_id,
                "company": company,
                "title": title,
                "status": "skipped",
                "reason": skip_reason
            })
            print()
            continue
        
        print(f"{status_prefix}[{i}/{len(matches)}] Generating for: {company[:25]} - {title[:35]} ({score}%)")
        
        if dry_run:
            results["details"].append({
                "job_id": job_id,
                "company": company,
                "title": title,
                "status": "would_generate"
            })
            print()
            continue
        
        # Generate documents
        results["processed"] += 1
        try:
            if doc_type == "resume":
                result = generate_resume(job_id, profile_id)
            elif doc_type == "cover-letter":
                result = generate_cover_letter(job_id, profile_id)
            else:  # both
                result = generate_application_package(job_id, profile_id)
            
            # Check for errors in result
            if "[error]" in result.lower():
                results["failed"] += 1
                results["details"].append({
                    "job_id": job_id,
                    "company": company,
                    "title": title,
                    "status": "failed",
                    "error": result
                })
                print(f"         FAILED: See error in output")
            else:
                results["success"] += 1
                results["details"].append({
                    "job_id": job_id,
                    "company": company,
                    "title": title,
                    "status": "success"
                })
                print(f"         SUCCESS")
            
            print()
            
        except Exception as e:
            logger.error(f"Error generating for {company}: {e}")
            results["failed"] += 1
            results["details"].append({
                "job_id": job_id,
                "company": company,
                "title": title,
                "status": "failed",
                "error": str(e)
            })
            print(f"         ERROR: {e}")
            print()
    
    # Print summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total jobs:  {results['total']}")
    print(f"Processed:   {results['processed']}")
    print(f"Skipped:     {results['skipped']}")
    print(f"Success:     {results['success']}")
    print(f"Failed:      {results['failed']}")
    print("=" * 80)
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate resume and cover letter PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List jobs to get job IDs
    python scripts/generate_documents.py --list
    
    # Generate resume only for a specific job
    python scripts/generate_documents.py --job-id abc123 --type resume
    
    # Generate cover letter only
    python scripts/generate_documents.py --job-id abc123 --type cover-letter
    
    # Generate both for a specific job
    python scripts/generate_documents.py --job-id abc123 --type both
    
    # Generate documents for top 5 matched jobs
    python scripts/generate_documents.py --top 5
    
    # Generate only resumes for top 3 jobs with score >= 70%
    python scripts/generate_documents.py --top 3 --type resume --min-score 70
    
    # Preview what would be generated (dry run)
    python scripts/generate_documents.py --top 5 --dry-run
    
    # Force regenerate even if documents exist
    python scripts/generate_documents.py --top 5 --no-skip-existing
"""
    )
    
    parser.add_argument("--job-id", help="Job ID to generate documents for")
    parser.add_argument(
        "--top",
        type=int,
        metavar="N",
        help="Generate documents for top N matched jobs"
    )
    parser.add_argument(
        "--type",
        choices=["resume", "cover-letter", "both"],
        default="both",
        help="Type of document to generate (default: both)"
    )
    parser.add_argument(
        "--profile-id",
        default="",
        help="Profile ID (optional, uses first profile if not specified)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available jobs with match scores"
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=60,
        help="Minimum match score filter (default: 60)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip jobs that already have generated documents (default: True)"
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Force regenerate documents even if they exist"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview which jobs would be processed without generating"
    )
    parser.add_argument(
        "--max-critiques",
        type=int,
        default=None,
        help="Maximum number of critique/regeneration iterations (default: 3)"
    )
    
    args = parser.parse_args()
    
    # Set max iterations for critique loop if explicitly provided
    if args.max_critiques is not None:
        set_max_iterations(args.max_critiques)
    
    # Handle skip-existing logic
    skip_existing = args.skip_existing and not args.no_skip_existing
    
    if args.list:
        list_jobs(min_score=args.min_score)
        return
    
    # Handle --top mode (batch generation)
    if args.top:
        generate_for_top_jobs(
            top_n=args.top,
            doc_type=args.type,
            min_score=args.min_score,
            profile_id=args.profile_id,
            skip_existing=skip_existing,
            dry_run=args.dry_run
        )
        return
    
    # Single job mode requires --job-id
    if not args.job_id:
        print("Error: --job-id or --top is required. Use --list to see available jobs.")
        sys.exit(1)
    
    print("=" * 80)
    print("DOCUMENT GENERATION")
    print("=" * 80)
    print(f"Job ID: {args.job_id}")
    print(f"Type: {args.type}")
    print()
    
    if args.type == "resume":
        result = generate_resume(args.job_id, args.profile_id)
        print(result)
    elif args.type == "cover-letter":
        result = generate_cover_letter(args.job_id, args.profile_id)
        print(result)
    else:  # both
        result = generate_application_package(args.job_id, args.profile_id)
        print(result)
    
    print()
    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
