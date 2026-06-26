import re
import urllib.request
import urllib.parse
from typing import List, Dict
from agent_fabric.tools.decorator import tool


@tool(name="web_search", description="Search the web for current events, news, or general information using DuckDuckGo.")
def web_search(query: str, limit: int = 5) -> str:
    """
    Search the web using DuckDuckGo HTML search.
    Does not require any API keys.
    """
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(
        url, 
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8")
            
        # Parse results using regex to avoid external HTML parsing libraries
        # In DDG HTML:
        # <a class="result__snippet" href="...">Snippet text here...</a>
        # <a class="result__url" href="...">URL here</a>
        # <a class="result__a" href="...">Title here</a>
        
        # Extract matches
        titles = re.findall(r'<a class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        links = re.findall(r'<a class="result__url"[^>]* href="([^"]+)"', html, re.DOTALL)
        
        # Standardize HTML entity decoding
        def clean_html_entities(text: str) -> str:
            text = re.sub(r'<[^>]+>', '', text)  # Strip nested tags if any
            text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&#x27;", "'")
            return text.strip()

        results = []
        for i in range(min(len(titles), len(snippets), limit)):
            title = clean_html_entities(titles[i])
            snippet = clean_html_entities(snippets[i])
            # Links might need decoding or un-redirecting
            link = links[i].strip() if i < len(links) else ""
            if link.startswith("//"):
                link = "https:" + link
            elif "/l/?" in link:
                # DDG redirect link, extract real URL
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
