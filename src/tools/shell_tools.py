import subprocess
import re
from rich.console import Console
from rich.prompt import Confirm

console = Console()

def execute_shell(command: str) -> str:
    """Execute a shell command with safety checks and user confirmation."""
    # Safety: Hard block dangerous commands
    danger_patterns = [
        r"rm\s+-rf\s+/",
        r"curl.*\|\s*sh",
        r"wget.*\|\s*sh",
        r"chmod\s+.*777",
        r"\.git/"
    ]
    
    for pattern in danger_patterns:
        if re.search(pattern, command):
            return f"Error: Command '{command}' is blocked for security reasons (Safety Policy)."

    console.print(f"\n[bold red]Safety Warning:[/bold red] Agent wants to execute: [cyan]{command}[/cyan]")
    if not Confirm.ask("[bold yellow]Execute this command?[/bold yellow]"):
        return "Command execution cancelled by user."

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=60
        )
        output = result.stdout or ""
        if result.stderr:
            output += f"\nErrors:\n{result.stderr}"
        return output or "Command executed successfully (no output)."
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"

def get_shell_tools():
    """Returns a list of tools for shell operations."""
    return [execute_shell]
