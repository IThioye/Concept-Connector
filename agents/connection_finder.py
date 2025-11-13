from services.ollama_service import ollama
from prompts.templates import CONNECTION_FINDER_SYSTEM, CONNECTION_FINDER_USER
import json
from .logging_config import logger

import json
import re

def extract_json(text):
    """Extract the first JSON object from any LLM output using brace counting."""

    if not text or not isinstance(text, str):
        return None

    # Remove code fences: ```json  ...  ```
    text = re.sub(r"```json", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)

    text = text.strip()

    # Find first '{'
    start = text.find("{")
    if start == -1:
        return None

    # Brace counter to find matching closing '}'
    brace_count = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            brace_count += 1
        elif text[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                json_str = text[start:i+1]
                try:
                    return json.loads(json_str)
                except Exception as e:
                    print("JSON parsing failed:", e)
                    print("Extracted JSON string:", json_str)
                    return None

    # No matching closing brace
    return None



class ConnectionFinder:
    def find(self, concept_a, concept_b, level, ctx):
        sys = CONNECTION_FINDER_SYSTEM.format(level=level)
        usr = CONNECTION_FINDER_USER.format(
            concept_a=concept_a,
            concept_b=concept_b,
            level=level,
            history=ctx.get('history', [])
        )

        raw_text = ollama.generate(prompt=usr, system_prompt=sys, temperature=0.5)

        # Step 1: Parse the outer Ollama response
        try:
            outer = json.loads(raw_text)
            raw_llm = outer.get("response", "").strip()
        except Exception:
            # Sometimes Ollama returns the raw model output directly
            raw_llm = raw_text.strip()

        logger.debug("==== RAW LLM Response FIELD ====")
        logger.debug(raw_llm)
        logger.debug("================================")

        # Step 2: Extract JSON from model output
        parsed = extract_json(raw_llm)

        if parsed is None:
            logger.error("Failed to extract JSON from LLM output")
            logger.error("RAW LLM OUTPUT WAS:\n%s", raw_llm)
            return {
                "path": [concept_a, "bridge concept", concept_b],
                "disciplines": [],
                "strength": 0.5
            }

        # Step 3: Return connections
        return parsed.get("connections", parsed)

