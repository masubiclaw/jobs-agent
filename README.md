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
│       profile           search              matcher            top_     │
│       _from_pdf    OR run_job_         OR rebuild_all_     matches     │
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

### Step 1: Create/Import Your Profile (Required First!)

```bash
# Option A: Create profile interactively
python scripts/add_profile.py

# Option B: Create profile via command line
python scripts/add_profile.py --name "John Doe" --email "john@example.com" \
    --skills "python,java,kubernetes" --target-roles "Software Engineer"

# Option C: Import from PDF resume - extracts skills, experience, preferences
python scripts/import_profile_from_pdf.py your_resume.pdf

# List existing profiles
python scripts/add_profile.py --list

# Preview PDF import without saving
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

**Option A: Show Top Matches**
```bash
# Show top matches with links (default: score >= 70%)
python scripts/show_top_matches.py

# Show matches with lower threshold
python scripts/show_top_matches.py --min 50

# Limit results
python scripts/show_top_matches.py --min 60 --limit 20
```

**Option B: Cache Stats**
```bash
python scripts/show_cache_stats.py --matches
```

**Option C: Chat Agent**
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

### Step 5: Generate Resume & Cover Letter (Optional)

Generate tailored PDF documents for your top job matches:

```bash
# List jobs with match scores
python scripts/generate_documents.py --list

# Generate for a single job
python scripts/generate_documents.py --job-id <JOB_ID> --type resume
python scripts/generate_documents.py --job-id <JOB_ID> --type cover-letter
python scripts/generate_documents.py --job-id <JOB_ID> --type both

# Batch generate for top N matched jobs
python scripts/generate_documents.py --top 5                    # Top 5 jobs
python scripts/generate_documents.py --top 3 --type resume      # Only resumes
python scripts/generate_documents.py --top 5 --min-score 70     # Score >= 70%
python scripts/generate_documents.py --top 5 --dry-run          # Preview mode
python scripts/generate_documents.py --top 5 --no-skip-existing # Force regenerate
python scripts/generate_documents.py --top 5 --max-critiques 5  # More iterations
```

**Features:**
- **Fact Verification:** All claims verified against your profile (no hallucination)
- **Iterative Refinement:** LLM generator + critic loop until quality thresholds met (default: 3 iterations, configurable with `--max-critiques`)
- **ATS Optimized:** Keyword matching and formatting for Applicant Tracking Systems
- **Single-Page Validated:** Resumes are validated to fit on exactly one page
- **Batch Generation:** Generate documents for top N jobs with progress tracking
- **Skip Existing:** Automatically skips jobs with existing documents (override with `--no-skip-existing`)
- **Auto-Naming:** Files named `{Company}_{Date}_{resume|coverletter}.pdf`

Output saved to `generated_documents/` directory.

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

Generated documents stored in `generated_documents/`:

| File | Format | When Created |
|------|--------|--------------|
| `{Company}_{Date}_resume.pdf` | Professional 1-page resume | `generate_documents.py --type resume` |
| `{Company}_{Date}_coverletter.pdf` | Tailored cover letter | `generate_documents.py --type cover-letter` |

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
python scripts/add_profile.py                           # Interactive profile creation
python scripts/add_profile.py --list                    # List existing profiles
python scripts/add_profile.py --name "Name" --email "email@example.com"
python scripts/import_profile_from_pdf.py resume.pdf    # Import profile from PDF
python scripts/import_profile_from_pdf.py resume.pdf --dry-run

# JobSpy Search (Indeed, LinkedIn, Glassdoor, ZipRecruiter)
python scripts/run_jobspy_search.py "software engineering manager" "Seattle"           # Basic search
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

# Stats & Results
python scripts/show_top_matches.py                      # Top matches >= 70%
python scripts/show_top_matches.py --min 50             # Matches >= 50%
python scripts/show_top_matches.py --min 60 --limit 20  # Custom threshold/limit
python scripts/show_cache_stats.py                      # Job stats
python scripts/show_cache_stats.py --matches            # Include matches

# Document Generation
python scripts/generate_documents.py --list             # List jobs
python scripts/generate_documents.py --job-id X --type resume
python scripts/generate_documents.py --job-id X --type cover-letter
python scripts/generate_documents.py --job-id X --type both
python scripts/generate_documents.py --top 5            # Batch: top 5 jobs
python scripts/generate_documents.py --top 3 --type resume --min-score 70
python scripts/generate_documents.py --top 5 --dry-run  # Preview mode
python scripts/generate_documents.py --top 5 --no-skip-existing
python scripts/generate_documents.py --top 5 --max-critiques 5  # More iterations
```

## Project Structure

```
jobs-agent/
├── scripts/                          # CLI pipeline scripts
│   ├── add_profile.py                # Step 1a: Create profile interactively
│   ├── import_profile_from_pdf.py    # Step 1b: Import profile from PDF
│   ├── run_jobspy_search.py          # Step 2a: Search aggregators
│   ├── run_job_scraper.py            # Step 2b: Scrape career pages
│   ├── run_job_matcher.py            # Step 3: Match jobs
│   ├── rebuild_all_matches.py        # Rebuild matches
│   ├── show_top_matches.py           # Step 4: View top matches with links
│   ├── show_cache_stats.py           # View cache stats
│   └── generate_documents.py         # Step 5: Generate resume/cover letter
├── job_agent_coordinator/            # Agent code
│   ├── agent.py                      # Chat agent (queries cache)
│   ├── sub_agents/job_matcher/       # Two-pass matching logic
│   └── tools/                        # Scraping, caching, document tools
│       ├── job_cache.py              # Job and match storage
│       ├── profile_store.py          # Profile management
│       ├── document_generator.py     # LLM resume/cover letter generation
│       ├── document_critic.py        # Fact verification & ATS scoring
│       ├── pdf_generator.py          # PDF rendering (single-page validated)
│       └── resume_tools.py           # Document generation orchestration
├── tests/                            # Unit and integration tests
│   ├── test_exclusions.py            # Exclusion list tests
│   ├── test_document_generation.py   # Artifact cleaning tests
│   ├── test_pdf_generation.py        # PDF page count tests
│   └── test_integration.py           # Integration tests
├── .job_cache/                       # Cached data (gitignored)
│   ├── profiles/*.toon               # User profiles
│   ├── jobs.toon                     # Job listings
│   ├── matches.toon                  # Match results
│   └── chroma/                       # Vector embeddings
├── generated_documents/              # Output PDFs (gitignored)
├── models/                           # ML models (gitignored)
├── data/                             # Training data (gitignored)
└── JobOpeningsLink.md                # Job source URLs
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
# Run all fast unit tests
pytest tests/ -v --ignore=tests/test_integration.py

# Run specific test files
pytest tests/test_exclusions.py -v           # Exclusion list tests
pytest tests/test_document_generation.py -v  # Artifact cleaning tests
pytest tests/test_pdf_generation.py -v       # PDF page count tests

# Run integration tests (requires LLM, slower)
python tests/test_integration.py
```

## License

Apache-2.0
