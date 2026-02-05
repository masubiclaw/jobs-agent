# Data Models

## TOON Format

Jobs Agent uses TOON (Text Object Oriented Notation), a human-readable structured text format.

### Syntax

```
[section_name]
key: value
nested_key: nested_value

[list_section]
- item 1
- item 2

[numbered_list]
[0]
  name: First
  value: 1
[1]
  name: Second
  value: 2
```

### Example Profile (TOON)

```
id: john_doe
name: John Doe
email: john@example.com
location: Seattle, WA
created_at: 2024-01-01T00:00:00

[skills]
[0]
  name: Python
  level: expert
[1]
  name: JavaScript
  level: advanced

[preferences]
target_roles: Software Engineer, Backend Developer
remote_preference: remote
salary_min: 150000
salary_max: 200000
```

## Storage Structure

```
.job_cache/
├── users.toon                    # User accounts
├── jobs.toon                     # Shared job listings
├── matches.toon                  # Match results
├── metadata.toon                 # Cache metadata
├── chroma/                       # Vector embeddings
│   └── chroma.sqlite3
├── profiles/                     # Legacy profiles (single-user)
│   └── *.toon
└── users/                        # Multi-user data
    └── {user_id}/
        ├── profiles/             # User's profiles
        │   ├── _meta.toon        # Active profile tracking
        │   └── {profile_id}.toon
        ├── job_metadata.toon     # User-specific job data
        └── documents/            # Generated documents
            └── _index.toon
```

## User Model

```python
{
    "id": str,                    # UUID (12 chars)
    "email": str,                 # Unique, lowercase
    "name": str,
    "hashed_password": str,       # bcrypt hash
    "is_admin": bool,
    "created_at": str,            # ISO 8601
    "updated_at": str,
}
```

## Profile Model

```python
{
    "id": str,                    # Sanitized name
    "user_id": str,               # Owner user ID
    "name": str,
    "email": str,
    "phone": str,
    "location": str,
    "created_at": str,
    "updated_at": str,
    
    "skills": [
        {
            "name": str,
            "level": "beginner" | "intermediate" | "advanced" | "expert",
            "added_at": str,
        }
    ],
    
    "experience": [
        {
            "title": str,
            "company": str,
            "start_date": str,    # "YYYY-MM"
            "end_date": str,      # "YYYY-MM" or "present"
            "description": str,
        }
    ],
    
    "preferences": {
        "target_roles": [str],
        "target_locations": [str],
        "remote_preference": "remote" | "hybrid" | "onsite",
        "salary_min": int | None,
        "salary_max": int | None,
        "job_types": [str],
        "industries": [str],
        "excluded_companies": [str],
    },
    
    "resume": {
        "summary": str,
        "content": str,
        "last_updated": str | None,
    },
    
    "notes": str,
}
```

## Job Model

```python
{
    "id": str,                    # MD5 hash of URL (12 chars)
    "title": str,
    "company": str,
    "location": str,
    "salary": str,
    "salary_min": int | None,
    "salary_max": int | None,
    "url": str,
    "description": str,
    "platform": str,              # indeed, linkedin, etc.
    "posted_date": str,
    "cached_at": str,
    "search_term": str,
    "search_location": str,
}
```

## Match Result Model

```python
{
    "job_id": str,
    "profile_hash": str,          # For cache invalidation
    
    "keyword_score": int,         # 0-100
    "llm_score": int | None,      # 0-100
    "combined_score": int,        # 0-100 (40% keyword + 60% LLM)
    
    "match_level": "strong" | "good" | "partial" | "weak" | "excluded",
    "toon_report": str,           # Full analysis report
    "cached_at": str,
}
```

## User-Specific Job Metadata

Stored separately from shared job data:

```python
{
    "job_id": {
        "status": "active" | "completed" | "archived",
        "notes": str,
        "added_by": "manual" | "url" | "pdf" | "scraped" | "search",
    }
}
```

## Document Model

```python
{
    "id": str,                    # MD5 hash
    "job_id": str,
    "profile_id": str,
    "document_type": "resume" | "cover_letter",
    "content": str,               # Generated text
    "pdf_path": str | None,
    "quality_scores": {
        "fact_score": int,        # 0-100
        "keyword_score": int,     # 0-100
        "ats_score": int,         # 0-100
        "length_score": int,      # 0-100
        "overall_score": int,     # 0-100
    },
    "iterations": int,
    "created_at": str,
}
```

## Vector Embeddings

ChromaDB stores embeddings for semantic search:

- **Collection**: "jobs"
- **Similarity**: Cosine
- **Document**: Title + Company + Location + Description (first 500 chars)
- **Metadata**: job_id, title, company
