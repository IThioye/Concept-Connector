from services.ollama_service import ollama
from prompts.templates import EXPLAINER_SYSTEM, EXPLAINER_USER
from services.text_formatter import format_llm_output
from .logging_config import logger


class ExplanationBuilder:
    async def build(self, connection, level):
        sys = EXPLAINER_SYSTEM
        usr = EXPLAINER_USER.format(connection=connection, level=level)
        text = await ollama.agenerate(prompt=usr, system_prompt=sys, temperature=0.6)
        # LOG RAW LLM OUTPUT
        logger.debug("==== RAW EXPLANATION BUILDER OUTPUT ====")
        logger.debug(text)
        logger.debug("======================================")

        return format_llm_output(text, as_list=False)
