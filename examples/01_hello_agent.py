"""
01_hello_agent.py — Basic single-agent execution in AgentFabric.
"""
from agent_fabric.runtime.agent import Agent

def main():
    agent = Agent(name="hello-agent")
    res = agent.run("Introduce yourself and welcome the user to AgentFabric.")
    print("Agent Output:", res.text)

if __name__ == "__main__":
    main()
