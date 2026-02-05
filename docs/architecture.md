# Architecture

## System Overview

Jobs Agent is a multi-component system for job searching, matching, and resume/cover letter generation.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Jobs Agent Architecture                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────┐              ┌────────────────────┐                 │
│  │     Web Frontend   │              │    CLI Scripts     │                 │
│  │  (React/TypeScript)│              │    (Python)        │                 │
│  │                    │              │                    │                 │
│  │  - Login/Register  │              │  - run_jobspy_     │                 │
│  │  - Profile Mgmt    │              │    search.py       │                 │
│  │  - Job Browsing    │              │  - run_job_        │                 │
│  │  - Doc Generation  │              │    matcher.py      │                 │
│  │  - Admin Dashboard │              │  - generate_       │                 │
│  │                    │              │    documents.py    │                 │
│  └─────────┬──────────┘              └─────────┬──────────┘                 │
│            │                                   │                             │
│            │ HTTP/REST                         │ Direct Import               │
│            ▼                                   ▼                             │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │                    FastAPI Backend                           │            │
│  │                    (api/main.py)                             │            │
│  │                                                              │            │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │            │
│  │  │  Auth    │  │ Profiles │  │  Jobs    │  │Documents │    │            │
│  │  │ Routes   │  │ Routes   │  │ Routes   │  │ Routes   │    │            │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │            │
│  │       │             │             │             │           │            │
│  │  ┌────┴─────────────┴─────────────┴─────────────┴────┐     │            │
│  │  │              Service Layer                         │     │            │
│  │  │  - ProfileService                                  │     │            │
│  │  │  - JobService                                      │     │            │
│  │  │  - DocumentService                                 │     │            │
│  │  │  - AdminService                                    │     │            │
│  │  └─────────────────────────┬─────────────────────────┘     │            │
│  └────────────────────────────┼─────────────────────────────────┘            │
│                               │                                              │
│                               ▼                                              │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │                   Core Tools Layer                           │            │
│  │              (job_agent_coordinator/tools/)                  │            │
│  │                                                              │            │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │            │
│  │  │ profile_     │  │ job_cache.py │  │ document_    │       │            │
│  │  │ store.py     │  │              │  │ generator.py │       │            │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │            │
│  │                                                              │            │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │            │
│  │  │ jobspy_      │  │ job_links_   │  │ pdf_         │       │            │
│  │  │ tools.py     │  │ scraper.py   │  │ generator.py │       │            │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │            │
│  │                                                              │            │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │            │
│  │  │ url_job_     │  │ document_    │  │ toon_        │       │            │
│  │  │ fetcher.py   │  │ critic.py    │  │ format.py    │       │            │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │            │
│  └─────────────────────────────┬─────────────────────────────────┘            │
│                               │                                              │
│                               ▼                                              │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │                    Data Storage Layer                        │            │
│  │                    (.job_cache/)                             │            │
│  │                                                              │            │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │            │
│  │  │ users.toon   │  │ jobs.toon    │  │ profiles/    │       │            │
│  │  │              │  │              │  │ *.toon       │       │            │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │            │
│  │                                                              │            │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │            │
│  │  │ matches.toon │  │ chroma/      │  │ users/       │       │            │
│  │  │              │  │ (vectors)    │  │ {id}/...     │       │            │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │            │
│  └─────────────────────────────────────────────────────────────┘            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### Frontend (web/)

React/TypeScript application built with Vite:

- **Framework**: React 18 with TypeScript
- **Styling**: Tailwind CSS
- **Routing**: React Router v6
- **State**: React Query for server state
- **HTTP**: Axios for API calls

### Backend API (api/)

FastAPI application providing RESTful endpoints:

- **Framework**: FastAPI with async support
- **Auth**: JWT-based authentication with bcrypt password hashing
- **Docs**: Auto-generated OpenAPI documentation at `/api/docs`

### Core Tools (job_agent_coordinator/)

Python modules for job operations:

- **Job Searching**: JobSpy integration for aggregator search
- **Web Scraping**: Playwright-based scraping with LLM extraction
- **Matching**: Two-pass matching (keyword + LLM)
- **Document Generation**: LLM-powered resume/cover letter generation

### Data Storage (.job_cache/)

TOON format files for persistence:

- **TOON Format**: Human-readable structured text format
- **ChromaDB**: Vector database for semantic search
- **User Isolation**: Per-user data directories

## Two-Pass Matching

```
Pass 1 (Keyword)              Pass 2 (LLM)                  Combined
~0.01s/job                    ~10s/job                      
                                                            
┌─────────────────┐           ┌─────────────────┐           ┌─────────────────┐
│ • Skill match   │           │ • Context       │           │ 40% keyword     │
│ • Role match    │    ───▶   │ • Experience    │    ───▶   │ 60% LLM         │
│ • Location      │           │ • Culture fit   │           │ = final score   │
└─────────────────┘           └─────────────────┘           └─────────────────┘
```

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, TypeScript, Tailwind CSS, Vite |
| Backend | FastAPI, Pydantic, python-jose |
| LLM | Ollama (gemma3:27b, gemma3:12b) |
| Vector DB | ChromaDB |
| Storage | TOON format (custom), JSON |
| PDF | ReportLab, PyMuPDF |
| Scraping | Playwright, BeautifulSoup |
