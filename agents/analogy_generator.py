from services.ollama_service import ollama
from prompts.templates import ANALOGY_SYSTEM, ANALOGY_USER
from services.text_formatter import format_llm_output
from .logging_config import logger


class AnalogyGenerator:
    async def generate(self, best_connection, level, profile=None, guidance: str = "", concept_a: str = "", concept_b: str = ""):
        if not best_connection:
            return []
        profile = profile or {}
        sys = ANALOGY_SYSTEM
        usr = ANALOGY_USER.format(
            connection=best_connection,
            level=level,
            guidance=guidance or "Keep analogies inclusive and age-appropriate.",
            education_level=profile.get("education_level") or "unspecified",
            education_system=profile.get("education_system") or "unspecified",
            concept_a=concept_a or "Concept A",
            concept_b=concept_b or "Concept B",
            concept_a_knowledge=profile.get("concept_a_knowledge", 0),
            concept_b_knowledge=profile.get("concept_b_knowledge", 0),
        )
        text = await ollama.agenerate(prompt=usr, system_prompt=sys, temperature=0.8)
        logger.debug("==== RAW ANALOGY OUTPUT ====")
        logger.debug(text)
        logger.debug("================================")

        return format_llm_output(text, as_list=True)
