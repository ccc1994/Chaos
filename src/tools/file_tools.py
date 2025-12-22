import os
import re
from rich.prompt import Confirm
from rich.console import Console

console = Console()

def read_file(path: str) -> str:
    """Read the contents of a file. (Level 2 Context)"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path: str, content: str) -> str:
    """Write content to a file. Requires user confirmation."""
    if not Confirm.ask(f"[bold yellow]Allow writing to {path}?[/bold yellow]"):
        return "Action cancelled by user."

    # Safety: Backup before writing
    backup_path = f"{path}.bak"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            old_content = f.read()
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(old_content)
            
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"File '{path}' written successfully. Backup created as '{backup_path}'."

def insert_code(path: str, line_number: int, content: str) -> str:
    """Insert code at a specific line number. Requires user confirmation."""
    if not Confirm.ask(f"[bold yellow]Allow code insertion into {path} at line {line_number}?[/bold yellow]"):
        return "Action cancelled by user."

    if not os.path.exists(path):
        return f"Error: File '{path}' does not exist."
    
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    idx = max(0, min(line_number - 1, len(lines)))
    lines.insert(idx, content + "\n")
    
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return f"Code inserted into '{path}' at line {line_number}."

def search_code(query: str, path: str = ".") -> str:
    """Search for a pattern in files (Level 3 Context)."""
    results = []
    for root, dirs, files in os.walk(path):
        if any(x in root for x in [".git", ".ca", "node_modules", "__pycache__"]):
            continue
        for file in files:
            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if query in line:
                            results.append(f"{file_path}:{i}: {line.strip()}")
            except (UnicodeDecodeError, PermissionError):
                continue
    return "\n".join(results) if results else "No matches found."

def get_file_tools():
    """Returns a list of tools for file operations."""
    return [read_file, write_file, insert_code, search_code]
