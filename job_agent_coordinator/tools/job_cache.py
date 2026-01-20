"""Job caching and persistence with vector search capabilities."""

import json
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Try to import ChromaDB for vector search
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("ChromaDB not installed. Vector search disabled. Install: pip install chromadb")


class JobCache:
    """
    Local caching and persistence for job listings and match results.
    
    Features:
    - Stores job metadata (title, location, salary, source, link, description)
    - Stores job match analysis results (score, skills, recommendations)
    - Vector search for semantic job matching (if ChromaDB available)
    - Deduplication by URL
    - Search by keywords, location, company
    - Persistence to disk
    """
    
    def __init__(self, cache_dir: Path = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(".job_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.jobs_file = self.cache_dir / "jobs.json"
        self.metadata_file = self.cache_dir / "metadata.json"
        self.matches_file = self.cache_dir / "matches.json"
        
        # Load existing jobs
        self._jobs: Dict[str, Dict[str, Any]] = self._load_jobs()
        self._metadata = self._load_metadata()
        self._matches: Dict[str, Dict[str, Any]] = self._load_matches()
        
        # Initialize ChromaDB for vector search
        self._collection = None
        if CHROMA_AVAILABLE:
            self._init_vector_store()
        
        logger.info(f"📦 JobCache ready: {len(self._jobs)} jobs, {len(self._matches)} matches at {self.cache_dir}")
    
    def _init_vector_store(self):
        """Initialize ChromaDB collection for vector search."""
        try:
            chroma_path = self.cache_dir / "chroma"
            self._client = chromadb.PersistentClient(
                path=str(chroma_path),
                settings=Settings(anonymized_telemetry=False)
            )
            self._collection = self._client.get_or_create_collection(
                name="jobs",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"✅ ChromaDB initialized ({self._collection.count()} vectors)")
        except Exception as e:
            logger.error(f"❌ ChromaDB init failed: {e}")
            self._collection = None
    
    def _load_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Load jobs from disk."""
        if self.jobs_file.exists():
            try:
                return json.loads(self.jobs_file.read_text())
            except Exception as e:
                logger.error(f"Failed to load jobs: {e}")
        return {}
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata."""
        if self.metadata_file.exists():
            try:
                return json.loads(self.metadata_file.read_text())
            except:
                pass
        return {"created": datetime.now().isoformat(), "total_added": 0}
    
    def _load_matches(self) -> Dict[str, Dict[str, Any]]:
        """Load job match results from disk."""
        if self.matches_file.exists():
            try:
                return json.loads(self.matches_file.read_text())
            except Exception as e:
                logger.error(f"Failed to load matches: {e}")
        return {}
    
    def _save_jobs(self):
        """Save jobs to disk."""
        self.jobs_file.write_text(json.dumps(self._jobs, indent=2, default=str))
        self._metadata["last_updated"] = datetime.now().isoformat()
        self.metadata_file.write_text(json.dumps(self._metadata, indent=2))
    
    def _save_matches(self):
        """Save match results to disk."""
        self.matches_file.write_text(json.dumps(self._matches, indent=2, default=str))
    
    # === Job Match Methods ===
    
    def add_match(self, job_id: str, match_result: Dict[str, Any], profile_hash: str = "") -> bool:
        """
        Store a job match analysis result.
        
        Args:
            job_id: The job ID this match is for
            match_result: The analysis result (score, skills, recommendations, toon_report)
            profile_hash: Hash of the user profile (for cache invalidation)
        
        Returns:
            True if stored, False if already exists with same profile
        """
        match_key = f"{job_id}:{profile_hash}" if profile_hash else job_id
        
        if match_key in self._matches:
            logger.debug(f"Match already cached: {job_id[:12]}")
            return False
        
        self._matches[match_key] = {
            "job_id": job_id,
            "profile_hash": profile_hash,
            "match_score": match_result.get("match_score", 0),
            "match_level": match_result.get("match_level", "unknown"),
            "toon_report": match_result.get("toon_report", ""),
            "cached_at": datetime.now().isoformat(),
        }
        
        self._save_matches()
        logger.info(f"🎯 Cached match: job={job_id[:12]} score={match_result.get('match_score', 0)}%")
        return True
    
    def get_match(self, job_id: str, profile_hash: str = "") -> Optional[Dict[str, Any]]:
        """
        Get cached match result for a job.
        
        Args:
            job_id: The job ID
            profile_hash: Hash of the user profile
        
        Returns:
            Cached match result or None if not found
        """
        match_key = f"{job_id}:{profile_hash}" if profile_hash else job_id
        
        # Try with profile hash first
        if match_key in self._matches:
            logger.debug(f"Match cache hit: {job_id[:12]}")
            return self._matches[match_key]
        
        # Try without profile hash (legacy)
        if job_id in self._matches:
            return self._matches[job_id]
        
        return None
    
    def list_matches(self, min_score: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """List cached matches, optionally filtered by minimum score."""
        matches = [
            m for m in self._matches.values()
            if m.get("match_score", 0) >= min_score
        ]
        # Sort by score descending
        matches.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        return matches[:limit]
    
    def clear_matches(self, job_id: str = None):
        """Clear match cache. If job_id provided, only clear that job's matches."""
        if job_id:
            to_remove = [k for k in self._matches if k.startswith(job_id)]
            for key in to_remove:
                del self._matches[key]
            logger.info(f"🗑️ Cleared {len(to_remove)} matches for job {job_id[:12]}")
        else:
            count = len(self._matches)
            self._matches.clear()
            logger.info(f"🗑️ Cleared all {count} cached matches")
        self._save_matches()
    
    def match_stats(self) -> Dict[str, Any]:
        """Get match cache statistics."""
        if not self._matches:
            return {"total_matches": 0, "score_distribution": {}}
        
        scores = [m.get("match_score", 0) for m in self._matches.values()]
        levels = {}
        for m in self._matches.values():
            level = m.get("match_level", "unknown")
            levels[level] = levels.get(level, 0) + 1
        
        return {
            "total_matches": len(self._matches),
            "avg_score": sum(scores) / len(scores) if scores else 0,
            "max_score": max(scores) if scores else 0,
            "min_score": min(scores) if scores else 0,
            "level_distribution": levels,
        }
    
    def _generate_id(self, job: Dict[str, Any]) -> str:
        """Generate unique ID for a job based on URL or content hash."""
        url = job.get("url", "")
        if url:
            return hashlib.md5(url.encode()).hexdigest()[:12]
        # Fallback to content hash
        content = f"{job.get('title', '')}{job.get('company', '')}{job.get('location', '')}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def add(self, job: Dict[str, Any]) -> bool:
        """
        Add a job to the cache.
        
        Args:
            job: Dict with keys: title, company, location, salary, url, description, platform
            
        Returns:
            True if added (new), False if already exists (duplicate)
        """
        job_id = self._generate_id(job)
        
        # Check for duplicate
        if job_id in self._jobs:
            logger.debug(f"Job already cached: {job.get('title', 'Unknown')[:30]}")
            return False
        
        # Normalize and store
        cached_job = {
            "id": job_id,
            "title": job.get("title", "Unknown"),
            "company": job.get("company", "Unknown"),
            "location": job.get("location", "Unknown"),
            "salary": job.get("salary") or job.get("min_amount") or "Not specified",
            "salary_min": job.get("min_amount"),
            "salary_max": job.get("max_amount"),
            "url": job.get("url", ""),
            "description": job.get("description", ""),
            "platform": job.get("platform", job.get("site", "unknown")),
            "posted_date": job.get("date_posted", ""),
            "cached_at": datetime.now().isoformat(),
            "search_term": job.get("search_term", ""),
            "search_location": job.get("search_location", ""),
        }
        
        self._jobs[job_id] = cached_job
        self._metadata["total_added"] = self._metadata.get("total_added", 0) + 1
        
        # Add to vector store for semantic search
        if self._collection is not None:
            try:
                # Create searchable text
                search_text = f"{cached_job['title']} {cached_job['company']} {cached_job['location']} {cached_job['description'][:500]}"
                self._collection.add(
                    documents=[search_text],
                    metadatas=[{"job_id": job_id, "title": cached_job["title"], "company": cached_job["company"]}],
                    ids=[job_id]
                )
            except Exception as e:
                logger.debug(f"Vector add failed: {e}")
        
        logger.info(f"💾 Cached: {cached_job['title'][:40]} @ {cached_job['company'][:20]}")
        return True
    
    def add_many(self, jobs: List[Dict[str, Any]], search_term: str = "", location: str = "") -> int:
        """Add multiple jobs, returns count of new jobs added."""
        added = 0
        for job in jobs:
            job["search_term"] = search_term
            job["search_location"] = location
            if self.add(job):
                added += 1
        
        if added > 0:
            self._save_jobs()
            logger.info(f"💾 Cached {added} new jobs (total: {len(self._jobs)})")
        
        return added
    
    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        return self._jobs.get(job_id)
    
    def get_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get a job by URL."""
        job_id = hashlib.md5(url.encode()).hexdigest()[:12]
        return self._jobs.get(job_id)
    
    def search(
        self,
        query: str = "",
        company: str = "",
        location: str = "",
        platform: str = "",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search cached jobs.
        
        Args:
            query: Search in title and description
            company: Filter by company name
            location: Filter by location
            platform: Filter by platform (indeed, linkedin, etc.)
            limit: Max results
            
        Returns:
            List of matching jobs
        """
        results = []
        query_lower = query.lower()
        company_lower = company.lower()
        location_lower = location.lower()
        platform_lower = platform.lower()
        
        for job in self._jobs.values():
            # Apply filters
            if query_lower:
                title = job.get("title", "").lower()
                desc = job.get("description", "").lower()
                if query_lower not in title and query_lower not in desc:
                    continue
            
            if company_lower and company_lower not in job.get("company", "").lower():
                continue
            
            if location_lower and location_lower not in job.get("location", "").lower():
                continue
            
            if platform_lower and platform_lower not in job.get("platform", "").lower():
                continue
            
            results.append(job)
            
            if len(results) >= limit:
                break
        
        return results
    
    def semantic_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Semantic search using vector similarity.
        
        Args:
            query: Natural language query (e.g., "machine learning engineer remote")
            limit: Max results
            
        Returns:
            List of semantically similar jobs
        """
        if self._collection is None:
            logger.warning("Vector search not available, using keyword search")
            return self.search(query=query, limit=limit)
        
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=limit,
                include=["metadatas", "distances"]
            )
            
            jobs = []
            if results and results.get("ids") and results["ids"][0]:
                for job_id in results["ids"][0]:
                    job = self._jobs.get(job_id)
                    if job:
                        jobs.append(job)
            
            logger.info(f"🔍 Semantic search '{query}' found {len(jobs)} jobs")
            return jobs
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return self.search(query=query, limit=limit)
    
    def list_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all cached jobs."""
        return list(self._jobs.values())[:limit]
    
    def list_by_platform(self) -> Dict[str, int]:
        """Get job counts by platform."""
        counts: Dict[str, int] = {}
        for job in self._jobs.values():
            platform = job.get("platform", "unknown")
            counts[platform] = counts.get(platform, 0) + 1
        return counts
    
    def list_companies(self, limit: int = 20) -> List[tuple]:
        """Get top companies by job count."""
        counts: Dict[str, int] = {}
        for job in self._jobs.values():
            company = job.get("company", "Unknown")
            counts[company] = counts.get(company, 0) + 1
        
        sorted_companies = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_companies[:limit]
    
    def remove(self, job_id: str) -> bool:
        """Remove a job by ID."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save_jobs()
            
            # Remove from vector store
            if self._collection:
                try:
                    self._collection.delete(ids=[job_id])
                except:
                    pass
            
            logger.info(f"🗑️ Removed job: {job_id}")
            return True
        return False
    
    def remove_company(self, company: str) -> int:
        """Remove all jobs from a specific company."""
        company_lower = company.lower()
        to_remove = [
            jid for jid, job in self._jobs.items()
            if company_lower in job.get("company", "").lower()
        ]
        
        for job_id in to_remove:
            del self._jobs[job_id]
            if self._collection:
                try:
                    self._collection.delete(ids=[job_id])
                except:
                    pass
        
        if to_remove:
            self._save_jobs()
            logger.info(f"🗑️ Removed {len(to_remove)} jobs from {company}")
        
        return len(to_remove)
    
    def clear(self):
        """Clear all cached jobs."""
        self._jobs.clear()
        self._save_jobs()
        
        if self._collection:
            try:
                # Delete and recreate collection
                self._client.delete_collection("jobs")
                self._collection = self._client.create_collection(
                    name="jobs",
                    metadata={"hnsw:space": "cosine"}
                )
            except:
                pass
        
        logger.info("🗑️ Cache cleared")
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        platforms = self.list_by_platform()
        companies = self.list_companies(10)
        
        return {
            "total_jobs": len(self._jobs),
            "total_matches": len(self._matches),
            "match_stats": self.match_stats(),
            "platforms": platforms,
            "top_companies": companies,
            "vector_search": self._collection is not None,
            "vector_count": self._collection.count() if self._collection else 0,
            "cache_dir": str(self.cache_dir),
            "created": self._metadata.get("created"),
            "last_updated": self._metadata.get("last_updated"),
            "total_ever_added": self._metadata.get("total_added", 0),
        }
    
    def export_csv(self, filepath: Path = None) -> Path:
        """Export jobs to CSV file."""
        import csv
        
        filepath = filepath or (self.cache_dir / "jobs_export.csv")
        
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            if not self._jobs:
                return filepath
            
            # Get all fields
            fields = ["id", "title", "company", "location", "salary", "url", "platform", "posted_date", "cached_at"]
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            
            for job in self._jobs.values():
                writer.writerow(job)
        
        logger.info(f"📄 Exported {len(self._jobs)} jobs to {filepath}")
        return filepath


# Global cache instance
_cache: Optional[JobCache] = None


def get_cache() -> JobCache:
    """Get or create the global job cache."""
    global _cache
    if _cache is None:
        _cache = JobCache()
    return _cache


# === FunctionTools for agent use ===

from google.adk.tools import FunctionTool


def cache_job(
    title: str,
    company: str,
    location: str,
    url: str,
    platform: str = "unknown",
    salary: str = "",
    description: str = ""
) -> dict:
    """
    Cache a single job listing.
    
    Args:
        title: Job title
        company: Company name
        location: Job location
        url: Link to job posting
        platform: Source platform (indeed, linkedin, etc.)
        salary: Salary information
        description: Job description
    
    Returns:
        Dict with success status and job_id
    """
    cache = get_cache()
    job = {
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "platform": platform,
        "salary": salary,
        "description": description,
    }
    
    is_new = cache.add(job)
    job_id = cache._generate_id(job)
    
    return {
        "success": True,
        "is_new": is_new,
        "job_id": job_id,
        "message": f"Job {'added' if is_new else 'already exists'}: {title[:40]}"
    }


def search_cached_jobs(
    query: str = "",
    company: str = "",
    location: str = "",
    semantic: bool = False,
    limit: int = 10
) -> str:
    """
    Search cached job listings.
    
    Args:
        query: Search term for title/description
        company: Filter by company name
        location: Filter by location
        semantic: Use AI-powered semantic search
        limit: Maximum results
    
    Returns:
        TOON formatted search results
    """
    cache = get_cache()
    
    if semantic and query:
        jobs = cache.semantic_search(query, limit=limit)
    else:
        jobs = cache.search(query=query, company=company, location=location, limit=limit)
    
    # Build TOON output
    lines = [
        "[job_search_results]",
        f"query: {query or 'all'}",
        f"company_filter: {company or 'none'}",
        f"location_filter: {location or 'none'}",
        f"semantic_search: {semantic}",
        f"results_found: {len(jobs)}",
        "",
        "[jobs]"
    ]
    
    for i, job in enumerate(jobs, 1):
        title = job.get("title", "Unknown")[:45]
        comp = job.get("company", "Unknown")[:20]
        loc = job.get("location", "")[:20]
        salary = job.get("salary", "")
        url = job.get("url", "")
        
        lines.append(f"{i}. {title}")
        lines.append(f"   company: {comp}")
        if loc:
            lines.append(f"   location: {loc}")
        if salary and salary != "Not specified":
            lines.append(f"   salary: {salary}")
        if url:
            lines.append(f"   url: {url}")
        lines.append("")
    
    if not jobs:
        lines.append("- no jobs found matching criteria")
    
    return "\n".join(lines)


def get_cache_stats() -> str:
    """Get job cache statistics in TOON format."""
    stats = get_cache().stats()
    
    lines = [
        "[job_cache_stats]",
        f"total_jobs: {stats['total_jobs']}",
        f"total_matches: {stats['total_matches']}",
        f"vector_count: {stats['vector_count']}",
        f"cache_dir: {stats['cache_dir']}",
        "",
        "[platforms]"
    ]
    
    for platform, count in stats.get("platforms", {}).items():
        lines.append(f"- {platform}: {count}")
    
    lines.extend(["", "[top_companies]"])
    for company, count in stats.get("top_companies", [])[:10]:
        lines.append(f"- {company}: {count}")
    
    match_stats = stats.get("match_stats", {})
    if match_stats.get("total_matches", 0) > 0:
        lines.extend([
            "",
            "[match_statistics]",
            f"total_matches: {match_stats.get('total_matches', 0)}",
            f"avg_score: {match_stats.get('avg_score', 0):.1f}%",
            f"max_score: {match_stats.get('max_score', 0)}%",
            f"min_score: {match_stats.get('min_score', 0)}%",
        ])
        for level, count in match_stats.get("level_distribution", {}).items():
            emoji = "🟢" if level in ("strong", "good") else "🟡" if level == "partial" else "🔴"
            lines.append(f"- {emoji} {level}: {count}")
    
    return "\n".join(lines)


def clear_job_cache() -> dict:
    """Clear all cached jobs."""
    get_cache().clear()
    return {"success": True, "message": "Job cache cleared"}


def remove_company_from_cache(company: str) -> dict:
    """Remove all jobs from a specific company."""
    count = get_cache().remove_company(company)
    return {"success": True, "removed": count, "message": f"Removed {count} jobs from {company}"}


def cache_job_match(
    job_id: str,
    match_score: int,
    match_level: str,
    toon_report: str = "",
    profile_hash: str = ""
) -> dict:
    """
    Cache a job match analysis result.
    
    Args:
        job_id: The job ID this match is for
        match_score: Match score (0-100)
        match_level: Match level (strong, good, partial, weak)
        toon_report: Full TOON formatted analysis report
        profile_hash: Hash of user profile for cache invalidation
    
    Returns:
        Dict with success status
    """
    cache = get_cache()
    match_result = {
        "match_score": match_score,
        "match_level": match_level,
        "toon_report": toon_report,
    }
    is_new = cache.add_match(job_id, match_result, profile_hash)
    return {
        "success": True,
        "is_new": is_new,
        "job_id": job_id,
        "message": f"Match {'cached' if is_new else 'already exists'}: score={match_score}%"
    }


def get_cached_match(job_id: str, profile_hash: str = "") -> dict:
    """
    Get a cached job match result.
    
    Args:
        job_id: The job ID to look up
        profile_hash: Hash of user profile
    
    Returns:
        Dict with match result or not found message
    """
    cache = get_cache()
    match = cache.get_match(job_id, profile_hash)
    if match:
        return {"success": True, "found": True, "match": match}
    return {"success": True, "found": False, "message": "No cached match found"}


def list_cached_matches(min_score: int = 0, limit: int = 20) -> str:
    """
    List cached job matches.
    
    Args:
        min_score: Minimum match score to include
        limit: Maximum results
    
    Returns:
        TOON formatted list of matches
    """
    cache = get_cache()
    matches = cache.list_matches(min_score=min_score, limit=limit)
    
    lines = [
        "[cached_matches]",
        f"min_score_filter: {min_score}%",
        f"limit: {limit}",
        f"matches_found: {len(matches)}",
        "",
        "[matches]"
    ]
    
    for i, m in enumerate(matches, 1):
        job = cache.get(m.get("job_id", ""))
        score = m.get("match_score", 0)
        level = m.get("match_level", "unknown")
        emoji = "🟢" if level in ("strong", "good") else "🟡" if level == "partial" else "🔴"
        
        if job:
            title = job.get("title", "Unknown")[:40]
            company = job.get("company", "Unknown")[:20]
            lines.append(f"{i}. {emoji} {score}% - {title} @ {company}")
        else:
            lines.append(f"{i}. {emoji} {score}% - job_id: {m.get('job_id', 'unknown')}")
    
    if not matches:
        lines.append("- no matches found")
    
    return "\n".join(lines)


def clear_cached_matches(job_id: str = "") -> dict:
    """
    Clear cached job matches.
    
    Args:
        job_id: Optional - clear only matches for this job. If empty, clears all.
    
    Returns:
        Dict with success status
    """
    cache = get_cache()
    cache.clear_matches(job_id if job_id else None)
    return {"success": True, "message": f"Cleared matches{' for ' + job_id if job_id else ''}"}


def aggregate_job_matches(
    min_score: int = 0,
    max_results: int = 50
) -> str:
    """
    Aggregate and analyze all cached job matches.
    
    Provides:
    - Ranked list of matches by score
    - Score distribution and statistics
    - Common skill gaps across all matches
    - Top recommendations
    
    Args:
        min_score: Only include matches with score >= this value
        max_results: Maximum number of jobs to include in ranking
    
    Returns:
        TOON formatted aggregation report
    """
    cache = get_cache()
    matches = cache.list_matches(min_score=min_score, limit=max_results)
    
    if not matches:
        return "[job_match_summary]\nstatus: no matches found\naction: run analyze_job_match on jobs of interest"
    
    # Get job details for each match
    jobs_with_matches = []
    for match in matches:
        job_id = match.get("job_id", "")
        job = cache.get(job_id)
        if job:
            jobs_with_matches.append({"job": job, "match": match})
    
    # Calculate statistics
    scores = [m.get("match_score", 0) for m in matches]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    # Count by level
    level_counts = {}
    for m in matches:
        level = m.get("match_level", "unknown")
        level_counts[level] = level_counts.get(level, 0) + 1
    
    # Extract skill gaps from TOON reports
    skill_gaps = {}
    for m in matches:
        report = m.get("toon_report", "")
        if "[skill_gaps]" in report:
            gap_section = report.split("[skill_gaps]")[1].split("[")[0]
            for line in gap_section.split("\n"):
                if line.strip().startswith("- ") and ":" in line:
                    skill = line.split(":")[0].replace("- ", "").strip()
                    if skill and skill != "none":
                        skill_gaps[skill] = skill_gaps.get(skill, 0) + 1
    
    top_skill_gaps = sorted(skill_gaps.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Build TOON output
    lines = [
        "[job_match_summary]",
        f"total_analyzed: {len(matches)}",
        f"avg_score: {avg_score:.1f}%",
        f"max_score: {max(scores)}%",
        f"min_score: {min(scores)}%",
        "",
        "[level_distribution]",
        f"🟢 strong (80%+): {level_counts.get('strong', 0)}",
        f"🟢 good (60-79%): {level_counts.get('good', 0)}",
        f"🟡 partial (40-59%): {level_counts.get('partial', 0)}",
        f"🔴 weak (<40%): {level_counts.get('weak', 0)}",
        "",
        "[top_matches]"
    ]
    
    for i, item in enumerate(jobs_with_matches[:15], 1):
        job = item["job"]
        match = item["match"]
        score = match.get("match_score", 0)
        level = match.get("match_level", "unknown")
        emoji = "🟢" if level in ("strong", "good") else "🟡" if level == "partial" else "🔴"
        title = job.get("title", "Unknown")[:40]
        company = job.get("company", "Unknown")[:20]
        location = job.get("location", "")[:25]
        url = job.get("url", "")
        
        lines.append(f"{i}. {emoji} {score}% - {title}")
        lines.append(f"   company: {company}")
        if location:
            lines.append(f"   location: {location}")
        lines.append(f"   url: {url if url else 'not available'}")
    
    lines.extend(["", "[common_skill_gaps]"])
    if top_skill_gaps:
        for skill, count in top_skill_gaps[:5]:
            lines.append(f"- {skill}: appears in {count} job(s)")
    else:
        lines.append("- none identified")
    
    lines.extend(["", "[recommendations]"])
    rec_num = 1
    if level_counts.get("strong", 0) > 0:
        lines.append(f"{rec_num}. Prioritize strong matches for immediate applications")
        rec_num += 1
    if level_counts.get("good", 0) > 0:
        lines.append(f"{rec_num}. Good matches ({level_counts.get('good', 0)}) - tailor resumes to specific requirements")
        rec_num += 1
    if top_skill_gaps:
        top_gap = top_skill_gaps[0][0]
        lines.append(f"{rec_num}. Consider learning {top_gap} - most common skill gap")
        rec_num += 1
    if not level_counts.get("strong", 0) and not level_counts.get("good", 0):
        lines.append(f"{rec_num}. No strong matches yet - consider updating profile or expanding search")
    
    return "\n".join(lines)


# Create FunctionTools
cache_job_tool = FunctionTool(func=cache_job)
search_cached_jobs_tool = FunctionTool(func=search_cached_jobs)
get_cache_stats_tool = FunctionTool(func=get_cache_stats)
clear_job_cache_tool = FunctionTool(func=clear_job_cache)
remove_company_tool = FunctionTool(func=remove_company_from_cache)

# Match caching tools
cache_job_match_tool = FunctionTool(func=cache_job_match)
get_cached_match_tool = FunctionTool(func=get_cached_match)
list_cached_matches_tool = FunctionTool(func=list_cached_matches)
clear_cached_matches_tool = FunctionTool(func=clear_cached_matches)
aggregate_job_matches_tool = FunctionTool(func=aggregate_job_matches)
