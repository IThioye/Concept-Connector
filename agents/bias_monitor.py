from email.mime import text
from prompts.templates import BIAS_SYSTEM, BIAS_USER
from services.ollama_service import ollama
from services.text_formatter import format_llm_output
from .logging_config import logger 

class BiasMonitor:
    def review(self, payload):
        sys = BIAS_SYSTEM
        usr = BIAS_USER.format(content=payload)
        text = ollama.generate(prompt=usr, system_prompt=sys, temperature=0.2)
        logger.debug("==== RAW BIAS OUTPUT ====")
        logger.debug(text)
        logger.debug("================================")

        # naive parse
        return {"has_bias": text.lower().startswith("has_bias:true"), "raw": format_llm_output(text,as_list=True)}