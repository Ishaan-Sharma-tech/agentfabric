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
from agent_fabric.pipelines.executor import PipelineExecutor
from agent_fabric.pipelines.yaml import load_pipeline_from_yaml
from agent_fabric.scheduler.scheduler import Schedule, scheduler_engine
from agent_fabric.plugins.manager import plugin_manager
from agent_fabric.registry import registry_catalog, install_package, update_packages, scaffold_plugin, PackageMetadata
from agent_fabric.mcp import mcp_manager, MCPServer

__all__ = ["app"]

# CLI App Setup
app = typer.Typer(help="AgentFabric: The runtime for AI agents.")
agent_app = typer.Typer(help="Manage and run AgentFabric agents.")
team_app = typer.Typer(help="Manage and run multi-agent teams.")
pipeline_app = typer.Typer(help="Manage and run workflow pipelines.")
schedule_app = typer.Typer(help="Manage recurring and event-based schedules.")
plugin_app = typer.Typer(help="Manage and inspect plugins.")
registry_app = typer.Typer(help="Search, install, publish, and update packages.")
mcp_app = typer.Typer(help="Manage Model Context Protocol (MCP) bridges.")
memory_app = typer.Typer(help="Query and inspect memory records.")
workspace_app = typer.Typer(help="Manage isolated workspaces.")
server_app = typer.Typer(help="Start and manage the API and WebSocket server.")

app.add_typer(agent_app, name="agent")
app.add_typer(team_app, name="team")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(schedule_app, name="schedule")
app.add_typer(plugin_app, name="plugin")
app.add_typer(registry_app, name="registry")
app.add_typer(mcp_app, name="mcp")
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


# --- Pipeline Subcommands ---
@pipeline_app.command(name="run")
def pipeline_run(
    config: str = typer.Argument(..., help="Path to YAML pipeline configuration file.")
):
    """Execute a DAG workflow pipeline from a YAML configuration file."""
    async def _async_run():
        pipeline = load_pipeline_from_yaml(config)
        executor = PipelineExecutor(pipeline)
        
        with console.status(f"[bold green]Executing pipeline '{pipeline.name}'..."):
            res = await executor.run()
            
        console.print(Panel(
            Text(json.dumps(res.outputs, indent=2, default=str), style="cyan"),
            title=f"[bold green]Pipeline '{pipeline.name}' Summary ({res.status})[/bold green]",
            border_style="green" if res.status == "completed" else "red"
        ))

    asyncio.run(_async_run())


# --- Schedule Subcommands ---
@schedule_app.command(name="create")
def schedule_create(
    name: str = typer.Argument(..., help="Schedule identifier name."),
    target_type: str = typer.Option("agent", "--target-type", "-t", help="Target workload type (agent, team, pipeline, tool)."),
    target_name: str = typer.Option("assistant", "--target-name", "-n", help="Target workload name."),
    interval: Optional[float] = typer.Option(None, "--interval", "-i", help="Interval trigger seconds."),
    event_type: Optional[str] = typer.Option(None, "--event", "-e", help="Event trigger type.")
):
    """Create a new recurring interval or reactive event-based schedule."""
    if interval is not None:
        trig_type = "interval"
        trig_cfg = {"seconds": interval}
    elif event_type is not None:
        trig_type = "event"
        trig_cfg = {"event_type": event_type}
    else:
        trig_type = "interval"
        trig_cfg = {"seconds": 60.0}
        
    s = Schedule(
        name=name,
        trigger_type=trig_type,
        trigger_config=trig_cfg,
        target_type=target_type,
        target_name=target_name,
        inputs={}
    )
    created = scheduler_engine.create_schedule(s)
    console.print(f"[bold green]Created schedule '{created.name}' (ID: {created.id})[/bold green]")


@schedule_app.command(name="list")
def schedule_list():
    """List active schedules in current workspace."""
    schedules = scheduler_engine.list_schedules()
    if not schedules:
        console.print("[yellow]No active schedules found.[/yellow]")
        return
        
    table = Table(title="Workspace Schedules")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold green")
    table.add_column("Trigger Type", style="cyan")
    table.add_column("Target", style="magenta")
    table.add_column("Enabled", style="yellow")
    
    for s in schedules:
        table.add_row(s.id[:8], s.name, s.trigger_type, f"{s.target_type}:{s.target_name}", "Yes" if s.enabled else "No")
        
    console.print(table)


@schedule_app.command(name="history")
def schedule_history(
    schedule_id: str = typer.Argument(..., help="Schedule ID or name.")
):
    """Retrieve execution history for a schedule."""
    s = scheduler_engine.get_schedule(schedule_id)
    sid = s.id if s else schedule_id
    history = scheduler_engine.history_store.get_history(sid)
    
    if not history:
        console.print(f"[yellow]No execution history found for schedule '{schedule_id}'.[/yellow]")
        return
        
    table = Table(title=f"Schedule History ({schedule_id})")
    table.add_column("Exec ID", style="dim")
    table.add_column("Status", style="bold")
    table.add_column("Trigger Time", style="cyan")
    table.add_column("Output / Error", style="white")
    
    for h in history:
        status_style = "green" if h.status == "completed" else "red"
        out_str = h.error if h.error else str(h.output)
        table.add_row(h.execution_id[:8], f"[{status_style}]{h.status}[/{status_style}]", str(h.trigger_time), out_str[:50])
        
    console.print(table)


# --- Plugin Subcommands ---
@plugin_app.command(name="list")
def plugin_list():
    """List registered plugins and their enabled status."""
    plugins = plugin_manager.list_plugins()
    if not plugins:
        console.print("[yellow]No registered plugins found.[/yellow]")
        return
        
    table = Table(title="AgentFabric Plugins")
    table.add_column("Name", style="bold green")
    table.add_column("Version", style="dim")
    table.add_column("Description", style="white")
    table.add_column("Tools", style="cyan")
    table.add_column("Enabled", style="yellow")
    
    for p in plugins:
        table.add_row(p.name, p.version, p.description or "", ", ".join(p.tools), "Yes" if p.enabled else "No")
        
    console.print(table)


@plugin_app.command(name="info")
def plugin_info(
    name: str = typer.Argument(..., help="Plugin name.")
):
    """View detailed metadata for a plugin."""
    p = plugin_manager.get_plugin(name)
    if not p:
        console.print(f"[red]Plugin '{name}' not found.[/red]")
        return
        
    console.print(Panel(
        Text(json.dumps(p.model_dump(), indent=2), style="cyan"),
        title=f"[bold green]Plugin '{p.name}' Info[/bold green]",
        border_style="green"
    ))


@plugin_app.command(name="enable")
def plugin_enable(
    name: str = typer.Argument(..., help="Plugin name.")
):
    """Enable a plugin."""
    plugin_manager.enable_plugin(name)
    console.print(f"[bold green]Enabled plugin '{name}'.[/bold green]")


@plugin_app.command(name="disable")
def plugin_disable(
    name: str = typer.Argument(..., help="Plugin name.")
):
    """Disable a plugin."""
    plugin_manager.disable_plugin(name)
    console.print(f"[bold yellow]Disabled plugin '{name}'.[/bold yellow]")


# --- Registry Subcommands ---
@registry_app.command(name="search")
def registry_search_cmd(
    query: str = typer.Argument("", help="Search query string."),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag.")
):
    """Search registered package catalog."""
    pkgs = registry_catalog.search(query=query, tag=tag)
    if not pkgs:
        console.print("[yellow]No packages found matching criteria.[/yellow]")
        return
        
    table = Table(title="AgentFabric Package Registry")
    table.add_column("Package Name", style="bold green")
    table.add_column("Version", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Downloads", style="yellow")
    table.add_column("Description", style="white")
    
    for p in pkgs:
        table.add_row(p.name, p.version, p.type, str(p.downloads), p.description)
        
    console.print(table)


@registry_app.command(name="install")
def registry_install_cmd(
    package_name: str = typer.Argument(..., help="Package name to install.")
):
    """Install a package from registry into active workspace."""
    res = install_package(package_name)
    if "Error" in res:
        console.print(f"[red]{res}[/red]")
    else:
        console.print(f"[bold green]{res}[/bold green]")


@registry_app.command(name="update")
def registry_update_cmd():
    """Update all installed packages in active workspace."""
    res = update_packages()
    console.print(f"[bold green]{res}[/bold green]")


@registry_app.command(name="publish")
def registry_publish_cmd(
    name: str = typer.Argument(..., help="Package name to publish."),
    description: str = typer.Option("", "--desc", "-d", help="Package description.")
):
    """Publish or update a package in the local registry catalog."""
    pkg = PackageMetadata(name=name, description=description, author="Local Developer")
    registry_catalog.register_package(pkg)
    console.print(f"[bold green]Successfully published '{name}' to registry catalog.[/bold green]")


@app.command(name="init")
def init_cmd(
    target_type: str = typer.Argument("plugin", help="Type to initialize (e.g. 'plugin')"),
    name: str = typer.Argument(..., help="Name of the project to initialize")
):
    """Scaffold a new project or plugin structure."""
    if target_type.lower() == "plugin":
        res = scaffold_plugin(name)
        if "Error" in res:
            console.print(f"[red]{res}[/red]")
        else:
            console.print(f"[bold green]{res}[/bold green]")
    else:
        console.print(f"[red]Unsupported init target type: '{target_type}'. Supported: plugin[/red]")


# --- MCP Subcommands ---
@mcp_app.command(name="list")
def mcp_list():
    """List connected external MCP servers."""
    servers = mcp_manager.list_connected()
    if not servers:
        console.print("[yellow]No active connected MCP servers.[/yellow]")
        return
        
    table = Table(title="Connected MCP Servers")
    table.add_column("Server URL", style="bold green")
    table.add_column("Status", style="cyan")
    
    for s in servers:
        table.add_row(s, "Connected")
        
    console.print(table)


@mcp_app.command(name="connect")
def mcp_connect(
    url: str = typer.Argument(..., help="External MCP server URL.")
):
    """Connect to an external MCP server."""
    mcp_manager.connect_server(url)
    console.print(f"[bold green]Connected to MCP server at '{url}'.[/bold green]")


@mcp_app.command(name="serve")
def mcp_serve():
    """Start an MCP server exposing AgentFabric tools over JSON-RPC."""
    server = MCPServer()
    console.print(f"[bold green]Started MCP Server '{server.server_name}' exposing {len(server.list_tools())} tools.[/bold green]")


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
        active_str = "[bold green][ACTIVE][/bold green]" if ws.name == current_ws.name else ""
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
    from agent_fabric.core.config import save_settings
    save_settings()
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


@app.command(name="tui")
def tui_start():
    """Start interactive Terminal Dashboard (TUI)."""
    from agent_fabric.cli.tui import run_tui
    run_tui(duration_sec=2.0)


# Entry Point
if __name__ == "__main__":
    app()


