# Admin Guide

## Overview

Admin users have access to system-wide management features including job scraping, searching, matching, and cleanup operations.

## Becoming Admin

The first user to register automatically becomes an admin. Admin status is stored in the user record and cannot be changed through the UI.

## Admin Dashboard

Access: `/admin`

The dashboard shows:
- Total jobs in cache
- Total registered users
- Total match results
- Vector search status
- Jobs by platform breakdown
- Top companies
- Cache statistics

## Operations

### Job Scraper

Scrapes job listings from company career pages defined in `JobOpeningsLink.md`.

**UI**: Admin Dashboard > Run Scraper

**Options**:
- Categories: Comma-separated list (e.g., "Tech,Aerospace")
- Max Sources: Limit number of sources (0 for all)

**API**:
```http
POST /api/admin/scraper/run?categories=Tech&max_sources=10
```

The scraper runs in the background. Check stats for progress.

### Job Searcher

Searches job aggregators (Indeed, LinkedIn, Glassdoor, ZipRecruiter).

**UI**: Admin Dashboard > Run Searcher

**Options**:
- Search Term: Required (e.g., "software engineer")
- Location: Optional (e.g., "Seattle, WA")
- Sites: Comma-separated (default: indeed,linkedin)
- Results Wanted: Number of results per site

**API**:
```http
POST /api/admin/searcher/run?search_term=software+engineer&location=Seattle
```

### Job Matcher

Analyzes cached jobs against user profiles.

**UI**: Admin Dashboard > Run Matcher

**Options**:
- Max Jobs: Limit jobs to match
- LLM Pass: Enable detailed LLM analysis (slower but more accurate)

**API**:
```http
POST /api/admin/matcher/run?llm_pass=true&limit=100
```

**Two-Pass Matching**:
1. Keyword pass: ~0.01s/job, checks skills, roles, location
2. LLM pass: ~10s/job, contextual understanding, experience alignment

Combined score = 40% keyword + 60% LLM

### Cleanup

Removes old or dead job listings.

**UI**: Admin Dashboard > Run Cleanup

**Options**:
- Days Old: Remove jobs cached more than N days ago
- Check URLs: Validate URLs are still accessible (slower)

**API**:
```http
POST /api/admin/cleanup?days_old=30&check_urls=false
```

## Job Management

Access: `/admin/jobs`

View all jobs in the system with:
- Title, company, location
- Platform source
- Cache date
- Direct link to original posting
- Delete action

## User Management

Access: `/admin/users` (API only)

List all registered users with:
- ID, email, name
- Admin status
- Created date

## Background Tasks

All admin operations run as background tasks to avoid timeout issues:

1. Request starts the task
2. API returns immediately with "started" status
3. Task runs in background
4. Check stats endpoint for progress/results

## Best Practices

1. **Run scraper periodically** to keep job cache fresh
2. **Clean up weekly** to remove expired jobs
3. **Run matcher after** profile changes or new job imports
4. **Use URL validation sparingly** - it's slow and may trigger rate limits

## CLI Equivalents

All admin operations are also available via CLI:

```bash
# Scraper
python scripts/run_job_scraper.py --all

# Searcher
python scripts/run_jobspy_search.py "software engineer" "Seattle"

# Matcher
python scripts/run_job_matcher.py --llm

# Cleanup
python scripts/clean_dead_jobs.py --older-than 30
```

## Monitoring

Check system health:

```bash
# Cache stats
python scripts/show_cache_stats.py --matches

# Match results
python scripts/show_top_matches.py --min 50
```

Or use the Admin Dashboard to view stats in real-time.
