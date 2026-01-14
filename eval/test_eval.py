"""Evaluation tests for job search agent."""

import json
from pathlib import Path

import pytest


def load_test_cases() -> list:
    """Load test cases from JSON file."""
    test_file = Path(__file__).parent / "data" / "job-search-agent.test.json"
    with open(test_file) as f:
        return json.load(f)


class TestEvaluationCases:
    """Test evaluation cases are properly structured."""

    def test_test_cases_exist(self) -> None:
        """Test that test cases file exists and loads."""
        cases = load_test_cases()
        assert len(cases) > 0

    def test_all_cases_have_required_fields(self) -> None:
        """Test that all cases have required fields."""
        cases = load_test_cases()
        required_fields = ["name", "query", "expected_tool_calls"]
        for case in cases:
            for field in required_fields:
                assert field in case, f"Missing {field} in case {case.get('name')}"

    def test_profile_analysis_case(self) -> None:
        """Test profile analysis case structure."""
        cases = load_test_cases()
        profile_case = next(c for c in cases if c["name"] == "profile_analysis_basic")
        assert "profile_analyst_agent" in profile_case["expected_tool_calls"]

    def test_job_search_case(self) -> None:
        """Test job search case structure."""
        cases = load_test_cases()
        search_case = next(c for c in cases if c["name"] == "job_search_software_engineer")
        assert "job_searcher_agent" in search_case["expected_tool_calls"]

    def test_parallel_search_case(self) -> None:
        """Test parallel search case structure."""
        cases = load_test_cases()
        parallel_case = next(c for c in cases if c["name"] == "parallel_search")
        assert "parallel_search_workflow" in parallel_case["expected_tool_calls"]

    def test_market_analysis_case(self) -> None:
        """Test market analysis case structure."""
        cases = load_test_cases()
        market_case = next(c for c in cases if c["name"] == "market_analysis")
        assert "market_analyst_agent" in market_case["expected_tool_calls"]

    def test_resume_creation_case(self) -> None:
        """Test resume creation case structure."""
        cases = load_test_cases()
        resume_case = next(c for c in cases if c["name"] == "resume_creation")
        assert "resume_designer_agent" in resume_case["expected_tool_calls"]

    def test_job_posting_analysis_case(self) -> None:
        """Test job posting analysis case structure."""
        cases = load_test_cases()
        posting_case = next(c for c in cases if c["name"] == "job_posting_analysis")
        assert "job_posting_analyst_agent" in posting_case["expected_tool_calls"]
