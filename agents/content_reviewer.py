import json
from typing import Any, Dict

from prompts.templates import REVIEW_SYSTEM, REVIEW_USER
from services.ollama_service import ollama
from .logging_config import logger


def _safe_json_parse(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Reviewer returned non-JSON payload; falling back to loose parsing")
        # crude fallback: wrap string as issue
        return {
            "level_alignment": False,
            "reading_level": "unknown",
            "issues": [text.strip()],
            "suggested_actions": ["Rewrite to match the requested learner level."],
            "bias_risk": "unknown",
        }


class ContentReviewer:
    async def evaluate(self, bundle: Dict[str, Any], level: str) -> Dict[str, Any]:
        """Ask the reviewer LLM to analyse level-fit and potential bias signals."""

        sys = REVIEW_SYSTEM
        usr = REVIEW_USER.format(level=level, content=json.dumps(bundle, ensure_ascii=False))
        text = await ollama.agenerate(prompt=usr, system_prompt=sys, temperature=0.2)
        logger.debug("==== RAW REVIEWER OUTPUT ====")
        logger.debug(text)
        logger.debug("================================")

        parsed = _safe_json_parse(text)
        # ensure structure consistency
        parsed.setdefault("level_alignment", True)
        parsed.setdefault("reading_level", "unknown")
        parsed.setdefault("issues", [])
        parsed.setdefault("suggested_actions", [])
        parsed.setdefault("bias_risk", "unknown")
        return parsed
