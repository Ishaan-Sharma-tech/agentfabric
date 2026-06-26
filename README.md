<div align="center">

<img src="https://img.shields.io/badge/AgentFabric-Runtime_for_AI_Agents-000000?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMCIgc3Ryb2tlPSIjZmZmIiBzdHJva2Utd2lkdGg9IjIiLz48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIzIiBmaWxsPSIjZmZmIi8+PC9zdmc+" alt="AgentFabric" />

# AgentFabric

### The Runtime for AI Agents

Memory · Tools · Permissions · Observability · Scheduling · Pipelines · Studio

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)

---

[Getting Started](#-getting-started) · [Core Concepts](#-core-concepts) · [Documentation](#-documentation) · [Architecture](#%EF%B8%8F-architecture) · [Contributing](#-contributing) · [License](#-license)

</div>

---

## Overview

AgentFabric is an open-source runtime layer for AI agents. It provides the foundational infrastructure — memory, tools, permissions, observability, scheduling, pipelines, and a desktop studio — that every agent needs to be production-ready.

AgentFabric is not another agent framework. It does not replace LangGraph, CrewAI, AutoGen, or the OpenAI SDK. It works **alongside** them, providing the infrastructure layer underneath.

```
┌──────────────────────────────────────────────────┐
│                YOUR APPLICATION                   │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│           YOUR FRAMEWORK (optional)               │
│     LangGraph · CrewAI · AutoGen · OpenAI SDK     │
└──────────────────┬───────────────────────────────┘
                   │
╔══════════════════▼═══════════════════════════════╗
║                 AgentFabric Runtime                   ║
║  Memory · Tools · Permissions · Observability     ║
║  Scheduler · Pipelines · EventBus · Plugins       ║
║  Knowledge Graph · Workspaces · Agent Teams       ║
╚══════════════════════════════════════════════════╝
```

---

## ⚡ Getting Started

### Installation

```bash
pip install agent-fabric
```

### Create Your First Agent

```python
from agent_fabric import Agent

agent = Agent("researcher")
result = agent.run("What are the latest breakthroughs in quantum computing?")
print(result.text)
```

No configuration files. No server to start. No database to set up. API keys are read from environment variables.

```bash
export OPENAI_API_KEY="sk-..."
```

---

## 📖 Core Concepts

### Agents

An agent is an autonomous entity that can think, use tools, remember information, and collaborate with other agents.

```python
from agent_fabric import Agent

agent = Agent(
    name="analyst",
    model="gpt-4o",
    system_prompt="You are a data analyst.",
)
result = agent.run("Analyze the trends in this dataset")
```

### Tools

Tools give agents the ability to interact with the outside world. Create custom tools with the `@tool` decorator:

```python
from agent_fabric import Agent, tool

@tool("Search the web for information")
def web_search(query: str) -> str:
    # Your search implementation
    return results

@tool("Read a webpage and extract its content")
def read_url(url: str) -> str:
    # Your implementation
    return content

agent = Agent("researcher", tools=[web_search, read_url])
```

### Memory

Agents automatically persist memory across sessions. You can also use memory directly:

```python
from agent_fabric import memory

memory.store("Project deadline is March 15th", tags=["projects", "deadlines"])
results = memory.search("upcoming deadlines")
```

### Agent Teams

Multiple agents can collaborate on complex tasks:

```python
from agent_fabric import Agent, Team

researcher = Agent("researcher", role="Research topics thoroughly")
writer = Agent("writer", role="Write clear, engaging content")
reviewer = Agent("reviewer", role="Review and improve quality")

team = Team(
    agents=[researcher, writer, reviewer],
    strategy="sequential",
)
result = team.run("Create a comprehensive report on AI infrastructure")
```

### Pipelines

Define multi-step workflows as directed acyclic graphs:

```yaml
# pipeline.yaml
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
from agent_fabric import Pipeline, Schedule

pipeline = Pipeline.from_yaml("pipeline.yaml")

# Run once
pipeline.run()

# Or schedule it
Schedule(pipeline, cron="0 8 * * *")  # Every day at 8 AM
```

### Bring Your Own Agent

Already have an existing agent? Add AgentFabric infrastructure without rewriting it:

```python
from agent_fabric import enhance

# Your existing agent — any Python class
class MyExistingBot:
    def run(self, task):
        return openai.chat.completions.create(...)

bot = enhance(MyExistingBot(), memory=True, observe=True)
bot.run("Analyze this data")
# Now it has persistent memory, logging, and metrics
```

### Framework Adapters

Use AgentFabric with your existing framework:

```python
from agent_fabric.adapters import LangGraphAdapter

agent = LangGraphAdapter(my_langgraph_app)
agent.run("Do research")
# Your LangGraph agent now has AgentFabric memory and observability
```

Adapters are available for OpenAI Agents SDK, LangGraph, and CrewAI.

---

## 🏗️ Architecture

AgentFabric is built as a modular runtime with the following core systems:

| System | Purpose |
|---|---|
| **Agent Runtime** | Agent lifecycle management, execution, state, and multi-agent team coordination |
| **Memory Engine** | Persistent storage with full-text search and optional vector/semantic search |
| **Knowledge Graph** | Structured relationships between entities for contextual understanding |
| **Tool Runtime** | Extensible tool execution with automatic schema generation and permission enforcement |
| **Skill System** | Declarative, composable high-level capabilities that bundle tools, prompts, and workflows |
| **Pipeline Engine** | DAG-based workflow execution with parallel processing, branching, and error handling |
| **Scheduler** | Cron, interval, and event-based scheduling with execution history |
| **Event Bus** | Async message-passing system for inter-component and inter-agent communication |
| **Permissions** | Capability-based security model controlling tool access, memory access, and operations |
| **Observability** | Structured logging, token usage tracking, latency metrics, and execution history |
| **Plugin System** | Package-based extensibility for adding new tools, skills, and integrations |
| **Workspaces** | Isolated environments with independent memory, configuration, and state |

### Design Principles

- **Embedded by default** — The SDK runs in-process. No server, no database setup, no infrastructure to manage.
- **Zero configuration** — Sensible defaults for everything. Configuration files are optional and only needed for customization.
- **Progressive complexity** — Simple use cases require simple code. Advanced capabilities are available when needed.
- **Framework agnostic** — Works with any agent framework or no framework at all.
- **À la carte** — Use the full runtime or individual components independently.
- **Local first** — All data stays on your machine by default. No cloud dependency.

---

## 🖥️ AgentFabric Studio

AgentFabric Studio is a desktop application for managing your AI infrastructure visually.

| Module | Description |
|---|---|
| **Dashboard** | Active agents, running pipelines, events, and resource usage at a glance |
| **Agent Manager** | Start, stop, configure, and debug agents with real-time log streaming |
| **Memory Explorer** | Search, browse, and visualize the knowledge graph |
| **Pipeline Editor** | Visual drag-and-drop DAG editor with live execution status |
| **Plugin Store** | Browse and install integrations |
| **Logs & Observability** | Real-time event stream, execution history, token usage, and performance metrics |

Built with Tauri and SvelteKit for a lightweight, fast, cross-platform experience.

```bash
agentfabric studio
```

---

## 🔌 Ecosystem

### LLM Providers

AgentFabric is model-agnostic. Configure your preferred provider:

| Provider | Package |
|---|---|
| OpenAI (GPT-4o, o3, o4-mini) | `agent-fabric-openai` |
| Anthropic (Claude) | `agent-fabric-anthropic` |
| Google (Gemini) | `agent-fabric-google` |
| Ollama (Local models) | `agent-fabric-ollama` |

### Plugins

Extend AgentFabric with integrations:

| Plugin | Capabilities |
|---|---|
| GitHub | Repository management, PR reviews, issue triage, CI status |
| Gmail | Read, send, search emails; inbox triage; email drafting |
| Slack | Send/read messages, channel digests, standup summaries |
| Notion | Page management, search, meeting notes, knowledge sync |
| Calendar | Events, scheduling, free slot detection, daily agenda |

### MCP Compatibility

AgentFabric supports the [Model Context Protocol](https://modelcontextprotocol.io/):

- **Expose** AgentFabric tools as MCP servers for use in Claude Desktop, Cursor, and other MCP clients
- **Consume** external MCP servers as AgentFabric tools

---

## 🧑‍💻 SDK Reference

### Quick Reference

```python
from agent_fabric import Agent, Team, Pipeline, Schedule
from agent_fabric import tool, memory, enhance
from agent_fabric import Runtime
```

| Import | Purpose |
|---|---|
| `Agent` | Create and run agents |
| `Team` | Multi-agent collaboration |
| `Pipeline` | DAG-based workflows |
| `Schedule` | Automated scheduling |
| `tool` | `@tool` decorator for custom tools |
| `memory` | Direct memory access |
| `enhance` | Add AgentFabric to existing agents |
| `Runtime` | Advanced runtime configuration |

### Runtime Configuration

For advanced use cases, configure the runtime explicitly:

```python
from agent_fabric import Runtime, Agent

runtime = Runtime(
    workspace="my-project",
    provider="anthropic",
    model="claude-sonnet-4",
    memory_backend="qdrant",
)

agent = Agent("analyst", runtime=runtime)
```

### CLI

```bash
agentfabric run "Research AI trends"       # One-shot agent
agentfabric agent start <name>             # Start a persistent agent
agentfabric agent list                     # List running agents
agentfabric memory search "query"          # Search memory
agentfabric pipeline run pipeline.yaml     # Run a pipeline
agentfabric schedule create --cron "..."   # Create a schedule
agentfabric studio                         # Open the Studio
agentfabric plugin list                    # List installed plugins
agentfabric workspace list                 # List workspaces
```

---

## 📖 Documentation

| Resource | Description |
|---|---|
| [Getting Started](docs/getting-started.md) | Installation, first agent, basic concepts |
| [Core Concepts](docs/core-concepts.md) | Agents, tools, memory, teams, pipelines |
| [SDK Reference](docs/sdk-reference.md) | Complete API documentation |
| [CLI Reference](docs/cli-reference.md) | All CLI commands and options |
| [Plugin Development](docs/plugin-development.md) | How to create and publish plugins |
| [Architecture Guide](docs/architecture.md) | System design and internals |
| [API Reference](docs/api-reference.md) | REST and WebSocket API documentation |

---

## 🤝 Contributing

We welcome contributions of all kinds — bug reports, feature requests, documentation improvements, and code contributions.

Please read our [Contributing Guide](CONTRIBUTING.md) for development setup, coding standards, and the contribution process.

---

## 📄 License

AgentFabric is licensed under the [Apache License 2.0](LICENSE).

---

<div align="center">

**AgentFabric — The foundational infrastructure layer for AI-native applications.**

</div>
