<div align="center">

# 🧠 AgentOS

### The Runtime for AI Agents

**Keep your agent. Keep your framework. AgentOS adds the infrastructure.**

Memory · Tools · Permissions · Observability · Scheduling · Pipelines · Studio

---

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-building_in_public-orange.svg)]()

[Getting Started](#-60-second-quickstart) · [Why AgentOS](#-why-agentos) · [Architecture](#-architecture) · [Roadmap](#-roadmap) · [Contributing](#-contributing)

</div>

---

## What is AgentOS?

AgentOS is an **open-source runtime layer for AI agents**. It's not another agent framework — it's the infrastructure that sits *underneath* any agent and provides everything it needs to be production-ready:

- 🧠 **Memory** — Persistent memory that survives across sessions
- 🔧 **Tools** — Extensible tool system with a dead-simple `@tool` decorator
- 🔐 **Permissions** — Capability-based security (what can this agent do?)
- 📊 **Observability** — Logs, metrics, token usage, execution history
- ⏰ **Scheduling** — Cron jobs, intervals, event triggers
- 🔗 **Pipelines** — DAG-based workflows with parallel execution
- 👥 **Agent Teams** — Multi-agent collaboration out of the box
- 🖥️ **Studio** — Desktop app to manage everything visually
- 🔌 **Plugins** — Gmail, GitHub, Slack, Notion, and more

Think of it this way: **AgentOS is for AI agents what Linux is for software applications.**

---

## ⚡ 60-Second Quickstart

```bash
pip install agent-os
export OPENAI_API_KEY="sk-..."
```

```python
from agent_os import Agent

agent = Agent("researcher")
result = agent.run("What are the top AI trends in 2026?")
print(result.text)
```

**That's it.** Memory works. Tools are available. Logs are captured. Zero config. Zero server. Zero setup.

---

## 🤔 Why AgentOS?

Every AI project rebuilds the same infrastructure:

| What you need | Without AgentOS | With AgentOS |
|---|---|---|
| Memory | Build your own database layer | `agent.memory.search("...")` |
| Tool execution | Write JSON schemas, handle errors | `@tool("Search web") def search(q): ...` |
| Observability | Custom logging, hope for the best | Automatic. Every call logged |
| Scheduling | Cron scripts, background workers | `Schedule(pipeline, cron="0 8 * * *")` |
| Agent teams | Build orchestration from scratch | `Team([agent1, agent2], strategy="sequential")` |
| Permissions | Nothing (pray it doesn't break things) | Capability-based, per-agent controls |
| Management UI | Build a dashboard | AgentOS Studio (desktop app) |

**AgentOS solves this once so you never rebuild it again.**

---

## 🔌 Works With Your Existing Agent

AgentOS doesn't ask you to rewrite anything. Bring your own agent:

### Already have an agent? Enhance it in one line:

```python
from agent_os import enhance

# Your existing agent — raw OpenAI, LangChain, whatever
class MyBot:
    def run(self, task):
        return openai.chat.completions.create(...)

bot = enhance(MyBot(), memory=True, observe=True)
bot.run("Analyze this data")
# Now it has persistent memory, logging, and metrics — zero rewrite
```

### Using LangGraph?

```python
from agent_os.adapters import LangGraphAdapter

agent = LangGraphAdapter(my_langgraph_app)
agent.run("Do research")
# Your LangGraph agent now has AgentOS memory + observability
```

### Just want the memory engine?

```python
from agent_os import memory

memory.store("User prefers dark mode", tags=["preferences"])
results = memory.search("user preferences")
# Use just the parts you need. No lock-in.
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│              YOUR APPLICATION                     │
│  (Personal Assistant, Research AI, Business AI)   │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│           YOUR FRAMEWORK (optional)               │
│  (LangGraph, CrewAI, AutoGen, OpenAI SDK, Raw)   │
└──────────────────┬───────────────────────────────┘
                   │
╔══════════════════▼═══════════════════════════════╗
║                 AgentOS Runtime                   ║
╠══════════════════════════════════════════════════╣
║  🧠 Memory Engine    │  🔧 Tool Runtime          ║
║  📊 Observability    │  🔐 Permissions            ║
║  ⏰ Scheduler        │  🔗 Pipeline Engine        ║
║  💬 EventBus         │  🧩 Plugin System          ║
║  🗂️ Knowledge Graph  │  📦 Skill System           ║
║  🏠 Workspaces       │  🔄 Agent Teams            ║
╚══════════════════════════════════════════════════╝
```

### Key Design Principles

- **Embedded by default** — No server to start. Import and use. The SDK works in-process.
- **Zero config** — Sensible defaults for everything. API keys from env vars. Config files are optional.
- **Progressive complexity** — Simple things are simple. Complex things are possible.
- **À la carte** — Use the full runtime, or just pick the components you need.
- **Framework agnostic** — Works with LangGraph, CrewAI, OpenAI SDK, or no framework at all.

---

## 📚 Usage Examples

### Custom Tools

```python
from agent_os import Agent, tool

@tool("Search the web for information")
def web_search(query: str) -> str:
    # Your search logic here
    return results

@tool("Read a webpage and extract its content")
def read_url(url: str) -> str:
    # Your reading logic here
    return content

agent = Agent("researcher", tools=[web_search, read_url])
result = agent.run("Find the latest papers on quantum computing")
```

### Multi-Agent Teams

```python
from agent_os import Agent, Team

researcher = Agent("researcher", role="Research topics thoroughly")
writer = Agent("writer", role="Write clear, engaging content")
reviewer = Agent("reviewer", role="Review and improve content")

team = Team(
    agents=[researcher, writer, reviewer],
    strategy="sequential"
)

result = team.run("Create a blog post about AI trends")
```

### Scheduled Pipelines

```yaml
# morning-briefing.yaml
name: morning-briefing
nodes:
  - id: scan_news
    type: skill
    skill: research
    inputs: { topic: "Top AI news today" }

  - id: scan_emails
    type: tool
    tool: gmail_read
    inputs: { filter: "is:unread" }

  - id: compile
    type: agent
    agent: writer
    depends_on: [scan_news, scan_emails]
```

```python
from agent_os import Pipeline, Schedule

pipeline = Pipeline.from_yaml("morning-briefing.yaml")
Schedule(pipeline, cron="0 8 * * *")  # Every day at 8 AM
```

---

## 🖥️ AgentOS Studio

A desktop application to manage your entire AI infrastructure visually.

- **Dashboard** — Active agents, pipelines, events, resource usage
- **Agent Manager** — Start, stop, configure, debug agents
- **Memory Explorer** — Search, browse, and visualize the knowledge graph
- **Pipeline Editor** — Visual drag-and-drop DAG editor
- **Plugin Store** — Browse and install integrations
- **Logs** — Real-time event stream and execution history

Built with Tauri + SvelteKit. Lightweight, fast, cross-platform.

> 🚧 Studio is currently under development. Star this repo to follow progress.

---

## 🗺️ Roadmap

| Phase | Timeline | Focus |
|---|---|---|
| **Phase 1** | Weeks 1–6 | Core runtime, memory, tools, CLI, SDK, minimal Studio. The "60-second agent" experience |
| **Phase 2** | Weeks 7–12 | Multi-agent teams, pipeline engine, scheduler, plugin system, framework adapters |
| **Phase 3** | Weeks 13–20 | Registry, community plugins (Gmail, GitHub, Slack), MCP bridge, advanced memory, docs, launch |
| **Phase 4** | Weeks 21+ | AgentOS Cloud, distributed execution, team collaboration, enterprise features |

See [ROADMAP.md](ROADMAP.md) for the detailed plan.

---

## 🧩 Ecosystem

### LLM Providers

| Provider | Status |
|---|---|
| OpenAI (GPT-4o, o3) | 🟢 Phase 1 |
| Ollama (local models) | 🟢 Phase 1 |
| Anthropic (Claude) | 🟡 Phase 2 |
| Google (Gemini) | 🟡 Phase 2 |

### Framework Adapters

| Framework | Status |
|---|---|
| Generic Python (`enhance()`) | 🟢 Phase 1 |
| OpenAI Agents SDK | 🟡 Phase 2 |
| LangGraph | 🟡 Phase 3 |
| CrewAI | 🟡 Phase 3 |

### Plugins

| Plugin | Status |
|---|---|
| GitHub | 🟡 Phase 2 |
| Gmail | 🔵 Phase 3 |
| Slack | 🔵 Phase 3 |
| Notion | 🔵 Phase 3 |
| Calendar | 🔵 Phase 3 |

---

## 🤝 Contributing

AgentOS is building in public and contributions are welcome!

- 🌟 **Star this repo** to follow progress
- 🐛 **Open issues** for bugs or feature requests
- 💡 **Discussions** for ideas and questions
- 🔧 **Pull requests** are welcome

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

---

## 📄 License

AgentOS is licensed under the [Apache License 2.0](LICENSE).

---

<div align="center">

**AgentOS is for AI agents what Linux is for software applications.**

Built with ❤️ for the AI community.

[⭐ Star to follow progress](../../stargazers)

</div>
