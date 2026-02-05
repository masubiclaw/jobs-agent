"""Pytest fixtures for API tests."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

# Set test environment before importing app
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing"


@pytest.fixture(scope="session")
def test_cache_dir() -> Generator[Path, None, None]:
    """Create a temporary cache directory for tests."""
    temp_dir = tempfile.mkdtemp(prefix="jobs_agent_test_")
    yield Path(temp_dir)
    # Cleanup after all tests
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def clean_cache_dir(test_cache_dir: Path) -> Generator[Path, None, None]:
    """Provide a clean cache directory for each test."""
    # Clear contents but keep directory
    for item in test_cache_dir.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    yield test_cache_dir


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the API."""
    from api.main import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_user_data() -> dict:
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "name": "Test User"
    }


@pytest.fixture
def test_profile_data() -> dict:
    """Sample profile data for testing."""
    return {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "555-1234",
        "location": "Seattle, WA"
    }


@pytest.fixture
def test_job_data() -> dict:
    """Sample job data for testing."""
    return {
        "title": "Software Engineer",
        "company": "Tech Corp",
        "location": "Seattle, WA",
        "description": "We are looking for a talented software engineer...",
        "url": "https://example.com/job/123",
        "salary": "$150,000 - $200,000"
    }


@pytest.fixture
def auth_headers(client: TestClient, test_user_data: dict) -> dict:
    """Get authentication headers for a test user."""
    # Register user
    response = client.post("/api/auth/register", json=test_user_data)
    
    # If user already exists, just login
    if response.status_code != 201:
        response = client.post("/api/auth/login", json={
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        })
    else:
        # Login to get token
        response = client.post("/api/auth/login", json={
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        })
    
    assert response.status_code == 200, f"Login failed: {response.json()}"
    token = response.json()["access_token"]
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client: TestClient) -> dict:
    """Get authentication headers for an admin user (first registered user)."""
    admin_data = {
        "email": "admin@example.com",
        "password": "adminpassword123",
        "name": "Admin User"
    }
    
    # Register admin (first user)
    response = client.post("/api/auth/register", json=admin_data)
    
    # Login
    response = client.post("/api/auth/login", json={
        "email": admin_data["email"],
        "password": admin_data["password"]
    })
    
    assert response.status_code == 200, f"Admin login failed: {response.json()}"
    token = response.json()["access_token"]
    
    return {"Authorization": f"Bearer {token}"}
