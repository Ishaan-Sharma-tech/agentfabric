"""
02_byoa_wrapper.py — Bring Your Own Agent (BYOA) wrapper example.
"""
import asyncio
from agent_fabric.adapters.generic import GenericAgentAdapter

class CustomLegacyAgent:
    def run(self, prompt: str) -> str:
        return f"Legacy Agent processed: {prompt}"

async def main():
    legacy_agent = CustomLegacyAgent()
    adapter = GenericAgentAdapter(target_agent=legacy_agent, name="legacy_adapter", memory=False, observe=False)
    res = await adapter.run("Analyze Q3 metrics")
    print("Adapted BYOA Output:", res.text)

if __name__ == "__main__":
    asyncio.run(main())
