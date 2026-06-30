import json
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from agent_fabric.core.config import settings
from agent_fabric.core.protocols import LLMProvider

logger = logging.getLogger("agent_fabric.providers.openai")

__all__ = ["format_openai_tools", "OpenAIProvider"]

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


def format_openai_tools(tools: Optional[List[Any]]) -> Optional[List[Dict[str, Any]]]:
    """Helper to transform arbitrary tool representations into OpenAI function formats."""
    if not tools:
        return None
    
    formatted = []
    for t in tools:
        if hasattr(t, "name") and hasattr(t, "parameters"):
            formatted.append({
                "type": "function",
                "function": {
                    "name": getattr(t, "name"),
                    "description": getattr(t, "description", ""),
                    "parameters": getattr(t, "parameters", {})
                }
            })
        elif isinstance(t, dict):
            if "type" in t and t["type"] == "function":
                formatted.append(t)
            elif "name" in t:
                formatted.append({
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters", {"type": "object", "properties": {}})
                    }
                })
            else:
                logger.warning(f"Skipping invalid tool dict missing 'name' or 'type': {t}")
        else:
            logger.warning(f"Skipping unrecognized tool object type: {type(t)}")
    return formatted or None


class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM Provider implementation.
    Integrates with OpenAI's Chat Completion API.
    """
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        default_model: Optional[str] = None
    ):
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI SDK is not installed. Please install it using: "
                "pip install agentfabric-sdk[openai]"
            )
            
        key = api_key or (settings.providers.openai_api_key.get_secret_value() if settings.providers.openai_api_key else None)
        if not key:
            raise ValueError(
                "OpenAI API Key is missing. Please set the OPENAI_API_KEY environment variable "
                "or define it in agentfabric.yaml."
            )
            
        self.client = AsyncOpenAI(api_key=key)
        self.default_model = default_model or settings.providers.openai_model or "gpt-4o-mini"

    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Executes a standard non-streaming chat completion request.
        """
        model = kwargs.pop("model", self.default_model)
        openai_tools = format_openai_tools(tools)
        
        call_params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }
        
        if max_tokens is not None:
            call_params["max_tokens"] = max_tokens
        if openai_tools:
            call_params["tools"] = openai_tools

        logger.debug(f"OpenAI chat request (model={model}): {messages}")
        response = await self.client.chat.completions.create(**call_params)
        message = response.choices[0].message
        
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except Exception as e:
                    logger.warning(f"Failed to parse tool call arguments '{tc.function.arguments}': {e}")
                    args = {}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args
                })
                
        return {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": tool_calls
        }

    async def stream(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Streams the response from OpenAI chat completion.
        Yields chunks with 'content' and 'tool_calls' delta structures.
        """
        model = kwargs.pop("model", self.default_model)
        openai_tools = format_openai_tools(tools)
        
        call_params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }
        
        if max_tokens is not None:
            call_params["max_tokens"] = max_tokens
        if openai_tools:
            call_params["tools"] = openai_tools

        response_stream = await self.client.chat.completions.create(**call_params)
        
        async for chunk in response_stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            
            chunk_data: Dict[str, Any] = {
                "role": "assistant",
                "content": delta.content or "",
                "tool_calls": []
            }
            
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    chunk_data["tool_calls"].append({
                        "index": tc.index,
                        "id": tc.id,
                        "name": tc.function.name if tc.function else None,
                        "arguments": tc.function.arguments if tc.function else None
                    })
                    
            yield chunk_data

