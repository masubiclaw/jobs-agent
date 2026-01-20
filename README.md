# Job Search Agent

A multi-agent job search and matching system built with Google ADK. Features intelligent job searching, profile matching, web scraping, and local caching with vector search.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/masubi/jobs-agent.git
cd jobs-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Setup Ollama (local LLM)
# Download from https://ollama.ai/ then:
ollama pull gemma3:27b
ollama pull gemma3:12b

# Create .env file
cat > .env << 'EOF'
LLM_PROVIDER=ollama
LLM_MODEL=ollama/gemma3:27b
OLLAMA_MODEL=gemma3:27b
OLLAMA_FAST_MODEL=gemma3:12b
OLLAMA_BASE_URL=http://localhost:11434
JOB_AGENT_LOG_LEVEL=INFO
EOF

# Run the agent
adk web
# Open http://localhost:8000
```

## Features

- 🔍 **Job Search** - Search across Indeed, LinkedIn, Glassdoor, ZipRecruiter via JobSpy
- 🎯 **Job Matching** - Analyze jobs against your profile with skill gap analysis (fetches job descriptions automatically)
- 👤 **Profile Management** - Store skills, preferences, and job search criteria
- 💾 **Smart Caching** - Local persistence with ChromaDB vector search (600+ jobs pre-cached)
- 🕷️ **Web Scraping** - Scrape job boards with URL extraction for direct job links
- 📊 **Match Aggregation** - Ranked summaries of all analyzed jobs in TOON format

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    job_agent_coordinator                         │
│                     (Main Orchestrator)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐                                           │
│  │ job_searcher     │  ← Agent (uses LLM for search planning)   │
│  │ - JobSpy search  │                                           │
│  │ - Multi-platform │                                           │
│  └────────┬─────────┘                                           │
│           │                                                      │
│  ┌────────┴─────────────────────────────────────────────┐       │
│  │                      Tools                            │       │
│  │  • analyze_job_match  (fast, algorithmic matching)   │       │
│  │  • JobSpy search      • Profile Store                │       │
│  │  • Job Cache          • Job Links Scraper            │       │
│  │  • Match Aggregation  • Prompt Parser                │       │
│  └───────────────────────────────────────────────────────┘       │
│                          │                                       │
│  ┌───────────────────────┴───────────────────┐                  │
│  │              Local Storage                 │                  │
│  │  .job_cache/                               │                  │
│  │  ├── jobs.json      (664+ job listings)   │                  │
│  │  ├── matches.json   (cached match results)│                  │
│  │  ├── profiles.json  (user profiles)       │                  │
│  │  ├── exclusions.json                      │                  │
│  │  └── chroma/        (vector embeddings)   │                  │
│  └───────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

**Note:** Job matching is a direct tool (not an agent) for speed - it processes 664 jobs in ~1 second!

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) (recommended for local LLM)
- Or Google AI API key for Gemini

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/masubi/jobs-agent.git
cd jobs-agent
```

### 2. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
# Using pip
pip install -r requirements.txt

# Or using uv (faster)
uv pip install -r requirements.txt
```

### 4. Install Playwright (for JS-rendered job sites)

```bash
playwright install chromium
```

### 5. Set up Ollama (recommended)

```bash
# Install Ollama from https://ollama.ai/

# Pull recommended models
ollama pull gemma3:27b     # Main model (better quality)
ollama pull gemma3:12b     # Fast model (for extraction)

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

### 6. Configure environment

Create a `.env` file:

```bash
# LLM Configuration
LLM_PROVIDER=ollama
LLM_MODEL=ollama/gemma3:27b
OLLAMA_MODEL=gemma3:27b
OLLAMA_FAST_MODEL=gemma3:12b
OLLAMA_BASE_URL=http://localhost:11434

# Optional: Use Google AI instead
# LLM_PROVIDER=google
# LLM_MODEL=gemini-2.0-flash
# GOOGLE_API_KEY=your_api_key_here

# Logging
JOB_AGENT_LOG_LEVEL=INFO
VERBOSE_MODEL_LOGGING=false

# Optional: Pre-seed initial prompt
INITIAL_PROMPT="search seattle for software engineering jobs"
```

## Running the Agent

### Web UI (Interactive)
```bash
# Start the web UI
adk web

# Open http://localhost:8000 in your browser
```

### CLI Scripts (Batch Operations)

```bash
# Show job cache statistics
python scripts/show_cache_stats.py
python scripts/show_cache_stats.py --matches    # Include match stats

# Run job matching on all cached jobs
python scripts/run_job_matcher.py               # Match all jobs (uses cache)
python scripts/run_job_matcher.py --limit 50    # Match first 50 jobs
python scripts/run_job_matcher.py --min-score 60  # Show only 60%+ matches
python scripts/run_job_matcher.py -v            # Verbose output

# Rebuild ALL matches from scratch (when profile changes)
python scripts/rebuild_all_matches.py           # Rebuild all matches
python scripts/rebuild_all_matches.py --fetch   # Fetch job descriptions from URLs (slower but more accurate)
python scripts/rebuild_all_matches.py --limit 100  # Rebuild first 100 only

# Run job scraper
python scripts/run_job_scraper.py               # Show available sources
python scripts/run_job_scraper.py --source Boeing  # Scrape single source
python scripts/run_job_scraper.py --category Aerospace  # Scrape category
python scripts/run_job_scraper.py --all         # Scrape ALL (10-20 min!)
```

## Example Commands

### Job Search
```
"Find software engineer jobs in Seattle"
"Search for data scientist positions in San Francisco"
"Look for remote Python developer jobs"
"Find ML Engineer jobs excluding Amazon"
```

### Profile Management
```
"Create profile for John"
"Add skill: Python (advanced)"
"Add skill: Machine Learning (intermediate)"
"Set preferences: ML Engineer, $180k+, Seattle, remote preferred"
"Show my profile"
```

### Job Matching
```
"Analyze this job: [paste job description]"
"Does this job match my profile?"
"Match score for Senior Engineer at Google"
```

### Cache & Aggregation
```
"Show cache stats"
"Find ML jobs in cache"
"Summarize my matches"
"Show best matches (score > 70)"
"List all matches"
```

### Web Scraping (use sparingly - slow!)
```
"Show job sources"                    # Fast - lists available sources
"Scrape Boeing jobs"                  # ~30 seconds
"Scrape Aerospace category"           # ~3 minutes
```

## Project Structure

```
jobs-agent/
├── job_agent_coordinator/
│   ├── __init__.py
│   ├── agent.py                    # Main coordinator agent
│   ├── prompt.py                   # Coordinator instructions
│   ├── sub_agents/
│   │   ├── job_searcher/           # JobSpy search agent
│   │   │   ├── agent.py
│   │   │   └── prompt.py
│   │   └── job_matcher/            # Job matching tool (algorithmic)
│   │       └── agent.py            # analyze_job_match function
│   └── tools/
│       ├── jobspy_tools.py         # JobSpy integration
│       ├── job_cache.py            # Job + match caching
│       ├── local_cache.py          # Exclusions cache
│       ├── profile_store.py        # User profiles
│       ├── job_links_scraper.py    # Web scraper
│       └── prompt_to_search_params.py
├── scripts/
│   ├── run_job_matcher.py          # Batch job matching
│   ├── rebuild_all_matches.py      # Rebuild matches from scratch
│   ├── run_job_scraper.py          # Batch job scraping
│   └── show_cache_stats.py         # Cache statistics
├── tests/
│   ├── test_jobspy.py
│   └── test_job_scraper.py
├── JobOpeningsLink.md              # Curated job board URLs
├── .env                            # Environment config
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Data Storage

All data is stored locally in `.job_cache/`:

| File | Purpose |
|------|---------|
| `jobs.json` | Cached job listings (~600+) |
| `matches.json` | Job match analysis results |
| `profiles.json` | User profiles |
| `exclusions.json` | Excluded companies list |
| `chroma/` | Vector embeddings for semantic search |

## Tips

1. **Use cache first** - The agent caches 600+ jobs. Check cache before scraping!
2. **Create a profile** - Matching works best with a complete profile
3. **Be specific** - Include location, role type, and any exclusions
4. **Scrape selectively** - Full scrape takes 10-20 minutes; use single source scraping

## Troubleshooting

### Ollama connection issues
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve
```

### Missing dependencies
```bash
pip install chromadb python-jobspy playwright
playwright install chromium
```

### Permission errors with .env
```bash
chmod 644 .env
```

## License

Apache-2.0
