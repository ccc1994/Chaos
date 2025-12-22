import os
import sys

# Ensure project root is in sys.path to resolve 'src' imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

from src.agent.manager import ensure_project_setup
from src.agent.agents import create_agents
from src.agent.orchestrator import setup_orchestration, start_multi_agent_session
from src.agent.context import get_level1_context

console = Console()

def main():
    # 1. Initialization
    load_dotenv()
    project_root = os.getcwd()
    ensure_project_setup(project_root)

    # 2. Config Check
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    
    if not api_key:
        console.print("[bold red]Error:[/bold red] DASHSCOPE_API_KEY not found in .env.")
        sys.exit(1)

    # 3. Agents & Orchestration
    with console.status("[bold green]Initializing Multi-Agent System...[/bold green]"):
        try:
            pm, coder, reviewer, tester, user_proxy = create_agents(api_key, base_url)
            manager = setup_orchestration(pm, coder, reviewer, tester, user_proxy)
        except Exception as e:
            console.print(f"[bold red]Error initializing system:[/bold red] {e}")
            sys.exit(1)

    # 4. Welcome Message
    console.print(Panel.fit(
        "[bold cyan]AI Coding Agent (Advanced Multi-Agent)[/bold cyan]\n"
        "[dim]Orchestrated by AutoGen | Powered by Volcengine Ark[/dim]",
        border_style="bright_blue"
    ))
    console.print("[yellow]Type 'exit' to quit. Spec-Driven Development is active.[/yellow]\n")

    # 5. Interaction Loop
    while True:
        try:
            user_input = Prompt.ask("[bold green]User[/bold green]")
            
            if user_input.lower() in ["exit", "quit"]:
                console.print("[yellow]Shutting down... Goodbye![/yellow]")
                break
            
            if not user_input.strip():
                continue

            # Inject Level 1 Context automatically
            l1_context = get_level1_context(project_root)
            full_prompt = f"{l1_context}\n[User Requirement]\n{user_input}"

            # Start Session
            console.print(f"\n[bold blue]Starting Group Chat...[/bold blue]\n")
            start_multi_agent_session(manager, user_proxy, full_prompt)

        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")

if __name__ == "__main__":
    main()
