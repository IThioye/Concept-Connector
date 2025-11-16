import markdown
import re
from typing import List, Union
import json


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


def _to_plain_list(html: str) -> List[str]:
    items = re.findall(r"<li>(.*?)</li>", html, flags=re.IGNORECASE | re.DOTALL)
    if not items:
        stripped = re.sub(r"<[^>]+>", "", html)
        return [segment.strip() for segment in stripped.split("\n") if segment.strip()]
    return [re.sub(r"<[^>]+>", "", item).strip() for item in items if item.strip()]


def format_llm_output(raw_text, as_list=False) -> Union[str, List[str]]:
    """Convert Markdown LLM output into HTML using a proper parser."""

    if not raw_text:
        return [] if as_list else ""

    text = raw_text.strip()

    # Remove filler endings
    text = re.sub(r"Do you want me to.*", "", text, flags=re.IGNORECASE)

    # Convert markdown to HTML
    html = markdown.markdown(
        text,
        extensions=['fenced_code', 'tables', 'nl2br']
    )

    html = html.strip()

    if as_list:
        return _to_plain_list(html)

    return html
