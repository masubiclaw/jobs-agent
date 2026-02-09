# Backend Guide

## Technology Stack

- **FastAPI** - Web framework
- **Pydantic** - Data validation
- **python-jose** - JWT handling
- **bcrypt** - Password hashing
- **uvicorn** - ASGI server

## Project Structure

```
api/
├── __init__.py
├── main.py                     # FastAPI application
├── auth/                       # Authentication module
│   ├── __init__.py
│   ├── jwt.py                  # JWT token handling
│   ├── password.py             # Password hashing
│   └── user_store.py           # User storage
├── models/                     # Pydantic models
│   ├── __init__.py
│   ├── user.py                 # User models
│   ├── profile.py              # Profile models
│   ├── job.py                  # Job models
│   └── document.py             # Document models
├── routes/                     # API routes
│   ├── __init__.py
│   ├── auth.py                 # Auth endpoints
│   ├── profiles.py             # Profile endpoints
│   ├── jobs.py                 # Job endpoints
│   ├── documents.py            # Document endpoints
│   └── admin.py                # Admin endpoints
├── services/                   # Business logic
│   ├── __init__.py
│   ├── profile_service.py      # Profile operations
│   ├── job_service.py          # Job operations
│   ├── document_service.py     # Document generation
│   └── admin_service.py        # Admin operations
└── tests/                      # API tests
    ├── conftest.py             # Pytest fixtures
    ├── test_auth.py
    ├── test_profiles.py
    ├── test_jobs.py
    ├── test_admin.py
    └── test_documents.py
```

## Authentication

### JWT Configuration

```python
# api/auth/jwt.py
SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # Required
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
```

### Password Hashing

Uses bcrypt directly (passwords over 72 bytes are truncated per bcrypt limits):

```python
from api.auth import hash_password, verify_password

hashed = hash_password("plaintext")
is_valid = verify_password("plaintext", hashed)
```

### User Storage

Users stored in `.job_cache/users.toon`:

```python
from api.auth import get_user_store

store = get_user_store()
user = store.create(email, password, name)
user = store.authenticate(email, password)
```

## Services

### ProfileService

Multi-user profile management:

```python
from api.services import ProfileService

service = ProfileService()
profiles = service.list_profiles(user_id)
profile = service.create_profile(user_id, name, email, phone, location)
profile = service.update_profile(profile_id, user_id, **kwargs)
```

### JobService

Job management with user-specific metadata:

```python
from api.services import JobService

service = JobService()
jobs = service.list_jobs(user_id, page=1, page_size=20)
job = service.create_job(user_id, job_data)
job = service.update_job(job_id, user_id, status="completed")
```

### DocumentService

Document generation wrapping existing tools:

```python
from api.services import DocumentService

service = DocumentService()
doc = service.generate_document(user_id, job_id, profile_id, DocumentType.RESUME)
pdf_path = service.get_document_pdf(document_id, user_id)
```

### AdminService

System management operations:

```python
from api.services import AdminService

service = AdminService()
stats = service.get_stats()
service.run_scraper(categories="Tech")
service.run_matcher(llm_pass=True)
```

## Dependencies

FastAPI dependencies for authentication:

```python
from api.auth import get_current_user, get_current_admin_user

@router.get("/protected")
async def protected_route(user: UserResponse = Depends(get_current_user)):
    return {"user": user.id}

@router.get("/admin-only")
async def admin_route(user: UserResponse = Depends(get_current_admin_user)):
    return {"admin": user.id}
```

## Running

```bash
# Development with auto-reload
uvicorn api.main:app --reload --port 8000

# Production
uvicorn api.main:app --host 0.0.0.0 --port 8000

# With multiple workers
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Auto-generated documentation available at:
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- OpenAPI JSON: `http://localhost:8000/api/openapi.json`

## Testing

```bash
# Run all API tests
pytest api/tests/ -v

# Run specific test file
pytest api/tests/test_auth.py -v

# Run with coverage
pytest api/tests/ --cov=api --cov-report=html
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| JWT_SECRET_KEY | Yes | - | Secret key for JWT signing |
| LLM_PROVIDER | No | ollama | LLM provider |
| OLLAMA_MODEL | No | gemma3:27b | Model for generation |
| OLLAMA_FAST_MODEL | No | gemma3:12b | Fast model for extraction |
