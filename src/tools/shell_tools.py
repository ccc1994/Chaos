import subprocess
import re
import os
import sys
import time
import signal
from rich.console import Console
from rich.prompt import Confirm

console = Console()

def execute_shell(command: str, timeout: int = None, cwd: str = ".") -> str:
    """
    执行 shell 命令。
    通过实时监控输出流来判断命令是否为交互式或阻塞式。
    
    逻辑：
    1. 启动命令。
    2. 监控前 3-5 秒的输出。
    3. 如果命令结束，返回结果。
    4. 如果命令仍在运行且看似在等待输入（如最后是冒号或问号），则提示（目前仅作为阻塞返回）。
    5. 如果命令长期运行且未等待输入（如服务器），返回PID并保持后台运行。
    
    Args:
        command: 要执行的命令
        timeout: 超时时间（秒），默认 None
        cwd: 工作目录，默认为当前目录
    
    Returns:
        命令执行结果摘要。
    """
    # 安全策略：硬阻断危险命令
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

    # 定义需要确认的危险命令模式
    confirm_patterns = [
        r"\brm\b", r"\bmv\b", r"\bsudo\b", r"\bdd\b",
        r"\bkill\b", r"\bchmod\b", r"\bchown\b", 
        r"\breboot\b", r"\bshutdown\b", r"\binit\b",
        r"\bmkfs\b", r"\bformat\b"
    ]
    
    # 检查是否为危险命令
    is_dangerous = any(re.search(pattern, command) for pattern in confirm_patterns)
    
    if is_dangerous:
        console.print(f"\n[bold red]安全警示：[/bold red] Agent 想要执行危险命令：[cyan]{command}[/cyan]")
        if not Confirm.ask("[bold yellow]确定执行此命令吗？[/bold yellow]"):
            return "用户取消了命令执行。"
    
    console.print(f"[dim]执行命令：{command}[/dim]")

    try:
        # 启动进程
        # 使用 setsid 创建新进程组，方便后续杀死整个进程树
        preexec_fn = os.setsid if sys.platform != "win32" else None
        
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, # 默认不给输入，防止挂起等待
            cwd=cwd,
            text=True,
            bufsize=1,
            universal_newlines=True,
            preexec_fn=preexec_fn
        )
        
        output_buffer = []
        error_buffer = []
        start_time = time.time()
        monitor_duration = 5.0 # 监控 5 秒
        
        import select
        
        # 实时监控循环
        while True:
            # 检查进程是否已结束
            return_code = process.poll()
            if return_code is not None:
                # 进程已结束，读取剩余输出
                stdout, stderr = process.communicate()
                if stdout:
                    output_buffer.append(stdout)
                    console.print(stdout, end="")
                if stderr:
                    error_buffer.append(stderr)
                    console.print(f"[red]{stderr}[/red]", end="")
                
                full_out = "".join(output_buffer)
                full_err = "".join(error_buffer)
                
                if return_code == 0:
                    return f"命令执行成功。\nOutput:\n{full_out}"
                else:
                    return f"命令执行失败 (Exit Code: {return_code})。\nOutput:\n{full_out}\nError:\n{full_err}"

            # 检查是否超过监控时间
            if time.time() - start_time > monitor_duration:
                # 超过监控时间仍在运行，视为后台服务/阻塞进程
                console.print(f"\n[green]✓[/green] 命令仍在运行，已转入后台（PID: {process.pid}）")
                full_out = "".join(output_buffer)
                return f"命令已启动并仍在后台运行 (PID: {process.pid})。\n前 {monitor_duration} 秒输出:\n{full_out}\n\n如需停止，请使用 kill 命令。"

            # 读取输出（非阻塞）
            if sys.platform != 'win32':
                reads = [process.stdout.fileno(), process.stderr.fileno()]
                ret = select.select(reads, [], [], 0.1)
                
                if process.stdout.fileno() in ret[0]:
                    line = process.stdout.readline()
                    if line:
                        console.print(line, end="")
                        output_buffer.append(line)
                
                if process.stderr.fileno() in ret[0]:
                    line = process.stderr.readline()
                    if line:
                        console.print(f"[red]{line}[/red]", end="")
                        error_buffer.append(line)
            else:
                # Windows 简单处理，可能略有阻塞
                time.sleep(0.1)
                # 暂时无法非阻塞读取，直接跳过具体实时输出逻辑，依赖最终结果或超时
                pass

    except Exception as e:
        return f"执行命令时出错：{str(e)}"

def get_shell_tools():
    """返回用于 Shell 操作的工具列表。"""
    return [execute_shell]
