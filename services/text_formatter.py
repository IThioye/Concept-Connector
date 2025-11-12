import markdown
from markdown.extensions import fenced_code, tables
import re

def format_llm_output(raw_text, as_list=False):
    """Convert Markdown LLM output into HTML using a proper parser."""
    
    if not raw_text:
        return ""
    
    text = raw_text.strip()
    
    # Remove filler endings
    text = re.sub(r"Do you want me to.*", "", text, flags=re.IGNORECASE)
    
    # Convert markdown to HTML
    html = markdown.markdown(
        text,
        extensions=['fenced_code', 'tables', 'nl2br']
    )
    
    return html.strip()