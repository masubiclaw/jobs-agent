"""Integration tests for job search agents.

These tests verify that agents can be instantiated and run basic operations.
They require Google Cloud credentials to be configured.
"""

import os

import pytest

# Skip all tests in this module if no credentials are available
pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    and not os.environ.get("GOOGLE_CLOUD_PROJECT"),
    reason="Google Cloud credentials not configured",
)


class TestAgentInstantiation:
    """Tests that verify agents can be properly instantiated."""

    def test_coordinator_instantiation(self) -> None:
        """Test coordinator agent instantiation."""
        from job_agent_coordinator.agent import job_agent_coordinator
        
        # Verify agent has all expected attributes
        assert hasattr(job_agent_coordinator, "name")
        assert hasattr(job_agent_coordinator, "model")
        assert hasattr(job_agent_coordinator, "instruction")
        assert hasattr(job_agent_coordinator, "tools")
        assert hasattr(job_agent_coordinator, "description")

    def test_sub_agents_instantiation(self) -> None:
        """Test all sub-agents can be instantiated."""
        from job_agent_coordinator.sub_agents.profile_analyst import profile_analyst_agent
        from job_agent_coordinator.sub_agents.resume_designer import resume_designer_agent
        from job_agent_coordinator.sub_agents.job_searcher import job_searcher_agent
        from job_agent_coordinator.sub_agents.job_posting_analyst import job_posting_analyst_agent
        from job_agent_coordinator.sub_agents.market_analyst import market_analyst_agent

        agents = [
            profile_analyst_agent,
            resume_designer_agent,
            job_searcher_agent,
            job_posting_analyst_agent,
            market_analyst_agent,
        ]

        for agent in agents:
            assert hasattr(agent, "name")
            assert hasattr(agent, "model")
            assert hasattr(agent, "instruction")
            assert hasattr(agent, "tools")

    def test_parallel_agents_instantiation(self) -> None:
        """Test parallel agents can be instantiated."""
        from job_agent_coordinator.agent import (
            parallel_job_search_agent,
            linkedin_search_agent,
            indeed_search_agent,
            glassdoor_search_agent,
        )

        assert parallel_job_search_agent is not None
        assert linkedin_search_agent is not None
        assert indeed_search_agent is not None
        assert glassdoor_search_agent is not None

    def test_pipelines_instantiation(self) -> None:
        """Test pipeline agents can be instantiated."""
        from job_agent_coordinator.agent import (
            profile_to_match_pipeline,
            resume_optimization_pipeline,
            parallel_search_workflow,
        )

        assert profile_to_match_pipeline is not None
        assert resume_optimization_pipeline is not None
        assert parallel_search_workflow is not None


@pytest.mark.asyncio
class TestAgentExecution:
    """Tests that verify agents can execute (requires credentials)."""

    @pytest.mark.skip(reason="Requires active API connection - run manually")
    async def test_profile_analyst_execution(self) -> None:
        """Test profile analyst can process a simple query."""
        from google.adk.runners import InMemoryRunner
        from job_agent_coordinator.sub_agents.profile_analyst import profile_analyst_agent

        runner = InMemoryRunner(agent=profile_analyst_agent)
        
        query = "Analyze this profile: Python developer with 3 years experience"
        async for event in runner.run_async(query):
            # Just verify we can iterate through events
            assert event is not None

    @pytest.mark.skip(reason="Requires active API connection - run manually")
    async def test_coordinator_execution(self) -> None:
        """Test coordinator can process a simple query."""
        from google.adk.runners import InMemoryRunner
        from job_agent_coordinator.agent import job_agent_coordinator

        runner = InMemoryRunner(agent=job_agent_coordinator)
        
        query = "Hello, what can you help me with?"
        async for event in runner.run_async(query):
            assert event is not None

