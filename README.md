# Job Search Agent

A job search pipeline with two-pass matching (fast keyword + LLM holistic analysis).

## Two Ways to Use

| Method | Best For | How |
|--------|----------|-----|
| **CLI Scripts** | Batch processing, automation | `python scripts/run_job_matcher.py` |
| **Chat Agent** | Interactive queries, exploration | `adk web` → http://localhost:8000 |

Both methods use the same underlying tools and cache. You can mix and match!

```
┌─────────────────┐     ┌─────────────────┐
│  CLI Scripts    │     │   Chat Agent    │
│  (scripts/)     │     │   (adk web)     │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
         ┌─────────────────────┐
         │       Tools         │  ← Single source of truth
         │  (tools/*.py)       │
         └──────────┬──────────┘
                    ▼
         ┌─────────────────────┐
         │   .job_cache/       │  ← Shared storage
         │  jobs.toon          │
         │  matches.toon       │
         │  profiles/*.toon    │
         └─────────────────────┘
```

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         JOB SEARCH PIPELINE                              │
│                    (CLI Scripts OR Chat Agent)                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Step 1              Step 2              Step 3              Step 4      │
│  ┌──────────┐        ┌──────────┐        ┌──────────┐        ┌────────┐ │
│  │ Import   │        │ Get      │        │ Match    │        │ Query  │ │
│  │ Profile  │───────▶│ Jobs     │───────▶│ Jobs     │───────▶│Results │ │
│  │          │        │          │        │ (2-pass) │        │        │ │
│  └──────────┘        └──────────┘        └──────────┘        └────────┘ │
│       │                   │                   │                   │      │
│  CLI: import_      CLI: run_jobspy_    CLI: run_job_       CLI: show_   │
│       profile           search              matcher            cache_   │
│       _from_pdf    OR run_job_         OR rebuild_all_     stats       │
│                        scraper              matches                     │
│       │                   │                   │                   │      │
│  Chat: "create     Chat: "search       Chat: "analyze      Chat: "show  │
│   profile for..."   ML jobs in..."      this job..."        matches"   │
│       │                   │                   │                   │      │
│       ▼                   ▼                   ▼                   ▼      │
│  profiles/*.toon     jobs.toon          matches.toon         Answers    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Important:** Profile must be imported before running matches (matching uses your skills/preferences).

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
```

## Running the Pipeline

### Step 1: Import Your Profile (Required First!)

```bash
# Import from PDF resume - extracts skills, experience, preferences
python scripts/import_profile_from_pdf.py your_resume.pdf

# Preview without saving
python scripts/import_profile_from_pdf.py your_resume.pdf --dry-run
```

### Step 2: Get Jobs (Two Options)

**Option A: Search Job Aggregators (JobSpy)**
```bash
# Search Indeed, LinkedIn, Glassdoor, ZipRecruiter
python scripts/run_jobspy_search.py "software engineer" "Seattle, WA"
python scripts/run_jobspy_search.py "ML engineer" "Remote" --results 50
python scripts/run_jobspy_search.py "data scientist" "Bay Area" --exclude "Amazon,Meta"
```

**Option B: Scrape Company Career Pages**
```bash
# View available sources (from JobOpeningsLink.md)
python scripts/run_job_scraper.py

# Scrape specific company
python scripts/run_job_scraper.py --source Boeing

# Scrape all sources (10-20 minutes, supports checkpoint!)
python scripts/run_job_scraper.py --all

# Resume interrupted scrape
python scripts/run_job_scraper.py --resume

# Check scrape progress
python scripts/run_job_scraper.py --status
```

**Note:** 600+ jobs pre-cached - you may not need to scrape/search.

### Step 3: Match Jobs Against Profile

```bash
# Fast keyword matching (instant, ~0.01s/job)
python scripts/run_job_matcher.py

# Two-pass with LLM analysis (thorough, ~10s/job)
python scripts/run_job_matcher.py --llm

# Resume interrupted LLM matching
python scripts/run_job_matcher.py --llm --resume

# Rebuild all matches (after profile changes)
python scripts/rebuild_all_matches.py --llm
```

### Step 4: Query Results

**Option A: CLI**
```bash
python scripts/show_cache_stats.py --matches
```

**Option B: Chat Agent**
```bash
adk web
# Open http://localhost:8000
```

The chat agent can do everything the scripts can:
- "Search for ML engineer jobs in Seattle" → uses JobSpy
- "Scrape Boeing jobs" → uses web scraper
- "Analyze this job against my profile" → runs matching
- "Show my top matches" → queries cache
- "What skills am I missing for the Anthropic jobs?" → analyzes gaps

**Tip:** Use CLI scripts for batch operations (faster). Use chat for exploration and one-off queries.

## What Gets Cached

All data stored in `.job_cache/` directory:

| File | What's Cached | When Updated |
|------|---------------|--------------|
| `profiles/*.toon` | Your skills, experience, preferences | `import_profile_from_pdf.py` |
| `jobs.toon` | Job listings (title, company, location, description, URL) | `run_job_scraper.py` |
| `matches.toon` | Match scores (keyword_score, llm_score, combined_score) | `run_job_matcher.py` |
| `matching_progress.json` | Checkpoint for resuming LLM matching | Auto-saved every 10 jobs |
| `scraping_progress.json` | Checkpoint for resuming web scraping | Auto-saved per source |
| `chroma/` | Vector embeddings for semantic search | Auto-updated |
| `exclusions.toon` | Companies to exclude from matches | Via agent or manually |

**Pre-cached:** 600+ jobs from tech companies, aerospace, government contractors.

## Two-Pass Matching

```
Pass 1 (Keyword)          Pass 2 (LLM)              Combined
~0.01s/job                ~10s/job                  
                                                    
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ • Skill match   │       │ • Context       │       │ 40% keyword     │
│ • Role match    │  ───▶ │ • Experience    │  ───▶ │ 60% LLM         │
│ • Location      │       │ • Culture fit   │       │ = final score   │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

- **Keyword-only:** Fast, good for initial filtering
- **With LLM:** Thorough, better for final candidates

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) with `gemma3:27b` and `gemma3:12b` models

## Setup

### 1. Clone and create environment

```bash
git clone https://github.com/masubi/jobs-agent.git
cd jobs-agent
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Set up Ollama

```bash
# Install from https://ollama.ai/
ollama pull gemma3:27b
ollama pull gemma3:12b
curl http://localhost:11434/api/tags  # Verify running
```

### 4. Configure environment

```bash
cat > .env << 'EOF'
LLM_PROVIDER=ollama
LLM_MODEL=ollama/gemma3:27b
OLLAMA_MODEL=gemma3:27b
OLLAMA_FAST_MODEL=gemma3:12b
OLLAMA_BASE_URL=http://localhost:11434
JOB_AGENT_LOG_LEVEL=INFO
EOF
```

### 5. Use Fine-Tuned Model (Optional)

A fine-tuned model is available for improved job matching accuracy. It was trained on labeled job-candidate matches using LoRA fine-tuning with MLX.

```bash
# Enable fine-tuned model (requires Apple Silicon)
export USE_MLX_MODEL=true
export MLX_MODEL_PATH=models/job-matcher-lora/fused_model

# Run job matcher with fine-tuned model
python scripts/run_job_matcher.py --llm
```

The fine-tuned model uses MLX for inference instead of Ollama. Training data is stored in `data/` and the model weights are in `models/job-matcher-lora/`.

## CLI Script Reference

```bash
# Profile
python scripts/import_profile_from_pdf.py resume.pdf    # Import profile
python scripts/import_profile_from_pdf.py resume.pdf --dry-run

# JobSpy Search (Indeed, LinkedIn, Glassdoor, ZipRecruiter)
python scripts/run_jobspy_search.py "engineer" "Seattle"           # Basic search
python scripts/run_jobspy_search.py "ML engineer" "Remote" -n 50   # 50 results
python scripts/run_jobspy_search.py "manager" "NYC" --sites indeed,glassdoor
python scripts/run_jobspy_search.py "dev" "SF" --exclude "Amazon,Meta"

# Web Scraping (company career pages from JobOpeningsLink.md)
python scripts/run_job_scraper.py                       # List sources
python scripts/run_job_scraper.py --source Boeing       # Single source
python scripts/run_job_scraper.py --all                 # All sources
python scripts/run_job_scraper.py --resume              # Resume interrupted
python scripts/run_job_scraper.py --status              # Check progress

# Matching
python scripts/run_job_matcher.py                       # Keyword only
python scripts/run_job_matcher.py --llm                 # With LLM
python scripts/run_job_matcher.py --llm --resume        # Resume
python scripts/run_job_matcher.py --limit 50            # Limit jobs

# Rebuild (clears matches first)
python scripts/rebuild_all_matches.py                   # Keyword only
python scripts/rebuild_all_matches.py --llm             # With LLM
python scripts/rebuild_all_matches.py --llm --resume    # Resume

# Stats
python scripts/show_cache_stats.py                      # Job stats
python scripts/show_cache_stats.py --matches            # Include matches
```

## Project Structure

```
jobs-agent/
├── scripts/                          # CLI pipeline scripts
│   ├── import_profile_from_pdf.py    # Step 1: Import profile
│   ├── run_jobspy_search.py          # Step 2a: Search aggregators
│   ├── run_job_scraper.py            # Step 2b: Scrape career pages
│   ├── run_job_matcher.py            # Step 3: Match jobs
│   ├── rebuild_all_matches.py        # Rebuild matches
│   └── show_cache_stats.py           # View cache stats
├── job_agent_coordinator/            # Agent code
│   ├── agent.py                      # Chat agent (queries cache)
│   ├── sub_agents/job_matcher/       # Two-pass matching logic
│   └── tools/                        # Scraping, caching tools
├── .job_cache/                       # Cached data (gitignored)
│   ├── profiles/*.toon               # User profiles
│   ├── jobs.toon                     # Job listings
│   ├── matches.toon                  # Match results
│   └── chroma/                       # Vector embeddings
├── JobOpeningsLink.md                # Job source URLs
└── tests/                            # Unit tests
```

## Troubleshooting

### Profile not imported
```bash
# Matching requires a profile - import first
python scripts/import_profile_from_pdf.py your_resume.pdf
```

### Ollama not running
```bash
curl http://localhost:11434/api/tags  # Check status
ollama serve                          # Start server
```

### LLM matching interrupted
```bash
# Resume from checkpoint (progress saved every 10 jobs)
python scripts/run_job_matcher.py --llm --resume
```

### Matches seem wrong after profile change
```bash
# Rebuild all matches with new profile
python scripts/rebuild_all_matches.py --llm
```

## Running Tests

```bash
pytest tests/ -v
pytest tests/test_job_matcher.py -v
```

## License

Apache-2.0
