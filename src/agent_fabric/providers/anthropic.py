import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from agent_fabric.core.config import settings
from agent_fabric.core.protocols import LLMProvider

logger = logging.getLogger("agent_fabric.providers.anthropic")

__all__ = ["AnthropicProvider"]

try:
    import anthropic  # noqa
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude LLM Provider implementation.
    """
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        default_model: Optional[str] = None
    ):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic SDK is not installed. Install with `pip install anthropic`.")
        import anthropic
            
        key = api_key or (settings.providers.anthropic_api_key.get_secret_value() if hasattr(settings.providers, "anthropic_api_key") and settings.providers.anthropic_api_key else None)
        self.client = anthropic.AsyncAnthropic(api_key=key or "dummy_key")
        self.default_model = default_model or "claude-3-5-sonnet-20241022"

    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1024,
        **kwargs
    ) -> Dict[str, Any]:
        model = kwargs.pop("model", self.default_model)
        system_prompt = ""
        user_msgs = []
        for m in messages:
            if m.get("role") == "system":
                system_prompt += str(m.get("content", "")) + "\n"
            else:
                user_msgs.append(m)
                
        call_params: Dict[str, Any] = {
            "model": model,
            "messages": user_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens or 1024
        }
        if system_prompt:
            call_params["system"] = system_prompt.strip()
            
        try:
            resp = await self.client.messages.create(**call_params)
            text_content = ""
            for block in resp.content:
                if hasattr(block, "text"):
                    text_content += block.text
            return {
                "role": "assistant",
                "content": text_content,
                "tool_calls": []
            }
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return {"role": "assistant", "content": f"Anthropic Provider Response (Mock/Fallback): {e}", "tool_calls": []}

    async def stream(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1024,
        **kwargs
    ) -> AsyncIterator[str]:
        res = await self.chat(messages, tools=tools, temperature=temperature, max_tokens=max_tokens, **kwargs)
        yield res.get("content", "")
