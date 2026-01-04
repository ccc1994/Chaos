import asyncio
import unittest
import os
import sys

# 将项目根目录添加到 sys.path 以便导入 src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.lsp_tools import lsp_get_definition, lsp_find_references
from src.tools.lsp_manager import lsp_manager

class TestLSPFrontend(unittest.IsolatedAsyncioTestCase):
    """
    针对 playground 里的前端项目进行 LSP 功能测试。
    """

    async def asyncSetUp(self):
        # 设置项目根目录为 playground
        self.playground_root = os.path.abspath("playground")
        # 暂时修改 lsp_manager 的 project_root 以便测试（单例模式）
        self.original_root = lsp_manager.project_root
        lsp_manager.project_root = self.playground_root
        
        self.app_file = os.path.join(self.playground_root, "src/App.tsx")
        self.symbol = "App"
        self.component_symbol = "DatePicker"
        
        if not os.path.exists(self.app_file):
            self.fail(f"Playground 测试文件不存在: {self.app_file}")

    async def asyncTearDown(self):
        await lsp_manager.shutdown_all()
        # 恢复 original_root
        lsp_manager.project_root = self.original_root

    async def test_frontend_definition(self):
        """测试 TypeScript 定义查找。"""
        print(f"\n[Frontend Test] 验证定义查找: {self.symbol} in App.tsx...")
        result = await lsp_get_definition(self.app_file, self.symbol)
        
        # 验证结果包含 App.tsx
        self.assertIn("App.tsx", result)
        print(f"前端定义查找成功: {result}")

    async def test_frontend_import_definition(self):
        """测试导入组件的定义查找。"""
        print(f"\n[Frontend Test] 验证组件定义查找: {self.component_symbol}...")
        
        # 在 App.tsx 中, <DatePicker /> 出现在第 13 行左右
        result = await lsp_get_definition(self.app_file, self.component_symbol, line=13, character=10)
        print(f"[Debug] Position (13, 10) Definition: {result}")
        
        # 再次尝试在 import 语句中点击路径部分 (./components/DatePicker)
        # 第2行: import DatePicker from './components/DatePicker';
        # 字母 '.' 的位置大约在 25
        print(f"[Frontend Test] 验证从 import 路径跳转: {self.component_symbol}...")
        path_result = await lsp_get_definition(self.app_file, "", line=2, character=26)
        print(f"[Debug] Position (2, 26) Definition: {path_result}")
        
        # 只要其中一个结果指向了 DatePicker.tsx 即可证明功能正常
        success = "DatePicker.tsx" in result or "DatePicker.tsx" in path_result
        self.assertTrue(success, f"未能在任何尝试中跳转到组件文件。结果: {result}, {path_result}")

    async def test_frontend_references(self):
        """测试 TypeScript 引用查找。"""
        print(f"\n[Frontend Test] 验证引用查找: {self.component_symbol}...")
        result = await lsp_find_references(self.app_file, self.component_symbol)
        
        # 验证结果包含引用点
        self.assertIn("App.tsx", result)
        print(f"前端引用查找成功，结果摘要:\n{result[:200]}...")

if __name__ == "__main__":
    unittest.main()
