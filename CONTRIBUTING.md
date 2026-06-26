# Contributing to AgentFabric

Thank you for your interest in contributing to AgentFabric! This document provides guidelines and instructions for contributing.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Commit Conventions](#commit-conventions)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Plugin Development](#plugin-development)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code. Please report unacceptable behavior by opening an issue.

---

## How to Contribute

There are many ways to contribute to AgentFabric:

- **Report bugs** — Open an issue describing the bug, steps to reproduce, and expected behavior
- **Suggest features** — Open an issue describing the feature and its use case
- **Improve documentation** — Fix typos, add examples, clarify explanations
- **Write code** — Fix bugs, implement features, improve performance
- **Create plugins** — Build integrations for new services and tools
- **Write tests** — Improve test coverage and add edge case tests

---

## Development Setup

### Prerequisites

- **Python 3.11+**
- **uv** (Python package manager) — [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- **Node.js 18+** and **pnpm** (for Studio development only)
- **Rust** (for Studio/Tauri development only)
- **Git**

### Clone the Repository

```bash
git clone https://github.com/Ishaan-Sharma-tech/agent-fabric.git
cd agent-fabric
```

### Install Dependencies

```bash
# Create virtual environment and install all dependencies
uv sync

# Install with development dependencies
uv sync --dev
```

### Run Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ -v --cov=agent_fabric --cov-report=html

# Run a specific test file
uv run pytest tests/test_agent.py -v
```

### Lint and Type Check

```bash
# Linting
uv run ruff check src/

# Auto-fix linting issues
uv run ruff check src/ --fix

# Type checking
uv run mypy src/
```

### Studio Development (Tauri + SvelteKit)

```bash
cd studio

# Install frontend dependencies
pnpm install

# Start development server
pnpm tauri dev
```

---

## Project Structure

```
agent-fabric/
├── src/agent_fabric/           # Main Python package
│   ├── core/               # EventBus, config, models, permissions, protocols
│   ├── runtime/            # Agent lifecycle, enhance(), teams, execution
│   ├── memory/             # Memory engine, SQLite, FTS, vector search, knowledge graph
│   ├── tools/              # @tool decorator, tool runtime, registry, builtins
│   ├── skills/             # Skill loader, executor, built-in skills
│   ├── pipelines/          # DAG engine, node types, pipeline executor
│   ├── scheduler/          # APScheduler wrapper, triggers
│   ├── plugins/            # Plugin discovery, manifest, lifecycle
│   ├── adapters/           # Framework adapters (OpenAI, LangGraph, CrewAI)
│   ├── observability/      # Logging, metrics, event store
│   ├── server/             # FastAPI server (REST + WebSocket)
│   └── cli/                # Typer CLI commands
│
├── providers/              # LLM provider packages (separate installs)
│   ├── agent-fabric-openai/
│   ├── agent-fabric-anthropic/
│   ├── agent-fabric-google/
│   └── agent-fabric-ollama/
│
├── plugins/                # Official plugin packages (separate installs)
│   ├── agent-fabric-plugin-github/
│   ├── agent-fabric-plugin-gmail/
│   ├── agent-fabric-plugin-slack/
│   ├── agent-fabric-plugin-notion/
│   └── agent-fabric-plugin-calendar/
│
├── studio/                 # Tauri + SvelteKit desktop app
├── docs/                   # Documentation
├── examples/               # Example agents, tools, pipelines
└── tests/                  # Unit and integration tests
```

---

## Coding Standards

### Python

- **Style**: Follow [PEP 8](https://peps.python.org/pep-0008/). Enforced by [Ruff](https://docs.astral.sh/ruff/).
- **Type hints**: All public functions and methods must have type annotations. Enforced by [mypy](https://mypy-lang.org/).
- **Docstrings**: Use [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for all public classes, methods, and functions.
- **Models**: Use Pydantic v2 for all data models and configuration.
- **Async**: Use `async/await` for I/O operations. Agents and tools should be async by default.
- **Testing**: Write tests for all new functionality. Target 80%+ code coverage.
- **Imports**: Use absolute imports from `agent_fabric`.

```python
# Good
from agent_fabric.core.models import AgentConfig
from agent_fabric.tools.decorator import tool

# Avoid
from .models import AgentConfig
```

### TypeScript (Studio)

- **Style**: Follow the project ESLint configuration.
- **Framework**: SvelteKit with TypeScript.
- **Styling**: TailwindCSS with shadcn-svelte components.
- **State**: Svelte stores for client-side state management.

### General

- Keep functions small and focused.
- Prefer composition over inheritance.
- Write self-documenting code. Add comments only for non-obvious logic.
- Handle errors explicitly. Never silently swallow exceptions.
- All public APIs must maintain backward compatibility within a major version.

---

## Commit Conventions

We use [Conventional Commits](https://www.conventionalcommits.org/) for clear, structured commit history.

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Description |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Code style changes (formatting, no logic change) |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `build` | Build system or dependency changes |
| `ci` | CI/CD configuration changes |
| `chore` | Other changes that don't modify src or test files |

### Scopes

Use the module name as scope: `core`, `runtime`, `memory`, `tools`, `skills`, `pipelines`, `scheduler`, `plugins`, `adapters`, `observability`, `server`, `cli`, `studio`, `docs`.

### Examples

```bash
feat(runtime): add supervisor strategy for agent teams
fix(memory): handle SQLite concurrent write errors
docs(readme): add pipeline YAML examples
test(tools): add tests for @tool decorator with async functions
refactor(core): simplify EventBus subscription handling
```

---

## Pull Request Process

### Before Submitting

1. **Create an issue first** for significant changes. Discuss the approach before writing code.
2. **Fork the repository** and create a branch from `main`.
3. **Branch naming**: `feat/description`, `fix/description`, `docs/description`.
4. **Write tests** for any new functionality.
5. **Run the full test suite** and ensure all tests pass.
6. **Run linting and type checking** and fix any issues.
7. **Update documentation** if your change affects public APIs.

### Submitting

1. Push your branch to your fork.
2. Open a pull request against `main`.
3. Fill out the PR template completely.
4. Link related issues using `Closes #123` or `Fixes #123`.

### Review Criteria

- All CI checks pass (tests, lint, type check).
- Code follows the project's coding standards.
- New functionality has appropriate test coverage.
- Documentation is updated where applicable.
- The change is backward compatible (or breaking changes are clearly documented).
- Commit messages follow conventional commits.

### After Merge

- Your contribution will be included in the next release.
- You will be credited in the release notes.

---

## Issue Guidelines

### Bug Reports

Include:
- **Description**: Clear description of the bug.
- **Steps to reproduce**: Minimal code or commands to reproduce.
- **Expected behavior**: What should happen.
- **Actual behavior**: What actually happens.
- **Environment**: Python version, OS, AgentFabric version.
- **Logs/Errors**: Relevant error messages or stack traces.

### Feature Requests

Include:
- **Description**: Clear description of the feature.
- **Use case**: Why you need this feature and how you would use it.
- **Proposed API**: How you envision the feature being used (code examples).
- **Alternatives**: Other approaches you've considered.

---

## Plugin Development

Plugins extend AgentFabric with new tools, skills, and integrations.

### Plugin Structure

```
agent-fabric-plugin-example/
├── pyproject.toml
├── plugin.yaml              # Plugin manifest
├── src/
│   └── agent_fabric_plugin_example/
│       ├── __init__.py
│       ├── tools.py         # Tool implementations
│       └── skills/
│           └── example.yaml # Skill definitions
└── tests/
```

### Plugin Manifest (`plugin.yaml`)

```yaml
name: agent-fabric-plugin-example
version: "0.1.0"
description: "Example AgentFabric plugin"
author: "Your Name"

tools:
  - agent_fabric_plugin_example.tools:ExampleTool

skills:
  - skills/example.yaml

config_schema:
  type: object
  properties:
    api_key:
      type: string
      description: "API key for the service"
  required: [api_key]

capabilities_required:
  - tool:example_api
```

### Entry Point Registration

In your `pyproject.toml`:

```toml
[project.entry-points."agentfabric.plugins"]
example = "agent_fabric_plugin_example"
```

### Testing Plugins

```python
from agent_fabric import Agent

agent = Agent("test", tools=["example_tool"])
result = agent.run("Use the example tool")
```

---

## Questions?

If you have questions about contributing, open a [Discussion](../../discussions) on GitHub.

---

Thank you for contributing to AgentFabric! 🚀
