"""Shared test configuration."""

import pytest


def pytest_collection_modifyitems(config, items):
    """Skip integration tests that require network or LLM by default."""
    skip_slow = pytest.mark.skip(reason="Slow integration test — requires network/LLM")
    for item in items:
        # Mark tests in files known to hang on network calls
        module = item.module.__name__ if item.module else ""
        if module in (
            "tests.test_job_scraper",
            "tests.test_jobspy",
            "tests.test_integration",
        ):
            item.add_marker(skip_slow)
        # Skip admin background-task tests — they launch real scraper/searcher/matcher
        # threads that make network calls and hang the test runner
        if module == "api.tests.test_admin" and "TestAdminBackgroundTasks" in item.nodeid:
            item.add_marker(skip_slow)
        # Skip document integration tests — they call ollama LLM and hang
        if module == "api.tests.test_documents" and "TestDocumentIntegration" in item.nodeid:
            item.add_marker(skip_slow)
        # Skip pipeline generate tests — they poll for pipeline completion and can exceed timeout
        if "TestPipelineGenerateStepAPI" in item.nodeid:
            item.add_marker(skip_slow)
