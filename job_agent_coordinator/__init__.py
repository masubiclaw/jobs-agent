"""Job Agent Coordinator: Simplified job search system with Ollama."""

import os
import logging
import warnings
from pathlib import Path

from dotenv import load_dotenv

# Suppress Pydantic warnings from LiteLLM
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

# Load .env
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

# Logging setup
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")  # Default to DEBUG for visibility
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Enable LiteLLM verbose logging for model calls
os.environ.setdefault("LITELLM_LOG", "DEBUG")

# Google Cloud defaults
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

LLM_MODEL = os.getenv("LLM_MODEL", "ollama/gemma3:27b")


def _check_ollama():
    """Check Ollama availability."""
    try:
        import httpx
        base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434").rstrip("/")
        resp = httpx.get(f"{base}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            logger.info(f"🦙 Ollama ready: {', '.join(models[:4])}")
            return True
    except:
        pass
    logger.warning("⚠️ Ollama not available")
    return False


def _setup_litellm_logging():
    """Setup LiteLLM callbacks for request/response logging."""
    try:
        import litellm
        
        # Custom callback for logging
        class ModelLogger(litellm.CustomLogger):
            def log_pre_api_call(self, model, messages, kwargs):
                logger.info(f"📤 REQUEST to {model}")
                for msg in messages[-3:]:  # Last 3 messages
                    role = msg.get("role", "?")
                    content = msg.get("content", "")[:200]
                    logger.info(f"   [{role}]: {content}...")
            
            def log_post_api_call(self, model, messages, response, kwargs):
                logger.info(f"📥 RESPONSE from {model}")
                if hasattr(response, 'choices') and response.choices:
                    choice = response.choices[0]
                    if hasattr(choice, 'message'):
                        msg = choice.message
                        content = getattr(msg, 'content', None)
                        tool_calls = getattr(msg, 'tool_calls', None)
                        
                        if content:
                            logger.info(f"   [content]: {content[:300]}...")
                        if tool_calls:
                            for tc in tool_calls[:3]:
                                fn = tc.function
                                logger.info(f"   [tool_call]: {fn.name}({fn.arguments[:100]}...)")
            
            def log_failure(self, model, messages, error, kwargs):
                logger.error(f"❌ ERROR from {model}: {error}")
        
        # Register the callback
        litellm.callbacks = [ModelLogger()]
        litellm.set_verbose = True
        logger.info("✅ LiteLLM logging callbacks registered")
        
    except ImportError:
        logger.warning("⚠️ LiteLLM not available for logging")
    except Exception as e:
        logger.warning(f"⚠️ Could not setup LiteLLM logging: {e}")


logger.info(f"🚀 Job Agent starting (model={LLM_MODEL})")
if LLM_MODEL.startswith("ollama/"):
    _check_ollama()

_setup_litellm_logging()

try:
    from . import agent  # noqa: F401
    logger.info("✅ Job Agent ready")
except ImportError as e:
    logger.warning(f"⚠️ Agent module not loaded (missing dependency): {e}")