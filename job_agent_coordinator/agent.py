"""Job Agent Coordinator: Multi-agent system for job searching and matching."""

import os
import logging

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from .sub_agents.job_searcher import job_searcher_agent
from .sub_agents.job_matcher import job_matcher_agent
from .tools.profile_store import (
    create_profile_tool,
    get_profile_tool,
    update_profile_tool,
    add_skill_tool,
    set_preferences_tool,
    get_search_context_tool,
)
from .tools.job_cache import (
    search_cached_jobs_tool,
    get_cache_stats_tool,
    aggregate_job_matches_tool,
    list_cached_matches_tool,
)
from .tools.job_links_scraper import (
    scrape_job_links_tool,
    get_links_summary_tool,
    scrape_single_source_tool,
)
from . import prompt

logger = logging.getLogger(__name__)

MODEL = os.getenv("LLM_MODEL", "ollama/gemma3:27b")

# =============================================================================
# Main Orchestration Agent
# =============================================================================

job_agent_coordinator = LlmAgent(
    name="job_agent_coordinator",
    model=MODEL,
    description=(
        "Orchestrates job searches and profile matching. Uses job_searcher to find jobs, "
        "job_matcher to analyze job fit, and profile tools to manage user preferences."
    ),
    instruction=prompt.JOB_AGENT_COORDINATOR_PROMPT,
    output_key="job_agent_coordinator_output",
    tools=[
        AgentTool(agent=job_searcher_agent),
        AgentTool(agent=job_matcher_agent),
        # Profile tools
        create_profile_tool,
        get_profile_tool,
        update_profile_tool,
        add_skill_tool,
        set_preferences_tool,
        get_search_context_tool,
        # Cache tools
        search_cached_jobs_tool,
        get_cache_stats_tool,
        # Match aggregation tools
        aggregate_job_matches_tool,
        list_cached_matches_tool,
        # Scraper tools
        scrape_job_links_tool,
        get_links_summary_tool,
        scrape_single_source_tool,
    ],
)

root_agent = job_agent_coordinator
