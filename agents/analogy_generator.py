from services.ollama_service import ollama
from prompts.templates import ANALOGY_SYSTEM, ANALOGY_USER
from services.text_formatter import format_llm_output


class AnalogyGenerator:
    def generate(self, best_connection, level):
        if not best_connection:
            return []
        sys = ANALOGY_SYSTEM
        usr = ANALOGY_USER.format(connection=best_connection, level=level)
        text = ollama.generate(prompt=usr, system_prompt=sys, temperature=0.8)
        return format_llm_output(text, as_list=True)