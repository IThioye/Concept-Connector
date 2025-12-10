from prompts.templates import BIAS_SYSTEM, BIAS_USER
from services.ollama_service import ollama
from services.text_formatter import format_llm_output, extract_json
from .logging_config import logger
from typing import Dict, Any


class BiasMonitor:
    async def review(self, payload) -> Dict[str, Any]:
        sys = BIAS_SYSTEM
        usr = BIAS_USER.format(content=payload)
        text = await ollama.agenerate(prompt=usr, system_prompt=sys, temperature=0.2)
        logger.debug("==== RAW BIAS OUTPUT ====")
        logger.debug(text)
        logger.debug("================================")

        # Robust parse (REQUIRES UPDATING BIAS_SYSTEM prompt to output JSON)
        parsed = extract_json(text)
        
        if parsed and isinstance(parsed, dict):
            # ASSUME LLM is prompted to return {"has_bias": boolean, "reasons": ["..."]}
            return {
                "has_bias": parsed.get("has_bias", False),
                "raw": parsed.get("reasons", ["Structured JSON parsed."])
            }
        
        # Naive fallback (retained for backward compatibility if prompt isn't updated)
        return {
            "has_bias": "bias: true" in text.lower().replace(" ", ""),
            "raw": format_llm_output(text, as_list=True)
        }
