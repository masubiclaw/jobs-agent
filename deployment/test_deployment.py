"""Tests for deployment configuration."""

import pytest


class TestDeploymentConfig:
    """Tests for deployment configuration."""

    def test_agent_importable(self) -> None:
        """Test that agent can be imported for deployment."""
        from job_agent_coordinator.agent import root_agent
        assert root_agent is not None

    def test_deploy_function_exists(self) -> None:
        """Test that deploy function is accessible."""
        from deployment.deploy import deploy_agent
        assert deploy_agent is not None

    def test_deploy_requires_project_id(self) -> None:
        """Test that deployment fails without project ID."""
        from deployment.deploy import deploy_agent
        import os
        
        # Clear env var if set
        original = os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        try:
            with pytest.raises(ValueError, match="Project ID must be provided"):
                deploy_agent(project_id=None)
        finally:
            if original:
                os.environ["GOOGLE_CLOUD_PROJECT"] = original

