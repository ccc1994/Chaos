import asyncio
import os
import logging
from typing import Dict, Optional, List, Any
from pygls.lsp.client import LanguageClient as BaseLanguageClient
from lsprotocol.types import (
    InitializeParams,
    ClientCapabilities,
    RegistrationParams,
    TextDocumentItem,
    Position,
    Location,
    TextDocumentIdentifier,
    ReferenceContext,
    ReferenceParams,
    DefinitionParams,
    CallHierarchyIncomingCallsParams,
    CallHierarchyItem,
    LogMessageParams,
    ShowMessageParams,
    PublishDiagnosticsParams,
    DiagnosticSeverity,
    MessageType,
)

logger = logging.getLogger(__name__)

class LSPManager:
    """管理多个语言服务器的生命周期和通信。"""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LSPManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, project_root: str = "."):
        if self._initialized:
            return
        self.project_root = os.path.abspath(project_root)
        self.clients: Dict[str, BaseLanguageClient] = {}
        self._initialized = True
        
        # 配置支持的语言及其服务器启动命令
        self.server_configs = {
            "python": {
                "command": ["pyright-langserver", "--stdio"],
                "extensions": [".py"]
            },
            "typescript": {
                "command": ["typescript-language-server", "--stdio"],
                "extensions": [".ts", ".tsx"]
            },
            "javascript": {
                "command": ["typescript-language-server", "--stdio"],
                "extensions": [".js", ".jsx"]
            },
            "go": {
                "command": ["gopls"],
                "extensions": [".go"]
            },
            "cpp": {
                "command": ["clangd"],
                "extensions": [".cpp", ".hpp", ".cxx", ".hxx", ".cc", ".hh"]
            },
            "c": {
                "command": ["clangd"],
                "extensions": [".c", ".h"]
            }
        }

    def _register_notification_handlers(self, client: BaseLanguageClient, language_id: str):
        """为客户端注册 LSP 通知处理程序。"""
        
        @client.feature("window/logMessage")
        def on_log_message(params: LogMessageParams):
            # 将服务器日志映射到本地日志
            level = logging.INFO
            if params.type == MessageType.Error:
                level = logging.ERROR
            elif params.type == MessageType.Warning:
                level = logging.WARNING
            elif params.type == MessageType.Info:
                level = logging.INFO
            elif params.type == MessageType.Log:
                level = logging.DEBUG
            
            logger.log(level, f"[{language_id}] LSP 服务器日志: {params.message}")

        @client.feature("window/showMessage")
        def on_show_message(params: ShowMessageParams):
            logger.info(f"[{language_id}] LSP 服务器消息: {params.message}")

        @client.feature("textDocument/publishDiagnostics")
        def on_publish_diagnostics(params: PublishDiagnosticsParams):
            # 记录诊断信息的统计，避免淹没日志
            if params.diagnostics:
                errors = [d for d in params.diagnostics if d.severity == DiagnosticSeverity.Error]
                if errors:
                    logger.warning(f"[{language_id}] {params.uri} 发现 {len(errors)} 个错误诊断信息")
                
                # 生产环境中可以根据需要决定是否记录详细信息
                # for diag in params.diagnostics:
                #     logger.debug(f"[{language_id}] 诊断: {diag.message} ({diag.range.start.line+1}:{diag.range.start.character+1})")

    async def get_client(self, language_id: str) -> Optional[BaseLanguageClient]:
        """获取或启动指定语言的 LSP 客户端。"""
        if language_id in self.clients:
            return self.clients[language_id]
        
        if language_id not in self.server_configs:
            logger.warning(f"由于尚未配置，无法启动 {language_id} 的 LSP。")
            return None
        
        config = self.server_configs[language_id]
        client = BaseLanguageClient("coding-agent-client", "0.1.0")
        
        # 注册通知处理程序
        self._register_notification_handlers(client, language_id)
        
        # 补丁：解决 cattrs 在处理某些 LSP 类型时的 Union 结构化问题
        def apply_lsp_patch(client):
            try:
                from lsprotocol import types
                # 尝试访问私有转换器
                converter = getattr(client.protocol, '_converter', None)
                if not converter:
                    return
                    
                # 注册针对 Notebook 相关类型的回退钩子，防止 cattrs 报错
                # 即使服务器发送了这些类型，我们也只是将其视为原始字典/对象
                for name in dir(types):
                    if "Notebook" in name:
                        t = getattr(types, name)
                        if isinstance(t, type):
                            converter.register_structure_hook(t, lambda obj, cl: obj)
                
                # 针对导致报错的具体 Union 类型进行特殊处理
                # 此处尝试通过 register_structure_hook 的更通用方式拦截
            except Exception as e:
                logger.warning(f"无法应用 LSP 兼容性补丁: {e}")

        apply_lsp_patch(client)

        try:
            logger.info(f"正在启动 {language_id} 的 LSP 服务器: {config['command']}")
            import subprocess
            cmd = config['command']
            try:
                # 尝试找到全路径
                full_path = subprocess.check_output(["which", cmd[0]], text=True).strip()
                cmd = [full_path] + cmd[1:]
            except:
                pass

            await client.start_io(*cmd)
            
            # 初始化请求
            # 禁用 notebookDocument 相关能力，因为 cattrs 在处理这些新类型的 Union 时会报错
            capabilities = ClientCapabilities()
            capabilities.notebook_document = None
            
            params = InitializeParams(
                process_id=os.getpid(),
                root_uri=f"file://{self.project_root}",
                root_path=self.project_root,
                capabilities=capabilities,
            )
            logger.info(f"正在初始化 {language_id} LSP...")
            await client.initialize_async(params)
            
            # 某些服务器需要发送 initialized 通知
            from lsprotocol.types import InitializedParams
            client.initialized(InitializedParams())
            
            # 给服务器一点时间进行初始索引（特别是 Pyright）
            if language_id in ["python", "typescript"]:
                logger.info(f"正在等待 {language_id} LSP 服务器热身...")
                await asyncio.sleep(2.0)
            
            logger.info(f"{language_id} LSP 初始化完成。")
            
            self.clients[language_id] = client
            return client
        except Exception as e:
            logger.error(f"启动 {language_id} 的 LSP 失败: {str(e)}")
            return None

    def get_language_id(self, file_path: str) -> Optional[str]:
        """根据文件后缀获取 language_id。"""
        ext = os.path.splitext(file_path)[1].lower()
        for lang_id, config in self.server_configs.items():
            if ext in config["extensions"]:
                return lang_id
        return None

    async def shutdown_all(self):
        """关闭所有 LSP 客户端。"""
        for lang_id, client in self.clients.items():
            try:
                # 1. 发送 LSP 退出协议
                try:
                    await asyncio.wait_for(client.shutdown_async(None), timeout=2.0)
                    client.exit(None)
                except:
                    pass
                
                # 2. 停止客户端 IO（pygls 2.0+ 推荐方式）
                if hasattr(client, 'stop'):
                    await client.stop()
                    
            except Exception as e:
                logger.error(f"关闭 {lang_id} 的 LSP 失败: {str(e)}")
        
        self.clients.clear()
        # 给事件循环一点时间来真正关闭底层传输
        await asyncio.sleep(0.1)

# 全局单例
lsp_manager = LSPManager()
