import json
from typing import Any, Dict

from services.ollama_service import ollama
from prompts.templates import EXPLAINER_SYSTEM, EXPLAINER_USER
from services.text_formatter import format_llm_output, extract_json
from .logging_config import logger


class ExplanationBuilder:
    """Produce explanation and analogies in a single model call."""

    @staticmethod
    def _extract_payload(raw_text: str) -> Dict[str, Any]:
        """Handle Ollama's wrapper JSON and ensure we end up with a dict."""

        if not raw_text:
            return {}

        candidate: Any = raw_text

        if isinstance(raw_text, dict):
            candidate = raw_text.get("response", "")
            if isinstance(candidate, str):
                candidate = candidate.strip()
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    logger.warning("Explanation builder response field was not JSON; using raw text")
                    return {"explanation_markdown": candidate, "analogies": []}
            if "explanation_markdown" in raw_text or "analogies" in raw_text:
                return raw_text
            return {}

        if isinstance(raw_text, str):
            try:
                outer = json.loads(raw_text)
                if isinstance(outer, dict) and "response" in outer:
                    candidate = outer.get("response", "")
                else:
                    candidate = outer
            except json.JSONDecodeError:
                candidate = raw_text

        if isinstance(candidate, str):
            try:
                json_candidate = extract_json(candidate)
                return json_candidate
            except Exception:
                logger.warning("Explanation builder returned non-JSON payload; falling back to text")
                return {"explanation_markdown": candidate, "analogies": []}

        if isinstance(candidate, dict):
            return candidate

        return {}

    @staticmethod
    def _normalise_analogies(raw_analogies: Any) -> list[str]:
        if isinstance(raw_analogies, list):
            return [str(item).strip() for item in raw_analogies if str(item).strip()]
        if isinstance(raw_analogies, str):
            return format_llm_output(raw_analogies, as_list=True)
        return []

    async def build(self, connection, level, profile=None, guidance: str = "", concept_a: str = "", concept_b: str = ""):
        profile = profile or {}
        sys = EXPLAINER_SYSTEM
        usr = EXPLAINER_USER.format(
            connection=connection or {},
            level=level,
            guidance=guidance or "Maintain clarity and inclusivity.",
            education_level=profile.get("education_level") or "unspecified",
            education_system=profile.get("education_system") or "unspecified",
            concept_a=concept_a or "Concept A",
            concept_b=concept_b or "Concept B",
            concept_a_knowledge=profile.get("concept_a_knowledge", 0),
            concept_b_knowledge=profile.get("concept_b_knowledge", 0),
        )
        text = await ollama.agenerate(prompt=usr, system_prompt=sys, temperature=0.45)
        logger.debug("==== RAW EXPLANATION BUILDER OUTPUT ====")
        logger.debug(text)
        logger.debug("======================================")

        payload = self._extract_payload(text)
        explanation_markdown = payload.get("explanation_markdown") or payload.get("explanation") or ""
        analogies = self._normalise_analogies(payload.get("analogies"))

        explanation_html = format_llm_output(explanation_markdown, as_list=False)

        return {
            "explanation": explanation_html,
            "analogies": analogies,
        }
