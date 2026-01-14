"""Logging configuration for Job Agent Coordinator observability."""

import logging
import os
import sys
import json
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional

# =============================================================================
# Logging Configuration
# =============================================================================

# Log level from environment variable (default: INFO)
LOG_LEVEL = os.getenv("JOB_AGENT_LOG_LEVEL", "INFO").upper()

# Model response logging (set to DEBUG to see full responses, INFO for truncated)
MODEL_RESPONSE_LOG_LEVEL = os.getenv("MODEL_RESPONSE_LOG_LEVEL", "INFO").upper()

# Max characters to show in model responses (0 = unlimited)
MODEL_RESPONSE_MAX_CHARS = int(os.getenv("MODEL_RESPONSE_MAX_CHARS", "500"))

# Log format options
DETAILED_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
)
SIMPLE_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"

# Use detailed format for DEBUG, simple for others
LOG_FORMAT = DETAILED_FORMAT if LOG_LEVEL == "DEBUG" else SIMPLE_FORMAT

# Configure root logger
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Create loggers for each component
def get_logger(name: str) -> logging.Logger:
    """Get a logger for a component."""
    logger = logging.getLogger(f"job_agent.{name}")
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    return logger


# Component loggers
coordinator_logger = get_logger("coordinator")
profile_logger = get_logger("profile_analyst")
resume_logger = get_logger("resume_designer")
application_logger = get_logger("application_designer")
job_search_logger = get_logger("job_searcher")
posting_logger = get_logger("posting_analyst")
market_logger = get_logger("market_analyst")
company_logger = get_logger("company_researcher")
history_logger = get_logger("history_manager")
mcp_logger = get_logger("mcp_tools")
vector_logger = get_logger("vector_store")
model_logger = get_logger("model_response")


# =============================================================================
# Model Response Logging
# =============================================================================

def truncate_text(text: str, max_chars: int = None) -> str:
    """Truncate text for logging display."""
    if max_chars is None:
        max_chars = MODEL_RESPONSE_MAX_CHARS
    if max_chars == 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + f"... [truncated, {len(text)} total chars]"


def log_model_response(
    agent_name: str,
    response_text: str,
    model_name: str = "",
    token_count: int = None,
    duration_ms: float = None
):
    """
    Log a model response with formatting and optional truncation.
    
    Set environment variables to control behavior:
    - MODEL_RESPONSE_LOG_LEVEL: INFO (default) or DEBUG
    - MODEL_RESPONSE_MAX_CHARS: 500 (default), 0 for unlimited
    """
    # Build header
    header_parts = [f"🤖 MODEL RESPONSE from {agent_name}"]
    if model_name:
        header_parts.append(f"[{model_name}]")
    if token_count:
        header_parts.append(f"({token_count} tokens)")
    if duration_ms:
        header_parts.append(f"({duration_ms:.0f}ms)")
    
    header = " ".join(header_parts)
    
    # Log header
    model_logger.info(header)
    
    # Log response content
    if response_text:
        display_text = truncate_text(response_text.strip())
        
        # Format multiline responses
        lines = display_text.split('\n')
        if len(lines) > 1:
            model_logger.info("   ┌" + "─" * 58)
            for line in lines[:20]:  # Limit to 20 lines
                model_logger.info(f"   │ {line}")
            if len(lines) > 20:
                model_logger.info(f"   │ ... [{len(lines) - 20} more lines]")
            model_logger.info("   └" + "─" * 58)
        else:
            model_logger.info(f"   → {display_text}")
    else:
        model_logger.info("   → [empty response]")


def log_model_request(
    agent_name: str,
    prompt_summary: str = "",
    model_name: str = "",
    tools: list = None
):
    """Log outgoing model request."""
    model_logger.info(f"📤 MODEL REQUEST from {agent_name}" + 
                      (f" [{model_name}]" if model_name else ""))
    if prompt_summary:
        model_logger.info(f"   Prompt: {truncate_text(prompt_summary, 150)}")
    if tools:
        tool_names = [t if isinstance(t, str) else getattr(t, 'name', str(t)) for t in tools[:5]]
        model_logger.debug(f"   Tools available: {', '.join(tool_names)}")


def log_tool_response(
    agent_name: str,
    tool_name: str,
    response: Any,
    duration_ms: float = None
):
    """Log a tool call response."""
    duration_str = f" ({duration_ms:.0f}ms)" if duration_ms else ""
    model_logger.info(f"🔧 TOOL RESPONSE for {agent_name}: {tool_name}{duration_str}")
    
    # Format response based on type
    if isinstance(response, dict):
        if 'error' in response:
            model_logger.warning(f"   ⚠️ Error: {response['error']}")
        else:
            # Pretty print dict
            try:
                formatted = json.dumps(response, indent=2, default=str)
                display = truncate_text(formatted, 300)
                model_logger.info(f"   → {display}")
            except:
                model_logger.info(f"   → {truncate_text(str(response), 300)}")
    elif isinstance(response, list):
        model_logger.info(f"   → List with {len(response)} items")
        if response and len(response) > 0:
            first_item = truncate_text(str(response[0]), 200)
            model_logger.debug(f"   First item: {first_item}")
    else:
        model_logger.info(f"   → {truncate_text(str(response), 300)}")


# =============================================================================
# Logging Decorators
# =============================================================================

def log_agent_call(logger: logging.Logger):
    """Decorator to log agent tool calls."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            func_name = func.__name__
            
            # Log entry
            logger.info(f"🔧 TOOL CALL: {func_name}")
            if kwargs:
                # Filter out large content for cleaner logs
                safe_kwargs = {
                    k: (v[:100] + "..." if isinstance(v, str) and len(v) > 100 else v)
                    for k, v in kwargs.items()
                }
                logger.debug(f"   Parameters: {safe_kwargs}")
            
            try:
                result = func(*args, **kwargs)
                
                # Log success
                if isinstance(result, dict):
                    if result.get("success"):
                        logger.info(f"   ✅ Success: {result.get('message', 'completed')}")
                    elif result.get("found") is not None:
                        status = "found" if result.get("found") else "not found"
                        logger.info(f"   📋 Result: {status}")
                    elif result.get("count") is not None:
                        logger.info(f"   📊 Found {result.get('count')} results")
                    else:
                        logger.debug(f"   Result: {str(result)[:200]}")
                
                return result
                
            except Exception as e:
                logger.error(f"   ❌ Error in {func_name}: {e}")
                raise
        
        return wrapper
    return decorator


def log_mcp_call(func: Callable) -> Callable:
    """Decorator to log MCP tool calls."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        func_name = func.__name__
        mcp_logger.info(f"🌐 MCP: {func_name}")
        
        try:
            result = func(*args, **kwargs)
            if result:
                mcp_logger.info(f"   ✅ MCP toolset loaded")
            else:
                mcp_logger.warning(f"   ⚠️ MCP toolset not available")
            return result
        except Exception as e:
            mcp_logger.error(f"   ❌ MCP error: {e}")
            return None
    
    return wrapper


# =============================================================================
# Agent Lifecycle Logging
# =============================================================================

class AgentObserver:
    """Observer for logging agent lifecycle events."""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = get_logger(agent_name)
        self.start_time = None
    
    def on_start(self, query: str = ""):
        """Log when agent starts processing."""
        self.start_time = datetime.now()
        self.logger.info(f"▶️  AGENT START: {self.agent_name}")
        if query:
            truncated = query[:150] + "..." if len(query) > 150 else query
            self.logger.info(f"   Query: {truncated}")
    
    def on_thinking(self, thought: str = ""):
        """Log agent thinking/reasoning."""
        self.logger.debug(f"🤔 THINKING: {thought[:200] if thought else 'processing...'}")
    
    def on_tool_use(self, tool_name: str, params: dict = None):
        """Log when agent uses a tool."""
        self.logger.info(f"🔧 USING TOOL: {tool_name}")
        if params:
            safe_params = {
                k: (str(v)[:50] + "..." if len(str(v)) > 50 else v)
                for k, v in params.items()
            }
            self.logger.debug(f"   Params: {safe_params}")
    
    def on_sub_agent_call(self, sub_agent_name: str):
        """Log when coordinator calls a sub-agent."""
        self.logger.info(f"📤 DELEGATING TO: {sub_agent_name}")
    
    def on_result(self, result_summary: str = ""):
        """Log agent result."""
        duration = ""
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            duration = f" ({elapsed:.2f}s)"
        
        self.logger.info(f"✅ AGENT COMPLETE: {self.agent_name}{duration}")
        if result_summary:
            self.logger.debug(f"   Result: {result_summary[:200]}")
    
    def on_error(self, error: str):
        """Log agent error."""
        self.logger.error(f"❌ AGENT ERROR: {self.agent_name} - {error}")


# =============================================================================
# Workflow Logging
# =============================================================================

def log_workflow_start(workflow_name: str, steps: list[str] = None):
    """Log the start of a multi-step workflow."""
    coordinator_logger.info(f"")
    coordinator_logger.info(f"{'='*60}")
    coordinator_logger.info(f"🚀 WORKFLOW START: {workflow_name}")
    if steps:
        coordinator_logger.info(f"   Steps: {' → '.join(steps)}")
    coordinator_logger.info(f"{'='*60}")


def log_workflow_step(step_num: int, total_steps: int, step_name: str):
    """Log a workflow step."""
    coordinator_logger.info(f"")
    coordinator_logger.info(f"📍 STEP {step_num}/{total_steps}: {step_name}")


def log_workflow_complete(workflow_name: str, duration_seconds: float = None):
    """Log workflow completion."""
    duration = f" in {duration_seconds:.2f}s" if duration_seconds else ""
    coordinator_logger.info(f"")
    coordinator_logger.info(f"{'='*60}")
    coordinator_logger.info(f"🎉 WORKFLOW COMPLETE: {workflow_name}{duration}")
    coordinator_logger.info(f"{'='*60}")


# =============================================================================
# Session Logging
# =============================================================================

def log_session_start(session_id: str, user_id: str = ""):
    """Log session start."""
    coordinator_logger.info(f"")
    coordinator_logger.info(f"{'#'*60}")
    coordinator_logger.info(f"👤 SESSION START")
    coordinator_logger.info(f"   Session ID: {session_id}")
    if user_id:
        coordinator_logger.info(f"   User ID: {user_id}")
    coordinator_logger.info(f"{'#'*60}")


def log_user_message(message: str):
    """Log user message."""
    truncated = message[:200] + "..." if len(message) > 200 else message
    coordinator_logger.info(f"")
    coordinator_logger.info(f"💬 USER: {truncated}")


def log_agent_response(response: str, agent_name: str = ""):
    """Log agent response with full formatting."""
    # Use model response logger for detailed output
    log_model_response(
        agent_name=agent_name or "Coordinator",
        response_text=response,
    )


# =============================================================================
# Performance Logging
# =============================================================================

class PerformanceTimer:
    """Context manager for timing operations."""
    
    def __init__(self, operation_name: str, logger: logging.Logger = None):
        self.operation_name = operation_name
        self.logger = logger or coordinator_logger
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"⏱️  START: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if exc_type:
            self.logger.error(f"⏱️  FAILED: {self.operation_name} ({elapsed:.2f}s) - {exc_val}")
        else:
            self.logger.debug(f"⏱️  DONE: {self.operation_name} ({elapsed:.2f}s)")
        return False


# =============================================================================
# Utility Functions
# =============================================================================

def set_log_level(level: str):
    """Change log level at runtime."""
    level_obj = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger().setLevel(level_obj)
    for handler in logging.getLogger().handlers:
        handler.setLevel(level_obj)
    coordinator_logger.info(f"Log level changed to: {level.upper()}")


def get_current_log_level() -> str:
    """Get current log level."""
    return logging.getLevelName(logging.getLogger().level)


# =============================================================================
# ADK Response Callback (for automatic logging)
# =============================================================================

class ModelResponseCallback:
    """
    Callback class for capturing and logging model responses.
    
    Can be integrated with ADK's event system or used manually.
    
    Usage:
        callback = ModelResponseCallback("my_agent")
        # Called automatically or manually when model responds
        callback.on_response("Model output here", model="gemini-2.5-pro")
    """
    
    def __init__(self, agent_name: str, log_requests: bool = True):
        self.agent_name = agent_name
        self.log_requests = log_requests
        self.request_count = 0
        self.response_count = 0
        self.total_tokens = 0
        self.logger = get_logger(f"callback.{agent_name}")
    
    def on_request(self, prompt: str = "", model: str = "", tools: list = None):
        """Called before sending request to model."""
        self.request_count += 1
        if self.log_requests:
            log_model_request(
                agent_name=self.agent_name,
                prompt_summary=prompt,
                model_name=model,
                tools=tools
            )
    
    def on_response(
        self, 
        response_text: str, 
        model: str = "", 
        token_count: int = None,
        duration_ms: float = None
    ):
        """Called when model response is received."""
        self.response_count += 1
        if token_count:
            self.total_tokens += token_count
        
        log_model_response(
            agent_name=self.agent_name,
            response_text=response_text,
            model_name=model,
            token_count=token_count,
            duration_ms=duration_ms
        )
    
    def on_tool_call(self, tool_name: str, args: dict = None):
        """Called when model requests a tool call."""
        model_logger.info(f"🔧 TOOL CALL from {self.agent_name}: {tool_name}")
        if args:
            safe_args = {
                k: truncate_text(str(v), 100) for k, v in args.items()
            }
            model_logger.debug(f"   Args: {json.dumps(safe_args)}")
    
    def on_tool_result(self, tool_name: str, result: Any, duration_ms: float = None):
        """Called when tool returns result."""
        log_tool_response(
            agent_name=self.agent_name,
            tool_name=tool_name,
            response=result,
            duration_ms=duration_ms
        )
    
    def get_stats(self) -> dict:
        """Get callback statistics."""
        return {
            "agent_name": self.agent_name,
            "request_count": self.request_count,
            "response_count": self.response_count,
            "total_tokens": self.total_tokens
        }


# Pre-built callbacks for main agents
coordinator_callback = ModelResponseCallback("coordinator")
profile_callback = ModelResponseCallback("profile_analyst")
application_callback = ModelResponseCallback("application_designer")
job_search_callback = ModelResponseCallback("job_searcher")
analysis_callback = ModelResponseCallback("analysis_synthesizer")


# =============================================================================
# Enable verbose model logging (helper function)
# =============================================================================

def enable_model_response_logging(verbose: bool = True):
    """
    Enable or disable detailed model response logging.
    
    Args:
        verbose: If True, shows full model responses. If False, shows truncated.
    """
    global MODEL_RESPONSE_MAX_CHARS
    if verbose:
        MODEL_RESPONSE_MAX_CHARS = 0  # Unlimited
        model_logger.setLevel(logging.DEBUG)
        coordinator_logger.info("📢 Model response logging: VERBOSE (full responses)")
    else:
        MODEL_RESPONSE_MAX_CHARS = 500
        model_logger.setLevel(logging.INFO)
        coordinator_logger.info("📢 Model response logging: NORMAL (truncated)")

