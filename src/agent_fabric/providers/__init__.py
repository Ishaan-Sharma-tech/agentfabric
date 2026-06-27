"""
AgentFabric LLM Provider adapters.
Implements the LLMProvider protocol for OpenAI and Ollama.
"""
from agent_fabric.providers.openai import OpenAIProvider as OpenAIProvider, format_openai_tools as format_openai_tools
from agent_fabric.providers.ollama import OllamaProvider as OllamaProvider

__all__ = ["OpenAIProvider", "OllamaProvider", "format_openai_tools"]
