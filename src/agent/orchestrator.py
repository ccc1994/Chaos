from autogen import GroupChat, GroupChatManager, register_function
from src.tools.file_tools import get_file_tools
from src.tools.shell_tools import get_shell_tools

def setup_orchestration(architect, coder, reviewer, tester, user_proxy):
    """注册工具并设置带有规范驱动流程的 GroupChat。"""
    
    # 1. 为 Coder 注册文件工具
    for tool in get_file_tools():
        register_function(
            tool,
            caller=coder,
            executor=coder,
            name=tool.__name__,
            description=tool.__doc__
        )

    # 2. 为 Tester 注册 Shell 工具
    for tool in get_shell_tools():
        register_function(
            tool,
            caller=tester,
            executor=tester,
            name=tool.__name__,
            description=tool.__doc__
        )

    # 3. 定义群聊流程 (Group Chat flow)
    # 特定顺序：Architect -> Coder -> Reviewer -> Tester
    # 我们使用自定义发言者选择逻辑来确保流程符合规范
    def custom_speaker_selection(last_speaker, groupchat):
        """确保规范驱动循环的自定义逻辑。"""
        messages = groupchat.messages
        if not messages:
            return architect # 从架构师开始
        
        last_msg = messages[-1]
        
        # 处理工具调用：如果有 tool_calls，由调用者自己执行（Auto-Execute）
        if "tool_calls" in last_msg and last_msg["tool_calls"]:
            return last_speaker

        last_speaker_name = last_speaker.name
        
        if last_speaker_name == "Architect":
            return coder
        elif last_speaker_name == "Coder":
            # Coder 完成工作（无论是写代码建议还是执行工具得到结果），都交给 Reviewer
            return reviewer
        elif last_speaker_name == "Reviewer":
            # 如果审核员批准，进入测试环节，否则返回 Coder 处修改
            content = last_msg.get("content", "")
            if content and ("APPROVE" in content.upper() or "LOOKS GOOD" in content.upper()):
                return tester
            return coder
        elif last_speaker_name == "Tester":
            # 如果测试通过，终止或询问用户，否则返回 Coder 调试
            content = last_msg.get("content", "")
            if content and ("FAIL" in content.upper() or "ERROR" in content.upper()):
                return coder
            return user_proxy
        
        return "auto"

    groupchat = GroupChat(
        agents=[user_proxy, architect, coder, reviewer, tester],
        messages=[],
        max_round=50,
        speaker_selection_method=custom_speaker_selection,
        allow_repeat_speaker=True
    )

    manager = GroupChatManager(
        groupchat=groupchat,
        llm_config=architect.llm_config
    )

    return manager

def start_multi_agent_session(manager, user_proxy, user_input: str):
    """启动协作会话。"""
    user_proxy.initiate_chat(manager, message=user_input)
