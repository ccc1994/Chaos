from autogen import GroupChat, GroupChatManager, register_function
from src.tools.file_tools import get_file_tools
from src.tools.shell_tools import get_shell_tools
from src.tools.git_tools import get_git_tools
import os
import json
from rich.console import Console

console = Console()

class ContextCompressingGroupChatManager(GroupChatManager):
    """
    具有上下文压缩功能的GroupChatManager。
    当对话上下文超过阈值时，会对较远的历史消息进行摘要压缩，保留最新消息的完整内容。
    """
    
    def __init__(self, groupchat, llm_config, max_context_length=10000, preserve_recent_rounds=5, **kwargs):
        """
        初始化上下文压缩管理器。
        
        Args:
            groupchat: 所属的GroupChat实例
            llm_config: LLM配置
            max_context_length: 上下文长度阈值（字符数），超过此值将触发压缩
            preserve_recent_rounds: 保留完整内容的最近轮数
            **kwargs: 传递给父类的其他参数
        """
        super().__init__(groupchat, llm_config, **kwargs)
        self.max_context_length = max_context_length
        self.preserve_recent_rounds = preserve_recent_rounds
        self._summary_cache = {
            "summary_content": None,  # 缓存的摘要内容
            "summary_index": -1       # 摘要在消息列表中的索引
        }
    
    def _get_context_length(self, messages):
        """计算当前上下文的总长度（字符数）。"""
        return sum(len(str(msg.get("content", ""))) for msg in messages)
    
    def _generate_summary(self, messages, llm_config):
        """使用LLM生成消息摘要。"""
        try:
            from openai import OpenAI
            
            # 获取LLM配置
            config_list = llm_config.get("config_list", [])
            if not config_list:
                console.print("[dim]警告：LLM配置为空，使用默认摘要[/dim]")
                return "[历史对话摘要：由于未配置LLM，无法生成详细摘要]"
            
            # 使用第一个配置
            config = config_list[0]
            
            # 构建OpenAI客户端
            client = OpenAI(
                api_key=config.get("api_key"),
                base_url=config.get("base_url"),
                api_type=config.get("api_type", "openai")
            )
            
            # 构建摘要请求
            summary_prompt = [
                {
                    "role": "system",
                    "content": "你是一个对话摘要专家。请将以下对话内容总结为简洁的摘要，保留关键信息、决策点和行动项。使用中文总结。"
                },
                {
                    "role": "user",
                    "content": "请总结以下对话历史：\n\n"
                }
            ]
            
            # 添加对话历史
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                summary_prompt[1]["content"] += f"[{role}] {content}\n"
            
            # 发送API请求
            response = client.chat.completions.create(
                model=config.get("model"),
                messages=summary_prompt,
                temperature=0.3,
                max_tokens=500
            )
            
            # 提取摘要内容
            if response and response.choices:
                return f"[历史对话摘要：{response.choices[0].message.content.strip()}]"
            
            return "[历史对话摘要：生成摘要时未能获取有效响应]"
        except Exception as e:
            console.print(f"[dim]生成摘要时出错：{e}[/dim]")
            return "[历史对话摘要：生成摘要时发生错误]"
    
    def compress_context(self):
        """压缩上下文，对较远的消息生成摘要，保留最新消息的完整内容。"""
        messages = self.groupchat.messages
        if not messages:
            return
        
        # 检查是否需要压缩
        current_length = self._get_context_length(messages)
        if current_length < self.max_context_length:
            return
        
        console.print(f"[dim]上下文长度 {current_length} 超过阈值 {self.max_context_length}，开始压缩...[/dim]")
        
        # 确定需要压缩的消息范围
        if self._summary_cache["summary_content"] is not None and self._summary_cache["summary_index"] != -1:
            # 如果已有摘要，保留摘要及其后的所有消息作为基础
            summary_msg = messages[self._summary_cache["summary_index"]]
            messages_after_summary = messages[self._summary_cache["summary_index"] + 1:]
            
            # 只保留最近几轮消息
            if len(messages_after_summary) > self.preserve_recent_rounds * 2:
                recent_messages = messages_after_summary[-self.preserve_recent_rounds * 2:]
                old_messages = [summary_msg] + messages_after_summary[:-len(recent_messages)]
            else:
                recent_messages = messages_after_summary
                old_messages = [summary_msg]
        else:
            # 没有摘要时，保留最近几轮消息
            recent_messages = messages[-self.preserve_recent_rounds * 2:]  # 每轮包含发送和回复
            old_messages = messages[:-len(recent_messages)]
        
        if old_messages:
            # 生成旧消息的摘要
            summary = self._generate_summary(old_messages, self.llm_config)
            
            # 构建压缩后的消息列表
            compressed_messages = [
                {
                    "role": "system",
                    "content": summary,
                    "name": "context_summary"
                }
            ] + recent_messages
            
            # 更新对话历史
            self.groupchat.messages = compressed_messages
            
            # 更新摘要缓存
            self._summary_cache["summary_content"] = summary
            self._summary_cache["summary_index"] = 0  # 摘要现在是消息列表的第一个元素
            
            console.print(f"[dim]上下文已压缩，保留 {len(recent_messages)} 条最新消息和 1 条摘要[/dim]")
    
    def forward(self, message, sender, **kwargs):
        """重写forward方法，在处理消息前检查并压缩上下文。"""
        # 在处理新消息前压缩上下文
        self.compress_context()
        
        # 调用父类的forward方法处理消息
        return super().forward(message, sender, **kwargs)

def setup_implementation_group_chat(coder, reviewer, tester, user_proxy,manager_config):
    """设置实现子聊天组，负责代码实现、审查和测试。"""
    # 定义实现子聊天组的 FSM 状态机图
    implementation_graph_dict = {
        user_proxy: [coder, reviewer, tester],
        coder: [reviewer,user_proxy],                 # 程序员 -> 审核员检查
        reviewer: [coder, tester,user_proxy],         # 审核员 -> 不通过回程序员，通过去测试员
        tester: [coder, user_proxy],           # 测试员 -> 失败回程序员，成功结束
    }

    implementation_groupchat = GroupChat(
        agents=[coder, reviewer, tester, user_proxy],
        messages=[],
        max_round=30,
        speaker_selection_method="auto",
        allowed_or_disallowed_speaker_transitions=implementation_graph_dict,
        speaker_transitions_type="allowed"
    )

    # 从环境变量获取上下文压缩配置
    max_context_length = int(os.getenv("CONTEXT_COMPRESS_MAX_LENGTH", "10000"))
    preserve_recent_rounds = int(os.getenv("CONTEXT_COMPRESS_RECENT_ROUNDS", "5"))

    implementation_manager = ContextCompressingGroupChatManager(
        groupchat=implementation_groupchat,
        llm_config=manager_config,
        is_termination_msg=lambda x: "TERMINATE" in x.get("content", ""),
        description="负责接受并完成 architect 的任务",
        max_context_length=max_context_length,
        preserve_recent_rounds=preserve_recent_rounds
    )

    return implementation_manager

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
            executor=architect,  # 改为architect自己执行，避免user_proxy权限问题
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
    implementation_manager = setup_implementation_group_chat(coder, reviewer, tester,user_proxy, manager_config)
    
    def prepare_task_message(recipient, messages, sender, config):
        full_content = messages[-1].get("content", "")
        # 如果你想把 "TODO:" 之前的内容（通常是思考过程）过滤掉
        if "TODO:" in full_content:
            return full_content.split("TODO:", 1)[-1].strip()
        return full_content
    def task_trigger_condition(sender, messages=None):
        # 1. 检查最新消息的内容
        try:
            if messages and len(messages) > 0:
                # 如果提供了messages参数，使用最新消息
                last_msg_content = messages[-1].get("content", "")
                return "TRIGGER_IMPLEMENTATION" in last_msg_content
            else:
                # 如果没有messages参数，尝试从sender获取最后一条消息
                last_msg_content = sender.last_message().get("content", "")
                return "TRIGGER_IMPLEMENTATION" in last_msg_content
        except Exception as e:
            # 如果发生任何异常，返回False
            return False


    user_proxy.register_nested_chats(
        chat_queue=[
            {
                "recipient": implementation_manager,
                "message": prepare_task_message,
                "summary_method": "last_msg",
            }
        ],
        trigger=task_trigger_condition
    )

    return architect

def start_multi_agent_session(manager, user_proxy, user_input: str):
    """启动协作会话。"""
    user_proxy.initiate_chat(manager, message=user_input)
