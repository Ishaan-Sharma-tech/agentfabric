import json
import uuid
import urllib.request
import urllib.error
import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from agent_fabric.core.config import settings
from agent_fabric.core.protocols import LLMProvider
from agent_fabric.providers.openai import format_openai_tools

logger = logging.getLogger("agent_fabric.providers.ollama")

__all__ = ["OllamaProvider"]


class OllamaProvider(LLMProvider):
    """
    Ollama LLM Provider implementation.
    Allows running local offline models (e.g. Llama 3, Mistral) via Ollama's REST API.
    Zero external dependencies.
    """
    def __init__(
        self, 
        host: Optional[str] = None, 
        default_model: Optional[str] = None,
        timeout: int = 300
    ):
        self.host = host or settings.providers.ollama_host or "http://localhost:11434"
        if self.host.endswith("/"):
            self.host = self.host[:-1]
            
        self.default_model = default_model or settings.providers.ollama_model or "llama3"
        self.timeout = timeout

    def _sync_post(self, path: str, payload: Dict[str, Any]) -> bytes:
        """Helper to run synchronous POST requests to Ollama."""
        url = f"{self.host}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return response.read()

    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Executes a chat completion request to Ollama via thread executor.
        """
        model = kwargs.pop("model", self.default_model)
        openai_tools = format_openai_tools(tools)
        
        options: Dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
            
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options,
            **kwargs
        }
        
        if openai_tools:
            payload["tools"] = openai_tools

        logger.debug(f"Ollama chat request (model={model}) to {self.host}/api/chat: {messages}")
        
        loop = asyncio.get_running_loop()
        try:
            response_bytes = await loop.run_in_executor(
                None, 
                self._sync_post, 
                "/api/chat", 
                payload
            )
            response_json = json.loads(response_bytes.decode("utf-8"))
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Could not connect to Ollama at {self.host}. "
                f"Make sure Ollama is running and accessible: {e}"
            ) from e

        message = response_json.get("message", {})
        
        tool_calls = []
        raw_tool_calls = message.get("tool_calls", [])
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            tool_calls.append({
                "id": f"ollama_{uuid.uuid4().hex[:8]}",
                "name": func.get("name"),
                "arguments": func.get("arguments", {})
            })
            
        return {
            "role": "assistant",
            "content": message.get("content", ""),
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
        Streams response from Ollama API.
        """
        model = kwargs.pop("model", self.default_model)
        options: Dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": options,
            **kwargs
        }
        if tools:
            payload["tools"] = format_openai_tools(tools)

        loop = asyncio.get_running_loop()
        
        def _get_stream():
            url = f"{self.host}/api/chat"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, 
                data=data, 
                headers={"Content-Type": "application/json"}
            )
            return urllib.request.urlopen(req, timeout=self.timeout)

        try:
            response = await loop.run_in_executor(None, _get_stream)
        except urllib.error.URLError as e:
            raise ConnectionError(
                f"Could not connect to Ollama at {self.host}. Make sure Ollama is running: {e}"
            ) from e

        try:
            while True:
                line_bytes = await loop.run_in_executor(None, response.readline)
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8").strip()
                if not line:
                    continue
                data = json.loads(line)
                
                if data.get("done", False):
                    break
                    
                message = data.get("message", {})
                yield {
                    "role": "assistant",
                    "content": message.get("content", ""),
                    "tool_calls": []
                }
        finally:
            response.close()

