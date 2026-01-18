"""Simple script to run and test the job search agent.

For the best interactive experience, use the ADK CLI:
    adk web .
"""

import os
import sys


def main():
    """Main entry point."""
    print("Job Search Agent")
    print("=" * 40)
    print()
    print("To run the agent, use:")
    print("  adk web .")
    print()
    print("Example queries:")
    print('  - "Find software engineer jobs in Seattle"')
    print('  - "Search for data scientist positions in remote"')
    print()
    
    # Verify import works
    try:
        from job_agent_coordinator.agent import root_agent
        print(f"✅ Agent loaded: {root_agent.name}")
    except Exception as e:
        print(f"❌ Error loading agent: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
