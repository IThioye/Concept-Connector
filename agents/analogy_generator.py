from services.ollama_service import ollama
from prompts.templates import ANALOGY_SYSTEM, ANALOGY_USER
from services.text_formatter import format_llm_output
from .logging_config import logger


class AnalogyGenerator:
    async def generate(self, best_connection, level, guidance: str = ""):
        if not best_connection:
            return []
        sys = ANALOGY_SYSTEM
        usr = ANALOGY_USER.format(connection=best_connection, level=level, guidance=guidance or "Keep analogies inclusive and age-appropriate.")
        text = await ollama.agenerate(prompt=usr, system_prompt=sys, temperature=0.8)
        logger.debug("==== RAW ANALOGY OUTPUT ====")
        logger.debug(text)
        logger.debug("================================")

        return format_llm_output(text, as_list=True)
