from autogen import GroupChat, GroupChatManager, register_function
from src.tools.file_tools import get_file_tools
from src.tools.shell_tools import get_shell_tools
from src.tools.git_tools import get_git_tools

def setup_implementation_group_chat(coder, reviewer, tester, manager_config):
    """设置实现子聊天组，负责代码实现、审查和测试。"""
    # 定义实现子聊天组的 FSM 状态机图
    implementation_graph_dict = {
        coder: [reviewer],                 # 程序员 -> 审核员检查
        reviewer: [coder, tester],         # 审核员 -> 不通过回程序员，通过去测试员
        tester: [coder, tester],           # 测试员 -> 失败回程序员，成功结束
    }

    implementation_groupchat = GroupChat(
        agents=[coder, reviewer, tester],
        messages=[],
        max_round=30,
        speaker_selection_method="auto",
        allowed_or_disallowed_speaker_transitions=implementation_graph_dict,
        speaker_transitions_type="allowed"
    )

    implementation_manager = GroupChatManager(
        groupchat=implementation_groupchat,
        llm_config=manager_config,
        is_termination_msg=lambda x: "TERMINATE" in x.get("content", "")
    )

    return implementation_manager

def setup_main_group_chat(architect, implementation_manager, user_proxy, manager_config):
    """设置主聊天组，负责项目规划和子聊天组协调。"""
    # 定义主聊天组的 FSM 状态机图
    main_graph_dict = {
        user_proxy: [architect],           # 用户输入 -> 架构师规划
        architect: [implementation_manager, user_proxy],  # 架构师 -> 实现管理器
        implementation_manager: [architect, user_proxy],  # 实现管理器 -> 架构师或用户
    }

    main_groupchat = GroupChat(
        agents=[user_proxy, architect, implementation_manager],
        messages=[],
        max_round=20,
        speaker_selection_method="auto",
        allowed_or_disallowed_speaker_transitions=main_graph_dict,
        speaker_transitions_type="allowed"
    )

    main_manager = GroupChatManager(
        groupchat=main_groupchat,
        llm_config=manager_config,
        is_termination_msg=lambda x: "TERMINATE" in x.get("content", "")
    )

    return main_manager

def setup_orchestration(architect, coder, reviewer, tester, user_proxy, manager_config):
    """注册工具并设置带有规范驱动流程的嵌套 GroupChat。"""
    
    # 1. 为 Coder 注册文件工具
    for tool in get_file_tools():
        register_function(
            tool,
            caller=coder,
            executor=user_proxy,
            name=tool.__name__,
            description=tool.__doc__
        )

    # 2. 为 Architect 注册文件工具（读取目录和文件内容）
    for tool in get_file_tools("read"):
        register_function(
            tool,
            caller=architect,
            executor=user_proxy,
            name=tool.__name__,
            description=tool.__doc__
        )

    # 2. 为 Coder 注册 Shell 工具（用于运行构建、测试等命令）
    for tool in get_shell_tools():
        register_function(
            tool,
            caller=coder,
            executor=user_proxy,
            name=tool.__name__,
            description=tool.__doc__
        )
        register_function(
            tool,
            caller=reviewer,
            executor=user_proxy,
            name=tool.__name__,
            description=tool.__doc__
        )

    # 3. 为 Coder 注册 Git 工具（版本控制）
    for tool in get_git_tools():
        register_function(
            tool,
            caller=coder,
            executor=user_proxy,
            name=tool.__name__,
            description=tool.__doc__
        )

    # 4. 为 Tester 注册 Shell 工具
    for tool in get_shell_tools():
        register_function(
            tool,
            caller=tester,
            executor=user_proxy,
            name=tool.__name__,
            description=tool.__doc__
        )

    # 设置实现子聊天组
    implementation_manager = setup_implementation_group_chat(coder, reviewer, tester, manager_config)
    
    # 设置主聊天组
    main_manager = setup_main_group_chat(architect, implementation_manager, user_proxy, manager_config)

    return main_manager

def start_multi_agent_session(manager, user_proxy, user_input: str):
    """启动协作会话。"""
    user_proxy.initiate_chat(manager, message=user_input)
