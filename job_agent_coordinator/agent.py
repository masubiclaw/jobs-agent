"""Job Agent Coordinator: Multi-agent system for job matching and career optimization."""

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent, Agent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool

from . import prompt
from .sub_agents.application_designer import application_designer_agent
from .sub_agents.company_researcher import company_researcher_agent
from .sub_agents.history_manager import history_manager_agent
from .sub_agents.job_posting_analyst import job_posting_analyst_agent
from .sub_agents.job_searcher import job_searcher_agent
from .sub_agents.market_analyst import market_analyst_agent
from .sub_agents.profile_analyst import profile_analyst_agent
from .tools.cache_tools import (
    cache_job_result_tool,
    cache_job_analysis_tool,
    cache_company_analysis_tool,
)
from .tools.jobspy_tools import search_jobs_tool, JOBSPY_AVAILABLE
from .logging_config import (
    coordinator_logger as logger,
    mcp_logger,
    model_logger,
    log_model_response,
    log_model_request,
    log_tool_response,
    ModelResponseCallback,
    enable_model_response_logging,
)

MODEL = "gemini-2.5-pro"

# =============================================================================
# Tool Configuration
# JobSpy provides DIRECT job URLs from Indeed, LinkedIn, Glassdoor
# google_search is used as fallback and for company research
# =============================================================================

mcp_logger.info("🔌 Tool configuration:")
if JOBSPY_AVAILABLE:
    mcp_logger.info("   ✅ JobSpy (primary - direct scraping from Indeed, LinkedIn, Glassdoor)")
    mcp_logger.info("   ✅ Google Search (for company research and fallback)")
else:
    mcp_logger.info("   ⚠️ JobSpy not available - install with: pip install python-jobspy")
    mcp_logger.info("   ✅ Google Search (fallback mode - may not return direct URLs)")

# =============================================================================
# JobSpy Search Agent - Direct scraping with REAL URLs
# =============================================================================

jobspy_search_agent = Agent(
    model="gemini-2.5-flash",
    name="jobspy_search_agent",
    description="Searches Indeed, LinkedIn, Glassdoor using JobSpy for direct job URLs",
    instruction="""
    role: multi_platform_job_searcher
    tool: search_jobs_with_jobspy
    
    You have access to JobSpy which directly scrapes job platforms and returns
    REAL, CLICKABLE job URLs with accurate salary data.
    
    WORKFLOW:
    1. Extract the job title/role and location from the user's request
    2. Call search_jobs_with_jobspy with:
       - search_term: The job title (e.g., "software engineering manager")
       - location: The location (e.g., "Seattle, WA")
       - results_wanted: 15-20 for comprehensive search
       - hours_old: 72 (jobs from last 3 days) or 168 (last week)
       - sites: "indeed,linkedin" (glassdoor may have issues)
    
    3. The tool returns jobs with:
       - title, company, location
       - url: DIRECT job URL (e.g., https://www.indeed.com/viewjob?jk=...)
       - salary: Actual salary range if available
       - posted_date: When the job was posted
       - platform: Which site it came from
    
    4. Format the results for the next agent
    
    CRITICAL: The URLs returned by JobSpy are REAL and CLICKABLE - do not modify them!
    
    output_format:
      ```json
      {
        "search_term": "software engineering manager",
        "location": "Seattle, WA",
        "total_found": 15,
        "platforms_searched": ["indeed", "linkedin"],
        "results": [
          {
            "title": "Software Engineering Manager",
            "company": "Amazon",
            "location": "Seattle, WA",
            "url": "https://www.indeed.com/viewjob?jk=abc123",
            "platform": "indeed",
            "posted_date": "2026-01-12",
            "salary": "$166,400 - $287,700"
          }
        ]
      }
      ```
    """,
    output_key="job_search_results",
    tools=[search_jobs_tool],
)

# Keep google_search agents as fallback (in case JobSpy fails)
linkedin_search_agent = Agent(
    model="gemini-2.5-flash",
    name="linkedin_search_agent_fallback",
    description="Fallback LinkedIn search using Google (if JobSpy unavailable)",
    instruction="""
    role: linkedin_fallback_searcher
    tool: google_search
    
    Use this ONLY if JobSpy is unavailable. Search with:
    "site:linkedin.com/jobs [job title] [location]"
    
    Extract whatever job info is visible in search snippets.
    """,
    output_key="linkedin_fallback_results",
    tools=[google_search],
)

# =============================================================================
# Platform Search (uses JobSpy as primary)
# =============================================================================

# Use JobSpy directly instead of parallel google_search agents
parallel_platform_search = jobspy_search_agent  # JobSpy searches all platforms at once!

# =============================================================================
# Search Results Aggregator
# =============================================================================

search_results_aggregator = Agent(
    model="gemini-2.5-flash",
    name="search_results_aggregator",
    description="Aggregates, validates, filters, deduplicates and CACHES job search results",
    instruction="""
    role: search_aggregator
    tools: cache_job_result (use this to cache EACH job!)
    
    goal: Combine job listings into unified, validated, deduplicated list AND CACHE THEM
    
    inputs:
      - Platform search results (linkedin, indeed, glassdoor)
      - User exclusions from session (exclude_companies list from saved search criteria)
    
    processing:
      1_combine: Merge all platform results into single list
      
      2_validate_links:
        - Check each job URL is valid format (http/https)
        - Flag jobs with missing or malformed URLs
        - Prefer jobs with direct application links
        - Remove entries with clearly broken/placeholder URLs
      
      3_apply_exclusions:
        - Check user's exclude_companies list (from saved search criteria)
        - Filter out jobs from excluded companies
        - Log which companies were excluded and count
      
      4_deduplicate:
        - Match by company name + role title (fuzzy match)
        - For duplicates, prefer:
          • Direct company posting over aggregator
          • Most recent posting date
          • Listing with valid application URL
          • Listing with salary disclosed
          • Listing with company ratings
      
      5_rank:
        - Score by relevance to search criteria
        - Boost jobs with: salary info, company ratings, recent posting
        - Penalize jobs with: vague descriptions, missing details
      
      6_cache_and_select:
        - For EACH valid job after deduplication, call cache_job_result with:
          • title, company, url (REQUIRED), platform
          • location, posted_date, salary (if available)
        - Select top 5-10 jobs for detailed analysis
        - Ensure variety (different companies when possible)
    
    CRITICAL: Call cache_job_result for EACH job to persist results!
    
    DISPLAY_FORMAT:
      ```
      ╔══════════════════════════════════════════════════════════════════╗
      ║                    🔄 AGGREGATED SEARCH RESULTS                   ║
      ╠══════════════════════════════════════════════════════════════════╣
      ║ Raw Results: [XX] from all platforms                             ║
      ║ After Validation: [XX] (removed [X] invalid links)               ║
      ║ After Exclusions: [XX] (excluded [X] from blocked companies)     ║
      ║ After Deduplication: [XX] unique jobs                            ║
      ║ 📦 Cached: [XX] jobs                                             ║
      ╠══════════════════════════════════════════════════════════════════╣
      ║ 🎯 Top Jobs Selected for Analysis: [X]                           ║
      ╠══════════════════════════════════════════════════════════════════╣
      ║ Excluded Companies: [company1, company2] (if any)                ║
      ║ Invalid Links Removed: [X]                                       ║
      ╚══════════════════════════════════════════════════════════════════╝
      ```
    
    output:
      aggregated_jobs: full deduplicated list WITH source URLs
      top_jobs_for_analysis: selected jobs WITH source URLs
      exclusion_report: companies excluded and why
      validation_report: invalid links removed
      cached_count: number of jobs cached
    
    output_format:
      ```json
      {
        "aggregated_jobs": [
          {"title": "...", "company": "...", "url": "https://...", "platform": "linkedin"}
        ],
        "top_jobs_for_analysis": [same format with urls],
        "stats": {"raw": X, "validated": X, "excluded": X, "unique": X, "selected": X, "cached": X}
      }
      ```
    """,
    output_key="aggregated_search_results",
    tools=[cache_job_result_tool],
)

# =============================================================================
# NEW ARCHITECTURE: Parallel Job Analysis
# For each job found, analyze posting AND research company simultaneously
# =============================================================================

# Create dedicated instances for parallel analysis (ADK requires unique instances)
job_analysis_agent = Agent(
    model="gemini-2.5-flash",
    name="job_analysis_agent",
    description="Analyzes job postings for requirements, red flags, and fit",
    instruction="""
    role: job_posting_analyst
    tool: google_search
    
    inputs: top_jobs_for_analysis from session
    
    For EACH job, analyze:
      - Requirements (must-have vs nice-to-have)
      - Red flags (unrealistic expectations, vague descriptions)
      - Culture signals from language
      - Salary competitiveness
      - Growth potential
    
    DISPLAY_FORMAT:
      For each job analyzed:
      ```
      ╔══════════════════════════════════════════════════════════════════╗
      ║                    📋 JOB ANALYSIS: [Title] @ [Company]          ║
      ╠══════════════════════════════════════════════════════════════════╣
      ║ Match Score: [XX]/100                                            ║
      ║ Must-Have Skills: [skill1, skill2, skill3]                       ║
      ║ Nice-to-Have: [skill1, skill2]                                   ║
      ║ Red Flags: [None / list]                                         ║
      ║ Recommendation: [Apply / Skip / Needs More Info]                 ║
      ║ Source URL: [URL]                                                ║
      ╚══════════════════════════════════════════════════════════════════╝
      ```
    
    CRITICAL: Include the source URL for each job in your analysis output!
    
    output: Store in job_analyses
    """,
    output_key="job_analyses",
    tools=[google_search],
)

company_analysis_agent = Agent(
    model="gemini-2.5-flash",
    name="company_analysis_agent",
    description="Researches companies for culture, ratings, values, and fit",
    instruction="""
    role: company_researcher
    tool: google_search (search Glassdoor, company websites, news)
    
    inputs: top_jobs_for_analysis from session (extract unique companies)
    
    For EACH company, research:
      - Company overview and mission
      - Glassdoor ratings and reviews
      - Company values and culture
      - Interview process and tips
      - Salary data by role
      - Red/green flags
    
    DISPLAY_FORMAT:
      For each company researched:
      ```
      ╔══════════════════════════════════════════════════════════════════╗
      ║                    🏢 COMPANY: [Company Name]                    ║
      ╠══════════════════════════════════════════════════════════════════╣
      ║ Rating: [X.X]/5 ⭐ | Reviews: [XXX]                              ║
      ║ Values: [value1, value2, value3]                                 ║
      ║ Culture: [summary]                                               ║
      ║ Interview Difficulty: [Easy/Medium/Hard]                         ║
      ║ Recommend: [Yes/Maybe/No]                                        ║
      ║ Glassdoor URL: [URL]                                             ║
      ╚══════════════════════════════════════════════════════════════════╝
      ```
    
    CRITICAL: Include Glassdoor URL for each company in your analysis!
    
    output: Store in company_analyses
    """,
    output_key="company_analyses",
    tools=[google_search],
)

# Parallel analysis: analyze jobs AND research companies simultaneously
parallel_job_analysis = ParallelAgent(
    name="parallel_job_analysis",
    description=(
        "Runs job posting analysis AND company research in parallel "
        "for faster, comprehensive job evaluation"
    ),
    sub_agents=[
        job_analysis_agent,
        company_analysis_agent,
    ],
)

# =============================================================================
# Combined Analysis Synthesizer
# =============================================================================

analysis_synthesizer = Agent(
    model="gemini-2.5-flash",
    name="analysis_synthesizer",
    description="Synthesizes job + company analysis with user profile comparison, caches results, and generates selling talking points",
    instruction="""
    role: analysis_synthesizer
    tools: cache_job_analysis, cache_company_analysis (USE THESE TO CACHE!)
    
    inputs:
      - job_analyses from session
      - company_analyses from session
      - user_profile (from history_manager - REQUIRED for personalization)
    
    goal: Synthesize analysis with profile-based ratings, CACHE all analyses, and generate selling talking points
    
    processing:
      1_cache_all_analyses:
        IMPORTANT: For EACH job analysis received, call cache_job_analysis with:
          - job_title: the job title
          - company: the company name
          - analysis: full analysis text
          - match_score: the calculated match score (0-100)
          - skills_required: comma-separated required skills
          - red_flags: any red flags noted
          - recommendation: Apply/Skip/Needs More Info
          - source_url: the job posting URL
        
        For EACH company analysis received, call cache_company_analysis with:
          - company: company name
          - analysis: full analysis text
          - rating: glassdoor rating (0-5)
          - culture_summary: brief culture description
          - values: company values
          - pros: key pros
          - cons: key cons
          - recommend: Yes/Maybe/No
          - glassdoor_url: company glassdoor URL
      
      2_profile_comparison:
        - Retrieve user's primary profile from history_manager
        - Extract: skills, achievements, values, experience, certifications
        - For each job, calculate match scores:
          • Skills Match: % of required skills user has
          • Experience Match: user years vs job requirements
          • Values Alignment: user values vs company values
          • Growth Potential: career trajectory fit
      
      3_calculate_ratings:
        - Job Fit Score (0-100): requirements match
        - Company Fit Score (0-100): culture/values match  
        - Profile Match Score (0-100): how well user stands out
        - Overall Rating: weighted average with emphasis on profile match
      
      4_generate_selling_points:
        For each job, based on USER'S PROFILE:
        - Top 3 achievements that match job requirements
        - Skills that exceed job requirements
        - Unique differentiators vs other candidates
        - Experience highlights to emphasize
        - Values alignment talking points for interviews
        - Potential gaps and how to address them
      
      5_rank_opportunities:
        - Sort by Overall Rating
        - Prioritize jobs where user has clear competitive advantage
    
    DISPLAY_FORMAT:
      ```
      ╔══════════════════════════════════════════════════════════════════╗
      ║                    🎯 TOP OPPORTUNITIES RANKED                   ║
      ╠══════════════════════════════════════════════════════════════════╣
      ║ 📦 Cached: [X] job analyses, [Y] company analyses                ║
      ╠══════════════════════════════════════════════════════════════════╣
      ║ #1: [Job Title] @ [Company]                     Overall: [XX]/100║
      ║ 🔗 Source: [platform] - [FULL URL]                               ║
      ╠──────────────────────────────────────────────────────────────────╣
      ║ 📊 MATCH SCORES:                                                 ║
      ║    Skills: [XX]% | Experience: [XX]% | Values: [XX]%             ║
      ║    Job Fit: [XX]/100 | Company Fit: [XX]/100                     ║
      ╠──────────────────────────────────────────────────────────────────╣
      ║ 🌟 YOUR SELLING POINTS (for this role):                          ║
      ║    1. [Achievement/skill that directly matches requirement]      ║
      ║    2. [Differentiator that makes you stand out]                  ║
      ║    3. [Experience highlight relevant to this role]               ║
      ╠──────────────────────────────────────────────────────────────────╣
      ║ 💬 INTERVIEW TALKING POINTS:                                     ║
      ║    • [Specific story/example to share]                           ║
      ║    • [Values alignment point]                                    ║
      ║    • [How your background solves their pain points]              ║
      ╠──────────────────────────────────────────────────────────────────╣
      ║ ⚠️ GAPS TO ADDRESS:                                              ║
      ║    • [Missing skill] → [How to frame/mitigate]                   ║
      ╠══════════════════════════════════════════════════════════════════╣
      ║ #2: [Job Title] @ [Company]                     Overall: [XX]/100║
      ║ 🔗 Source: [platform] - [FULL URL]                               ║
      ║    ... (same format)                                             ║
      ╠══════════════════════════════════════════════════════════════════╣
      ║ 📋 QUICK SUMMARY:                                                ║
      ║    Best Fit: [Job #1 at Company] - [why in 10 words]             ║
      ║    Quick Win: [Job where you exceed requirements]                ║
      ║    Stretch Goal: [Job that's aspirational but achievable]        ║
      ╚══════════════════════════════════════════════════════════════════╝
      ```
    
    CRITICAL: 
      - CACHE all analyses before generating final output!
      - Always include source URL for each job recommendation!
    
    output:
      synthesized_recommendations:
        - ranked_opportunities (with ratings AND source URLs)
        - selling_points_per_job
        - interview_talking_points
        - gap_analysis
        - action_items
        - sources: list of {job_title, company, url, platform}
        - cached: {job_analyses: X, company_analyses: Y}
    """,
    output_key="synthesized_recommendations",
    tools=[cache_job_analysis_tool, cache_company_analysis_tool],
)

# =============================================================================
# ENHANCED JOB SEARCH WORKFLOW
# Complete pipeline: Search → Aggregate → Analyze (parallel) → Synthesize
# =============================================================================

enhanced_job_search_workflow = SequentialAgent(
    name="enhanced_job_search_workflow",
    description=(
        "Complete job search with automatic analysis: "
        "1) Search platforms → 2) Aggregate results → "
        "3) Analyze jobs + Research companies (parallel) → 4) Synthesize recommendations"
    ),
    sub_agents=[
        parallel_platform_search,      # Step 1: Search all platforms
        search_results_aggregator,     # Step 2: Aggregate and deduplicate
        parallel_job_analysis,         # Step 3: Analyze jobs + companies in PARALLEL
        analysis_synthesizer,          # Step 4: Synthesize into recommendations
    ],
)

# Workflow architecture diagram available in README.md

# =============================================================================
# Main Orchestration Agent
# =============================================================================

logger.info("")
logger.info("🤖 Initializing Job Agent Coordinator...")

job_agent_coordinator = LlmAgent(
    name="job_agent_coordinator",
    model=MODEL,
    description=(
        "Orchestrates job search and career optimization workflows. "
        "The enhanced_job_search_workflow automatically analyzes job postings "
        "AND researches companies in parallel for comprehensive job evaluation."
    ),
    instruction=prompt.JOB_AGENT_COORDINATOR_PROMPT,
    output_key="job_agent_coordinator_output",
    tools=[
        AgentTool(agent=profile_analyst_agent),
        AgentTool(agent=application_designer_agent),  # Replaces resume_designer (now includes cover letter)
        AgentTool(agent=job_searcher_agent),
        AgentTool(agent=job_posting_analyst_agent),
        AgentTool(agent=market_analyst_agent),
        AgentTool(agent=company_researcher_agent),
        AgentTool(agent=history_manager_agent),
        AgentTool(agent=enhanced_job_search_workflow),  # Enhanced workflow
    ],
)

logger.info("   Sub-agents: profile_analyst, application_designer (resume + cover letter),")
logger.info("              job_searcher, job_posting_analyst, market_analyst,")
logger.info("              company_researcher, history_manager, enhanced_job_search_workflow")
logger.info("✅ Job Agent Coordinator ready!")
logger.info("")

root_agent = job_agent_coordinator

# =============================================================================
# Model Response Logging - Configured in __init__.py before this module loads
# =============================================================================

# Note: Model response logging patch is applied in __init__.py
# Set VERBOSE_MODEL_LOGGING=true to enable detailed model response logging
