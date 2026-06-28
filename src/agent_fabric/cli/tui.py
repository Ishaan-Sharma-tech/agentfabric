import time
import logging
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live

logger = logging.getLogger("agent_fabric.cli.tui")

__all__ = ["TerminalDashboard", "run_tui"]


class TerminalDashboard:
    """
    Rich-based Terminal UI dashboard for monitoring active AgentFabric execution.
    """
    def __init__(self) -> None:
        self.console = Console()

    def generate_layout(self) -> Layout:
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )
        
        # Header
        layout["header"].update(Panel("[bold cyan]AgentFabric Terminal Dashboard (v0.1.0)[/bold cyan]", style="white on blue"))
        
        # Left Panel: Active Runtime Summary
        table_runtime = Table(title="Runtime Components")
        table_runtime.add_column("Component", style="green")
        table_runtime.add_column("Status", style="bold yellow")
        table_runtime.add_row("Agent Core Loop", "Active")
        table_runtime.add_row("Event Bus", "Listening")
        table_runtime.add_row("Memory Store (SQLite)", "Connected")
        table_runtime.add_row("MCP Server Bridge", "Ready")
        layout["left"].update(Panel(table_runtime, title="Engine Status"))
        
        # Right Panel: Active Schedulers & Pipelines
        table_pipelines = Table(title="Pipelines & Schedulers")
        table_pipelines.add_column("ID", style="cyan")
        table_pipelines.add_column("Target", style="magenta")
        table_pipelines.add_column("State", style="bold green")
        table_pipelines.add_row("pipe-main", "Sequential Team", "Completed")
        table_pipelines.add_row("sched-01", "Memory Sync Cron", "Scheduled")
        layout["right"].update(Panel(table_pipelines, title="Tasks & Automation"))
        
        # Footer
        layout["footer"].update(Panel("[bold yellow]Press Ctrl+C to exit TUI dashboard[/bold yellow]"))
        return layout

    def start(self, duration_sec: float = 2.0) -> None:
        """Runs live TUI rendering for duration_sec (or continuously if duration_sec <= 0)."""
        layout = self.generate_layout()
        with Live(layout, refresh_per_second=4, console=self.console):
            start_time = time.time()
            while True:
                time.sleep(0.25)
                if duration_sec > 0 and (time.time() - start_time) >= duration_sec:
                    break


def run_tui(duration_sec: float = 2.0) -> None:
    dashboard = TerminalDashboard()
    dashboard.start(duration_sec=duration_sec)
