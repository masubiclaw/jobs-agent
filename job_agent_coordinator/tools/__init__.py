"""Tools for the job search agent.

Imports are deferred to avoid requiring google.adk when only using
individual tool modules (e.g. toon_format, job_cache).
"""


def __getattr__(name):
    """Lazy import: only load submodules when their exports are accessed."""
    import importlib

    _MODULE_MAP = {
        # jobspy_tools
        "search_jobs_with_jobspy": ".jobspy_tools",
        "search_jobs_tool": ".jobspy_tools",
        "JOBSPY_AVAILABLE": ".jobspy_tools",
        # prompt_to_search_params
        "prompt_to_search_params": ".prompt_to_search_params",
        "prompt_to_search_params_tool": ".prompt_to_search_params",
        # local_cache
        "get_local_cache": ".local_cache",
        "LocalCache": ".local_cache",
        "get_exclusions": ".local_cache",
        "add_exclusion": ".local_cache",
        "remove_exclusion": ".local_cache",
        "get_cached_jobs": ".local_cache",
        "get_local_cache_stats": ".local_cache",
        "get_exclusions_tool": ".local_cache",
        "add_exclusion_tool": ".local_cache",
        "remove_exclusion_tool": ".local_cache",
        "get_cached_jobs_tool": ".local_cache",
        "get_local_cache_stats_tool": ".local_cache",
        # job_cache
        "JobCache": ".job_cache",
        "get_job_cache": ".job_cache",
        "cache_job": ".job_cache",
        "search_cached_jobs": ".job_cache",
        "get_cache_stats": ".job_cache",
        "clear_job_cache": ".job_cache",
        "remove_company_from_cache": ".job_cache",
        "cache_job_tool": ".job_cache",
        "search_cached_jobs_tool": ".job_cache",
        "get_cache_stats_tool": ".job_cache",
        "clear_job_cache_tool": ".job_cache",
        "remove_company_tool": ".job_cache",
        "cache_job_match": ".job_cache",
        "get_cached_match": ".job_cache",
        "list_cached_matches": ".job_cache",
        "clear_cached_matches": ".job_cache",
        "aggregate_job_matches": ".job_cache",
        "cache_job_match_tool": ".job_cache",
        "get_cached_match_tool": ".job_cache",
        "list_cached_matches_tool": ".job_cache",
        "clear_cached_matches_tool": ".job_cache",
        "aggregate_job_matches_tool": ".job_cache",
        # profile_store
        "ProfileStore": ".profile_store",
        "get_profile_store": ".profile_store",
        "create_profile": ".profile_store",
        "get_profile": ".profile_store",
        "update_profile": ".profile_store",
        "add_skill_to_profile": ".profile_store",
        "set_job_preferences": ".profile_store",
        "set_resume_summary": ".profile_store",
        "get_search_context": ".profile_store",
        "list_all_profiles": ".profile_store",
        "create_profile_tool": ".profile_store",
        "get_profile_tool": ".profile_store",
        "update_profile_tool": ".profile_store",
        "add_skill_tool": ".profile_store",
        "set_preferences_tool": ".profile_store",
        "set_resume_tool": ".profile_store",
        "get_search_context_tool": ".profile_store",
        "list_profiles_tool": ".profile_store",
        # job_links_scraper
        "parse_markdown_links": ".job_links_scraper",
        "scrape_webpage": ".job_links_scraper",
        "scrape_job_links": ".job_links_scraper",
        "scrape_single_source": ".job_links_scraper",
        "get_links_summary": ".job_links_scraper",
        "scrape_job_links_tool": ".job_links_scraper",
        "get_links_summary_tool": ".job_links_scraper",
        "scrape_single_source_tool": ".job_links_scraper",
        "parse_markdown_links_tool": ".job_links_scraper",
        # resume_tools
        "generate_resume": ".resume_tools",
        "generate_cover_letter": ".resume_tools",
        "generate_application_package": ".resume_tools",
        "generate_resume_tool": ".resume_tools",
        "generate_cover_letter_tool": ".resume_tools",
        "generate_application_package_tool": ".resume_tools",
    }

    if name in _MODULE_MAP:
        mod = importlib.import_module(_MODULE_MAP[name], __package__)
        # Handle renamed imports
        real_name = name
        if name == "get_local_cache":
            real_name = "get_cache"
        elif name == "get_local_cache_stats":
            real_name = "get_cache_stats"
        elif name == "get_local_cache_stats_tool":
            real_name = "get_cache_stats_tool"
        elif name == "get_job_cache":
            real_name = "get_cache"
        elif name == "get_profile_store":
            real_name = "get_store"
        return getattr(mod, real_name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
