#!/usr/bin/env python3
"""Test script for JobSpy integration."""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_jobspy_import():
    """Test that JobSpy can be imported."""
    print("Testing JobSpy import...")
    try:
        from jobspy import scrape_jobs
        print("✅ JobSpy imported successfully")
        return True
    except ImportError as e:
        print(f"❌ JobSpy import failed: {e}")
        return False


def test_jobspy_search():
    """Test a basic JobSpy search."""
    print("\nTesting JobSpy search...")
    
    from job_agent_coordinator.tools.jobspy_tools import search_jobs_with_jobspy
    
    result = search_jobs_with_jobspy(
        search_term="software engineer",
        location="Seattle, WA",
        results_wanted=5,
        hours_old=168,
        sites="indeed,linkedin"
    )
    
    if result["success"]:
        print(f"✅ Search successful - found {result['count']} jobs")
        print("\nJobs found:")
        for i, job in enumerate(result["jobs"], 1):
            print(f"  {i}. {job['title']} @ {job['company']}")
            print(f"     📍 {job['location']}")
            print(f"     💰 {job['salary']}")
            print(f"     🔗 {job['url'][:60]}...")
            print()
        return True
    else:
        print(f"❌ Search failed: {result.get('error', 'Unknown error')}")
        return False


def test_jobspy_exclusions():
    """Test JobSpy with company exclusions."""
    print("\nTesting JobSpy with exclusions...")
    
    from job_agent_coordinator.tools.jobspy_tools import search_jobs_with_jobspy
    
    result = search_jobs_with_jobspy(
        search_term="software engineer",
        location="Seattle, WA",
        results_wanted=10,
        hours_old=168,
        exclude_companies="amazon,microsoft,google"
    )
    
    if result["success"]:
        print(f"✅ Search with exclusions successful - found {result['count']} jobs")
        
        # Verify no excluded companies
        excluded = ["amazon", "microsoft", "google"]
        for job in result["jobs"]:
            company_lower = job["company"].lower()
            for exc in excluded:
                if exc in company_lower:
                    print(f"❌ Found excluded company: {job['company']}")
                    return False
        
        print("✅ No excluded companies in results")
        return True
    else:
        print(f"❌ Search failed: {result.get('error', 'Unknown error')}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("JobSpy Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Import", test_jobspy_import),
        ("Basic Search", test_jobspy_search),
        ("Exclusions", test_jobspy_exclusions),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{'─' * 60}")
        print(f"TEST: {name}")
        print("─" * 60)
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
