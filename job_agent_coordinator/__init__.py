"""Job Agent Coordinator: Multi-agent system for job matching and career optimization."""

import os
import sys
import logging as _logging
from pathlib import Path

# Load .env file from the package directory
from dotenv import load_dotenv

# Find .env file in the project root (parent of this package)
_package_dir = Path(__file__).parent
_project_root = _package_dir.parent
_env_file = _project_root / ".env"

if _env_file.exists():
    load_dotenv(_env_file)

try:
    import google.auth
    _, project_id = google.auth.default()
    if project_id:
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
except Exception:
    # Google auth not configured - agent can still work with API key
    pass

os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

# Import logging config first to set up logging
from .logging_config import (  # noqa: F401
    coordinator_logger, 
    get_current_log_level,
    log_model_response,
    log_model_request,
    log_tool_response,
    enable_model_response_logging,
    ModelResponseCallback,
    model_logger,
)

coordinator_logger.info("")
coordinator_logger.info("=" * 60)
coordinator_logger.info("🚀 JOB AGENT COORDINATOR - Starting up...")
coordinator_logger.info(f"   Log level: {get_current_log_level()}")
coordinator_logger.info(f"   Set JOB_AGENT_LOG_LEVEL=DEBUG for detailed logs")
coordinator_logger.info(f"   Set VERBOSE_MODEL_LOGGING=true for full model responses")
coordinator_logger.info(f"   Set MODEL_RESPONSE_MAX_CHARS=0 for unlimited response display")
coordinator_logger.info("=" * 60)

# =============================================================================
# Model Response Logging - Apply patch EARLY before any imports use BaseLlm
# =============================================================================

VERBOSE_MODEL_LOGGING = os.getenv("VERBOSE_MODEL_LOGGING", "false").lower() == "true"

if VERBOSE_MODEL_LOGGING:
    enable_model_response_logging(verbose=True)
    coordinator_logger.info("📢 Verbose model logging ENABLED")
    
    # Patch Gemini class (the actual LLM implementation used by ADK)
    try:
        from google.adk.models.google_llm import Gemini
        
        _original_generate_async = Gemini.generate_content_async
        
        def _extract_and_log_response(result, model_name):
            """Extract and log response content."""
            text_parts = []
            function_calls = []
            
            # LlmResponse structure - check content.parts
            if hasattr(result, 'content') and result.content:
                content = result.content
                if hasattr(content, 'parts') and content.parts:
                    for part in content.parts:
                        if hasattr(part, 'text') and part.text:
                            text_parts.append(part.text)
                        if hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call
                            fc_name = getattr(fc, 'name', 'unknown')
                            fc_args = dict(fc.args) if hasattr(fc, 'args') and hasattr(fc.args, 'items') else str(getattr(fc, 'args', {}))
                            function_calls.append(f"{fc_name}({fc_args})")
            
            # Also check candidates (Vertex AI structure)
            if hasattr(result, 'candidates') and result.candidates:
                for candidate in result.candidates:
                    if hasattr(candidate, 'content') and candidate.content:
                        content = candidate.content
                        if hasattr(content, 'parts') and content.parts:
                            for part in content.parts:
                                if hasattr(part, 'text') and part.text:
                                    text_parts.append(part.text)
                                if hasattr(part, 'function_call') and part.function_call:
                                    fc = part.function_call
                                    fc_name = getattr(fc, 'name', 'unknown')
                                    fc_args = dict(fc.args) if hasattr(fc, 'args') and hasattr(fc.args, 'items') else str(getattr(fc, 'args', {}))
                                    function_calls.append(f"{fc_name}({fc_args})")
            
            # Direct text attribute
            if not text_parts and hasattr(result, 'text') and result.text:
                text_parts.append(result.text)
            
            # Log text response
            if text_parts:
                log_model_response(
                    agent_name="Gemini",
                    response_text='\n'.join(text_parts),
                    model_name=str(model_name)
                )
            
            # Log function calls
            if function_calls:
                model_logger.info(f"🔧 MODEL FUNCTION CALL [{model_name}]:")
                for fc in function_calls:
                    model_logger.info(f"   → {fc}")
        
        # The original is an async generator function, so we must return an async generator
        async def _patched_generate_async(self, llm_request, stream=False):
            """Patched generate_content_async that logs responses."""
            model_name = getattr(self, 'model', 'unknown')
            
            # Original always returns an async generator - iterate and yield
            async for response in _original_generate_async(self, llm_request, stream):
                try:
                    _extract_and_log_response(response, model_name)
                except Exception as e:
                    model_logger.debug(f"Could not log response: {e}")
                yield response
        
        Gemini.generate_content_async = _patched_generate_async
        coordinator_logger.info("   ✅ Patched Gemini.generate_content_async for response logging")
        
    except Exception as e:
        coordinator_logger.warning(f"   ⚠️ Could not patch Gemini: {e}")
        import traceback
        coordinator_logger.debug(traceback.format_exc())
        
        # Fallback: Enable DEBUG on all ADK loggers
        for name in ['google_llm', 'google.adk', 'google.adk.models', 'google.genai']:
            _logging.getLogger(name).setLevel(_logging.DEBUG)
        coordinator_logger.info("   ℹ️  Enabled DEBUG logging for ADK modules")

else:
    coordinator_logger.info("ℹ️  Model logging: standard (set VERBOSE_MODEL_LOGGING=true for verbose)")

coordinator_logger.info(f"   Log level: {os.getenv('JOB_AGENT_LOG_LEVEL', 'INFO')}")
coordinator_logger.info(f"   Model response max chars: {os.getenv('MODEL_RESPONSE_MAX_CHARS', '500')}")

from . import agent  # noqa: F401

