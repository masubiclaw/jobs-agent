"""Centralized LLM request queue with observability.

All Ollama calls are serialized through this queue so we can track
queue depth, wait time, request duration, and success/failure rates.
"""

import asyncio
import enum
import logging
import os
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests as http_requests

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")


class Priority(enum.IntEnum):
    """Lower number = higher priority."""
    USER_INTERACTIVE = 1   # User-initiated doc gen, resume import
    USER_BACKGROUND = 5    # User-triggered matching
    PIPELINE = 10          # Scheduled pipeline background jobs


@dataclass
class RequestMetrics:
    request_type: str
    model: str
    priority: int
    enqueued_at: float
    started_at: float
    finished_at: float
    success: bool
    prompt_len: int = 0
    response_len: int = 0
    error: Optional[str] = None

    @property
    def queue_wait_seconds(self) -> float:
        return round(self.started_at - self.enqueued_at, 2)

    @property
    def duration_seconds(self) -> float:
        return round(self.finished_at - self.started_at, 2)


# Sequence counter for FIFO ordering within same priority
_seq_counter = 0
_seq_lock = threading.Lock()


def _next_seq() -> int:
    global _seq_counter
    with _seq_lock:
        _seq_counter += 1
        return _seq_counter


class LLMQueue:
    """Singleton priority queue for serializing Ollama requests."""

    _instance: Optional["LLMQueue"] = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._queue: asyncio.PriorityQueue = None  # Created in start()
        self._worker_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Metrics
        self._history: deque[RequestMetrics] = deque(maxlen=500)
        self._pending: List[Dict[str, Any]] = []  # Tracks queued items for visibility
        self._current: Optional[Dict[str, Any]] = None  # Currently processing
        self._pending_lock = threading.Lock()
        self._in_flight = 0
        self._total_requests = 0
        self._total_success = 0
        self._total_failures = 0

        logger.info("LLM Queue initialized")

    def start(self):
        """Start the queue worker. Must be called from async context."""
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.PriorityQueue()
        self._worker_task = self._loop.create_task(self._process_loop())
        logger.info("LLM Queue worker started")

    def stop(self):
        """Stop the queue worker."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            self._worker_task = None
        logger.info("LLM Queue worker stopped")

    @property
    def queue_depth(self) -> int:
        if self._queue is None:
            return 0
        return self._queue.qsize()

    async def submit(
        self,
        request_type: str,
        model: str,
        prompt: str,
        options: Dict[str, Any],
        timeout: int = 300,
        priority: Priority = Priority.PIPELINE,
    ) -> str:
        """Submit a request to the queue and wait for the result."""
        future = self._loop.create_future()
        seq = _next_seq()
        pending_entry = {
            "seq": seq,
            "request_type": request_type,
            "model": model,
            "priority": int(priority),
            "priority_name": priority.name if isinstance(priority, Priority) else str(priority),
            "prompt_preview": prompt[:80].replace("\n", " "),
            "enqueued_at": time.time(),
        }
        item = (
            int(priority),
            seq,
            {
                "request_type": request_type,
                "model": model,
                "prompt": prompt,
                "options": options,
                "timeout": timeout,
                "future": future,
                "enqueued_at": time.time(),
                "seq": seq,
            },
        )
        with self._pending_lock:
            self._pending.append(pending_entry)
        await self._queue.put(item)
        logger.info(
            f"LLM queued: type={request_type} model={model} "
            f"priority={priority.name if isinstance(priority, Priority) else priority} depth={self.queue_depth}"
        )
        return await future

    async def _process_loop(self):
        """Worker loop: pull from queue, call Ollama, set result."""
        while True:
            try:
                priority, seq, req = await self._queue.get()
            except asyncio.CancelledError:
                return

            request_type = req["request_type"]
            model = req["model"]
            prompt = req["prompt"]
            options = req["options"]
            timeout = req["timeout"]
            future: asyncio.Future = req["future"]
            enqueued_at = req["enqueued_at"]

            # Move from pending to current
            seq = req.get("seq")
            with self._pending_lock:
                self._pending = [p for p in self._pending if p.get("seq") != seq]
                self._current = {
                    "request_type": request_type,
                    "model": model,
                    "priority": priority,
                    "enqueued_at": enqueued_at,
                    "started_at": time.time(),
                }

            self._in_flight = 1
            self._total_requests += 1
            started_at = time.time()
            wait_time = round(started_at - enqueued_at, 1)

            logger.info(
                f"LLM processing: type={request_type} model={model} "
                f"waited={wait_time}s depth={self.queue_depth}"
            )

            success = False
            error_msg = None
            response_text = ""

            try:
                response_text = await asyncio.to_thread(
                    self._call_ollama, model, prompt, options, timeout
                )
                success = True
                self._total_success += 1
                if not future.done():
                    future.set_result(response_text)
            except Exception as e:
                error_msg = str(e)
                self._total_failures += 1
                if not future.done():
                    future.set_exception(e)
            finally:
                finished_at = time.time()
                self._in_flight = 0
                self._current = None

                metrics = RequestMetrics(
                    request_type=request_type,
                    model=model,
                    priority=priority,
                    enqueued_at=enqueued_at,
                    started_at=started_at,
                    finished_at=finished_at,
                    success=success,
                    prompt_len=len(prompt),
                    response_len=len(response_text),
                    error=error_msg,
                )
                self._history.append(metrics)

                logger.info(
                    f"LLM done: type={request_type} "
                    f"duration={metrics.duration_seconds}s "
                    f"wait={metrics.queue_wait_seconds}s "
                    f"success={success}"
                )

                self._queue.task_done()

    @staticmethod
    def _call_ollama(
        model: str, prompt: str, options: Dict[str, Any], timeout: int
    ) -> str:
        """Make the actual HTTP call to Ollama."""
        url = OLLAMA_BASE_URL.rstrip("/") + "/api/generate"
        resp = http_requests.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": options,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")

    # ── Stats ────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return current queue stats for the dashboard."""
        history = list(self._history)

        # Per-type aggregation
        by_type: Dict[str, Dict[str, Any]] = {}
        for m in history:
            t = m.request_type
            if t not in by_type:
                by_type[t] = {
                    "count": 0,
                    "total_duration": 0.0,
                    "total_wait": 0.0,
                    "successes": 0,
                    "failures": 0,
                }
            by_type[t]["count"] += 1
            by_type[t]["total_duration"] += m.duration_seconds
            by_type[t]["total_wait"] += m.queue_wait_seconds
            if m.success:
                by_type[t]["successes"] += 1
            else:
                by_type[t]["failures"] += 1

        by_type_out = {}
        for t, v in by_type.items():
            c = v["count"]
            by_type_out[t] = {
                "count": c,
                "avg_duration": round(v["total_duration"] / c, 1) if c else 0,
                "avg_wait": round(v["total_wait"] / c, 1) if c else 0,
                "success_rate": round(v["successes"] / c, 3) if c else 0,
            }

        # Recent requests (last 20)
        recent = [
            {
                "type": m.request_type,
                "model": m.model,
                "priority": m.priority,
                "duration": m.duration_seconds,
                "wait": m.queue_wait_seconds,
                "success": m.success,
                "error": m.error,
                "finished_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(m.finished_at)
                ),
            }
            for m in list(self._history)[-20:]
        ]
        recent.reverse()

        all_durations = [m.duration_seconds for m in history]
        all_waits = [m.queue_wait_seconds for m in history]

        # Pending items
        now = time.time()
        with self._pending_lock:
            pending = [
                {
                    "type": p["request_type"],
                    "model": p["model"],
                    "priority": p["priority"],
                    "priority_name": p.get("priority_name", ""),
                    "prompt_preview": p.get("prompt_preview", ""),
                    "waiting_seconds": round(now - p["enqueued_at"], 1),
                }
                for p in self._pending
            ]

        # Current request
        current = None
        if self._current:
            current = {
                "type": self._current["request_type"],
                "model": self._current["model"],
                "priority": self._current["priority"],
                "running_seconds": round(now - self._current["started_at"], 1),
                "waited_seconds": round(
                    self._current["started_at"] - self._current["enqueued_at"], 1
                ),
            }

        return {
            "queue_depth": self.queue_depth,
            "in_flight": self._in_flight,
            "total_requests": self._total_requests,
            "total_success": self._total_success,
            "total_failures": self._total_failures,
            "avg_duration_seconds": round(
                sum(all_durations) / len(all_durations), 1
            )
            if all_durations
            else 0,
            "avg_queue_wait_seconds": round(
                sum(all_waits) / len(all_waits), 1
            )
            if all_waits
            else 0,
            "by_type": by_type_out,
            "recent": recent,
            "pending": pending,
            "current": current,
        }


# ── Singleton + sync bridge ──────────────────────────────────

_queue_instance: Optional[LLMQueue] = None


def get_queue() -> LLMQueue:
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = LLMQueue()
    return _queue_instance


def llm_request(
    request_type: str,
    model: str,
    prompt: str,
    options: Optional[Dict[str, Any]] = None,
    timeout: int = 300,
    priority: Priority = Priority.PIPELINE,
) -> str:
    """Synchronous interface for existing callers.

    Safe to call from worker threads (asyncio.to_thread, FastAPI sync handlers).
    Submits the request to the async queue and blocks until the result is ready.
    """
    # Prevent deadlock: if called from the main thread while an event loop is
    # running, run_coroutine_threadsafe would block the loop forever.
    if threading.current_thread() is threading.main_thread():
        try:
            asyncio.get_running_loop()
            raise RuntimeError(
                "llm_request() cannot be called from the main thread while an "
                "asyncio event loop is running — this would deadlock. "
                "Use 'await queue.submit(...)' or call from a worker thread."
            )
        except RuntimeError as e:
            if "deadlock" in str(e):
                raise
            pass  # No running loop — safe to proceed

    queue = get_queue()

    # If the queue worker hasn't started yet (e.g., called outside API context),
    # fall back to a direct Ollama call.
    if queue._loop is None or queue._worker_task is None:
        logger.warning("LLM Queue not started, calling Ollama directly")
        return LLMQueue._call_ollama(model, prompt, options or {}, timeout)

    future = asyncio.run_coroutine_threadsafe(
        queue.submit(request_type, model, prompt, options or {}, timeout, priority),
        queue._loop,
    )
    # Extra margin for queue wait time
    return future.result(timeout=timeout + 60)
