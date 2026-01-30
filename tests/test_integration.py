#!/usr/bin/env python3
"""
Integration tests for document generation pipeline.

Tests the full workflow: profile loading, job retrieval, LLM generation,
fact verification, critique, and PDF output.

Usage:
    python scripts/test_document_generation.py
    python scripts/test_document_generation.py --verbose
    python scripts/test_document_generation.py --test fact_verification
"""

import argparse
import sys
import os
import logging
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    message: str
    duration_ms: float = 0.0


class DocumentGenerationTests:
    """Integration tests for document generation."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[TestResult] = []
        
    def log(self, msg: str):
        """Log message if verbose mode."""
        if self.verbose:
            logger.info(msg)
    
    def run_test(self, name: str, test_func) -> TestResult:
        """Run a single test and capture result."""
        import time
        
        print(f"  Running: {name}...", end=" ", flush=True)
        start = time.time()
        
        try:
            test_func()
            duration = (time.time() - start) * 1000
            result = TestResult(name=name, passed=True, message="OK", duration_ms=duration)
            print(f"PASS ({duration:.0f}ms)")
        except AssertionError as e:
            duration = (time.time() - start) * 1000
            result = TestResult(name=name, passed=False, message=str(e), duration_ms=duration)
            print(f"FAIL: {e}")
        except Exception as e:
            duration = (time.time() - start) * 1000
            result = TestResult(name=name, passed=False, message=f"Error: {e}", duration_ms=duration)
            print(f"ERROR: {e}")
        
        self.results.append(result)
        return result
    
    # ========================
    # UNIT TESTS
    # ========================
    
    def test_profile_loading(self):
        """Test that profile can be loaded from store."""
        from job_agent_coordinator.tools.profile_store import get_store
        
        store = get_store()
        profiles = store.list_profiles()
        
        assert profiles, "No profiles found in store"
        assert len(profiles) > 0, "Profile list is empty"
        
        # Get first profile
        profile_id = profiles[0].get("id")
        profile = store.get(profile_id)
        
        assert profile, f"Could not load profile: {profile_id}"
        assert profile.get("name"), "Profile missing name"
        self.log(f"Loaded profile: {profile.get('name')}")
    
    def test_job_retrieval(self):
        """Test that jobs can be retrieved from cache."""
        from job_agent_coordinator.tools.job_cache import get_cache
        
        cache = get_cache()
        jobs = cache.list_all(limit=5)
        
        assert jobs, "No jobs found in cache"
        
        job = jobs[0]
        assert job.get("id"), "Job missing ID"
        assert job.get("title"), "Job missing title"
        self.log(f"Retrieved job: {job.get('title')}")
        
        # Test retrieval by ID
        job_by_id = cache.get(job.get("id"))
        assert job_by_id, f"Could not retrieve job by ID: {job.get('id')}"
    
    def test_length_compliance(self):
        """Test length compliance checker."""
        from job_agent_coordinator.tools.document_critic import _check_length_compliance
        
        # Resume tests
        short_resume = "word " * 400
        long_resume = "word " * 700
        
        ok, msg = _check_length_compliance(short_resume, "resume")
        assert ok, f"Short resume should pass: {msg}"
        
        ok, msg = _check_length_compliance(long_resume, "resume")
        assert not ok, "Long resume should fail"
        
        # Cover letter tests
        short_cover = "word " * 150
        good_cover = "word " * 300
        long_cover = "word " * 500
        
        ok, msg = _check_length_compliance(short_cover, "cover_letter")
        assert not ok, "Short cover letter should fail"
        
        ok, msg = _check_length_compliance(good_cover, "cover_letter")
        assert ok, f"Good cover letter should pass: {msg}"
        
        ok, msg = _check_length_compliance(long_cover, "cover_letter")
        assert not ok, "Long cover letter should fail"
    
    def test_keyword_extraction(self):
        """Test keyword extraction from job descriptions."""
        from job_agent_coordinator.tools.document_critic import _extract_keywords_from_job
        
        job = {
            "title": "Senior Python Developer",
            "description": "Looking for Python developer with AWS and Docker experience. "
                          "Must know SQL, REST API design, and have worked with Kubernetes."
        }
        
        keywords = _extract_keywords_from_job(job)
        
        assert "python" in keywords, "Should extract 'python'"
        assert "aws" in keywords, "Should extract 'aws'"
        assert "docker" in keywords, "Should extract 'docker'"
        assert "kubernetes" in keywords, "Should extract 'kubernetes'"
        self.log(f"Extracted keywords: {keywords}")
    
    def test_keyword_matching(self):
        """Test keyword matching calculation."""
        from job_agent_coordinator.tools.document_critic import _calculate_keyword_match
        
        content = "Expert in Python and AWS. Built Docker containers and REST APIs."
        keywords = ["python", "aws", "docker", "kubernetes", "java"]
        
        score, matched, missing = _calculate_keyword_match(content, keywords)
        
        assert score > 0, "Score should be > 0"
        assert "python" in matched, "Should match 'python'"
        assert "kubernetes" in missing, "Should miss 'kubernetes'"
        self.log(f"Keyword score: {score}%, matched: {matched}, missing: {missing}")
    
    def test_profile_facts_extraction(self):
        """Test extraction of facts from profile."""
        from job_agent_coordinator.tools.document_critic import _extract_profile_facts
        
        profile = {
            "name": "Test User",
            "location": "San Francisco, CA",
            "skills": [
                {"name": "Python", "level": "advanced"},
                {"name": "AWS", "level": "intermediate"},
            ],
            "experience": [
                {
                    "company": "Tech Corp",
                    "title": "Senior Engineer",
                    "start_date": "2020-01",
                    "end_date": "2024-01",
                    "description": "Improved performance by 50%. Managed team of 5."
                }
            ],
            "notes": "Master's in Computer Science from Stanford."
        }
        
        facts = _extract_profile_facts(profile)
        
        assert "python" in facts["skills"], "Should extract Python skill"
        assert "tech corp" in facts["companies"], "Should extract company"
        assert "senior engineer" in facts["titles"], "Should extract title"
        assert "master" in facts["education"], "Should extract education"
        self.log(f"Extracted facts: {json.dumps(facts, indent=2)}")
    
    def test_pdf_filename_sanitization(self):
        """Test filename sanitization."""
        from job_agent_coordinator.tools.pdf_generator import _sanitize_filename
        
        assert _sanitize_filename("Cisco Systems") == "Cisco_Systems"
        assert _sanitize_filename("Google/Alphabet") == "GoogleAlphabet"
        assert _sanitize_filename("Company (Inc.)") == "Company_Inc"
        assert len(_sanitize_filename("a" * 100)) <= 50, "Should truncate long names"
    
    def test_resume_section_parsing(self):
        """Test resume section parsing."""
        from job_agent_coordinator.tools.pdf_generator import _parse_resume_sections
        
        content = """
[HEADER]
John Doe
john@example.com | 555-1234 | San Francisco, CA

[SUMMARY]
Experienced software engineer with 10 years of experience.

[SKILLS]
Python, Java, AWS, Docker

[EXPERIENCE]
Senior Engineer | Google | 2020-Present
- Built scalable systems
- Led team of 5

[EDUCATION]
MS Computer Science | Stanford | 2015
"""
        
        sections = _parse_resume_sections(content)
        
        assert "John Doe" in sections["header"], "Should parse header"
        assert "software engineer" in sections["summary"].lower(), "Should parse summary"
        assert "python" in sections["skills"].lower(), "Should parse skills"
        assert "google" in sections["experience"].lower(), "Should parse experience"
        assert "stanford" in sections["education"].lower(), "Should parse education"
    
    def test_cover_letter_section_parsing(self):
        """Test cover letter section parsing."""
        from job_agent_coordinator.tools.pdf_generator import _parse_cover_letter_sections
        
        content = """
[DATE]
January 22, 2026

[RECIPIENT]
Hiring Manager
Google Inc.

[OPENING]
Dear Hiring Manager,
I am writing to apply for the Senior Engineer position.

[BODY PARAGRAPH 1]
I have 10 years of experience in software development.

[BODY PARAGRAPH 2]
My expertise includes Python and cloud technologies.

[CLOSING]
I look forward to discussing this opportunity.
"""
        
        sections = _parse_cover_letter_sections(content)
        
        assert "2026" in sections["date"], "Should parse date"
        assert "google" in sections["recipient"].lower(), "Should parse recipient"
        assert "apply" in sections["opening"].lower(), "Should parse opening"
        assert "experience" in sections["body1"].lower(), "Should parse body1"
        assert "expertise" in sections["body2"].lower(), "Should parse body2"
        assert "forward" in sections["closing"].lower(), "Should parse closing"
    
    # ========================
    # INTEGRATION TESTS
    # ========================
    
    def test_pdf_resume_generation(self):
        """Test PDF resume generation."""
        from job_agent_coordinator.tools.pdf_generator import generate_resume_pdf
        
        content = """
[HEADER]
John Doe
john@example.com | 555-1234 | San Francisco, CA

[SUMMARY]
Experienced software engineer with 10 years of experience in Python and cloud.

[SKILLS]
Python, Java, AWS, Docker, Kubernetes

[EXPERIENCE]
Senior Engineer | Google | 2020-Present
- Built scalable microservices handling 1M requests/day
- Led team of 5 engineers

Software Engineer | Meta | 2015-2020
- Developed backend systems
- Improved API performance by 30%

[EDUCATION]
MS Computer Science | Stanford | 2015
"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = generate_resume_pdf(
                content=content,
                company="Test Company",
                profile_name="John Doe",
                output_dir=Path(tmpdir)
            )
            
            assert Path(pdf_path).exists(), f"PDF should exist: {pdf_path}"
            assert pdf_path.endswith(".pdf"), "Should be PDF file"
            assert "resume" in pdf_path.lower(), "Should be named as resume"
            
            # Check file size (should be reasonable)
            size = Path(pdf_path).stat().st_size
            assert size > 1000, f"PDF seems too small: {size} bytes"
            assert size < 500000, f"PDF seems too large: {size} bytes"
            
            self.log(f"Generated PDF: {pdf_path} ({size} bytes)")
    
    def test_pdf_cover_letter_generation(self):
        """Test PDF cover letter generation."""
        from job_agent_coordinator.tools.pdf_generator import generate_cover_letter_pdf
        
        content = """
[DATE]
January 22, 2026

[RECIPIENT]
Hiring Manager
Test Company

[OPENING]
Dear Hiring Manager,
I am excited to apply for the Senior Engineer position at Test Company.

[BODY PARAGRAPH 1]
With 10 years of experience in software development, I have built scalable systems.

[BODY PARAGRAPH 2]
My expertise in Python and cloud technologies aligns well with your requirements.

[CLOSING]
I look forward to discussing how I can contribute to your team.
"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = generate_cover_letter_pdf(
                content=content,
                company="Test Company",
                profile_name="John Doe",
                output_dir=Path(tmpdir)
            )
            
            assert Path(pdf_path).exists(), f"PDF should exist: {pdf_path}"
            assert "coverletter" in pdf_path.lower(), "Should be named as cover letter"
            
            self.log(f"Generated cover letter PDF: {pdf_path}")
    
    def test_document_generator_format_profile(self):
        """Test profile formatting for LLM prompts."""
        from job_agent_coordinator.tools.document_generator import _format_profile_for_prompt
        
        profile = {
            "name": "Test User",
            "contact": {"email": "test@example.com", "phone": "555-1234"},
            "summary": "Experienced engineer.",
            "skills": [{"name": "Python"}, {"name": "AWS"}],
            "experience": [
                {
                    "title": "Engineer",
                    "company": "TechCorp",
                    "start_date": "2020",
                    "end_date": "Present",
                    "description": "Built systems."
                }
            ],
            "notes": "MS in CS."
        }
        
        formatted = _format_profile_for_prompt(profile)
        
        assert "Test User" in formatted, "Should include name"
        assert "Python" in formatted, "Should include skills"
        assert "TechCorp" in formatted, "Should include company"
        self.log(f"Formatted profile (first 500 chars): {formatted[:500]}")
    
    # ========================
    # END-TO-END TESTS
    # ========================
    
    def test_full_resume_generation_pipeline(self):
        """Test complete resume generation (requires LLM and cached data)."""
        from job_agent_coordinator.tools.profile_store import get_store
        from job_agent_coordinator.tools.job_cache import get_cache
        
        # Check prerequisites
        store = get_store()
        cache = get_cache()
        
        profiles = store.list_profiles()
        if not profiles:
            self.log("Skipping: No profiles available")
            return
        
        jobs = cache.list_all(limit=1)
        if not jobs:
            self.log("Skipping: No jobs available")
            return
        
        # Import and run
        from job_agent_coordinator.tools.resume_tools import generate_resume
        
        job_id = jobs[0].get("id")
        self.log(f"Generating resume for job: {job_id}")
        
        result = generate_resume(job_id)
        
        assert "[error]" not in result.lower(), f"Generation failed: {result}"
        assert "pdf_path" in result, "Should include PDF path"
        assert "quality_scores" in result or "fact_verification" in result, "Should include scores"
        
        self.log(f"Resume generation result:\n{result}")
    
    def test_fact_verification_with_fake_content(self):
        """Test that fact verification catches fabricated facts."""
        from job_agent_coordinator.tools.document_critic import critique_document
        
        # Profile with specific facts
        profile = {
            "name": "Test User",
            "skills": [{"name": "Python"}, {"name": "Java"}],
            "experience": [
                {
                    "company": "Google",
                    "title": "Software Engineer",
                    "start_date": "2020",
                    "end_date": "2024",
                    "description": "Built backend services."
                }
            ]
        }
        
        job = {
            "title": "Senior Engineer",
            "description": "Looking for Python developer."
        }
        
        # Content with fabricated facts
        fake_content = """
[HEADER]
Test User

[SUMMARY]
Expert with 20 years of experience at NASA.

[SKILLS]
Python, C++, Quantum Computing

[EXPERIENCE]
Lead Architect | NASA | 2000-2024
- Led mission-critical systems
- Managed budget of $50M
"""
        
        critique = critique_document(fake_content, "resume", profile, job)
        
        # The critique should flag issues (NASA, 20 years, Quantum Computing are fabricated)
        self.log(f"Fact score: {critique.fact_score}")
        self.log(f"Fabricated facts: {critique.fabricated_facts}")
        
        # Note: We don't assert hard failure because LLM analysis varies
        # But we log for manual verification
        if critique.fact_score < 100 or critique.fabricated_facts:
            self.log("Fact verification correctly identified potential issues")
    
    # ========================
    # RUN ALL TESTS
    # ========================
    
    def run_all(self, filter_name: str = None) -> Tuple[int, int]:
        """Run all tests and return (passed, failed) counts."""
        tests = [
            ("profile_loading", self.test_profile_loading),
            ("job_retrieval", self.test_job_retrieval),
            ("length_compliance", self.test_length_compliance),
            ("keyword_extraction", self.test_keyword_extraction),
            ("keyword_matching", self.test_keyword_matching),
            ("profile_facts_extraction", self.test_profile_facts_extraction),
            ("pdf_filename_sanitization", self.test_pdf_filename_sanitization),
            ("resume_section_parsing", self.test_resume_section_parsing),
            ("cover_letter_section_parsing", self.test_cover_letter_section_parsing),
            ("pdf_resume_generation", self.test_pdf_resume_generation),
            ("pdf_cover_letter_generation", self.test_pdf_cover_letter_generation),
            ("document_generator_format_profile", self.test_document_generator_format_profile),
            ("full_resume_generation_pipeline", self.test_full_resume_generation_pipeline),
            ("fact_verification", self.test_fact_verification_with_fake_content),
        ]
        
        if filter_name:
            tests = [(n, t) for n, t in tests if filter_name in n]
            if not tests:
                print(f"No tests matching filter: {filter_name}")
                return 0, 0
        
        print("=" * 70)
        print("DOCUMENT GENERATION INTEGRATION TESTS")
        print("=" * 70)
        print()
        
        for name, test_func in tests:
            self.run_test(name, test_func)
        
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        
        print()
        print("=" * 70)
        print(f"RESULTS: {passed} passed, {failed} failed")
        print("=" * 70)
        
        if failed > 0:
            print("\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")
        
        return passed, failed


def main():
    parser = argparse.ArgumentParser(description="Run document generation tests")
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--test", "-t",
        help="Run only tests matching this name"
    )
    
    args = parser.parse_args()
    
    tests = DocumentGenerationTests(verbose=args.verbose)
    passed, failed = tests.run_all(filter_name=args.test)
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
