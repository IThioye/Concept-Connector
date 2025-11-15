from services.ollama_service import ollama
from prompts.templates import EXPLAINER_SYSTEM, EXPLAINER_USER
from services.text_formatter import format_llm_output
from .logging_config import logger


class ExplanationBuilder:
    async def build(self, connection, level, profile=None, guidance: str = "", concept_a: str = "", concept_b: str = ""):
        profile = profile or {}
        sys = EXPLAINER_SYSTEM
        usr = EXPLAINER_USER.format(
            connection=connection,
            level=level,
            guidance=guidance or "Maintain clarity and inclusivity.",
            education_level=profile.get("education_level") or "unspecified",
            education_system=profile.get("education_system") or "unspecified",
            concept_a=concept_a or "Concept A",
            concept_b=concept_b or "Concept B",
            concept_a_knowledge=profile.get("concept_a_knowledge", 0),
            concept_b_knowledge=profile.get("concept_b_knowledge", 0),
        )
        text = await ollama.agenerate(prompt=usr, system_prompt=sys, temperature=0.6)
        # LOG RAW LLM OUTPUT
        logger.debug("==== RAW EXPLANATION BUILDER OUTPUT ====")
        logger.debug(text)
        logger.debug("======================================")

        return format_llm_output(text, as_list=False)
