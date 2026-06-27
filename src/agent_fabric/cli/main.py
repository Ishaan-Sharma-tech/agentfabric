import json
import asyncio
import uvicorn
import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from agent_fabric.core.config import settings
from agent_fabric.core.workspace import Workspace, validate_workspace_name
from agent_fabric.memory.engine import memory_engine
from agent_fabric.runtime.agent import Agent, validate_agent_name
from agent_fabric.runtime.team import Team

__all__ = ["app"]

# CLI App Setup
app = typer.Typer(help="AgentFabric: The runtime for AI agents.")
agent_app = typer.Typer(help="Manage and run AgentFabric agents.")
team_app = typer.Typer(help="Manage and run multi-agent teams.")
memory_app = typer.Typer(help="Query and inspect memory records.")
workspace_app = typer.Typer(help="Manage isolated workspaces.")
server_app = typer.Typer(help="Start and manage the API and WebSocket server.")

app.add_typer(agent_app, name="agent")
app.add_typer(team_app, name="team")
app.add_typer(memory_app, name="memory")
app.add_typer(workspace_app, name="workspace")
app.add_typer(server_app, name="server")

console = Console()


# --- Main Command: agentfabric run ---
@app.command(name="run")
def run_task(
    task: str = typer.Argument(..., help="The task for the agent to execute."),
    agent_name: str = typer.Option("assistant", "--agent", "-a", help="Name of the agent."),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Provider-specific model name."),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM Provider: 'openai' or 'ollama'."),
    system_prompt: Optional[str] = typer.Option(None, "--system", "-s", help="Custom system prompt."),
    max_steps: int = typer.Option(10, "--steps", help="Maximum tool execution steps.")
):
    """Execute a task using a one-shot agent run directly from the terminal."""
    try:
        valid_name = validate_agent_name(agent_name)
    except ValueError as ve:
        console.print(f"[bold red]Error:[/bold red] {ve}")
        raise typer.Exit(1)
        
    async def _async_run():
        agent = Agent(
            name=valid_name,
            model=model,
            provider=provider,
            system_prompt=system_prompt
        )
        
        with console.status(f"[bold green]Agent '{valid_name}' is thinking..."):
            res = await agent.run(task, max_steps=max_steps)
            
        for handler in agent.logger.handlers:
            handler.close()
        agent.logger.handlers.clear()
        
        console.print(Panel(
            Text(res.text, style="cyan"),
            title=f"[bold green]Agent '{valid_name}' Response[/bold green]",
            border_style="green"
        ))

    asyncio.run(_async_run())


# --- Agent Subcommands ---
@agent_app.command(name="logs")
def agent_logs(
    name: str = typer.Argument(..., help="Name of the agent to fetch logs for."),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of log records to show.")
):
    """Display the isolated execution log history for an agent."""
    try:
        clean_name = validate_agent_name(name)
    except ValueError as ve:
        console.print(f"[bold red]Error:[/bold red] {ve}")
        raise typer.Exit(1)
        
    workspace = Workspace.current()
    log_file = workspace.logs_path / f"{clean_name}.log"
    
    if not log_file.exists():
        console.print(f"[bold red]Error:[/bold red] No logs found for agent '{clean_name}' in workspace '{workspace.name}'.")
        raise typer.Exit(1)
        
    table = Table(title=f"Logs for Agent '{clean_name}'", show_header=True, header_style="bold magenta")
    table.add_column("Timestamp", style="dim", width=25)
    table.add_column("Level", width=10)
    table.add_column("Message", style="cyan")
    
    lines = []
    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                lines.append(json.loads(line.strip()))
            except Exception:
                pass
                
    for row in lines[-limit:]:
        level_style = "green" if row.get("level") == "INFO" else "red"
        table.add_row(
            row.get("timestamp", ""),
            Text(row.get("level", ""), style=level_style),
            row.get("message", "")
        )
        
    console.print(table)


# --- Team Subcommands ---
@team_app.command(name="run")
def team_run(
    task: str = typer.Argument(..., help="The task for the multi-agent team to execute."),
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to YAML team configuration file."),
    strategy: str = typer.Option("sequential", "--strategy", "-s", help="Team strategy: 'sequential', 'parallel', or 'supervisor'."),
    agents: Optional[str] = typer.Option(None, "--agents", "-a", help="Comma-separated list of agent names.")
):
    """Execute a task using a multi-agent team collaboration strategy."""
    async def _async_run():
        if config:
            team = Team.from_yaml(config)
        else:
            agent_names = [a.strip() for a in agents.split(",")] if agents else ["researcher", "writer"]
            team = Team(agents=[Agent(name=a) for a in agent_names], strategy=strategy)
            
        with console.status(f"[bold green]Team '{team.name}' is executing strategy '{strategy}'..."):
            res = await team.run(task)
            
        console.print(Panel(
            Text(res.text, style="cyan"),
            title=f"[bold green]Team '{team.name}' Response[/bold green]",
            border_style="green"
        ))

    asyncio.run(_async_run())


# --- Memory Subcommands ---
@memory_app.command(name="search")
def memory_search(
    query: str = typer.Argument(..., help="The search terms."),
    limit: int = typer.Option(5, "--limit", "-l", help="Maximum results to return."),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by memory tag.")
):
    """Search workspace memories using full-text FTS5 or semantic search."""
    async def _search():
        filters = {}
        if tag:
            filters["tag"] = tag
            
        results = await memory_engine.search(query, limit=limit, filters=filters)
        
        if not results:
            console.print("[yellow]No matching memories found.[/yellow]")
            return
            
        table = Table(title=f"Memory Search Results for: '{query}'", show_header=True, header_style="bold green")
        table.add_column("ID", style="dim", width=12)
        table.add_column("Memory Text", style="cyan")
        table.add_column("Tags", style="magenta")
        table.add_column("Importance", style="yellow")
        
        for m in results:
            table.add_row(
                m.id[:8] + "...",
                m.text,
                ", ".join(m.tags),
                f"{m.importance_score:.2f}"
            )
        console.print(table)

    asyncio.run(_search())


@memory_app.command(name="store")
def memory_store(
    text: str = typer.Argument(..., help="Text content to memorize."),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="Comma-separated tags list.")
):
    """Manually persist a text snippet into the workspace memory store."""
    async def _store():
        tag_list = [t.strip() for t in tags.split(",")] if tags else []
        record_id = await memory_engine.store(text=text, tags=tag_list)
        console.print(f"[bold green]Successfully stored memory! ID: {record_id}[/bold green]")

    asyncio.run(_store())


# --- Workspace Subcommands ---
@workspace_app.command(name="list")
def workspace_list():
    """List all workspaces currently registered on disk."""
    workspaces = Workspace.list_all()
    if not workspaces:
        console.print("[yellow]No workspaces found.[/yellow]")
        return
        
    table = Table(title="AgentFabric Workspaces", show_header=True, header_style="bold cyan")
    table.add_column("Workspace Name", style="bold green")
    table.add_column("Active", justify="center")
    table.add_column("Path", style="dim")
    
    current_ws = Workspace.current()
    for ws in workspaces:
        active_str = "[bold green]✓[/bold green]" if ws.name == current_ws.name else ""
        table.add_row(ws.name, active_str, str(ws.path))
        
    console.print(table)


@workspace_app.command(name="create")
def workspace_create(name: str = typer.Argument(..., help="Name of the new workspace.")):
    """Create a new workspace context directory."""
    try:
        clean_name = validate_workspace_name(name)
    except ValueError as ve:
        console.print(f"[bold red]Error:[/bold red] {ve}")
        raise typer.Exit(1)
        
    ws = Workspace.get(clean_name)
    ws.ensure_exists()
    console.print(f"[bold green]Created workspace '{clean_name}' at {ws.path}[/bold green]")


@workspace_app.command(name="select")
def workspace_select(name: str = typer.Argument(..., help="Name of the workspace to select.")):
    """Select the active workspace."""
    try:
        clean_name = validate_workspace_name(name)
    except ValueError as ve:
        console.print(f"[bold red]Error:[/bold red] {ve}")
        raise typer.Exit(1)
        
    ws = Workspace.get(clean_name)
    if not ws.path.exists():
        console.print(f"[bold red]Error:[/bold red] Workspace '{clean_name}' does not exist. Create it first using 'agentfabric workspace create {clean_name}'.")
        raise typer.Exit(1)
    settings.current_workspace = clean_name
    console.print(f"[bold green]Switched active workspace context to '{clean_name}'.[/bold green]")


# --- Server & Studio Subcommands ---
@server_app.command(name="start")
def server_start(
    host: str = typer.Option("127.0.0.1", "--host", help="Host address to bind server to."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to run server on.")
):
    """Start the REST API and WebSocket event streaming server."""
    console.print(f"[bold green]Starting AgentFabric server on {host}:{port}...[/bold green]")
    uvicorn.run("agent_fabric.server.app:create_app", factory=True, host=host, port=port, log_level="info")


@app.command(name="studio")
def studio_start(
    port: int = typer.Option(8000, "--port", "-p", help="Port to start backend server on.")
):
    """Start the AgentFabric server backend for Studio."""
    console.print(Panel(
        Text(f"AgentFabric Studio Backend is launching at http://127.0.0.1:{port}\nOpen the desktop Studio app to connect.", style="green"),
        title="[bold green]AgentFabric Studio Backend[/bold green]",
        border_style="green"
    ))
    uvicorn.run("agent_fabric.server.app:create_app", factory=True, host="127.0.0.1", port=port, log_level="info")


# Entry Point
if __name__ == "__main__":
    app()

