from prompts.templates import BIAS_SYSTEM, BIAS_USER
from services.ollama_service import ollama


class BiasMonitor:
    def review(self, payload):
        sys = BIAS_SYSTEM
        usr = BIAS_USER.format(content=payload)
        text = ollama.generate(prompt=usr, system_prompt=sys, temperature=0.2)
        # naive parse
        return {"has_bias": text.lower().startswith("has_bias:true"), "raw": text}