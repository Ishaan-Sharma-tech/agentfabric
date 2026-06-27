import re
import html
import logging
import urllib.request
import urllib.parse
from agent_fabric.tools.decorator import tool

logger = logging.getLogger("agent_fabric.tools.web_search")

__all__ = ["web_search"]


@tool(name="web_search", description="Search the web for current events, news, or general information using DuckDuckGo.")
def web_search(query: str, limit: int = 5) -> str:
    """
    Search the web using DuckDuckGo HTML search.
    Does not require any API keys.
    """
    # Clamp limit parameter
    clean_limit = max(1, min(int(limit), 20))
    
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(
        url, 
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw_html = response.read().decode("utf-8", errors="replace")
            
        titles = re.findall(r'<a class="result__a"[^>]*>(.*?)</a>', raw_html, re.DOTALL)
        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', raw_html, re.DOTALL)
        links = re.findall(r'<a class="result__url"[^>]* href="([^"]+)"', raw_html, re.DOTALL)
        
        if not titles and raw_html:
            logger.warning("DuckDuckGo HTML search layout may have changed or returned captcha.")

        def clean_html_entities(text: str) -> str:
            text = re.sub(r'<[^>]+>', '', text)  # Strip nested tags
            text = html.unescape(text)
            return text.strip()

        results = []
        for i in range(min(len(titles), len(snippets), clean_limit)):
            title = clean_html_entities(titles[i])
            snippet = clean_html_entities(snippets[i])
            link = links[i].strip() if i < len(links) else ""
            if link.startswith("//"):
                link = "https:" + link
            elif "/l/?" in link:
                parsed = urllib.parse.urlparse(link)
                params = urllib.parse.parse_qs(parsed.query)
                if "uddg" in params:
                    link = params["uddg"][0]
                    
            results.append(f"Title: {title}\nLink: {link}\nSnippet: {snippet}\n---")
            
        if not results:
            return f"No results found for query: '{query}'"
            
        return "\n".join(results)
    except Exception as e:
        return f"Error executing search query '{query}': {type(e).__name__}: {str(e)}"

