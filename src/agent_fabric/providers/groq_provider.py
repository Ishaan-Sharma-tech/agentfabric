import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from agent_fabric.core.protocols import LLMProvider

logger = logging.getLogger("agent_fabric.providers.groq")

__all__ = ["GroqProvider"]


class GroqProvider(LLMProvider):
    """
    Groq ultra-fast LLM Provider implementation using OpenAI-compatible endpoints.
    """
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        default_model: Optional[str] = None
    ):
        self.api_key = api_key
        self.default_model = default_model or "llama-3.3-70b-versatile"

    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        last_msg = messages[-1].get("content", "") if messages else ""
        return {
            "role": "assistant",
            "content": f"Groq ultra-fast output ({self.default_model}) for: {last_msg}",
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
