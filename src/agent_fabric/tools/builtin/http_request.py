import urllib.request
from typing import Optional, Dict
from agent_fabric.tools.decorator import tool

__all__ = ["http_request"]


@tool("Perform generic HTTP API request")
def http_request(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, body: Optional[str] = None) -> str:
    """Executes an HTTP request (GET, POST, PUT, DELETE) and returns response text."""
    try:
        req_headers = headers or {}
        if "User-Agent" not in req_headers:
            req_headers["User-Agent"] = "AgentFabric/1.0"
            
        data_bytes = body.encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method.upper())
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            content = resp.read().decode("utf-8")
            return content[:2000]  # Truncate output to reasonable length
    except Exception as e:
        return f"HTTP request failed: {e}"
