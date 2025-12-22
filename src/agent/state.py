import os
import json

STATE_FILE = ".ca/state.json"

def save_state(project_root: str, current_task: str, status: str, history: list):
    """Saves the current session state."""
    state_path = os.path.join(project_root, STATE_FILE)
    state = {
        "current_task": current_task,
        "status": status,
        "history_count": len(history)
    }
    with open(state_path, "w") as f:
        json.dump(state, f, indent=4)

def load_state(project_root: str):
    """Loads the session state if it exists."""
    state_path = os.path.join(project_root, STATE_FILE)
    if os.path.exists(state_path):
        with open(state_path, "r") as f:
            return json.load(f)
    return None
