import re
import urllib.request
import urllib.parse
from agent_fabric.tools.decorator import tool


@tool(name="url_reader", description="Fetch the contents of a webpage and extract clean plain text. Useful for reading web articles or documentation.")
def url_reader(url: str) -> str:
    """
    Download a URL and parse it to return clean, readable text.
    Strips scripts, styles, and HTML tags.
    """
    # Standardize URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
        
    req = urllib.request.Request(
        url, 
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            content_type = response.info().get_content_type()
            if "text/html" not in content_type and "text/plain" not in content_type:
                return f"Unsupported content type: {content_type}. Only html and text pages are supported."
            
            html = response.read().decode("utf-8", errors="replace")
            
        # Clean HTML content
        # Remove script, style, head, and iframe tags
        html = re.sub(r'<(script|style|head|iframe)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        # Strip all HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Decode HTML entities
        text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&#x27;", "'").replace("&nbsp;", " ")
        # Compress whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Limit return text length to fit in context windows (e.g. max 10000 characters)
        max_chars = 15000
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n... [Truncated: Page content exceeded {max_chars} characters] ..."
            
        return text
    except Exception as e:
        return f"Failed to read from URL '{url}': {type(e).__name__}: {str(e)}"
