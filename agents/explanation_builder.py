from services.ollama_service import ollama
from prompts.templates import EXPLAINER_SYSTEM, EXPLAINER_USER
from services.text_formatter import format_llm_output

class ExplanationBuilder:
    def build(self, connection, level):
        sys = EXPLAINER_SYSTEM
        usr = EXPLAINER_USER.format(connection=connection, level=level)
        text = ollama.generate(prompt=usr, system_prompt=sys, temperature=0.6)
        return format_llm_output(text, as_list=False)