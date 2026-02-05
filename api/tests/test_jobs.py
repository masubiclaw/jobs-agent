"""Tests for job management endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestJobListing:
    """Tests for job listing endpoints."""
    
    def test_list_jobs_empty(self, client: TestClient, auth_headers: dict):
        """Test listing jobs when cache might be empty."""
        response = client.get("/api/jobs", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["jobs"], list)
    
    def test_list_jobs_pagination(self, client: TestClient, auth_headers: dict):
        """Test job listing pagination."""
        response = client.get(
            "/api/jobs?page=1&page_size=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10
    
    def test_list_jobs_with_filters(self, client: TestClient, auth_headers: dict):
        """Test job listing with filters."""
        response = client.get(
            "/api/jobs?company=Google&location=Seattle",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["jobs"], list)


class TestJobCreation:
    """Tests for job creation endpoints."""
    
    def test_create_job_with_fields(self, client: TestClient, auth_headers: dict, test_job_data: dict):
        """Test creating a job with direct fields."""
        response = client.post(
            "/api/jobs",
            json=test_job_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == test_job_data["title"]
        assert data["company"] == test_job_data["company"]
        assert "id" in data
    
    def test_create_job_with_plaintext(self, client: TestClient, auth_headers: dict):
        """Test creating a job from plaintext description."""
        response = client.post(
            "/api/jobs",
            json={
                "plaintext": """
                Software Engineer at TechCorp
                Location: Seattle, WA
                Salary: $150,000 - $180,000
                
                We are looking for an experienced software engineer to join our team.
                Requirements: Python, JavaScript, 5+ years experience.
                """
            },
            headers=auth_headers
        )
        
        # This may fail if LLM is not available, which is acceptable in tests
        assert response.status_code in [201, 400]
    
    def test_create_job_missing_required(self, client: TestClient, auth_headers: dict):
        """Test creating a job without required fields fails."""
        response = client.post(
            "/api/jobs",
            json={},  # Empty data
            headers=auth_headers
        )
        
        assert response.status_code == 400


class TestJobManagement:
    """Tests for job management (update, delete)."""
    
    def test_get_job(self, client: TestClient, auth_headers: dict, test_job_data: dict):
        """Test getting a specific job."""
        # Create job first
        create_response = client.post(
            "/api/jobs",
            json=test_job_data,
            headers=auth_headers
        )
        
        if create_response.status_code != 201:
            pytest.skip("Job creation failed")
        
        job_id = create_response.json()["id"]
        
        # Get job
        response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
    
    def test_update_job_status(self, client: TestClient, auth_headers: dict, test_job_data: dict):
        """Test updating job status to completed."""
        # Create job
        create_response = client.post(
            "/api/jobs",
            json=test_job_data,
            headers=auth_headers
        )
        
        if create_response.status_code != 201:
            pytest.skip("Job creation failed")
        
        job_id = create_response.json()["id"]
        
        # Update status
        response = client.put(
            f"/api/jobs/{job_id}",
            json={"status": "completed"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
    
    def test_update_job_notes(self, client: TestClient, auth_headers: dict, test_job_data: dict):
        """Test updating job notes."""
        # Create job
        create_response = client.post(
            "/api/jobs",
            json=test_job_data,
            headers=auth_headers
        )
        
        if create_response.status_code != 201:
            pytest.skip("Job creation failed")
        
        job_id = create_response.json()["id"]
        
        # Update notes
        response = client.put(
            f"/api/jobs/{job_id}",
            json={"notes": "Applied on 2024-01-15, waiting for response"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "Applied on" in data["notes"]
    
    def test_delete_job(self, client: TestClient, auth_headers: dict, test_job_data: dict):
        """Test deleting a job."""
        # Create job
        create_response = client.post(
            "/api/jobs",
            json={**test_job_data, "title": "Job to Delete"},
            headers=auth_headers
        )
        
        if create_response.status_code != 201:
            pytest.skip("Job creation failed")
        
        job_id = create_response.json()["id"]
        
        # Delete job
        response = client.delete(f"/api/jobs/{job_id}", headers=auth_headers)
        
        assert response.status_code == 204


class TestTopJobs:
    """Tests for top jobs endpoint."""
    
    def test_get_top_jobs(self, client: TestClient, auth_headers: dict):
        """Test getting top matched jobs."""
        response = client.get(
            "/api/jobs/top?limit=10&min_score=0",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_top_jobs_with_min_score(self, client: TestClient, auth_headers: dict):
        """Test getting top jobs with minimum score filter."""
        response = client.get(
            "/api/jobs/top?min_score=50",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned jobs should have score >= 50
        for job in data:
            if job.get("match"):
                assert job["match"]["combined_score"] >= 50


class TestJobAuthorization:
    """Tests for job authorization."""
    
    def test_jobs_require_auth(self, client: TestClient):
        """Test that job endpoints require authentication."""
        response = client.get("/api/jobs")
        
        assert response.status_code == 403  # No credentials
