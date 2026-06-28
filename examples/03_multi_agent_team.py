"""
03_multi_agent_team.py — Multi-agent team with supervisor strategy.
"""
import asyncio
from agent_fabric.runtime.team import Team
from agent_fabric.runtime.agent import Agent

async def main():
    researcher = Agent(name="researcher")
    writer = Agent(name="writer")
    team = Team(agents=[researcher, writer], strategy="supervisor")
    res = await team.run("Draft a report on renewable energy trends")
    print("Team Response:", res.text)

if __name__ == "__main__":
    asyncio.run(main())
