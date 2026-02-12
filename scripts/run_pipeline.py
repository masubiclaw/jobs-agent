#!/usr/bin/env python3
"""
Run the full job pipeline: search -> clean -> fetch -> match -> generate.

Combines job searching, cleaning dead jobs, fetching descriptions, matching,
and document generation into a single workflow. All steps enabled by default.

Usage:
    # Full pipeline with defaults
    python scripts/run_pipeline.py
    
    # Skip cleaning dead jobs
    python scripts/run_pipeline.py --no-clean
    
    # Skip fetching descriptions
    python scripts/run_pipeline.py --no-fetch
    
    # Skip document generation
    python scripts/run_pipeline.py --no-generate
    
    # Generate for matches >= 80%
    python scripts/run_pipeline.py --min-score 80
    
    # Dry run to preview what would be generated
    python scripts/run_pipeline.py --dry-run
"""

import argparse
import sys
import time
import re
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.tools.jobspy_tools import search_jobs_with_jobspy, JOBSPY_AVAILABLE
from job_agent_coordinator.tools.job_links_scraper import scrape_job_links, scrape_single_source
from job_agent_coordinator.tools.job_cache import get_cache
from job_agent_coordinator.tools.profile_store import get_store
from job_agent_coordinator.sub_agents.job_matcher.agent import analyze_job_match, batch_match
from job_agent_coordinator.tools.resume_tools import (
    generate_resume,
    generate_cover_letter,
    generate_application_package,
)

# Output directory for generated documents
GENERATED_DOCS_DIR = Path(__file__).parent.parent / "generated_documents"


def run_search(args, exclusions):
    """Run JobSpy search and return results."""
    print()
    print("=" * 70)
    print("STEP 1: SEARCH")
    print("=" * 70)
    
    if not JOBSPY_AVAILABLE:
        print("❌ JobSpy not installed! Install with: pip install python-jobspy")
        return {"success": False, "error": "JobSpy not available"}
    
    print(f"🔍 Search: '{args.search_term}'")
    print(f"📍 Location: {args.location}")
    print(f"🌐 Sites: {args.sites}")
    print(f"📊 Results: {args.results}")
    print(f"⏰ Max age: {args.hours} hours")
    if exclusions:
        print(f"🚫 Excluding: {', '.join(exclusions)}")
    print()
    
    result = search_jobs_with_jobspy(
        search_term=args.search_term,
        location=args.location,
        results_wanted=args.results,
        hours_old=args.hours,
        sites=args.sites,
        exclude_companies=",".join(exclusions) if exclusions else "",
    )
    
    if result.get("success"):
        jobs = result.get("jobs", [])
        print(f"✅ Found {len(jobs)} jobs")
        
        # Group by platform
        by_platform = {}
        for job in jobs:
            p = job.get("platform", "unknown")
            by_platform[p] = by_platform.get(p, 0) + 1
        
        if by_platform:
            print("📊 By Platform:", ", ".join(f"{k}: {v}" for k, v in sorted(by_platform.items())))
    else:
        print(f"❌ Search failed: {result.get('error', 'Unknown error')}")
    
    return result


def run_scrape(args, exclusions):
    """Run job scraper and return results."""
    print()
    print("=" * 70)
    print("STEP 1: SCRAPE")
    print("=" * 70)
    
    force = getattr(args, 'force', False)
    
    if args.source:
        print(f"🕷️  Scraping source: {args.source}")
        if force:
            print("   (force mode: ignoring same-day cache)")
        result = scrape_single_source(
            source_name=args.source,
            cache_results=True,
            force=force,
        )
    else:
        category = args.category or ""
        max_sources = args.max_sources or 5
        print(f"🕷️  Scraping category: {category or 'all'} (max {max_sources} sources)")
        if force:
            print("   (force mode: ignoring same-day cache)")
        result = scrape_job_links(
            categories=category,
            max_sources=max_sources,
            cache_results=True,
            delay_seconds=2,
            skip_same_day=not force,
        )
    
    if result.get("success"):
        if result.get("skipped"):
            print(f"⏭️  Skipped: {result.get('reason', 'already scraped today')}")
        else:
            print(f"✅ Found {result.get('jobs_found', 0)} jobs, cached {result.get('jobs_cached', 0)}")
    else:
        print(f"❌ Scrape failed: {result.get('error', 'Unknown error')}")
    
    return result


def check_url_alive(url: str, timeout: int = 5) -> bool:
    """Check if a URL is still accessible (returns 2xx/3xx status)."""
    if not url:
        return False
    
    try:
        import requests
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        return response.status_code < 400
    except Exception:
        return False


def run_clean_jobs(cache, args):
    """Clean dead/expired jobs from the cache."""
    print()
    print("=" * 70)
    print("STEP: CLEAN DEAD JOBS")
    print("=" * 70)
    
    all_jobs = cache.list_all(limit=100000)
    print(f"📊 Total jobs in cache: {len(all_jobs)}")
    print(f"🔍 Check URLs: {'yes' if args.check_urls else 'no'}")
    if args.older_than:
        print(f"📅 Older than: {args.older_than} days")
    print(f"🏃 Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()
    
    # Categorize jobs
    no_url_jobs = []
    old_jobs = []
    dead_url_jobs = []
    
    cutoff_date = None
    if args.older_than and args.older_than > 0:
        cutoff_date = datetime.now() - timedelta(days=args.older_than)
    
    # Pass 1: Find jobs with no URLs and old jobs
    print("🔍 Scanning jobs...")
    for job in all_jobs:
        url = job.get("url", "").strip()
        
        if not url:
            no_url_jobs.append(job)
            continue
        
        if cutoff_date:
            added_at = job.get("added_at") or job.get("scraped_at")
            if added_at:
                try:
                    if isinstance(added_at, str):
                        job_date = datetime.fromisoformat(added_at.replace("Z", "+00:00").split("+")[0])
                    else:
                        job_date = added_at
                    
                    if job_date < cutoff_date:
                        old_jobs.append(job)
                        continue
                except Exception:
                    pass
    
    print(f"   📭 Jobs with no URL: {len(no_url_jobs)}")
    if cutoff_date:
        print(f"   📅 Jobs older than {args.older_than} days: {len(old_jobs)}")
    
    # Pass 2: Check URLs (if enabled)
    if args.check_urls:
        flagged_ids = {j["id"] for j in no_url_jobs + old_jobs}
        jobs_to_check = [j for j in all_jobs if j["id"] not in flagged_ids and j.get("url")]
        
        print(f"\n🌐 Checking {len(jobs_to_check)} URLs...")
        
        start_time = time.time()
        checked = 0
        
        def check_job_url(job):
            url = job.get("url", "")
            alive = check_url_alive(url, timeout=5)
            return job, alive
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(check_job_url, job): job for job in jobs_to_check}
            
            for future in as_completed(futures):
                job, alive = future.result()
                checked += 1
                
                if not alive:
                    dead_url_jobs.append(job)
                
                if checked % 50 == 0 or checked == len(jobs_to_check):
                    elapsed = time.time() - start_time
                    print(f"   [{checked}/{len(jobs_to_check)}] {len(dead_url_jobs)} dead URLs found")
        
        print(f"   🔗 Dead URLs found: {len(dead_url_jobs)}")
    
    # Combine all jobs to remove
    to_remove = []
    seen_ids = set()
    
    for job in no_url_jobs + old_jobs + dead_url_jobs:
        if job["id"] not in seen_ids:
            to_remove.append(job)
            seen_ids.add(job["id"])
    
    print()
    print(f"📋 Total to remove: {len(to_remove)} jobs")
    
    if not to_remove:
        print("✅ No dead jobs found!")
        return {"removed": 0}
    
    # Remove jobs
    if args.dry_run:
        print("🏃 DRY RUN - No jobs removed")
        return {"removed": 0, "would_remove": len(to_remove)}
    else:
        removed = 0
        for job in to_remove:
            if cache.remove(job["id"]):
                removed += 1
            cache.clear_matches(job["id"])
        
        print(f"✅ Removed {removed} jobs")
        return {"removed": removed}


def run_fetch_descriptions(cache, limit=100):
    """Fetch missing descriptions for cached jobs."""
    print()
    print("-" * 70)
    print("STEP: FETCH DESCRIPTIONS")
    print("-" * 70)
    
    jobs = cache.list_all(limit=limit)
    jobs_without_desc = [j for j in jobs if not j.get("description")]
    
    if not jobs_without_desc:
        print("✅ All jobs have descriptions")
        return
    
    print(f"📥 Fetching descriptions for {len(jobs_without_desc)} jobs...")
    
    # Import fetcher
    try:
        from job_agent_coordinator.tools.url_job_fetcher import fetch_job_from_url
    except ImportError:
        print("⚠️ URL job fetcher not available")
        return
    
    fetched = 0
    failed = 0
    for i, job in enumerate(jobs_without_desc[:50]):  # Limit to 50 to avoid long waits
        url = job.get("url")
        if not url:
            continue
        
        try:
            result = fetch_job_from_url(url)
            if result.get("success") and result.get("job", {}).get("description"):
                # Update cache
                job["description"] = result["job"]["description"]
                cache.add(job)
                fetched += 1
                if fetched % 5 == 0:
                    print(f"   Fetched {fetched}...")
        except Exception as e:
            failed += 1
        
        # Brief delay to be polite
        time.sleep(0.5)
    
    print(f"✅ Fetched {fetched} descriptions ({failed} failed)")


def run_matching(args, cache):
    """Run job matching on cached jobs."""
    print()
    print("=" * 70)
    print(f"STEP {'2' if args.match_only else '3'}: MATCHING")
    print("=" * 70)
    
    limit = args.limit if args.limit > 0 else 500
    jobs = cache.list_all(limit=limit)
    
    print(f"📊 Jobs to match: {len(jobs)}")
    print(f"🔍 Mode: {'LLM (thorough)' if args.llm else 'Keyword (fast)'}")
    print()
    
    results = {"strong": [], "good": [], "partial": [], "weak": [], "excluded": [], "error": []}
    start_time = time.time()
    
    def on_progress(completed, total, result):
        if args.verbose:
            kw = result.get("keyword_score", 0)
            llm = result.get("llm_score")
            combined = result.get("combined_score", kw)
            llm_str = f" llm={llm}%" if llm is not None else ""
            print(f"  [{completed}/{total}] kw={kw}%{llm_str} combined={combined}%")
    
    if args.llm:
        # Use batch_match for LLM
        batch_result = batch_match(
            jobs=jobs,
            run_llm=True,
            resume=False,
            batch_size=10,
            on_progress=on_progress if args.verbose else None,
        )
        
        for level in ["strong", "good", "partial", "weak", "excluded", "error"]:
            results[level] = batch_result["results"].get(level, [])
    else:
        # Fast keyword-only matching
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
                    run_llm=False,
                )
                
                level = result.get("match_level", "error")
                results[level].append({
                    "title": job["title"][:50],
                    "company": job["company"][:25],
                    "keyword_score": result.get("keyword_score", 0),
                    "combined_score": result.get("combined_score", result.get("keyword_score", 0)),
                    "url": job.get("url", ""),
                })
                
                if not args.verbose and (i + 1) % 50 == 0:
                    print(f"  Processed {i + 1}/{len(jobs)}")
                    
            except Exception as e:
                results["error"].append({"title": job["title"][:40], "error": str(e)[:50]})
    
    elapsed = time.time() - start_time
    
    return results, elapsed


def show_results(results, elapsed, args):
    """Display matching results."""
    print()
    print("=" * 70)
    print(f"RESULTS ({elapsed:.1f}s)")
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
    all_good = results["strong"] + results["good"]
    if all_good:
        filtered = sorted(
            all_good,
            key=lambda x: x.get("combined_score", x.get("keyword_score", 0)),
            reverse=True
        )
        
        print("🏆 TOP MATCHES:")
        print("-" * 70)
        for i, m in enumerate(filtered[:args.top], 1):
            kw = m.get("keyword_score", 0)
            combined = m.get("combined_score", kw)
            print(f"{i:2}. {combined}% - {m['title'][:40]}")
            print(f"    📍 {m['company']}")
            if m.get("url"):
                print(f"    🔗 {m['url'][:60]}...")
            print()


def _sanitize_company_name(company: str) -> str:
    """Sanitize company name to match PDF filename format."""
    return re.sub(r'[^\w\s-]', '', company).replace(' ', '').replace('.', '')


def _check_existing_docs(company: str, doc_type: str) -> dict:
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


def run_document_generation(cache, args, min_score: int = 60):
    """Generate documents for all matches over min_score threshold."""
    print()
    print("=" * 70)
    print("STEP: GENERATE DOCUMENTS")
    print("=" * 70)
    
    matches = cache.list_matches(min_score=min_score, limit=1000)
    jobs = {j['id']: j for j in cache.list_all(limit=10000)}
    
    doc_type = getattr(args, 'doc_type', 'both')
    skip_existing = not getattr(args, 'no_skip_existing', False)
    dry_run = getattr(args, 'dry_run', False)
    
    print(f"📊 Matches >= {min_score}%: {len(matches)}")
    print(f"📄 Document type: {doc_type}")
    print(f"⏭️  Skip existing: {skip_existing}")
    print(f"🏃 Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()
    
    results = {
        "total": len(matches),
        "processed": 0,
        "skipped": 0,
        "success": 0,
        "failed": 0,
    }
    
    for i, match in enumerate(matches, 1):
        job_id = match.get("job_id", "")
        job = jobs.get(job_id, {})
        
        if not job:
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
                skip_reason = "both exist"
        
        prefix = "[DRY RUN] " if dry_run else ""
        if should_skip:
            print(f"{prefix}[{i}/{len(matches)}] SKIP: {company[:20]} - {title[:30]} ({score}%) - {skip_reason}")
            results["skipped"] += 1
            continue
        
        print(f"{prefix}[{i}/{len(matches)}] Generating: {company[:20]} - {title[:30]} ({score}%)")
        
        if dry_run:
            continue
        
        # Generate documents
        results["processed"] += 1
        try:
            if doc_type == "resume":
                result = generate_resume(job_id, "")
            elif doc_type == "cover-letter":
                result = generate_cover_letter(job_id, "")
            else:  # both
                result = generate_application_package(job_id, "")
            
            if "[error]" in result.lower():
                results["failed"] += 1
                print(f"         ❌ FAILED")
            else:
                results["success"] += 1
                print(f"         ✅ SUCCESS")
                
        except Exception as e:
            results["failed"] += 1
            print(f"         ❌ ERROR: {str(e)[:50]}")
    
    print()
    print("-" * 70)
    print(f"📊 Summary: {results['success']} success, {results['failed']} failed, {results['skipped']} skipped")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run the full job pipeline: search -> clean -> fetch -> match -> generate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (all steps enabled by default)
  python scripts/run_pipeline.py
  
  # Skip cleaning dead jobs
  python scripts/run_pipeline.py --no-clean
  
  # Skip fetching descriptions
  python scripts/run_pipeline.py --no-fetch
  
  # Skip document generation
  python scripts/run_pipeline.py --no-generate
  
  # Generate for matches >= 80%
  python scripts/run_pipeline.py --min-score 80
  
  # Dry run to preview what would be generated
  python scripts/run_pipeline.py --dry-run
"""
    )
    
    # Search arguments
    parser.add_argument("search_term", nargs="?", type=str, default="software engineering manager", help="Job search term (default: software engineering manager)")
    parser.add_argument("location", nargs="?", type=str, default="seattle", help="Location (default: seattle)")
    parser.add_argument("--results", "-n", type=int, default=25, help="Search results (default: 25)")
    parser.add_argument("--sites", type=str, default="indeed,linkedin", help="Sites to search")
    parser.add_argument("--hours", type=int, default=72, help="Max hours old (default: 72)")
    
    # Scrape arguments
    parser.add_argument("--scrape", action="store_true", help="Use scraper instead of JobSpy search")
    parser.add_argument("--source", type=str, help="Scrape single source")
    parser.add_argument("--category", type=str, help="Scrape category")
    parser.add_argument("--max-sources", type=int, default=5, help="Max sources to scrape")
    parser.add_argument("--force", "-f", action="store_true", help="Force scrape even if already done today")
    
    # Matching arguments
    parser.add_argument("--match-only", action="store_true", help="Skip search, match cached jobs")
    parser.add_argument("--llm", action="store_true", help="Use LLM matching (slower, thorough)")
    parser.add_argument("--limit", type=int, default=0, help="Limit jobs to match")
    parser.add_argument("--top", type=int, default=15, help="Show top N matches (default: 15)")
    
    # Clean arguments (enabled by default)
    parser.add_argument("--clean", action="store_true", default=True, help="Clean dead/expired jobs from cache (default: on)")
    parser.add_argument("--no-clean", action="store_true", help="Skip cleaning dead jobs")
    parser.add_argument("--check-urls", action="store_true", help="Also validate URLs are still accessible")
    parser.add_argument("--older-than", type=int, default=0, help="Remove jobs older than N days")
    
    # Generate arguments
    parser.add_argument("--no-generate", action="store_true", help="Skip document generation")
    parser.add_argument("--min-score", type=int, default=70, help="Minimum match score for generation (default: 70)")
    parser.add_argument("--doc-type", choices=["resume", "cover-letter", "both"], default="both",
                        help="Document type to generate (default: both)")
    parser.add_argument("--no-skip-existing", action="store_true", help="Regenerate even if documents exist")
    parser.add_argument("--dry-run", action="store_true", help="Preview mode for clean and generate")
    
    # Other options
    parser.add_argument("--fetch", action="store_true", default=True, help="Fetch missing descriptions (default: on)")
    parser.add_argument("--no-fetch", action="store_true", help="Skip fetching missing descriptions")
    parser.add_argument("--no-exclude", action="store_true", help="Disable exclusion filtering")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # No validation needed - defaults are provided for search_term and location
    
    # Load exclusions from profile
    exclusions = []
    if not args.no_exclude:
        context = get_store().get_search_context()
        exclusions = context.get("excluded_companies", [])
    
    cache = get_cache()
    initial_count = len(cache.list_all(limit=10000))
    total_start = time.time()
    
    print("=" * 70)
    print("JOB PIPELINE")
    print("=" * 70)
    print(f"📦 Initial cache: {initial_count} jobs")
    if exclusions:
        print(f"🚫 Exclusions: {', '.join(exclusions[:5])}{'...' if len(exclusions) > 5 else ''}")
    
    # Track stats for final summary
    pipeline_stats = {
        "search": None,
        "clean": None,
        "fetch": None,
        "match": None,
        "generate": None,
    }
    
    # Step 1: Search or Scrape
    if not args.match_only:
        if args.scrape:
            result = run_scrape(args, exclusions)
            pipeline_stats["search"] = {
                "type": "scrape",
                "jobs_found": result.get("jobs_found", 0),
                "jobs_cached": result.get("jobs_cached", 0),
                "sources_scraped": result.get("sources_scraped", 0),
                "sources_failed": result.get("sources_failed", 0),
                "skipped_same_day": result.get("skipped", False),
                "source": result.get("source", ""),
            }
        else:
            result = run_search(args, exclusions)
            pipeline_stats["search"] = {
                "type": "search",
                "jobs_found": len(result.get("jobs", [])) if result.get("success") else 0,
            }
        
        if not result.get("success"):
            print("\n❌ Pipeline stopped due to search/scrape failure")
            sys.exit(1)
    else:
        pipeline_stats["search"] = {"type": "skipped"}
    
    # Step 2: Clean dead jobs (default: on, skip with --no-clean)
    if args.clean and not args.no_clean:
        clean_result = run_clean_jobs(cache, args)
        pipeline_stats["clean"] = {
            "removed": clean_result.get("removed", 0),
            "would_remove": clean_result.get("would_remove", 0),
        }
    
    # Step 3: Fetch descriptions (default: on, skip with --no-fetch)
    if args.fetch and not args.no_fetch:
        run_fetch_descriptions(cache, limit=args.limit or 100)
        pipeline_stats["fetch"] = {"enabled": True}
    
    # Step 4: Matching
    results, match_elapsed = run_matching(args, cache)
    pipeline_stats["match"] = {
        "strong": len(results["strong"]),
        "good": len(results["good"]),
        "partial": len(results["partial"]),
        "weak": len(results["weak"]),
        "excluded": len(results["excluded"]),
        "elapsed": match_elapsed,
    }
    
    # Show results
    show_results(results, match_elapsed, args)
    
    # Step 5: Generate documents (default on, skip with --no-generate)
    if not args.no_generate:
        gen_result = run_document_generation(cache, args, min_score=args.min_score)
        pipeline_stats["generate"] = {
            "total": gen_result.get("total", 0),
            "success": gen_result.get("success", 0),
            "failed": gen_result.get("failed", 0),
            "skipped": gen_result.get("skipped", 0),
        }
    
    # Final summary
    final_count = len(cache.list_all(limit=10000))
    total_elapsed = time.time() - total_start
    
    print()
    print("=" * 70)
    print("PIPELINE SUMMARY")
    print("=" * 70)
    
    # Search/Scrape summary
    search_stats = pipeline_stats.get("search", {})
    if search_stats.get("type") == "skipped":
        print("1. Search/Scrape: skipped (--match-only)")
    elif search_stats.get("type") == "scrape":
        if search_stats.get("skipped_same_day"):
            source = search_stats.get("source", "source")
            print(f"1. Scrape: {source} skipped (already scraped today)")
        else:
            sources_scraped = search_stats.get("sources_scraped", 0)
            sources_failed = search_stats.get("sources_failed", 0)
            jobs_found = search_stats.get("jobs_found", 0)
            jobs_cached = search_stats.get("jobs_cached", 0)
            if sources_scraped > 0:
                print(f"1. Scrape: {sources_scraped} sources scraped, {jobs_found} jobs found, {jobs_cached} cached")
                if sources_failed > 0:
                    print(f"          ({sources_failed} sources failed)")
            else:
                print(f"1. Scrape: {jobs_found} jobs found, {jobs_cached} cached")
    else:
        print(f"1. Search: {search_stats.get('jobs_found', 0)} jobs found")
    
    # Clean summary
    clean_stats = pipeline_stats.get("clean")
    if clean_stats:
        if args.dry_run:
            print(f"2. Clean: would remove {clean_stats.get('would_remove', 0)} jobs (dry run)")
        else:
            print(f"2. Clean: {clean_stats.get('removed', 0)} jobs removed")
    else:
        print("2. Clean: skipped")
    
    # Fetch summary
    if pipeline_stats.get("fetch"):
        print("3. Fetch: descriptions fetched")
    else:
        print("3. Fetch: skipped")
    
    # Match summary
    match_stats = pipeline_stats.get("match", {})
    strong_good = match_stats.get("strong", 0) + match_stats.get("good", 0)
    print(f"4. Match: {strong_good} good matches ({match_stats.get('strong', 0)} strong, {match_stats.get('good', 0)} good)")
    
    # Generate summary
    gen_stats = pipeline_stats.get("generate")
    if gen_stats:
        print(f"5. Generate: {gen_stats.get('success', 0)} success, {gen_stats.get('failed', 0)} failed, {gen_stats.get('skipped', 0)} skipped")
    else:
        print("5. Generate: skipped (--no-generate)")
    
    print()
    print(f"Total time: {total_elapsed:.1f}s")
    print(f"Cache: {final_count} jobs ({final_count - initial_count:+d} change)")
    print("=" * 70)
    
    # Suggest next steps (only if generation was skipped)
    if args.no_generate:
        if strong_good > 0:
            print()
            print("💡 Next steps:")
            print("   python scripts/run_pipeline.py --match-only")
            print("   python scripts/show_top_matches.py --limit 10")


if __name__ == "__main__":
    main()
