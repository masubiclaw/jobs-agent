#!/usr/bin/env python3
"""
Generate resume and cover letter from a job posting URL.

Fetches job details from any URL (Indeed, LinkedIn, Glassdoor, etc.) using
Playwright and generates tailored PDF documents.

Usage:
    python scripts/generate_from_url.py "https://www.indeed.com/viewjob?jk=abc123"
    python scripts/generate_from_url.py URL --type resume
    python scripts/generate_from_url.py URL --type cover-letter
    python scripts/generate_from_url.py URL --no-cache --dry-run
"""

import argparse
import sys
import logging
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Generate resume and cover letter from a job posting URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/generate_from_url.py "https://www.indeed.com/viewjob?jk=abc123"
  python scripts/generate_from_url.py URL --type resume
  python scripts/generate_from_url.py URL --type cover-letter
  python scripts/generate_from_url.py URL --dry-run
  python scripts/generate_from_url.py URL --no-cache
  python scripts/generate_from_url.py URL --profile justin_masui
"""
    )
    parser.add_argument("url", help="Job posting URL (Indeed, LinkedIn, Glassdoor, etc.)")
    parser.add_argument("--type", choices=["resume", "cover-letter", "both"], 
                        default="both", help="Document type to generate (default: both)")
    parser.add_argument("--profile", help="Profile ID to use (default: first profile)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Don't add job to cache after fetching")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and extract job details without generating documents")
    parser.add_argument("--max-critiques", type=int, default=3,
                        help="Maximum critique iterations (default: 3)")
    args = parser.parse_args()
    
    from job_agent_coordinator.tools.url_job_fetcher import fetch_job_from_url, detect_job_site
    from job_agent_coordinator.tools.job_cache import get_cache
    from job_agent_coordinator.tools.profile_store import get_store
    from job_agent_coordinator.tools import resume_tools
    
    print("=" * 70)
    print("GENERATE DOCUMENTS FROM URL")
    print("=" * 70)
    
    # Detect job site
    site = detect_job_site(args.url)
    print(f"🌐 Job Site: {site.capitalize()}")
    print(f"🔗 URL: {args.url[:70]}...")
    print(f"📄 Document Type: {args.type}")
    print(f"💾 Cache Job: {'no' if args.no_cache else 'yes'}")
    print(f"🏃 Mode: {'DRY RUN' if args.dry_run else 'GENERATE'}")
    print("=" * 70)
    print()
    
    # Step 1: Fetch job details from URL
    print("📋 Step 1: Fetching job details...")
    print("-" * 50)
    
    job = fetch_job_from_url(args.url)
    
    if not job:
        print("\n❌ Failed to fetch job details from URL")
        print("   This could be due to:")
        print("   - URL requires login (not supported)")
        print("   - Page uses anti-bot protection")
        print("   - Network/timeout issues")
        sys.exit(1)
    
    # Display extracted job info
    print()
    print("✅ Job Details Extracted:")
    print("-" * 50)
    print(f"   📌 Title: {job.get('title', 'Unknown')}")
    print(f"   🏢 Company: {job.get('company', 'Unknown')}")
    print(f"   📍 Location: {job.get('location', 'Not specified')}")
    print(f"   💰 Salary: {job.get('salary', 'Not disclosed')}")
    desc_preview = job.get('description', '')[:200].replace('\n', ' ')
    print(f"   📝 Description: {desc_preview}...")
    print()
    
    # Dry run - just show extracted info
    if args.dry_run:
        print("🏃 DRY RUN complete. No documents generated.")
        print("\nFull job description:")
        print("-" * 50)
        print(job.get('description', 'No description')[:2000])
        if len(job.get('description', '')) > 2000:
            print("...[truncated]")
        return
    
    # Step 2: Add to cache (unless --no-cache)
    cache = get_cache()
    job_id = None
    
    # Generate job ID from URL (same logic as cache)
    import hashlib
    job_id = hashlib.md5(job.get('url', '').encode()).hexdigest()[:12]
    
    if not args.no_cache:
        print("📋 Step 2: Adding job to cache...")
        print("-" * 50)
        
        # Check if already cached (by URL)
        existing = cache.get_by_url(job.get('url', ''))
        if existing:
            job_id = existing.get('id')
            print(f"   ℹ️  Job already in cache (ID: {job_id})")
        else:
            if cache.add(job):
                print(f"   ✅ Job cached (ID: {job_id})")
                cache._save_jobs()  # Persist to disk
            else:
                print("   ⚠️  Failed to cache job, continuing anyway...")
        print()
    else:
        # Temporarily add to cache for document generation (will be removed after)
        job['id'] = job_id
        cache.add(job)
        print(f"📋 Step 2: Temporary job ID: {job_id} (not persisted)")
        print()
    
    # Step 3: Check profile
    print("📋 Step 3: Loading profile...")
    print("-" * 50)
    
    store = get_store()
    profiles = store.list_profiles()
    
    if not profiles:
        print("❌ No profiles found. Create a profile first:")
        print("   python scripts/add_profile.py")
        sys.exit(1)
    
    if args.profile:
        profile = store.get(args.profile)
        if not profile:
            print(f"❌ Profile not found: {args.profile}")
            print("   Available profiles:", [p.get('id') for p in profiles])
            sys.exit(1)
    else:
        profile = store.get(profiles[0].get('id'))
    
    print(f"   👤 Using profile: {profile.get('name', profile.get('id'))}")
    print()
    
    # Step 4: Generate documents
    print("📋 Step 4: Generating documents...")
    print("-" * 50)
    
    # Set max iterations
    resume_tools.set_max_iterations(args.max_critiques)
    
    generated_files = []
    
    try:
        if args.type in ["resume", "both"]:
            print("\n📄 Generating resume...")
            result = resume_tools.generate_resume(job_id, profile.get('id', ''))
            # Parse result to get file path
            if "pdf_path:" in result:
                for line in result.split('\n'):
                    if line.strip().startswith('pdf_path:'):
                        pdf_path = line.split(':', 1)[1].strip()
                        generated_files.append(("Resume", pdf_path))
                        break
            print(f"   ✅ Resume generated")
        
        if args.type in ["cover-letter", "both"]:
            print("\n📄 Generating cover letter...")
            result = resume_tools.generate_cover_letter(job_id, profile.get('id', ''))
            # Parse result to get file path
            if "pdf_path:" in result:
                for line in result.split('\n'):
                    if line.strip().startswith('pdf_path:'):
                        pdf_path = line.split(':', 1)[1].strip()
                        generated_files.append(("Cover Letter", pdf_path))
                        break
            print(f"   ✅ Cover letter generated")
            
    except Exception as e:
        print(f"\n❌ Error generating documents: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Cleanup: Remove from cache if --no-cache
    if args.no_cache:
        cache.remove(job_id)
    
    # Summary
    print()
    print("=" * 70)
    print("✅ COMPLETE")
    print("=" * 70)
    print(f"   Job: {job.get('title', 'Unknown')} @ {job.get('company', 'Unknown')}")
    
    if generated_files:
        print("\n   Generated files:")
        for doc_type, path in generated_files:
            print(f"   📄 {doc_type}: {path}")
    
    if not args.no_cache:
        print(f"\n   💾 Job cached with ID: {job_id}")
        print("      View with: python scripts/show_top_matches.py")
    
    print()


if __name__ == "__main__":
    main()
