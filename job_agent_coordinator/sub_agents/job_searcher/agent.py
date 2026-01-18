"""Job Searcher agent for finding jobs via JobSpy."""

import os
import logging

from google.adk import Agent
from google.adk.tools import FunctionTool

from job_agent_coordinator.tools.jobspy_tools import search_jobs_with_jobspy
from job_agent_coordinator.tools.prompt_to_search_params import prompt_to_search_params
from . import prompt

logger = logging.getLogger(__name__)

MODEL = os.getenv("LLM_MODEL", "ollama/gemma3:27b")

jobspy_search_tool = FunctionTool(func=search_jobs_with_jobspy)
prompt_to_search_params_tool = FunctionTool(func=prompt_to_search_params)

job_searcher_agent = Agent(
    model=MODEL,
    name="job_searcher_agent",
    description="Searches for jobs using JobSpy across Indeed, LinkedIn, Glassdoor, and ZipRecruiter.",
    instruction=prompt.JOB_SEARCHER_PROMPT,
    output_key="job_search_output",
    tools=[prompt_to_search_params_tool, jobspy_search_tool],
)
