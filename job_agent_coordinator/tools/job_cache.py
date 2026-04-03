"""Job caching and persistence with SQLite backend and vector search."""

import csv
import hashlib
import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import ChromaDB for vector search
try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("ChromaDB not installed. Vector search disabled.")

# Column list used for INSERT/SELECT
_JOB_COLS = [
    "id", "title", "company", "location", "salary", "salary_min", "salary_max",
    "url", "description", "platform", "posted_date", "cached_at",
    "search_term", "search_location",
]

_MATCH_COLS = [
    "match_key", "job_id", "profile_hash",
    "keyword_score", "llm_score", "combined_score", "match_score",
    "match_level", "toon_report", "cached_at",
]


class JobCache:
    """
    SQLite-backed job cache with optional ChromaDB vector search.

    Replaces the previous TOON flat-file storage with atomic writes,
    indexed queries, and concurrent-safe access.
    """

    def __init__(self, cache_dir: Path = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(".job_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.cache_dir / "jobs.db"
        self._lock = threading.Lock()

        # Open connection and create schema
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

        # Migrate from TOON/JSON if this is a fresh DB
        if self._count_table("jobs") == 0:
            self._migrate_from_legacy()

        # ChromaDB vector search
        self._collection = None
        if CHROMA_AVAILABLE:
            self._init_vector_store()

        total_jobs = self._count_table("jobs")
        total_matches = self._count_table("matches")
        logger.info(f"📦 JobCache ready: {total_jobs} jobs, {total_matches} matches at {self.cache_dir}")

    # ── Schema ───────────────────────────────────────────────

    def _create_tables(self):
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id              TEXT PRIMARY KEY,
                title           TEXT NOT NULL DEFAULT 'Unknown',
                company         TEXT NOT NULL DEFAULT 'Unknown',
                location        TEXT NOT NULL DEFAULT 'Unknown',
                salary          TEXT DEFAULT 'Not specified',
                salary_min      REAL,
                salary_max      REAL,
                url             TEXT DEFAULT '',
                description     TEXT DEFAULT '',
                platform        TEXT DEFAULT 'unknown',
                posted_date     TEXT DEFAULT '',
                cached_at       TEXT NOT NULL,
                search_term     TEXT DEFAULT '',
                search_location TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_company  ON jobs(company);
            CREATE INDEX IF NOT EXISTS idx_jobs_platform ON jobs(platform);
            CREATE INDEX IF NOT EXISTS idx_jobs_url      ON jobs(url);

            CREATE TABLE IF NOT EXISTS matches (
                match_key       TEXT PRIMARY KEY,
                job_id          TEXT NOT NULL,
                profile_hash    TEXT DEFAULT '',
                keyword_score   INTEGER DEFAULT 0,
                llm_score       INTEGER,
                combined_score  INTEGER DEFAULT 0,
                match_score     INTEGER DEFAULT 0,
                match_level     TEXT DEFAULT 'unknown',
                toon_report     TEXT DEFAULT '',
                cached_at       TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_matches_job_id ON matches(job_id);
            CREATE INDEX IF NOT EXISTS idx_matches_score  ON matches(combined_score);

            CREATE TABLE IF NOT EXISTS metadata (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            -- FTS5 for ranked full-text search (standalone, not content-sync)
            CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
                job_id UNINDEXED, title, company, location, description
            );
        """)
        self._conn.commit()

        # Rebuild FTS index if out of sync
        fts_count = self._conn.execute("SELECT COUNT(*) FROM jobs_fts").fetchone()[0]
        jobs_count = self._count_table("jobs")
        if jobs_count > 0 and (fts_count == 0 or abs(fts_count - jobs_count) > jobs_count * 0.1):
            logger.info(f"Rebuilding FTS index ({fts_count} fts vs {jobs_count} jobs)...")
            self._conn.execute("DELETE FROM jobs_fts")
            self._conn.execute("""
                INSERT INTO jobs_fts(job_id, title, company, location, description)
                SELECT id, title, company, location, description FROM jobs
            """)
            self._conn.commit()
            logger.info(f"FTS index rebuilt: {self._conn.execute('SELECT COUNT(*) FROM jobs_fts').fetchone()[0]} entries")

    def _count_table(self, table: str) -> int:
        row = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return row[0] if row else 0

    # ── Legacy migration ─────────────────────────────────────

    def _migrate_from_legacy(self):
        """Migrate data from TOON/JSON files to SQLite on first run."""
        from .toon_format import jobs_from_toon, matches_from_toon, from_toon

        # Try TOON files first, then JSON
        jobs_data: Dict[str, Dict[str, Any]] = {}
        matches_data: Dict[str, Dict[str, Any]] = {}

        toon_jobs = self.cache_dir / "jobs.toon"
        json_jobs = self.cache_dir / "jobs.json"
        toon_matches = self.cache_dir / "matches.toon"
        json_matches = self.cache_dir / "matches.json"
        toon_meta = self.cache_dir / "metadata.toon"
        json_meta = self.cache_dir / "metadata.json"

        # Load jobs
        if toon_jobs.exists():
            try:
                jobs_data = jobs_from_toon(toon_jobs.read_text())
                logger.info(f"Migrating {len(jobs_data)} jobs from TOON")
            except Exception as e:
                logger.warning(f"Failed to parse jobs.toon: {e}")
        if not jobs_data and json_jobs.exists():
            try:
                jobs_data = json.loads(json_jobs.read_text())
                logger.info(f"Migrating {len(jobs_data)} jobs from JSON")
            except Exception as e:
                logger.warning(f"Failed to parse jobs.json: {e}")

        # Load matches
        if toon_matches.exists():
            try:
                matches_data = matches_from_toon(toon_matches.read_text())
            except Exception:
                pass
        if not matches_data and json_matches.exists():
            try:
                matches_data = json.loads(json_matches.read_text())
            except Exception:
                pass

        # Load metadata
        meta = {}
        if toon_meta.exists():
            try:
                meta = from_toon(toon_meta.read_text())
            except Exception:
                pass
        if not meta and json_meta.exists():
            try:
                meta = json.loads(json_meta.read_text())
            except Exception:
                pass

        if not jobs_data and not matches_data:
            return

        # Bulk insert jobs
        cur = self._conn.cursor()
        for job_id, job in jobs_data.items():
            job.setdefault("id", job_id)
            self._insert_job(cur, job)

        # Bulk insert matches
        for match_key, match in matches_data.items():
            match.setdefault("match_key", match_key)
            self._insert_match(cur, match)

        # Insert metadata
        for k, v in meta.items():
            cur.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                (k, str(v)),
            )

        self._conn.commit()
        logger.info(
            f"✅ Migrated {len(jobs_data)} jobs, {len(matches_data)} matches to SQLite"
        )

        # Rename old files as backup
        for f in [toon_jobs, json_jobs, toon_matches, json_matches, toon_meta, json_meta]:
            if f.exists():
                backup = f.with_suffix(f.suffix + ".bak")
                try:
                    f.rename(backup)
                except Exception:
                    pass

    # ── Helper: insert rows ──────────────────────────────────

    @staticmethod
    def _insert_job(cur: sqlite3.Cursor, job: Dict[str, Any]):
        cur.execute(
            """INSERT OR REPLACE INTO jobs
               (id, title, company, location, salary, salary_min, salary_max,
                url, description, platform, posted_date, cached_at,
                search_term, search_location)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job.get("id", ""),
                job.get("title", "Unknown"),
                job.get("company", "Unknown"),
                job.get("location", "Unknown"),
                job.get("salary") or job.get("min_amount") or "Not specified",
                job.get("salary_min") or job.get("min_amount"),
                job.get("salary_max") or job.get("max_amount"),
                job.get("url", ""),
                job.get("description", ""),
                job.get("platform", job.get("site", "unknown")),
                job.get("posted_date", job.get("date_posted", "")),
                job.get("cached_at", datetime.now().isoformat()),
                job.get("search_term", ""),
                job.get("search_location", ""),
            ),
        )

    @staticmethod
    def _insert_match(cur: sqlite3.Cursor, match: Dict[str, Any]):
        match_key = match.get("match_key", match.get("job_id", ""))
        job_id = match.get("job_id", match_key.split(":")[0] if ":" in match_key else match_key)
        cur.execute(
            """INSERT OR REPLACE INTO matches
               (match_key, job_id, profile_hash,
                keyword_score, llm_score, combined_score, match_score,
                match_level, toon_report, cached_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                match_key,
                job_id,
                match.get("profile_hash", ""),
                match.get("keyword_score", 0),
                match.get("llm_score"),
                match.get("combined_score", match.get("match_score", 0)),
                match.get("match_score", match.get("combined_score", 0)),
                match.get("match_level", "unknown"),
                match.get("toon_report", ""),
                match.get("cached_at", datetime.now().isoformat()),
            ),
        )

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row)

    # ── Vector store ─────────────────────────────────────────

    def _init_vector_store(self):
        try:
            chroma_path = self.cache_dir / "chroma"
            self._client = chromadb.PersistentClient(
                path=str(chroma_path),
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name="jobs", metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"✅ ChromaDB initialized ({self._collection.count()} vectors)")
        except Exception as e:
            logger.error(f"❌ ChromaDB init failed: {e}")
            self._collection = None

    # ── Public: ID generation ────────────────────────────────

    def generate_id(self, job: Dict[str, Any]) -> str:
        """Generate a deterministic ID for a job based on URL or content."""
        url = job.get("url", "")
        if url:
            return hashlib.md5(url.encode()).hexdigest()[:12]
        content = f"{job.get('title', '')}{job.get('company', '')}{job.get('location', '')}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    # Keep old name for backward compat
    _generate_id = generate_id

    # ── Public: Job CRUD ─────────────────────────────────────

    def add(self, job: Dict[str, Any]) -> bool:
        """Add a job. Returns True if new, False if duplicate."""
        job_id = self.generate_id(job)

        with self._lock:
            existing = self._conn.execute(
                "SELECT id FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            if existing:
                return False

            job["id"] = job_id
            job.setdefault("cached_at", datetime.now().isoformat())
            cur = self._conn.cursor()
            self._insert_job(cur, job)
            self._conn.execute(
                "INSERT OR REPLACE INTO metadata (key,value) VALUES ('last_updated',?)",
                (datetime.now().isoformat(),),
            )
            self._conn.commit()

        # Vector store
        if self._collection:
            try:
                text = f"{job.get('title','')} {job.get('company','')} {job.get('location','')} {job.get('description','')[:500]}"
                self._collection.add(
                    documents=[text],
                    metadatas=[{"job_id": job_id, "title": job.get("title", ""), "company": job.get("company", "")}],
                    ids=[job_id],
                )
            except Exception:
                pass

        # FTS index
        with self._lock:
            self._conn.execute(
                "INSERT INTO jobs_fts(job_id, title, company, location, description) VALUES (?,?,?,?,?)",
                (job_id, job.get("title",""), job.get("company",""), job.get("location",""), job.get("description","")),
            )
            self._conn.commit()

        logger.info(f"💾 Cached: {job.get('title','?')[:40]} @ {job.get('company','?')[:20]}")
        return True

    def add_many(self, jobs: List[Dict[str, Any]], search_term: str = "", location: str = "") -> int:
        """Add multiple jobs. Returns count of new jobs added."""
        added = 0
        with self._lock:
            cur = self._conn.cursor()
            for job in jobs:
                job["search_term"] = search_term
                job["search_location"] = location
                job_id = self.generate_id(job)
                existing = cur.execute("SELECT id FROM jobs WHERE id=?", (job_id,)).fetchone()
                if existing:
                    continue
                job["id"] = job_id
                job.setdefault("cached_at", datetime.now().isoformat())
                self._insert_job(cur, job)
                added += 1

                if self._collection:
                    try:
                        text = f"{job.get('title','')} {job.get('company','')} {job.get('location','')} {job.get('description','')[:500]}"
                        self._collection.add(
                            documents=[text],
                            metadatas=[{"job_id": job_id, "title": job.get("title",""), "company": job.get("company","")}],
                            ids=[job_id],
                        )
                    except Exception:
                        pass

            if added:
                cur.execute(
                    "INSERT OR REPLACE INTO metadata (key,value) VALUES ('last_updated',?)",
                    (datetime.now().isoformat(),),
                )
                self._conn.commit()
                logger.info(f"💾 Cached {added} new jobs (total: {self._count_table('jobs')})")

        return added

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return self._row_to_dict(row) if row else None

    def get_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get a job by URL."""
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE url=?", (url,)).fetchone()
            return self._row_to_dict(row) if row else None

    def update_job(self, job_id: str, **fields) -> bool:
        """Update specific fields of an existing job."""
        if not fields:
            return False
        allowed = {"title", "company", "location", "salary", "url", "description", "platform", "posted_date"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [job_id]
        fts_fields = {"title", "company", "location", "description"}
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE jobs SET {set_clause} WHERE id=?", values
            )
            # Update FTS if any indexed field changed
            if cur.rowcount > 0 and updates.keys() & fts_fields:
                job = self._conn.execute("SELECT title, company, location, description FROM jobs WHERE id=?", (job_id,)).fetchone()
                if job:
                    self._conn.execute("DELETE FROM jobs_fts WHERE job_id=?", (job_id,))
                    self._conn.execute(
                        "INSERT INTO jobs_fts(job_id, title, company, location, description) VALUES (?,?,?,?,?)",
                        (job_id, job[0], job[1], job[2], job[3]),
                    )
            self._conn.commit()
            return cur.rowcount > 0

    def remove(self, job_id: str) -> bool:
        """Remove a job by ID (cascades to matches, cleans FTS)."""
        with self._lock:
            self._conn.execute("DELETE FROM jobs_fts WHERE job_id=?", (job_id,))
            cur = self._conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
            self._conn.commit()
        if cur.rowcount > 0:
            if self._collection:
                try:
                    self._collection.delete(ids=[job_id])
                except Exception:
                    pass
            logger.info(f"🗑️ Removed job: {job_id}")
            return True
        return False

    def remove_company(self, company: str) -> int:
        """Remove all jobs from a company."""
        ids = []
        with self._lock:
            rows = self._conn.execute(
                "SELECT id FROM jobs WHERE LOWER(company) LIKE ?",
                (f"%{company.lower()}%",),
            ).fetchall()
            ids = [r["id"] for r in rows]
            if ids:
                placeholders = ",".join("?" * len(ids))
                self._conn.execute(f"DELETE FROM jobs WHERE id IN ({placeholders})", ids)
                self._conn.commit()
                if self._collection:
                    try:
                        self._collection.delete(ids=ids)
                    except Exception:
                        pass
                logger.info(f"🗑️ Removed {len(ids)} jobs from {company}")
        return len(ids) if ids else 0

    def clear(self):
        """Clear all jobs and matches."""
        with self._lock:
            self._conn.executescript("DELETE FROM matches; DELETE FROM jobs;")
            self._conn.commit()
        if self._collection:
            try:
                self._client.delete_collection("jobs")
                self._collection = self._client.create_collection(
                    name="jobs", metadata={"hnsw:space": "cosine"}
                )
            except Exception:
                pass
        logger.info("🗑️ Cache cleared")

    # ── Public: Search ───────────────────────────────────────

    def search(
        self,
        query: str = "",
        company: str = "",
        location: str = "",
        platform: str = "",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search jobs using FTS5 ranked search with company-name boost.

        Results are ranked by relevance: exact company matches first,
        then title matches, then description matches.
        """
        # If we have a free-text query, use FTS5 for ranked results
        if query and not company and not location and not platform:
            return self._fts_search(query, limit)

        # For structured filters (company/location/platform), use LIKE
        conditions = []
        params: list = []

        if query:
            # Still use FTS for the text part, join with filters
            return self._fts_search_with_filters(query, company, location, platform, limit)
        if company:
            conditions.append("LOWER(company) LIKE ?")
            params.append(f"%{company.lower()}%")
        if location:
            conditions.append("LOWER(location) LIKE ?")
            params.append(f"%{location.lower()}%")
        if platform:
            conditions.append("LOWER(platform) LIKE ?")
            params.append(f"%{platform.lower()}%")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM jobs WHERE {where} ORDER BY cached_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def _fts_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """FTS5 ranked search with company-name boosting.

        Ranking strategy:
        - Exact company match gets highest boost (weight 10)
        - Title match gets medium boost (weight 5)
        - Location match gets small boost (weight 2)
        - Description match gets base weight (weight 1)
        """
        # Escape FTS special characters and build query
        fts_query = self._build_fts_query(query)

        try:
            # Use bm25 ranking: job_id(unindexed)=0, title=5, company=10, location=2, description=1
            sql = """
                SELECT j.*, bm25(jobs_fts, 0, 5.0, 10.0, 2.0, 1.0) AS rank
                FROM jobs_fts f
                JOIN jobs j ON j.id = f.job_id
                WHERE jobs_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            with self._lock:
                rows = self._conn.execute(sql, (fts_query, limit)).fetchall()
            return [self._row_to_dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"FTS search failed, falling back to LIKE: {e}")
            # Fallback to LIKE search (BUG-013: escape LIKE wildcards)
            escaped = query.lower().replace('%', '\\%').replace('_', '\\_')
            q = f"%{escaped}%"
            with self._lock:
                rows = self._conn.execute(
                    """SELECT * FROM jobs
                       WHERE LOWER(title) LIKE ? ESCAPE '\\' OR LOWER(company) LIKE ? ESCAPE '\\' OR LOWER(description) LIKE ? ESCAPE '\\'
                       ORDER BY
                           CASE WHEN LOWER(company) LIKE ? ESCAPE '\\' THEN 0 ELSE 1 END,
                           CASE WHEN LOWER(title) LIKE ? ESCAPE '\\' THEN 0 ELSE 1 END,
                           cached_at DESC
                       LIMIT ?""",
                    (q, q, q, q, q, limit),
                ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def _fts_search_with_filters(
        self, query: str, company: str = "", location: str = "", platform: str = "", limit: int = 20
    ) -> List[Dict[str, Any]]:
        """FTS search combined with structured filters."""
        fts_query = self._build_fts_query(query)

        conditions = ["jobs_fts MATCH ?"]
        params: list = [fts_query]

        if company:
            conditions.append("LOWER(j.company) LIKE ?")
            params.append(f"%{company.lower()}%")
        if location:
            conditions.append("LOWER(j.location) LIKE ?")
            params.append(f"%{location.lower()}%")
        if platform:
            conditions.append("LOWER(j.platform) LIKE ?")
            params.append(f"%{platform.lower()}%")

        where = " AND ".join(conditions)
        params.append(limit)

        try:
            sql = f"""
                SELECT j.*, bm25(jobs_fts, 0, 5.0, 10.0, 2.0, 1.0) AS rank
                FROM jobs_fts f
                JOIN jobs j ON j.id = f.job_id
                WHERE {where}
                ORDER BY rank
                LIMIT ?
            """
            with self._lock:
                rows = self._conn.execute(sql, params).fetchall()
            return [self._row_to_dict(r) for r in rows]
        except Exception:
            # Fallback (BUG-013: escape LIKE wildcards)
            escaped = query.lower().replace('%', '\\%').replace('_', '\\_')
            q = f"%{escaped}%"
            with self._lock:
                rows = self._conn.execute(
                    "SELECT * FROM jobs WHERE LOWER(title) LIKE ? ESCAPE '\\' OR LOWER(company) LIKE ? ESCAPE '\\' LIMIT ?",
                    (q, q, limit),
                ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _build_fts_query(query: str) -> str:
        """Build an FTS5 query from user input.

        Handles multi-word queries by quoting terms and joining with implicit AND.
        Escapes special FTS characters.
        """
        # Remove FTS5 special chars that could cause syntax errors
        cleaned = query.replace('"', '').replace("'", "").replace('*', '').replace('(', '').replace(')', '')
        terms = cleaned.split()
        if not terms:
            return '""'
        # Quote each term for exact matching, join with implicit AND
        quoted = " ".join(f'"{t}"' for t in terms)
        return quoted

    def semantic_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Semantic search using ChromaDB vectors."""
        if self._collection is None:
            return self.search(query=query, limit=limit)
        try:
            results = self._collection.query(
                query_texts=[query], n_results=limit, include=["metadatas", "distances"]
            )
            jobs = []
            if results and results.get("ids") and results["ids"][0]:
                for job_id in results["ids"][0]:
                    job = self.get(job_id)
                    if job:
                        jobs.append(job)
            return jobs
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return self.search(query=query, limit=limit)

    def list_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all jobs."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM jobs ORDER BY cached_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_by_platform(self) -> Dict[str, int]:
        """Job counts by platform."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT platform, COUNT(*) as cnt FROM jobs GROUP BY platform"
            ).fetchall()
        return {r["platform"]: r["cnt"] for r in rows}

    def list_companies(self, limit: int = 20) -> List[tuple]:
        """Top companies by job count."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT company, COUNT(*) as cnt FROM jobs GROUP BY company ORDER BY cnt DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [(r["company"], r["cnt"]) for r in rows]

    # ── Public: Match CRUD ───────────────────────────────────

    def add_match(self, job_id: str, match_result: Dict[str, Any], profile_hash: str = "") -> bool:
        """Store a match result. Returns True if stored."""
        match_key = f"{job_id}:{profile_hash}" if profile_hash else job_id

        # Allow LLM score update over keyword-only
        existing = self.get_match(job_id, profile_hash)
        if existing:
            has_llm_now = match_result.get("llm_score") is not None
            had_llm_before = existing.get("llm_score") is not None
            if had_llm_before or not has_llm_now:
                return False

        match_data = {
            "match_key": match_key,
            "job_id": job_id,
            "profile_hash": profile_hash,
            "keyword_score": match_result.get("keyword_score", 0),
            "llm_score": match_result.get("llm_score"),
            "combined_score": match_result.get("combined_score", match_result.get("match_score", 0)),
            "match_score": match_result.get("match_score", match_result.get("combined_score", 0)),
            "match_level": match_result.get("match_level", "unknown"),
            "toon_report": match_result.get("toon_report", ""),
            "cached_at": datetime.now().isoformat(),
        }
        with self._lock:
            self._insert_match(self._conn.cursor(), match_data)
            self._conn.commit()
        return True

    def get_match(self, job_id: str, profile_hash: str = "") -> Optional[Dict[str, Any]]:
        """Get match result for a job."""
        match_key = f"{job_id}:{profile_hash}" if profile_hash else job_id
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM matches WHERE match_key=?", (match_key,)
            ).fetchone()
            if row:
                return self._row_to_dict(row)
            # Fallback: try without profile hash
            row = self._conn.execute(
                "SELECT * FROM matches WHERE job_id=? ORDER BY cached_at DESC LIMIT 1",
                (job_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def list_matches(self, min_score: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """List matches filtered by score, excluding excluded companies."""
        from .profile_store import get_store
        context = get_store().get_search_context()
        excluded = [c.lower() for c in context.get("excluded_companies", [])]

        with self._lock:
            rows = self._conn.execute(
                """SELECT m.*, j.company FROM matches m
                   JOIN jobs j ON m.job_id = j.id
                   WHERE m.match_score >= ? AND m.match_level != 'excluded'
                   ORDER BY m.match_score DESC LIMIT ?""",
                (min_score, limit * 3),  # over-fetch to account for exclusions
            ).fetchall()

        results = []
        for r in rows:
            company = (r["company"] or "").lower()
            if any(exc in company for exc in excluded):
                continue
            d = self._row_to_dict(r)
            d.pop("company", None)  # remove join column
            results.append(d)
            if len(results) >= limit:
                break
        return results

    def clear_matches(self, job_id: str = None):
        """Clear match cache."""
        with self._lock:
            if job_id:
                self._conn.execute(
                    "DELETE FROM matches WHERE job_id=? OR match_key LIKE ?",
                    (job_id, f"{job_id}:%"),
                )
            else:
                self._conn.execute("DELETE FROM matches")
            self._conn.commit()

    def match_stats(self) -> Dict[str, Any]:
        """Get match statistics."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT match_score, match_level FROM matches"
            ).fetchall()
        if not rows:
            return {"total_matches": 0}

        scores = [r["match_score"] for r in rows]
        levels: Dict[str, int] = {}
        for r in rows:
            lv = r["match_level"]
            levels[lv] = levels.get(lv, 0) + 1

        return {
            "total_matches": len(scores),
            "avg_score": sum(scores) / len(scores),
            "max_score": max(scores),
            "min_score": min(scores),
            "level_distribution": levels,
        }

    # ── Public: Stats ────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            meta_rows = self._conn.execute("SELECT key, value FROM metadata").fetchall()
        meta = {r["key"]: r["value"] for r in meta_rows}

        return {
            "total_jobs": self._count_table("jobs"),
            "total_matches": self._count_table("matches"),
            "match_stats": self.match_stats(),
            "platforms": self.list_by_platform(),
            "top_companies": self.list_companies(10),
            "vector_search": self._collection is not None,
            "vector_count": self._collection.count() if self._collection else 0,
            "cache_dir": str(self.cache_dir),
            "created": meta.get("created"),
            "last_updated": meta.get("last_updated"),
            "total_ever_added": int(meta.get("total_added", 0)),
        }

    def export_csv(self, filepath: Path = None) -> Path:
        """Export jobs to CSV."""
        filepath = filepath or (self.cache_dir / "jobs_export.csv")
        rows = self._conn.execute("SELECT * FROM jobs").fetchall()
        fields = ["id", "title", "company", "location", "salary", "url", "platform", "posted_date", "cached_at"]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
        logger.info(f"📄 Exported {len(rows)} jobs to {filepath}")
        return filepath

    # ── Compat: no-op methods for callers that used to call _save ──

    def _save_jobs(self):
        """No-op. SQLite writes are immediate."""
        pass

    def _save_matches(self):
        """No-op. SQLite writes are immediate."""
        pass

    def flush(self):
        """Explicit commit."""
        with self._lock:
            self._conn.commit()


# ── Global singleton ─────────────────────────────────────────

_cache: Optional[JobCache] = None
_cache_lock = threading.Lock()


def get_cache() -> JobCache:
    """Get or create the global job cache."""
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = JobCache()
    return _cache


# === FunctionTools for agent use ===

try:
    from google.adk.tools import FunctionTool
except ImportError:
    FunctionTool = lambda func: func


def cache_job(
    title: str,
    company: str,
    location: str,
    url: str,
    platform: str = "unknown",
    salary: str = "",
    description: str = "",
) -> dict:
    """Cache a single job listing."""
    cache = get_cache()
    job = {
        "title": title, "company": company, "location": location,
        "url": url, "platform": platform, "salary": salary, "description": description,
    }
    is_new = cache.add(job)
    job_id = cache.generate_id(job)
    return {
        "success": True, "is_new": is_new, "job_id": job_id,
        "message": f"Job {'added' if is_new else 'already exists'}: {title[:40]}",
    }


def search_cached_jobs(
    query: str = "", company: str = "", location: str = "",
    semantic: bool = False, limit: int = 10,
) -> str:
    """Search cached job listings."""
    cache = get_cache()
    if semantic and query:
        jobs = cache.semantic_search(query, limit=limit)
    else:
        jobs = cache.search(query=query, company=company, location=location, limit=limit)

    lines = [
        "[job_search_results]",
        f"query: {query or 'all'}", f"results_found: {len(jobs)}", "", "[jobs]",
    ]
    for i, job in enumerate(jobs, 1):
        lines.append(f"{i}. {job.get('title','?')[:45]}")
        lines.append(f"   company: {job.get('company','?')[:20]}")
        loc = job.get("location", "")
        if loc:
            lines.append(f"   location: {loc[:20]}")
        sal = job.get("salary", "")
        if sal and sal != "Not specified":
            lines.append(f"   salary: {sal}")
        url = job.get("url", "")
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
        f"total_jobs: {stats['total_jobs']}", f"total_matches: {stats['total_matches']}",
        f"vector_count: {stats['vector_count']}", f"cache_dir: {stats['cache_dir']}",
        "", "[platforms]",
    ]
    for platform, count in stats.get("platforms", {}).items():
        lines.append(f"- {platform}: {count}")
    lines.extend(["", "[top_companies]"])
    for company, count in stats.get("top_companies", [])[:10]:
        lines.append(f"- {company}: {count}")
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
    job_id: str, match_score: int, match_level: str,
    toon_report: str = "", profile_hash: str = "",
) -> dict:
    """Cache a job match analysis result."""
    cache = get_cache()
    match_result = {"match_score": match_score, "match_level": match_level, "toon_report": toon_report}
    is_new = cache.add_match(job_id, match_result, profile_hash)
    return {"success": True, "is_new": is_new, "job_id": job_id}


def get_cached_match(job_id: str, profile_hash: str = "") -> dict:
    """Get a cached job match result."""
    match = get_cache().get_match(job_id, profile_hash)
    if match:
        return {"success": True, "found": True, "match": match}
    return {"success": True, "found": False, "message": "No cached match found"}


def list_cached_matches(min_score: int = 0, limit: int = 20) -> str:
    """List cached job matches."""
    cache = get_cache()
    matches = cache.list_matches(min_score=min_score, limit=limit)
    lines = [
        "[cached_matches]", f"min_score_filter: {min_score}%",
        f"matches_found: {len(matches)}", "", "[matches]",
    ]
    for i, m in enumerate(matches, 1):
        job = cache.get(m.get("job_id", ""))
        score = m.get("match_score", 0)
        level = m.get("match_level", "unknown")
        if job:
            lines.append(f"{i}. {score}% - {job.get('title','?')[:40]} @ {job.get('company','?')[:20]}")
        else:
            lines.append(f"{i}. {score}% - job_id: {m.get('job_id', 'unknown')}")
    if not matches:
        lines.append("- no matches found")
    return "\n".join(lines)


def clear_cached_matches(job_id: str = "") -> dict:
    """Clear cached job matches."""
    get_cache().clear_matches(job_id if job_id else None)
    return {"success": True, "message": f"Cleared matches{' for ' + job_id if job_id else ''}"}


def aggregate_job_matches(min_score: int = 0, max_results: int = 50) -> str:
    """Aggregate and analyze all cached job matches."""
    cache = get_cache()
    matches = cache.list_matches(min_score=min_score, limit=max_results)
    if not matches:
        return "[job_match_summary]\nstatus: no matches found"

    scores = [m.get("match_score", 0) for m in matches]
    level_counts: Dict[str, int] = {}
    for m in matches:
        lv = m.get("match_level", "unknown")
        level_counts[lv] = level_counts.get(lv, 0) + 1

    lines = [
        "[job_match_summary]",
        f"total_analyzed: {len(matches)}",
        f"avg_score: {sum(scores)/len(scores):.1f}%",
        f"max_score: {max(scores)}%",
        f"min_score: {min(scores)}%",
        "", "[top_matches]",
    ]
    for i, m in enumerate(matches[:15], 1):
        job = cache.get(m.get("job_id", ""))
        score = m.get("match_score", 0)
        if job:
            lines.append(f"{i}. {score}% - {job.get('title','?')[:40]} @ {job.get('company','?')[:20]}")
    return "\n".join(lines)


# Create FunctionTools
cache_job_tool = FunctionTool(func=cache_job)
search_cached_jobs_tool = FunctionTool(func=search_cached_jobs)
get_cache_stats_tool = FunctionTool(func=get_cache_stats)
clear_job_cache_tool = FunctionTool(func=clear_job_cache)
remove_company_tool = FunctionTool(func=remove_company_from_cache)
cache_job_match_tool = FunctionTool(func=cache_job_match)
get_cached_match_tool = FunctionTool(func=get_cached_match)
list_cached_matches_tool = FunctionTool(func=list_cached_matches)
clear_cached_matches_tool = FunctionTool(func=clear_cached_matches)
aggregate_job_matches_tool = FunctionTool(func=aggregate_job_matches)
