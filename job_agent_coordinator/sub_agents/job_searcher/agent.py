"""Job Searcher agent for orchestrating parallel job searches and aggregation."""

from google.adk import Agent
from google.adk.tools import FunctionTool

from job_agent_coordinator.config import get_search_model
from job_agent_coordinator.tools.jobspy_tools import (
    search_jobs_with_jobspy,
    check_jobspy_status,
    get_jobspy_stats,
)
from job_agent_coordinator.tools.cache_tools import (
    cache_job_result,
    list_cached_jobs,
)

from . import prompt

# Tools for job search orchestration
jobspy_search_tool = FunctionTool(func=search_jobs_with_jobspy)
jobspy_status_tool = FunctionTool(func=check_jobspy_status)
jobspy_stats_tool = FunctionTool(func=get_jobspy_stats)
cache_job_tool = FunctionTool(func=cache_job_result)
list_cache_tool = FunctionTool(func=list_cached_jobs)

job_searcher_agent = Agent(
    model=get_search_model(),
    name="job_searcher_agent",
    description=(
        "Orchestrates parallel job searches using JobSpy across Indeed, LinkedIn, "
        "Glassdoor, and ZipRecruiter. Generates search variations, aggregates results, "
        "deduplicates, validates URLs, flags red flags, and caches valid jobs. "
        "Does NOT rank or analyze jobs - that's for downstream agents."
    ),
    instruction=prompt.JOB_SEARCHER_PROMPT,
    output_key="job_search_output",
    tools=[
        jobspy_search_tool,
        jobspy_status_tool,
        jobspy_stats_tool,
        cache_job_tool,
        list_cache_tool,
    ],
)
