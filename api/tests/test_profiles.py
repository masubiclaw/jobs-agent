"""Tests for profile management endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestProfileCRUD:
    """Tests for profile CRUD operations."""
    
    def test_create_profile(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test creating a profile."""
        response = client.post(
            "/api/profiles",
            json=test_profile_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == test_profile_data["name"]
        assert data["email"] == test_profile_data["email"]
        assert data["location"] == test_profile_data["location"]
        assert "id" in data
    
    def test_list_profiles(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test listing profiles."""
        # Create a profile first
        client.post("/api/profiles", json=test_profile_data, headers=auth_headers)
        
        response = client.get("/api/profiles", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_get_profile(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test getting a specific profile."""
        # Create profile
        create_response = client.post(
            "/api/profiles",
            json=test_profile_data,
            headers=auth_headers
        )
        profile_id = create_response.json()["id"]
        
        # Get profile
        response = client.get(f"/api/profiles/{profile_id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == profile_id
        assert data["name"] == test_profile_data["name"]
    
    def test_get_nonexistent_profile(self, client: TestClient, auth_headers: dict):
        """Test getting a nonexistent profile returns 404."""
        response = client.get("/api/profiles/nonexistent", headers=auth_headers)
        
        assert response.status_code == 404
    
    def test_update_profile(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test updating a profile."""
        # Create profile
        create_response = client.post(
            "/api/profiles",
            json=test_profile_data,
            headers=auth_headers
        )
        profile_id = create_response.json()["id"]
        
        # Update profile
        response = client.put(
            f"/api/profiles/{profile_id}",
            json={"name": "Updated Name", "location": "San Francisco, CA"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["location"] == "San Francisco, CA"
    
    def test_delete_profile(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test deleting a profile."""
        # Create profile
        create_response = client.post(
            "/api/profiles",
            json={**test_profile_data, "name": "To Delete"},
            headers=auth_headers
        )
        profile_id = create_response.json()["id"]
        
        # Delete profile
        response = client.delete(f"/api/profiles/{profile_id}", headers=auth_headers)
        
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(f"/api/profiles/{profile_id}", headers=auth_headers)
        assert get_response.status_code == 404


class TestProfileActivation:
    """Tests for profile activation."""
    
    def test_activate_profile(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test activating a profile."""
        # Create first profile
        create1 = client.post(
            "/api/profiles",
            json={**test_profile_data, "name": "Profile 1"},
            headers=auth_headers
        )
        profile1_id = create1.json()["id"]
        
        # Create second profile
        create2 = client.post(
            "/api/profiles",
            json={**test_profile_data, "name": "Profile 2"},
            headers=auth_headers
        )
        profile2_id = create2.json()["id"]
        
        # Activate second profile
        response = client.post(
            f"/api/profiles/{profile2_id}/activate",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] == True


class TestProfileSkillsAndExperience:
    """Tests for profile skills and experience updates."""
    
    def test_update_skills(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test updating profile skills."""
        # Create profile
        create_response = client.post(
            "/api/profiles",
            json=test_profile_data,
            headers=auth_headers
        )
        profile_id = create_response.json()["id"]
        
        # Update with skills
        skills = [
            {"name": "Python", "level": "expert"},
            {"name": "JavaScript", "level": "advanced"},
            {"name": "Machine Learning", "level": "intermediate"}
        ]
        
        response = client.put(
            f"/api/profiles/{profile_id}",
            json={"skills": skills},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["skills"]) == 3
        assert data["skills"][0]["name"] == "Python"
    
    def test_update_preferences(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test updating profile preferences."""
        # Create profile
        create_response = client.post(
            "/api/profiles",
            json=test_profile_data,
            headers=auth_headers
        )
        profile_id = create_response.json()["id"]
        
        # Update preferences
        preferences = {
            "target_roles": ["Software Engineer", "Backend Developer"],
            "target_locations": ["Seattle", "Remote"],
            "remote_preference": "remote",
            "salary_min": 150000,
            "salary_max": 200000,
            "excluded_companies": ["BadCorp", "WorstCompany"]
        }
        
        response = client.put(
            f"/api/profiles/{profile_id}",
            json={"preferences": preferences},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["preferences"]["target_roles"] == preferences["target_roles"]
        assert data["preferences"]["salary_min"] == 150000


class TestProfileAuthorization:
    """Tests for profile authorization."""
    
    def test_cannot_access_other_user_profile(self, client: TestClient):
        """Test that users cannot access other users' profiles."""
        # Create first user and profile
        user1_data = {
            "email": "user1@example.com",
            "password": "password123",
            "name": "User One"
        }
        client.post("/api/auth/register", json=user1_data)
        login1 = client.post("/api/auth/login", json={
            "email": user1_data["email"],
            "password": user1_data["password"]
        })
        token1 = login1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        # Create profile for user 1
        profile_response = client.post(
            "/api/profiles",
            json={"name": "User1 Profile", "location": "Seattle"},
            headers=headers1
        )
        profile_id = profile_response.json()["id"]
        
        # Create second user
        user2_data = {
            "email": "user2@example.com",
            "password": "password123",
            "name": "User Two"
        }
        client.post("/api/auth/register", json=user2_data)
        login2 = client.post("/api/auth/login", json={
            "email": user2_data["email"],
            "password": user2_data["password"]
        })
        token2 = login2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        # User 2 should not see user 1's profile
        response = client.get(f"/api/profiles/{profile_id}", headers=headers2)
        
        # Should return 404 (not found for this user)
        assert response.status_code == 404
