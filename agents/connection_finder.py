from services.ollama_service import ollama
from prompts.templates import CONNECTION_FINDER_SYSTEM, CONNECTION_FINDER_USER


class ConnectionFinder:
    def find(self, concept_a, concept_b, level, ctx):
        sys = CONNECTION_FINDER_SYSTEM.format(level=level)
        usr = CONNECTION_FINDER_USER.format(concept_a=concept_a, concept_b=concept_b, level=level, history=ctx.get('history', []))
        text = ollama.generate(prompt=usr, system_prompt=sys, temperature=0.5)
        # Expect LLM returns JSON list of paths
        try:
            import json
            data = json.loads(text)
            return data.get("connections") or data
        except Exception:
            # fallback: simple single path structure
            return [{"path": [concept_a, "bridge concept", concept_b], "disciplines": [], "strength": 0.5}]