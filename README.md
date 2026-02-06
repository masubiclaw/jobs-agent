# Jobs Agent

AI-powered job search and resume builder with two-pass matching and multi-user web interface.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- [Ollama](https://ollama.ai/) with `gemma3:27b` and `gemma3:12b` models

### Installation

```bash
# Clone and setup
git clone https://github.com/masubi/jobs-agent.git
cd jobs-agent

# Backend setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Setup Ollama
ollama pull gemma3:27b
ollama pull gemma3:12b

# Create .env file
cat > .env << 'EOF'
LLM_PROVIDER=ollama
LLM_MODEL=ollama/gemma3:27b
OLLAMA_MODEL=gemma3:27b
OLLAMA_FAST_MODEL=gemma3:12b
OLLAMA_API_BASE=http://localhost:11434
JWT_SECRET_KEY=your-secure-secret-key-change-this
EOF

# Frontend setup
cd web
npm install
cd ..
```

### Running

```bash
# Terminal 1: Backend API
uvicorn api.main:app --reload --port 8000

# Terminal 2: Frontend
cd web && npm run dev

# Open http://localhost:3000
```

### CLI Mode (Alternative)

```bash
# Profile Management
python scripts/import_profile_from_pdf.py your_resume.pdf    # Import from PDF
python scripts/add_profile.py --list                          # List profiles

# Job Searching
python scripts/run_jobspy_search.py "software engineer manager" "Seattle, WA"  # Search aggregators
python scripts/run_jobspy_search.py "ML engineer" "Remote" -n 50       # More results
python scripts/run_job_scraper.py --source Boeing                      # Scrape career page
python scripts/run_job_scraper.py --all                                # Scrape all sources

# Job Matching
python scripts/run_job_matcher.py              # Keyword matching (fast)
python scripts/run_job_matcher.py --llm        # LLM analysis (thorough)
python scripts/rebuild_all_matches.py --llm    # Rebuild all matches

# View Results
python scripts/show_top_matches.py             # Show matches >= 70%
python scripts/show_top_matches.py --min 70    # Custom threshold
python scripts/show_cache_stats.py --matches   # Cache statistics

# Document Generation
python scripts/generate_documents.py --list                    # List jobs with scores
python scripts/generate_documents.py --job-id <ID>             # Single job (both docs)
python scripts/generate_documents.py --top 5 --min-score 70    # Batch top matches

# Quick Apply from URL(s)
python scripts/generate_from_url.py "https://linkedin.com/jobs/view/123"  # Single URL
python scripts/generate_from_url.py URL1 URL2 URL3            # Multiple URLs (both docs)
python scripts/generate_from_url.py URL --dry-run              # Preview extraction only

# Maintenance
python scripts/clean_dead_jobs.py --check-urls --older-than 14 --dry-run  # Preview cleanup
```

See [docs/cli-reference.md](docs/cli-reference.md) for complete CLI documentation.


## Docker

You may build a containerized version of jobs-agent. This separates the Ollama model in one container, and the jobs agent in a second one.

First, copy `env.template` into `envfile`. Edit this file, it will be projected into the container. Then run docker to build and bring the containers up.

```
$ cd jobs-agent
$ cp env.template envfile
$ vim envfile
$ mkdir generated_documents
$ docker build -t jobs-agent .
$ docker compose up
```

After that, you will need to pull the gemma models you've set in the env file since we're running the default image of Ollama.

```
$ docker exec -it ollama ollama pull gemma3:27b
$ docker exec -it ollama ollama pull gemma3:12b
```

Head your browser to http://localhost:8000 or use the CLI scripts right on the container.

```
$ docker exec -it jobs-agent /bin/bash
$ python3 scripts/add_profile.py
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Jobs Agent System                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐        ┌─────────────┐                     │
│  │   Web UI    │        │  CLI Tools  │                     │
│  │  (React)    │        │  (scripts/) │                     │
│  └──────┬──────┘        └──────┬──────┘                     │
│         │                      │                             │
│         └──────────┬───────────┘                             │
│                    ▼                                         │
│         ┌─────────────────────┐                             │
│         │    FastAPI Backend  │                             │
│         │    (/api)           │                             │
│         └──────────┬──────────┘                             │
│                    ▼                                         │
│         ┌─────────────────────┐                             │
│         │   Core Tools        │                             │
│         │  (job_agent_coord.) │                             │
│         └──────────┬──────────┘                             │
│                    ▼                                         │
│  ┌────────────┬────────────┬────────────┐                   │
│  │ Profiles   │   Jobs     │  Documents │                   │
│  │  (TOON)    │   (TOON)   │   (PDF)    │                   │
│  └────────────┴────────────┴────────────┘                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Documentation

See [docs/](docs/) for detailed documentation:

- [Architecture](docs/architecture.md) - Full system architecture
- [API Reference](docs/api-reference.md) - API endpoint documentation
- [Frontend Guide](docs/frontend.md) - Frontend component details
- [Backend Guide](docs/backend.md) - Backend service details
- [Authentication](docs/authentication.md) - Auth flow and security
- [Data Models](docs/data-models.md) - TOON format and structures
- [Admin Guide](docs/admin-guide.md) - Admin functionality
- [Development](docs/development.md) - Development workflow
- [CLI Reference](docs/cli-reference.md) - CLI script documentation

## Testing

```bash
# Backend tests
pytest tests/ -v
pytest api/tests/ -v

# Frontend tests
cd web && npm test
```

## License

Apache-2.0
