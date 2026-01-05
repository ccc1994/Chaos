import os
import sys
import re
import time
import pexpect
import signal
from typing import Dict, Optional, Union, List
from rich.console import Console
from rich.prompt import Confirm
import logging

# Configure logging
logger = logging.getLogger(__name__)
console = Console()

class DualLogger:
    """捕获进程输出到缓冲区，供 Agent 后续读取。终端输出由 pexpect.interact 处理。"""
    def __init__(self):
        self.buffer = []

    def write(self, data):
        if not data:
            return
        
        # 确保 data 是字符串，避免 join 时报错
        if isinstance(data, bytes):
            try:
                data = data.decode('utf-8', errors='replace')
            except:
                data = str(data)
                
        self.buffer.append(data)

    def flush(self):
        pass

    def get_content(self) -> str:
        return "".join(self.buffer)

class JobManager:
    """管理后台进程。"""
    def __init__(self):
        self.jobs: Dict[int, pexpect.spawn] = {}

    def register(self, process: pexpect.spawn):
        self.jobs[process.pid] = process

    def get_job(self, pid: int) -> Optional[pexpect.spawn]:
        return self.jobs.get(pid)

    def kill_job(self, pid: int) -> str:
        if pid in self.jobs:
            try:
                proc = self.jobs[pid]
                if proc.isalive():
                    proc.close(force=True)
                del self.jobs[pid]
                return f"进程 {pid} 已终止。"
            except Exception as e:
                return f"终止进程 {pid} 时出错: {str(e)}"
        return f"错误：未找到 PID 为 {pid} 的任务。"

# 全局任务管理器
_job_manager = JobManager()

def execute_shell_command(command: str, timeout: int = 10, cwd: str = ".") -> str:
    """
    直接执行 shell 命令并转接标准输入输出。
    用户可以直接在终端与命令交互（如选择菜单、输入确认）。
    如果命令是长期运行的服务，用户可以按 Ctrl+] 脱离并交还控制权给 Agent。
    """
    # 安全策略
    danger_patterns = [
        r"rm\s+-rf\s+/", r"curl.*\|\s*sh", r"wget.*\|\s*sh", 
        r"chmod\s+.*777", r"\.git/"
    ]
    for pattern in danger_patterns:
        if re.search(pattern, command):
            return f"Error: Command '{command}' is blocked for security reasons."

    confirm_patterns = [
        r"\brm\b", r"\bmv\b", r"\bsudo\b", r"\bdd\b",
        r"\bkill\b", r"\bchmod\b", r"\bchown\b", 
        r"\breboot\b", r"\bshutdown\b", r"\binit\b",
        r"\bmkfs\b", r"\bformat\b"
    ]
    if any(re.search(pattern, command) for pattern in confirm_patterns):
        console.print(f"\n[bold red]安全警示：[/bold red] Agent 想要执行危险命令：[cyan]{command}[/cyan]")
        if not Confirm.ask("[bold yellow]确定执行此命令吗？[/bold yellow]"):
            return "用户取消了命令执行。"

    console.print(f"[dim]执行命令: {command}[/dim]")
    if sys.platform != "win32":
        console.print(f"[dim](若是长期运行的服务，处理完后可按 Ctrl+] 返回 Agent)[/dim]")

    try:
        # 启动进程
        process = pexpect.spawn(
            command,
            cwd=cwd,
            encoding='utf-8',
            timeout=None, # 由 interact 控制
            dimensions=(24, 80)
        )
        
        # 设置日志记录（仅缓冲，不直接写 stdout，因为 interact 会处理）
        logger_instance = DualLogger()
        process.logfile_read = logger_instance
        
        # 直接进入交互模式
        try:
            process.interact()
        except Exception:
            pass

        # 获取最终捕获的所有内容
        full_output = logger_instance.get_content()

        if process.isalive():
            # 用户按了脱离快捷键，或者 interact 因为其他原因返回但进程还活着
            _job_manager.register(process)
            return f"命令已转入后台运行 (PID: {process.pid})。目前已捕获的输出：\n{full_output}"
        else:
            # 进程已结束
            process.close()
            if process.exitstatus is not None:
                status = f"Exit Code: {process.exitstatus}"
                # 特殊处理 Ctrl+C (130)
                if process.exitstatus == 130:
                    status += " (Interrupted by user)"
            else:
                status = f"Signal: {process.signalstatus}"
            
            return f"命令执行结束 ({status})。输出内容：\n{full_output}"

    except Exception as e:
        return f"执行 shell 出错：{str(e)}"

def send_shell_input(pid: int, text: str) -> str:
    """向后台进程发送文本。"""
    proc = _job_manager.get_job(pid)
    if proc and proc.isalive():
        try:
            if not text.endswith('\n'):
                text += '\n'
            proc.send(text)
            return f"已向进程 {pid} 发送输入。"
        except Exception as e:
            return f"发送失败: {e}"
    return f"错误：未找到运行中的进程 {pid}。"

def kill_process(pid: int) -> str:
    """终止后台进程。"""
    return _job_manager.kill_job(pid)

def list_background_jobs() -> str:
    """列出当前运行中的后台任务。"""
    if not _job_manager.jobs:
        return "当前没有运行中的后台任务。"
    jobs_info = []
    for pid, proc in _job_manager.jobs.items():
        if proc.isalive():
            jobs_info.append(f"PID: {pid} | 命令: {proc.command} {proc.args}")
    return "\n".join(jobs_info) if jobs_info else "当前没有运行中的后台任务。"

def get_shell_tools():
    return [execute_shell_command, send_shell_input, kill_process, list_background_jobs]
