"""Deployment script for job search agent."""

import os
from typing import Optional

from absl import app, flags
from google.cloud import aiplatform

FLAGS = flags.FLAGS
flags.DEFINE_string("project_id", None, "GCP project ID")
flags.DEFINE_string("location", "us-central1", "GCP location for deployment")
flags.DEFINE_string("display_name", "job-search-agent", "Display name for the agent")
flags.DEFINE_string(
    "description",
    "AI-driven multi-agent system for job search orchestration",
    "Description for the agent",
)


def deploy_agent(
    project_id: Optional[str] = None,
    location: str = "us-central1",
    display_name: str = "job-search-agent",
    description: str = "AI-driven multi-agent system for job search orchestration",
) -> str:
    """Deploy the job search agent to Vertex AI Agent Builder.

    Args:
        project_id: GCP project ID. Uses default if not provided.
        location: GCP location for deployment.
        display_name: Display name for the deployed agent.
        description: Description for the deployed agent.

    Returns:
        The resource name of the deployed agent.
    """
    project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise ValueError(
            "Project ID must be provided via --project_id or GOOGLE_CLOUD_PROJECT env var"
        )

    aiplatform.init(project=project_id, location=location)

    from job_agent_coordinator.agent import root_agent

    # Deploy using Agent Builder
    deployed_agent = aiplatform.Agent.create(
        display_name=display_name,
        description=description,
        agent=root_agent,
    )

    print(f"Agent deployed successfully: {deployed_agent.resource_name}")
    return deployed_agent.resource_name


def main(argv: list) -> None:
    """Main entry point for deployment."""
    del argv  # Unused
    deploy_agent(
        project_id=FLAGS.project_id,
        location=FLAGS.location,
        display_name=FLAGS.display_name,
        description=FLAGS.description,
    )


if __name__ == "__main__":
    flags.mark_flag_as_required("project_id")
    app.run(main)

