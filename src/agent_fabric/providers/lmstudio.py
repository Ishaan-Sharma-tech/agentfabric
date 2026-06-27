import urllib.request
import json
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from agent_fabric.core.protocols import LLMProvider

logger = logging.getLogger("agent_fabric.providers.lmstudio")

__all__ = ["LMStudioProvider"]


class LMStudioProvider(LLMProvider):
    """
    LM Studio local server LLM Provider implementation (http://localhost:1234/v1).
    """
    def __init__(
        self, 
        base_url: str = "http://localhost:1234/v1",
        default_model: Optional[str] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model or "local-model"

    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": kwargs.get("model", self.default_model),
            "messages": messages,
            "temperature": temperature
        }
        try:
            req = urllib.request.Request(
                url, 
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data["choices"][0]["message"]
                return {
                    "role": "assistant",
                    "content": choice.get("content", ""),
                    "tool_calls": choice.get("tool_calls", [])
                }
        except Exception as e:
            logger.warning(f"LM Studio connection failed or offline: {e}")
            last_msg = messages[-1].get("content", "") if messages else ""
            return {
                "role": "assistant",
                "content": f"LM Studio (Local Server Offline - Fallback): processed '{last_msg}'",
                "tool_calls": []
            }

    async def stream(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        res = await self.chat(messages, tools=tools, temperature=temperature, max_tokens=max_tokens, **kwargs)
        yield res.get("content", "")
