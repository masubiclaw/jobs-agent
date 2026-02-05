# API Reference

Base URL: `http://localhost:8000/api`

## Authentication

All endpoints except `/auth/register` and `/auth/login` require JWT authentication.

Include the token in the Authorization header:
```
Authorization: Bearer <token>
```

### Register

```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123",
  "name": "John Doe"
}
```

Response (201):
```json
{
  "id": "abc123",
  "email": "user@example.com",
  "name": "John Doe",
  "is_admin": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

Note: First registered user becomes admin.

### Login

```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

Response (200):
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### Get Current User

```http
GET /auth/me
Authorization: Bearer <token>
```

Response (200):
```json
{
  "id": "abc123",
  "email": "user@example.com",
  "name": "John Doe",
  "is_admin": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

## Profiles

### List Profiles

```http
GET /profiles
Authorization: Bearer <token>
```

Response (200):
```json
[
  {
    "id": "john_doe",
    "name": "John Doe",
    "location": "Seattle, WA",
    "skills_count": 15,
    "is_active": true
  }
]
```

### Create Profile

```http
POST /profiles
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "555-1234",
  "location": "Seattle, WA"
}
```

### Get Profile

```http
GET /profiles/{profile_id}
Authorization: Bearer <token>
```

### Update Profile

```http
PUT /profiles/{profile_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "John Doe Updated",
  "skills": [
    {"name": "Python", "level": "expert"},
    {"name": "JavaScript", "level": "advanced"}
  ],
  "preferences": {
    "target_roles": ["Software Engineer", "Backend Developer"],
    "remote_preference": "remote",
    "salary_min": 150000,
    "salary_max": 200000
  }
}
```

### Delete Profile

```http
DELETE /profiles/{profile_id}
Authorization: Bearer <token>
```

### Activate Profile

```http
POST /profiles/{profile_id}/activate
Authorization: Bearer <token>
```

## Jobs

### List Jobs

```http
GET /jobs?page=1&page_size=20&status=active&query=engineer
Authorization: Bearer <token>
```

Query parameters:
- `page` (int): Page number (default: 1)
- `page_size` (int): Items per page (default: 20, max: 100)
- `status` (string): Filter by status (active, completed, archived)
- `company` (string): Filter by company name
- `location` (string): Filter by location
- `query` (string): Search in title/description
- `semantic` (bool): Use semantic search (default: false)

Response (200):
```json
{
  "jobs": [...],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

### Get Top Matches

```http
GET /jobs/top?limit=10&min_score=50
Authorization: Bearer <token>
```

### Create Job

```http
POST /jobs
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Software Engineer",
  "company": "Tech Corp",
  "location": "Seattle, WA",
  "description": "...",
  "url": "https://example.com/job"
}
```

Or from URL:
```json
{
  "job_url": "https://linkedin.com/jobs/view/123456"
}
```

Or from plaintext:
```json
{
  "plaintext": "Software Engineer at Tech Corp\nLocation: Seattle\n..."
}
```

### Upload Job PDF

```http
POST /jobs/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <PDF file>
```

### Get Job

```http
GET /jobs/{job_id}
Authorization: Bearer <token>
```

### Update Job

```http
PUT /jobs/{job_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "status": "completed",
  "notes": "Applied on 2024-01-15"
}
```

### Delete Job

```http
DELETE /jobs/{job_id}
Authorization: Bearer <token>
```

## Documents

### Generate Resume

```http
POST /documents/resume
Authorization: Bearer <token>
Content-Type: application/json

{
  "job_id": "abc123",
  "profile_id": "john_doe"  // optional, uses active profile if omitted
}
```

Response (200):
```json
{
  "id": "doc123",
  "job_id": "abc123",
  "profile_id": "john_doe",
  "document_type": "resume",
  "content": "...",
  "pdf_path": "/path/to/resume.pdf",
  "quality_scores": {
    "fact_score": 100,
    "keyword_score": 85,
    "ats_score": 90,
    "length_score": 95,
    "overall_score": 92
  },
  "iterations": 2,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Generate Cover Letter

```http
POST /documents/cover-letter
Authorization: Bearer <token>
Content-Type: application/json

{
  "job_id": "abc123"
}
```

### Generate Package (Both)

```http
POST /documents/package
Authorization: Bearer <token>
Content-Type: application/json

{
  "job_id": "abc123"
}
```

### Download Document

```http
GET /documents/{document_id}/download
Authorization: Bearer <token>
```

Returns PDF file.

## Admin (Admin Only)

### Get System Stats

```http
GET /admin/stats
Authorization: Bearer <token>
```

### Run Scraper

```http
POST /admin/scraper/run?categories=Local,Tech&max_sources=10
Authorization: Bearer <token>
```

### Run Searcher

```http
POST /admin/searcher/run?search_term=software+engineer&location=Seattle
Authorization: Bearer <token>
```

### Run Matcher

```http
POST /admin/matcher/run?llm_pass=false&limit=100
Authorization: Bearer <token>
```

### Run Cleanup

```http
POST /admin/cleanup?days_old=30&check_urls=false
Authorization: Bearer <token>
```

### List All Jobs

```http
GET /admin/jobs?page=1&page_size=50
Authorization: Bearer <token>
```

### Delete Job (Admin)

```http
DELETE /admin/jobs/{job_id}
Authorization: Bearer <token>
```

### List Users

```http
GET /admin/users
Authorization: Bearer <token>
```

## Error Responses

```json
{
  "detail": "Error message here"
}
```

Common status codes:
- 400: Bad Request (validation error)
- 401: Unauthorized (missing/invalid token)
- 403: Forbidden (insufficient permissions)
- 404: Not Found
- 500: Internal Server Error
