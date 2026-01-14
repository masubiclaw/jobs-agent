"""MCP tool integrations for job search agent."""

import logging
import os
from typing import Optional

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

logger = logging.getLogger(__name__)


def _get_apify_token() -> str:
    """Get APIFY_API_TOKEN from environment (loaded lazily)."""
    return os.getenv("APIFY_API_TOKEN", "")


# =============================================================================
# Apify MCP via npx @apify/actors-mcp-server (STDIO - more reliable)
# =============================================================================
#
# The Apify MCP server connects to Apify actors via the official MCP server.
# This uses stdio connection which is more reliable than SSE.
#
# Prerequisites:
#   - Node.js 18+
#   - APIFY_API_TOKEN environment variable
#
# =============================================================================


def get_apify_mcp(actors: list[str]) -> Optional[McpToolset]:
    """
    Get Apify MCP toolset using the official @apify/actors-mcp-server.
    
    Uses npx to run the MCP server with specified actors.
    
    Args:
        actors: List of actor IDs (e.g., ["getdataforme/glassdoor-jobs-scraper"])
    
    Returns:
        McpToolset or None if token not configured
    """
    token = _get_apify_token()
    if not token:
        logger.warning(
            "APIFY_API_TOKEN not set. Apify MCP will not be available. "
            "Set APIFY_API_TOKEN environment variable to enable."
        )
        return None
    
    try:
        actors_arg = ",".join(actors)
        return McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@apify/actors-mcp-server", "--actors", actors_arg],
                    env={
                        **os.environ,
                        "APIFY_TOKEN": token,
                    },
                ),
            ),
        )
    except Exception as e:
        logger.error(f"Failed to initialize Apify MCP: {e}")
        return None


def get_glassdoor_jobs_mcp() -> Optional[McpToolset]:
    """
    Get Glassdoor Jobs Scraper MCP toolset via Apify.
    
    Tools provided:
    - Search jobs by title and location
    - Get job details (title, company, salary, location, requirements)
    - Application URLs
    
    Returns:
        McpToolset or None if API token not configured
    """
    return get_apify_mcp(["getdataforme/glassdoor-jobs-scraper"])


def get_glassdoor_company_mcp() -> Optional[McpToolset]:
    """
    Get Glassdoor Company Data MCP toolset via Apify.
    
    Tools provided:
    - Company overview and ratings
    - Employee reviews summary
    - Salary information
    - Interview experiences
    
    Returns:
        McpToolset or None if API token not configured
    """
    return get_apify_mcp(["autoscraping/glassdoor-company-data"])


def get_glassdoor_company_search_mcp() -> Optional[McpToolset]:
    """
    Get Glassdoor Company Search MCP toolset via Apify.
    
    Tools provided:
    - Search companies by keyword
    - Get company details (reviews, ratings, interviews, revenue)
    - HR and recruitment intelligence
    
    Returns:
        McpToolset or None if API token not configured
    """
    return get_apify_mcp(["autoscraping/glassdoor-company-search-by-keyword"])


def get_glassdoor_tools() -> list:
    """
    Get all available Glassdoor MCP tools.
    
    Returns:
        List of available McpToolset objects (may be empty if token not configured)
    """
    tools = []
    
    jobs_mcp = get_glassdoor_jobs_mcp()
    if jobs_mcp:
        tools.append(jobs_mcp)
        logger.info("✅ Glassdoor Jobs MCP loaded")
    
    company_mcp = get_glassdoor_company_mcp()
    if company_mcp:
        tools.append(company_mcp)
        logger.info("✅ Glassdoor Company MCP loaded")
    
    company_search_mcp = get_glassdoor_company_search_mcp()
    if company_search_mcp:
        tools.append(company_search_mcp)
        logger.info("✅ Glassdoor Company Search MCP loaded")
    
    if not tools:
        logger.warning(
            "⚠️ No Glassdoor MCP tools loaded. Set APIFY_API_TOKEN to enable."
        )
    
    return tools


# =============================================================================
# Indeed MCP Tools
# =============================================================================
#
# Option 1: Apify Indeed Scrapers (requires APIFY_API_TOKEN)
#   - indeed-jobs-scraper: Job listings by keyword/location
#   - indeed-company-scraper: Company profiles, salaries, reviews
#
# Option 2: JobSpy MCP Server (open source, requires npm install)
#   - Searches Indeed, LinkedIn, Glassdoor, ZipRecruiter simultaneously
#   - Install: npm install -g jobspy-mcp-server
#   - GitHub: https://github.com/borgius/jobspy-mcp-server
#
# =============================================================================


def get_indeed_jobs_mcp() -> Optional[McpToolset]:
    """
    Get Indeed Jobs Scraper MCP toolset (via Apify).
    
    Tools provided:
    - Search jobs by keyword and location
    - Get job details (title, company, salary, description)
    - Application URLs
    
    Returns:
        McpToolset or None if API token not configured
    """
    return get_apify_mcp(["misceres/indeed-scraper"])


def get_indeed_company_mcp() -> Optional[McpToolset]:
    """
    Get Indeed Company Scraper MCP toolset (via Apify).
    
    Tools provided:
    - Company profiles from Indeed
    - Salary data by role
    - Employee reviews
    - Q&A and happiness scores
    
    Returns:
        McpToolset or None if API token not configured
    """
    return get_apify_mcp(["autoscraping/indeed-company-scraper"])


def get_jobspy_mcp() -> Optional[McpToolset]:
    """
    Get JobSpy MCP toolset (searches Indeed, LinkedIn, Glassdoor, ZipRecruiter).
    
    NOTE: JobSpy MCP server is not currently available on npm.
    This function returns None - system uses Google Search + Apify MCPs as fallback.
    
    Returns:
        None (JobSpy MCP not available)
    """
    # JobSpy MCP server doesn't exist on npm - disabled
    # System falls back to Google Search + Apify MCPs (Glassdoor, Indeed)
    logger.info("ℹ️ JobSpy MCP disabled (package not available). Using Google Search + Apify MCPs.")
    return None


def get_indeed_tools() -> list:
    """
    Get all available Indeed MCP tools.
    
    Returns:
        List of available McpToolset objects
    """
    tools = []
    
    jobs_mcp = get_indeed_jobs_mcp()
    if jobs_mcp:
        tools.append(jobs_mcp)
        logger.info("✅ Indeed Jobs MCP loaded (Apify)")
    
    company_mcp = get_indeed_company_mcp()
    if company_mcp:
        tools.append(company_mcp)
        logger.info("✅ Indeed Company MCP loaded (Apify)")
    
    if not tools:
        logger.warning(
            "⚠️ No Indeed MCP tools loaded. Set APIFY_API_TOKEN to enable."
        )
    
    return tools


def get_all_job_platform_tools() -> dict:
    """
    Get all available job platform MCP tools organized by platform.
    
    Returns:
        Dict with platform names as keys and tool lists as values
    """
    return {
        "glassdoor": get_glassdoor_tools(),
        "indeed": get_indeed_tools(),
        "jobspy": [get_jobspy_mcp()] if get_jobspy_mcp() else [],
    }


# =============================================================================
# Note: MCP tools are created on-demand by calling the get_*_mcp() functions
# Do NOT pre-initialize here as it causes issues with parallel agents
# =============================================================================
