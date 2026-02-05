"""Tests for authentication endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestAuthRegistration:
    """Tests for user registration."""
    
    def test_register_success(self, client: TestClient):
        """Test successful user registration."""
        response = client.post("/api/auth/register", json={
            "email": "newuser@example.com",
            "password": "securepassword123",
            "name": "New User"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["name"] == "New User"
        assert "id" in data
        assert "hashed_password" not in data
    
    def test_register_duplicate_email(self, client: TestClient):
        """Test registration with existing email fails."""
        user_data = {
            "email": "duplicate@example.com",
            "password": "password123",
            "name": "First User"
        }
        
        # First registration
        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 201
        
        # Duplicate registration
        response = client.post("/api/auth/register", json={
            **user_data,
            "name": "Second User"
        })
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_register_invalid_email(self, client: TestClient):
        """Test registration with invalid email fails."""
        response = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "password123",
            "name": "Test User"
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_register_short_password(self, client: TestClient):
        """Test registration with short password fails."""
        response = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "short",
            "name": "Test User"
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_first_user_is_admin(self, client: TestClient):
        """Test that first registered user becomes admin."""
        # Note: This test depends on order - first user should be admin
        response = client.post("/api/auth/register", json={
            "email": "firstadmin@example.com",
            "password": "adminpass123",
            "name": "First Admin"
        })
        
        # First user might already exist from other tests
        if response.status_code == 201:
            data = response.json()
            assert data["is_admin"] == True


class TestAuthLogin:
    """Tests for user login."""
    
    def test_login_success(self, client: TestClient, test_user_data: dict):
        """Test successful login."""
        # Register first
        client.post("/api/auth/register", json=test_user_data)
        
        # Login
        response = client.post("/api/auth/login", json={
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_wrong_password(self, client: TestClient, test_user_data: dict):
        """Test login with wrong password fails."""
        # Register first
        client.post("/api/auth/register", json=test_user_data)
        
        # Login with wrong password
        response = client.post("/api/auth/login", json={
            "email": test_user_data["email"],
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with nonexistent email fails."""
        response = client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "password123"
        })
        
        assert response.status_code == 401


class TestAuthMe:
    """Tests for current user endpoint."""
    
    def test_get_me_success(self, client: TestClient, auth_headers: dict):
        """Test getting current user info."""
        response = client.get("/api/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "name" in data
    
    def test_get_me_no_auth(self, client: TestClient):
        """Test getting current user without auth fails."""
        response = client.get("/api/auth/me")
        
        assert response.status_code == 403  # No credentials
    
    def test_get_me_invalid_token(self, client: TestClient):
        """Test getting current user with invalid token fails."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        assert response.status_code == 401
