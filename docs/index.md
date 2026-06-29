# AgentFabric Documentation 🚀

Welcome to **AgentFabric** — the foundational runtime infrastructure for AI agents, multi-agent teams, workflow pipelines, and enterprise tools.

---

## ⚡ 1. Python SDK (Developer Core)
The primary interface for developers to build, orchestrate, and deploy production agents programmatically in Python.

```python
from agent_fabric import Agent, Team, Pipeline, tool

@tool(name="web_search", description="Search the web")
def web_search(query: str) -> str:
    return f"Results for {query}"

agent = Agent(name="researcher", tools=[web_search])
result = agent.run("Research agent runtime frameworks")
print(result.text)
```

---

## 🛠️ 2. Terminal CLI & Interactive Dashboard
Manage workspaces, run background agents, inspect memories, and monitor live execution with the built-in terminal dashboard.

```bash
agentfabric run "Summarize recent trends"
agentfabric tui
```

---

## 🖥️ 3. AgentFabric Desktop Studio
Lightweight desktop application (powered by Tauri & SvelteKit) providing interactive visual execution DAG graphs, memory inspection, and live telemetry tracking.

```bash
agentfabric studio
```

---

## 🌐 4. REST API & Real-Time WebSockets
Production-ready FastAPI server exposing HTTP routes and `/events` WebSocket streams for frontend integration.

---

## 🔌 5. Ecosystem, Plugins & MCP Bridge
- **Community Plugins**: Gmail, GitHub, Slack, Notion, Calendar.
- **Model Context Protocol (MCP)**: Bidirectional JSON-RPC tool sharing.
- **Framework Adapters**: BYOA wrappers for OpenAI SDK, LangGraph, and CrewAI.

---

## 📖 Quick Navigation
- [SDK Reference](sdk-reference.md)
- [CLI Reference](cli-reference.md)
- [Core Concepts](core-concepts.md)
- [Tutorials](tutorials/01_first_agent.md)
