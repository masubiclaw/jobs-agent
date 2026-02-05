# CLI Reference

All CLI scripts are in the `scripts/` directory.

## Profile Management

### add_profile.py

Create or list profiles interactively.

```bash
# Interactive mode
python scripts/add_profile.py

# List profiles
python scripts/add_profile.py --list

# Create with arguments
python scripts/add_profile.py --name "John Doe" --email "john@example.com" \
    --skills "python,java,kubernetes" --target-roles "Software Engineer"
```

### import_profile_from_pdf.py

Import profile from PDF resume.

```bash
# Basic import
python scripts/import_profile_from_pdf.py resume.pdf

# Preview without saving
python scripts/import_profile_from_pdf.py resume.pdf --dry-run
```

## Job Searching

### run_jobspy_search.py

Search job aggregators (Indeed, LinkedIn, Glassdoor, ZipRecruiter).

```bash
# Basic search
python scripts/run_jobspy_search.py "software engineer" "Seattle, WA"

# More results
python scripts/run_jobspy_search.py "ML engineer" "Remote" -n 50

# Specific sites
python scripts/run_jobspy_search.py "manager" "NYC" --sites indeed,glassdoor

# Exclude companies
python scripts/run_jobspy_search.py "dev" "SF" --exclude "Amazon,Meta"
```

### run_job_scraper.py

Scrape company career pages from JobOpeningsLink.md.

```bash
# List available sources
python scripts/run_job_scraper.py

# Scrape specific company
python scripts/run_job_scraper.py --source Boeing

# Scrape all sources
python scripts/run_job_scraper.py --all

# Resume interrupted scrape
python scripts/run_job_scraper.py --resume

# Check progress
python scripts/run_job_scraper.py --status
```

## Job Matching

### run_job_matcher.py

Match jobs against profile.

```bash
# Keyword matching only (fast)
python scripts/run_job_matcher.py

# With LLM analysis (thorough)
python scripts/run_job_matcher.py --llm

# Resume interrupted LLM matching
python scripts/run_job_matcher.py --llm --resume

# Limit jobs
python scripts/run_job_matcher.py --limit 50
```

### rebuild_all_matches.py

Clear and rebuild all matches.

```bash
# Keyword only
python scripts/rebuild_all_matches.py

# With LLM
python scripts/rebuild_all_matches.py --llm

# Resume interrupted
python scripts/rebuild_all_matches.py --llm --resume
```

## Results & Stats

### show_top_matches.py

Display top job matches.

```bash
# Default (score >= 70%)
python scripts/show_top_matches.py

# Custom threshold
python scripts/show_top_matches.py --min 50

# Limit results
python scripts/show_top_matches.py --min 60 --limit 20
```

### show_cache_stats.py

Display cache statistics.

```bash
# Job stats
python scripts/show_cache_stats.py

# Include match stats
python scripts/show_cache_stats.py --matches
```

## Document Generation

### generate_documents.py

Generate resume and cover letter PDFs.

```bash
# List jobs with match scores
python scripts/generate_documents.py --list

# Generate for single job
python scripts/generate_documents.py --job-id <JOB_ID> --type resume
python scripts/generate_documents.py --job-id <JOB_ID> --type cover-letter
python scripts/generate_documents.py --job-id <JOB_ID> --type both

# Batch generate for top jobs
python scripts/generate_documents.py --top 5
python scripts/generate_documents.py --top 3 --type resume
python scripts/generate_documents.py --top 5 --min-score 70

# Preview mode
python scripts/generate_documents.py --top 5 --dry-run

# Force regenerate
python scripts/generate_documents.py --top 5 --no-skip-existing

# More iterations
python scripts/generate_documents.py --top 5 --max-critiques 5
```

### generate_from_url.py

Generate documents from any job URL.

```bash
# Generate both
python scripts/generate_from_url.py "https://linkedin.com/jobs/view/123"

# Specific type
python scripts/generate_from_url.py URL --type resume
python scripts/generate_from_url.py URL --type cover-letter

# Preview extracted job
python scripts/generate_from_url.py URL --dry-run

# Don't cache job
python scripts/generate_from_url.py URL --no-cache

# Use specific profile
python scripts/generate_from_url.py URL --profile john_doe
```

## Maintenance

### clean_dead_jobs.py

Remove expired or invalid jobs.

```bash
# Remove jobs with no URLs
python scripts/clean_dead_jobs.py

# Validate URLs
python scripts/clean_dead_jobs.py --check-urls

# Remove old jobs
python scripts/clean_dead_jobs.py --older-than 14

# Combine filters with preview
python scripts/clean_dead_jobs.py --check-urls --older-than 7 --dry-run

# Performance tuning
python scripts/clean_dead_jobs.py --check-urls --threads 20 --timeout 10
```

## Output

- Job cache: `.job_cache/`
- Generated documents: `generated_documents/`
- Logs: Console (configurable via `JOB_AGENT_LOG_LEVEL`)
