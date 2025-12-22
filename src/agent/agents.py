import os
from autogen import AssistantAgent, UserProxyAgent
from src.tools.file_tools import get_file_tools
from src.tools.shell_tools import get_shell_tools

def get_agent_configs():
    """Load agent-specific configurations from .env with fallback."""
    default_model = os.getenv("DEFAULT_MODEL_ID")
    return {
        "Architect": {
            "model": os.getenv("PM_MODEL_ID") or default_model,
            "system_message": """You are the **Product Manager and Architect**. 
Your goal is to analyze user requirements and convert them into structured technical specifications (specs.md) or task lists (todo_list).
Focus on file structure, API definitions, and logic flows. 
Ensure the plan is clear for the Coder to implement."""
        },
        "Coder": {
            "model": os.getenv("CODER_MODEL_ID") or default_model,
            "system_message": """You are the **Coder**. Your goal is to implement specific code based on the Architect's design.
Follow a 'Level 1-3' context loading strategy:
- Level 1 (Structure/Todo) is already in your context.
- Use 'read_file' for Level 2 context (file content).
- Use 'search_code' for Level 3 context (discovery).
Use 'insert_code' for precise changes to save tokens.
After implementation, tell the Reviewer to audit your work."""
        },
        "Reviewer": {
            "model": os.getenv("REVIEWER_MODEL_ID") or default_model,
            "system_message": """You are the **Code Reviewer**. Audit the Coder's work for bugs, style, and edge cases.
Reference the Architect's plan to ensure compliance.
If you find issues, provide specific feedback.
If the code is correct, say 'APPROVE' clearly to proceed to testing."""
        },
        "Tester": {
            "model": os.getenv("TESTER_MODEL_ID") or default_model,
            "system_message": """You are the **QA/Tester**. Write/run tests for the code changes.
Use 'execute_shell' to run commands and observe outputs.
If tests pass, say 'VERIFIED' and 'TERMINATE' to end the session.
If tests fail, provide logs to the Coder for debugging."""
        }
    }

def create_agents(api_key: str, base_url: str):
    """Initialize AutoGen agents with per-agent model configs."""
    configs = get_agent_configs()
    
    # Validate that all required model IDs are set
    missing_models = [role for role, config in configs.items() if not config.get("model")]
    if missing_models:
        raise ValueError(f"Missing model IDs in .env for: {', '.join(missing_models)}")

    def make_config(model_id):
        return {
            "config_list": [{
                "model": model_id,
                "api_key": api_key,
                "base_url": base_url,
                "api_type": "openai",
            }],
            "cache_seed": 42
        }

    pm = AssistantAgent(
        name="Architect",
        system_message=configs["Architect"]["system_message"],
        llm_config=make_config(configs["Architect"]["model"])
    )

    coder = AssistantAgent(
        name="Coder",
        system_message=configs["Coder"]["system_message"],
        llm_config=make_config(configs["Coder"]["model"])
    )

    reviewer = AssistantAgent(
        name="Reviewer",
        system_message=configs["Reviewer"]["system_message"],
        llm_config=make_config(configs["Reviewer"]["model"])
    )

    tester = AssistantAgent(
        name="Tester",
        system_message=configs["Tester"]["system_message"],
        llm_config=make_config(configs["Tester"]["model"])
    )

    user_proxy = UserProxyAgent(
        name="User",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=10,
        is_termination_msg=lambda x: "TERMINATE" in (x.get("content", "") or "").upper(),
        code_execution_config=False
    )

    return pm, coder, reviewer, tester, user_proxy
