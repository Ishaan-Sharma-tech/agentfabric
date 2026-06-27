import re
import html
import socket
import ipaddress
import urllib.request
import urllib.parse
from agent_fabric.tools.decorator import tool

__all__ = ["url_reader"]


def _is_private_ip(hostname: str) -> bool:
    """Check if the resolved IP of hostname is private, loopback, or link-local."""
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except Exception:
        # If hostname cannot be resolved, block it to be safe
        return True


@tool(name="url_reader", description="Fetch the contents of a webpage and extract clean plain text. Useful for reading web articles or documentation.")
def url_reader(url: str) -> str:
    """
    Download a URL and parse it to return clean, readable text.
    Strips scripts, styles, and HTML tags. Includes SSRF protection.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return f"Error: Invalid URL scheme '{parsed.scheme}'. Only http and https are allowed."
            
        hostname = parsed.hostname
        if not hostname or _is_private_ip(hostname):
            return f"Error: Access denied. Destination '{hostname}' resolves to a restricted or private network address."
    except Exception as e:
        return f"Error parsing URL '{url}': {e}"
        
    req = urllib.request.Request(
        url, 
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            content_type = response.info().get_content_type() if response.info() else "text/html"
            if content_type and not any(t in content_type for t in ("text/html", "text/plain", "application/xhtml+xml")):
                return f"Unsupported content type: {content_type}. Only html and text pages are supported."
            
            raw_data = response.read()
            html_text = raw_data.decode("utf-8", errors="replace")
            
        # Clean HTML content
        html_text = re.sub(r'<(script|style|head|iframe)[^>]*>.*?</\1>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        html_text = re.sub(r'<!--.*?-->', '', html_text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', html_text)
        
        # Robust HTML entity decoding
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        max_chars = 15000
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n... [Truncated: Page content exceeded {max_chars} characters] ..."
            
        return text
    except Exception as e:
        return f"Failed to read from URL '{url}': {type(e).__name__}: {str(e)}"

