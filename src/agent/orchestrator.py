from autogen import GroupChat, GroupChatManager, register_function
from src.tools.file_tools import get_file_tools
from src.tools.shell_tools import get_shell_tools

def setup_orchestration(pm, coder, reviewer, tester, user_proxy):
    """Register tools and setup GroupChat with spec-driven flow."""
    
    # 1. Register File Tools for Coder
    for tool in get_file_tools():
        register_function(
            tool,
            caller=coder,
            executor=coder,
            name=tool.__name__,
            description=tool.__doc__
        )

    # 2. Register Shell Tools for Tester
    for tool in get_shell_tools():
        register_function(
            tool,
            caller=tester,
            executor=tester,
            name=tool.__name__,
            description=tool.__doc__
        )

    # 3. Define Group Chat flow
    # Specific sequence: Architect -> Coder -> Reviewer -> Tester
    # We use custom speaker selection to ensure the loop follows the spec
    def custom_speaker_selection(last_speaker, groupchat):
        """Custom logic to ensure spec-driven loop."""
        messages = groupchat.messages
        if not messages:
            return pm # Start with Architect
        
        last_speaker_name = last_speaker.name
        
        if last_speaker_name == "User":
            return pm
        elif last_speaker_name == "Architect":
            return coder
        elif last_speaker_name == "Coder":
            return reviewer
        elif last_speaker_name == "Reviewer":
            # If reviewer approves, go to tester, else back to coder
            last_msg = messages[-1]["content"].upper()
            if "APPROVE" in last_msg or "LOOKS GOOD" in last_msg:
                return tester
            return coder
        elif last_speaker_name == "Tester":
            # If tester passes, terminate or ask user, else back to coder
            last_msg = messages[-1]["content"].upper()
            if "FAIL" in last_msg or "ERROR" in last_msg:
                return coder
            return user_proxy
        
        return "auto"

    groupchat = GroupChat(
        agents=[user_proxy, pm, coder, reviewer, tester],
        messages=[],
        max_round=50,
        speaker_selection_method=custom_speaker_selection,
        allow_repeat_speaker=True
    )

    manager = GroupChatManager(
        groupchat=groupchat,
        llm_config=pm.llm_config
    )

    return manager

def start_multi_agent_session(manager, user_proxy, user_input: str):
    """Initiates the cooperative conversation."""
    user_proxy.initiate_chat(manager, message=user_input)
