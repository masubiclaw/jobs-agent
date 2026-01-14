"""Profile Analyst agent for analyzing candidate profiles and career positioning."""

import logging
from google.adk import Agent
from google.adk.tools import FunctionTool

from . import prompt

# Import user profile storage functions from history_manager
from ..history_manager.agent import (
    save_user_profile,
    get_primary_profile,
    get_user_profile,
    list_user_profiles,
    update_user_profile,
    search_user_profiles,
)

logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-pro"

# NOTE: Gemini API limitation - cannot mix google_search with FunctionTools
# Profile Analyst uses storage tools only; coordinator can use google_search separately
profile_analyst_agent = Agent(
    model=MODEL,
    name="profile_analyst_agent",
    description=(
        "Analyzes candidate profiles including resumes, LinkedIn profiles, and "
        "experience descriptions. Extracts skills, assesses experience depth, "
        "identifies strengths and gaps, and maps potential career paths. "
        "Includes storage for user profiles."
    ),
    instruction=prompt.PROFILE_ANALYST_PROMPT,
    output_key="profile_analysis_output",
    tools=[
        # User Profile Storage Tools (no google_search due to Gemini API limitation)
        FunctionTool(func=save_user_profile),
        FunctionTool(func=get_primary_profile),
        FunctionTool(func=get_user_profile),
        FunctionTool(func=list_user_profiles),
        FunctionTool(func=update_user_profile),
        FunctionTool(func=search_user_profiles),
    ],
)

logger.info("✅ Profile Analyst Agent initialized with user profile storage")

