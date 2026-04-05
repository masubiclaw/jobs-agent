# Jobs Agent — Product Spec

> Living document. Updated automatically on each session via stop hook.

## Overview

AI-powered job search and resume builder with two-pass matching, multi-user web interface, and automated pipeline.

## Core Requirements

### Job Management
- [x] Browse jobs with pagination, search (FTS5 ranked), and status filters
- [x] Default filter: active jobs only
- [x] "Not Interested" button on Jobs and Top Matches pages (archives job, optimistic UI)
- [x] Add job manually (title + company) or via URL (Playwright + LLM extraction)
- [x] Job data stored in SQLite (migrated from TOON flat file)
- [x] FTS5 search with bm25 ranking — company name matches weighted 10x
- [x] Server-side sorting by date, company, title, score
- [x] Excluded companies filtered from Top Matches (per-user profile preferences)
- [x] Duplicate detection by URL hash; batch dedup by title+company

### Job Matching
- [x] Two-pass matching: keyword (fast) then LLM (thorough, gemma3:27b)
- [x] Keyword pass on all jobs; LLM pass on candidates scoring >= 40%
- [x] Match scores: 80+ strong, 60-79 good, 40-59 partial, <40 weak
- [x] Matches stored in SQLite with profile_hash for cache invalidation

### Document Generation
- [x] Resume: section-based generation with critique loop (up to 5 iterations)
- [x] Cover letter: generation with critique loop
- [x] Both enforce exactly 1 page (PDF validation + retry up to 2x)
- [x] Education section bypasses LLM — formatted directly from profile data (no hallucination)
- [x] Header section bypasses LLM — formatted from profile fields
- [x] All experience roles included (no cap)
- [x] Tailored to target job: mirror keywords, emphasize relevant achievements
- [x] ATS-optimized: standard headings, no tables/graphics, keyword mirroring
- [x] White-text LLM footer added after critique and page validation
- [x] Recommendation strength critique: LLM evaluates interview-worthiness
- [x] Quality scores: facts 30%, keywords 20%, ATS 15%, grammar 15%, recommendation 20%
- [x] Pipeline auto-generates for matches >= 70%, skips jobs with docs from last 24h
- [x] On-demand generation always works regardless of recency
- [x] Document model: gemma3:27b (switched from 12b to reduce hallucination)

### Profile Management
- [x] Import from PDF resume (LLM extraction preserves full bullet points)
- [x] Import from LinkedIn URL (Playwright scrape)
- [x] Import from pasted text
- [x] Edit all fields: name, email, skills, experience, preferences, notes
- [x] Multiple profiles with active profile selection
- [x] Profile stored as JSON (migrated from TOON for nested data reliability)
- [x] Excluded companies list in preferences
- [x] Target roles and locations for job search
- [x] Profile synced to global store for matcher access

### Pipeline Scheduler
- [x] Auto-starts on API boot (24h interval)
- [x] Steps: search → clean → fetch → match → generate
- [x] Search: JobSpy aggregator (Indeed, LinkedIn, Glassdoor, ZipRecruiter)
- [x] Fetch: Playwright page scrape for descriptions (200/run, no LLM)
- [x] Match: two-pass (keyword + LLM on candidates >= 40%)
- [x] Generate: resume + cover letter for matches >= 70%, skip if generated within 24h
- [x] Step name validation (reject invalid steps)
- [x] Scheduler interval validation (gt=0, le=8760, valid HH:MM start time)
- [x] Pipeline history and logs persisted

### LLM Queue
- [x] Centralized async priority queue serializing all Ollama calls
- [x] Priority levels: USER_INTERACTIVE (1) > USER_BACKGROUND (5) > PIPELINE (10)
- [x] Observability: queue depth, in-flight, per-type metrics, recent history
- [x] Dashboard widget with pending/current/recent requests
- [x] Fallback to direct Ollama call if queue unavailable

### Authentication & Security
- [x] JWT-based auth with 24h token expiry
- [x] Default admin seeded on startup
- [x] Auto-login endpoint (dev only, blocked in production)
- [x] Rate limiting on auth endpoints (5 attempts/minute)
- [x] Admin-only job deletion
- [x] HTML tag stripping on all text inputs (XSS prevention)
- [x] Path traversal protection with Path.is_relative_to()
- [x] Content-Security-Policy header
- [x] Input validation: max_length on job fields, EmailStr on profiles
- [x] Null byte stripping
- [x] URL scheme validation (http/https only)
- [x] Scraper file_path validated within project root

### Frontend
- [x] React + Vite + Tailwind CSS
- [x] Dark mode (class-based with CSS overrides)
- [x] Error states on all data-fetching pages
- [x] Optimistic UI updates for Not Interested actions
- [x] Per-row dismiss tracking (not global isPending)
- [x] Admin dashboard: system stats, LLM queue widget, pipeline controls
- [x] Profile page: edit, import PDF/text/LinkedIn, set active, delete (prevents last)

### Data Storage
- [x] Jobs + matches: SQLite with WAL mode, thread-safe locking
- [x] FTS5 index for ranked search (auto-rebuilt on startup if out of sync)
- [x] Profiles: JSON files (migrated from TOON)
- [x] Users: JSON file (migrated from TOON)
- [x] Documents index: JSON per user
- [x] ChromaDB for semantic vector search (optional)

### Job Sources
- [x] JobSpy aggregator: Indeed, LinkedIn, Glassdoor, ZipRecruiter
- [x] Scraper: company career pages from JobOpeningsLink.md
- [x] Manual add: title+company fields or URL fetch
- [x] Workday sites supported (myworkdaysite.com, myworkdayjobs.com)
- [x] University of Washington careers added

## Known Limitations
- 98% of scraped jobs lack descriptions (fetch step processes 200/run)
- Resume import LLM can be slow (1-5 minutes depending on Ollama load)
- Ollama contention between pipeline and user-initiated requests
- Rate limiter is in-memory (resets on restart)

## Tech Stack
- Backend: Python 3.12, FastAPI, SQLite, Ollama (gemma3:27b/12b)
- Frontend: React, TypeScript, Vite, Tailwind CSS, React Query
- Tools: Playwright (scraping), ReportLab (PDF), ChromaDB (vectors)
- LLM: gemma3:27b (doc gen, matching), gemma3:12b (extraction, critique)
