# Development Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- Ollama with models (gemma3:27b, gemma3:12b)

## Setup

### 1. Clone Repository

```bash
git clone https://github.com/masubi/jobs-agent.git
cd jobs-agent
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 3. Frontend Setup

```bash
cd web
npm install
cd ..
```

### 4. Environment Variables

Create `.env` file:

```bash
# LLM Configuration
LLM_PROVIDER=ollama
LLM_MODEL=ollama/gemma3:27b
OLLAMA_MODEL=gemma3:27b
OLLAMA_FAST_MODEL=gemma3:12b
OLLAMA_BASE_URL=http://localhost:11434

# JWT Configuration
JWT_SECRET_KEY=your-secret-key-here

# Logging
JOB_AGENT_LOG_LEVEL=INFO
```

Generate a secure JWT key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 5. Start Ollama

```bash
ollama serve  # If not running as service
ollama pull gemma3:27b
ollama pull gemma3:12b
```

## Running

### Development Mode

```bash
# Terminal 1: Backend
uvicorn api.main:app --reload --port 8000

# Terminal 2: Frontend
cd web && npm run dev
```

Access:
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/api/docs

### CLI Mode

```bash
# Import profile
python scripts/import_profile_from_pdf.py resume.pdf

# Search jobs
python scripts/run_jobspy_search.py "software engineer" "Seattle"

# Match jobs
python scripts/run_job_matcher.py --llm
```

## Testing

### Backend Tests

```bash
# All tests
pytest tests/ -v
pytest api/tests/ -v

# Specific test file
pytest api/tests/test_auth.py -v

# With coverage
pytest api/tests/ --cov=api --cov-report=html
```

### Frontend Tests

```bash
cd web

# Run tests
npm test

# Run with UI
npm run test:ui

# With coverage
npm run test:coverage
```

### Integration Tests

```bash
# Requires LLM - slower
python tests/test_integration.py
```

## Code Style

### Python

- Follow PEP 8
- Use type hints
- Document functions with docstrings

### TypeScript

- Use strict mode
- Define types for all data
- Use functional components

## Project Structure

```
jobs-agent/
├── api/                    # FastAPI backend
│   ├── auth/               # Authentication
│   ├── models/             # Pydantic models
│   ├── routes/             # API endpoints
│   ├── services/           # Business logic
│   └── tests/              # API tests
├── docs/                   # Documentation
├── job_agent_coordinator/  # Core tools
│   ├── sub_agents/         # Matching logic
│   └── tools/              # Job operations
├── scripts/                # CLI tools
├── tests/                  # Core tests
├── web/                    # React frontend
│   ├── src/
│   │   ├── api/            # API client
│   │   ├── components/     # UI components
│   │   ├── contexts/       # React contexts
│   │   ├── pages/          # Page components
│   │   ├── tests/          # Frontend tests
│   │   └── types/          # TypeScript types
│   └── ...
└── .job_cache/             # Data storage (gitignored)
```

## Adding Features

### New API Endpoint

1. Define Pydantic models in `api/models/`
2. Add service method in `api/services/`
3. Create route in `api/routes/`
4. Add tests in `api/tests/`

### New Frontend Page

1. Define types in `web/src/types/`
2. Add API function in `web/src/api/`
3. Create page component in `web/src/pages/`
4. Add route in `web/src/App.tsx`
5. Add tests in `web/src/tests/`

## Debugging

### Backend

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Frontend

Use React DevTools and Network tab in browser DevTools.

### LLM Issues

```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Test generation
curl http://localhost:11434/api/generate -d '{"model": "gemma3:12b", "prompt": "Hello"}'
```

## Common Issues

### "JWT_SECRET_KEY not set"

Set the environment variable in `.env` or export it:
```bash
export JWT_SECRET_KEY=your-secret-key
```

### "Ollama connection refused"

Start Ollama:
```bash
ollama serve
```

### "Module not found"

Activate virtual environment:
```bash
source .venv/bin/activate
```

### Frontend proxy not working

Check that backend is running on port 8000.
