import markdown
import re
from typing import List, Union


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
