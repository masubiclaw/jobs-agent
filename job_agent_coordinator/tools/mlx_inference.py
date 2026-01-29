"""
MLX-LM inference for fine-tuned job matching model.

Uses the fine-tuned LoRA adapter for improved scoring accuracy on Apple Silicon.
Falls back to base model if adapter not found.
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Configuration
MLX_MODEL = os.getenv("MLX_MODEL", "mlx-community/gemma-2-9b-it-4bit")
MLX_ADAPTER_PATH = os.getenv("MLX_ADAPTER_PATH", "models/job-matcher-lora/adapters")
USE_MLX = os.getenv("USE_MLX", "false").lower() == "true"

# Lazy-loaded model
_model = None
_tokenizer = None
_adapter_loaded = False


def is_mlx_available() -> bool:
    """Check if mlx_lm is available."""
    try:
        import mlx_lm
        return True
    except ImportError:
        return False


def _load_model():
    """Lazy load the MLX model and adapter."""
    global _model, _tokenizer, _adapter_loaded
    
    if _model is not None:
        return
    
    try:
        from mlx_lm import load
        
        adapter_path = Path(MLX_ADAPTER_PATH)
        
        if adapter_path.exists():
            logger.info(f"🔧 Loading MLX model with fine-tuned adapter: {adapter_path}")
            _model, _tokenizer = load(MLX_MODEL, adapter_path=str(adapter_path))
            _adapter_loaded = True
        else:
            logger.warning(f"⚠️ Adapter not found at {adapter_path}, using base model")
            _model, _tokenizer = load(MLX_MODEL)
            _adapter_loaded = False
            
        logger.info(f"✅ MLX model loaded (adapter: {_adapter_loaded})")
        
    except Exception as e:
        logger.error(f"❌ Failed to load MLX model: {e}")
        raise


def generate(
    prompt: str,
    max_tokens: int = 400,
    temperature: float = 0.3,
) -> str:
    """
    Generate text using the MLX model.
    
    Args:
        prompt: The input prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
    
    Returns:
        Generated text
    """
    _load_model()
    
    from mlx_lm import generate as mlx_generate
    
    # Pass temperature via sampler or top_p (mlx_lm uses kwargs)
    result = mlx_generate(
        _model,
        _tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        top_p=0.9,
        verbose=False,
    )
    
    return result


def extract_score(text: str) -> Optional[int]:
    """Extract score from generated text."""
    # Try multiple patterns
    patterns = [
        r'score:\s*(\d+)%?',
        r'(\d+)%\s*match',
        r'score\s*[:=]\s*(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            score = int(match.group(1))
            return max(0, min(100, score))
    
    return None


def analyze_job(
    job_title: str,
    company: str,
    job_description: str,
    location: str,
    profile: Dict[str, Any],
    keyword_context: str = "",
) -> Dict[str, Any]:
    """
    Analyze job match using the fine-tuned MLX model.
    
    Args:
        job_title: Job title
        company: Company name
        job_description: Job description text
        location: Job location
        profile: User profile dict
        keyword_context: Optional keyword analysis context
    
    Returns:
        Dict with llm_score, toon_report, llm_success
    """
    # Build the prompt in Gemma chat format
    profile_text = f"""CANDIDATE PROFILE:
- Skills: {', '.join(profile.get('skills', [])[:20])}
- Target Roles: {', '.join(profile.get('target_roles', []))}
- Experience: {profile.get('resume_summary', 'Not provided')[:400]}"""

    desc_truncated = job_description[:4000] if job_description else "No description"
    
    prompt = f"""<start_of_turn>user
Analyze how well this candidate matches the job. Be calibrated - most jobs should score 20-60%.

{profile_text}
{keyword_context}
JOB POSTING:
- Title: {job_title}
- Company: {company}
- Location: {location}

JOB DESCRIPTION:
{desc_truncated}

Provide a score (0-100) and brief assessment in this format:
[llm_analysis]
score: [NUMBER]%
assessment: [2-3 sentences]

[key_strengths]
- [strength 1]
- [strength 2]

[concerns]
- [concern 1]
- [concern 2]

[recommendations]
1. [recommendation]
<end_of_turn>
<start_of_turn>model
[llm_analysis]
score:"""

    try:
        result = generate(prompt, max_tokens=400, temperature=0.3)
        
        # The result should continue from "score:"
        full_response = f"[llm_analysis]\nscore:{result}"
        
        score = extract_score(result)
        if score is None:
            score = 50  # Default if extraction fails
        
        return {
            "llm_score": score,
            "match_level": _determine_level(score),
            "toon_report": full_response,
            "llm_success": True,
            "mlx_adapter": _adapter_loaded,
        }
        
    except Exception as e:
        logger.error(f"❌ MLX inference error: {e}")
        return {
            "llm_score": None,
            "llm_success": False,
            "error": str(e),
        }


def _determine_level(score: int) -> str:
    """Determine match level from score."""
    if score >= 80:
        return "strong"
    elif score >= 60:
        return "good"
    elif score >= 40:
        return "partial"
    return "weak"


# Test function
def test_inference():
    """Test the MLX inference with a sample prompt."""
    if not is_mlx_available():
        print("❌ mlx_lm not available")
        return
    
    print(f"📍 Model: {MLX_MODEL}")
    print(f"📍 Adapter: {MLX_ADAPTER_PATH}")
    print(f"📍 USE_MLX: {USE_MLX}")
    print()
    
    test_profile = {
        "skills": ["Python", "Machine Learning", "TensorFlow"],
        "target_roles": ["ML Engineer", "Software Engineer"],
        "resume_summary": "10+ years in software engineering and ML",
    }
    
    result = analyze_job(
        job_title="Senior Software Engineer",
        company="TechCorp",
        job_description="We're looking for a senior engineer with Python and ML experience...",
        location="Remote",
        profile=test_profile,
    )
    
    print(f"Score: {result.get('llm_score')}%")
    print(f"Success: {result.get('llm_success')}")
    print(f"Adapter loaded: {result.get('mlx_adapter')}")
    print()
    print("Report:")
    print(result.get('toon_report', 'No report'))


if __name__ == "__main__":
    test_inference()
