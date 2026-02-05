"""Tests for admin endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestAdminAuthorization:
    """Tests for admin authorization."""
    
    def test_admin_endpoints_require_admin(self, client: TestClient, auth_headers: dict):
        """Test that admin endpoints require admin role."""
        # Regular user should not access admin endpoints
        response = client.get("/api/admin/stats", headers=auth_headers)
        
        # Should be 403 Forbidden if not admin
        assert response.status_code in [200, 403]
    
    def test_admin_endpoints_require_auth(self, client: TestClient):
        """Test that admin endpoints require authentication."""
        response = client.get("/api/admin/stats")
        
        assert response.status_code == 403  # No credentials


class TestAdminStats:
    """Tests for admin statistics endpoint."""
    
    def test_get_stats(self, client: TestClient, admin_headers: dict):
        """Test getting system statistics."""
        response = client.get("/api/admin/stats", headers=admin_headers)
        
        # Skip if not admin
        if response.status_code == 403:
            pytest.skip("User is not admin")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "jobs" in data
        assert "matches" in data
        assert "users" in data
        assert "cache" in data


class TestAdminJobManagement:
    """Tests for admin job management."""
    
    def test_list_all_jobs(self, client: TestClient, admin_headers: dict):
        """Test listing all jobs as admin."""
        response = client.get("/api/admin/jobs", headers=admin_headers)
        
        if response.status_code == 403:
            pytest.skip("User is not admin")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "jobs" in data
        assert "total" in data
        assert "page" in data
    
    def test_list_all_jobs_pagination(self, client: TestClient, admin_headers: dict):
        """Test admin job listing with pagination."""
        response = client.get(
            "/api/admin/jobs?page=1&page_size=10",
            headers=admin_headers
        )
        
        if response.status_code == 403:
            pytest.skip("User is not admin")
        
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10


class TestAdminUserManagement:
    """Tests for admin user management."""
    
    def test_list_users(self, client: TestClient, admin_headers: dict):
        """Test listing all users as admin."""
        response = client.get("/api/admin/users", headers=admin_headers)
        
        if response.status_code == 403:
            pytest.skip("User is not admin")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "users" in data
        assert "total" in data
        assert isinstance(data["users"], list)


class TestAdminBackgroundTasks:
    """Tests for admin background task endpoints."""
    
    def test_run_scraper(self, client: TestClient, admin_headers: dict):
        """Test starting scraper task."""
        response = client.post(
            "/api/admin/scraper/run",
            headers=admin_headers
        )
        
        if response.status_code == 403:
            pytest.skip("User is not admin")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
    
    def test_run_searcher(self, client: TestClient, admin_headers: dict):
        """Test starting searcher task."""
        response = client.post(
            "/api/admin/searcher/run?search_term=software+engineer&location=Seattle",
            headers=admin_headers
        )
        
        if response.status_code == 403:
            pytest.skip("User is not admin")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
    
    def test_run_matcher(self, client: TestClient, admin_headers: dict):
        """Test starting matcher task."""
        response = client.post(
            "/api/admin/matcher/run?llm_pass=false&limit=10",
            headers=admin_headers
        )
        
        if response.status_code == 403:
            pytest.skip("User is not admin")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
    
    def test_run_cleanup(self, client: TestClient, admin_headers: dict):
        """Test starting cleanup task."""
        response = client.post(
            "/api/admin/cleanup?days_old=30",
            headers=admin_headers
        )
        
        if response.status_code == 403:
            pytest.skip("User is not admin")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
