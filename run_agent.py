"""Simple script to run and test the job search agent.

For the best interactive experience, use the ADK CLI:
    adk run job_agent_coordinator

This script provides verification and simple query capabilities.
"""

import os
import sys


def setup_environment() -> None:
    """Set up environment variables for Google Cloud."""
    import google.auth
    
    try:
        _, project_id = google.auth.default()
        if project_id:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
    except Exception as e:
        print(f"Warning: Could not get default credentials: {e}")
    
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")


def verify_agents() -> bool:
    """Verify all agents can be imported and are configured correctly."""
    print("Verifying agent configuration...")
    
    try:
        from job_agent_coordinator.agent import (
            root_agent,
            job_agent_coordinator,
            parallel_platform_search,
            parallel_search_workflow,
            linkedin_search_agent,
            indeed_search_agent,
            glassdoor_search_agent,
            search_results_aggregator_agent,
        )
        
        # Import sub-agents to verify structure
        from job_agent_coordinator.sub_agents.profile_analyst import profile_analyst_agent
        from job_agent_coordinator.sub_agents.resume_designer import resume_designer_agent
        from job_agent_coordinator.sub_agents.job_searcher import job_searcher_agent
        from job_agent_coordinator.sub_agents.job_posting_analyst import job_posting_analyst_agent
        from job_agent_coordinator.sub_agents.market_analyst import market_analyst_agent
        from job_agent_coordinator.sub_agents.company_researcher import company_researcher_agent
        from job_agent_coordinator.sub_agents.history_manager import history_manager_agent

        print("✓ All agents imported successfully")
        print(f"✓ Root agent: {root_agent.name}")
        print(f"✓ Coordinator has {len(job_agent_coordinator.tools)} tools")
        print(f"✓ Parallel platform search has {len(parallel_platform_search.sub_agents)} sub-agents")
        print(f"✓ Parallel workflow has {len(parallel_search_workflow.sub_agents)} steps")
        
        # List all sub-agents
        print("\nSub-agents loaded:")
        print(f"  - {profile_analyst_agent.name}")
        print(f"  - {resume_designer_agent.name}")
        print(f"  - {job_searcher_agent.name}")
        print(f"  - {job_posting_analyst_agent.name}")
        print(f"  - {market_analyst_agent.name}")
        print(f"  - {company_researcher_agent.name}")
        print(f"  - {history_manager_agent.name}")
        print(f"  - {linkedin_search_agent.name}")
        print(f"  - {indeed_search_agent.name}")
        print(f"  - {glassdoor_search_agent.name}")
        print(f"  - {search_results_aggregator_agent.name}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error verifying agents: {e}")
        import traceback
        traceback.print_exc()
        return False


def show_usage() -> None:
    """Show usage information."""
    print("Job Search Agent - Run Script")
    print("=" * 60)
    print("\nUsage:")
    print("  python run_agent.py --verify     # Verify agent configuration")
    print("  python run_agent.py --test       # Run a test query")
    print("  python run_agent.py --help       # Show this help message")
    print("")
    print("For interactive mode, use the ADK CLI:")
    print("  adk run job_agent_coordinator")
    print("")
    print("Or to start the web UI:")
    print("  adk web job_agent_coordinator")
    print("")
    print("Quick start with verbose logging:")
    print("  VERBOSE_MODEL_LOGGING=true adk web .")
    print("")
    print("Example queries to try:")
    print('  - "Hello! What can you help me with?"')
    print('  - "Analyze my profile: 5 years Python, React, worked at startups"')
    print('  - "Find senior software engineer jobs in San Francisco"')
    print('  - "search seattle for software engineering manager jobs"')
    print('  - "What\'s the job market like for ML engineers?"')
    print('  - "Create a resume for a data scientist position"')
    print('  - "Research Google as a company"')
    print('  - "Show my search history"')


async def run_test_query() -> bool:
    """Run a test query against the agent."""
    print("\n" + "=" * 60)
    print("Running test query: 'search seattle for software engineering manager jobs'")
    print("=" * 60 + "\n")
    
    try:
        from google.adk.runners import InMemoryRunner
        from job_agent_coordinator.agent import root_agent
        
        runner = InMemoryRunner(agent=root_agent)
        
        # Create a test session
        session = await runner.session_service.create_session(
            app_name="job_agent_coordinator",
            user_id="test_user"
        )
        
        # Pre-seeded test query
        test_query = "search seattle for software engineering manager jobs"
        
        print(f"📤 Query: {test_query}")
        print("-" * 60)
        
        # Run the query
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session.id,
            new_message=test_query
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(f"🤖 {event.author} > {part.text}")
                    elif hasattr(part, 'function_call') and part.function_call:
                        print(f"🔧 [Tool: {part.function_call.name}]")
        
        print("\n" + "=" * 60)
        print("✅ Test query completed successfully!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main() -> None:
    """Main entry point."""
    setup_environment()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--verify":
            success = verify_agents()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == "--test":
            import asyncio
            success = asyncio.run(run_test_query())
            sys.exit(0 if success else 1)
        elif sys.argv[1] in ["--help", "-h"]:
            show_usage()
            sys.exit(0)
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            show_usage()
            sys.exit(1)
    else:
        # Default behavior: show help
        show_usage()
        print("\n" + "=" * 60)
        print("Running verification check...")
        print("=" * 60 + "\n")
        verify_agents()


if __name__ == "__main__":
    main()
