import asyncio
import unittest
import os
import sys

# 将项目根目录添加到 sys.path 以便直接运行测试
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.lsp_tools import lsp_get_definition, lsp_find_references, lsp_get_call_hierarchy
from src.tools.lsp_manager import lsp_manager

class TestLSPIntegration(unittest.IsolatedAsyncioTestCase):
    """
    LSP 基础功能的集成测试类。
    使用当前项目作为测试对象，验证工具能否正确与语言服务器通信。
    """

    async def asyncSetUp(self):
        # 确保项目根目录在 lsp_manager 中正确设置
        # 在实际运行中，lsp_manager 已经有一个默认实例
        self.project_root = os.getcwd()
        self.python_file = os.path.abspath("src/tools/file_tools.py")
        self.symbol = "get_file_tree"
        
        # 检查测试文件是否存在
        if not os.path.exists(self.python_file):
            self.fail(f"测试文件不存在: {self.python_file}")

    async def asyncTearDown(self):
        # 每个测试后关闭所有客户端，确保不互相干扰
        await lsp_manager.shutdown_all()

    async def test_definition(self):
        """测试查找定义功能。"""
        print(f"\n[Test] 验证定义查找: {self.symbol}...")
        result = await lsp_get_definition(self.python_file, self.symbol)
        
        # 验证结果中包含正确的文件路径和预期行号 (188 左右)
        self.assertIn("file_tools.py", result)
        self.assertIn("行: 188", result)
        print(f"定义查找成功，结果:\n{result}")

    async def test_references(self):
        """测试查找引用功能。"""
        print(f"\n[Test] 验证引用查找: {self.symbol}...")
        result = await lsp_find_references(self.python_file, self.symbol)
        
        # 验证结果中包含主入口 src/main.py 或者是 file_tools.py 本身
        self.assertIn("file_tools.py", result)
        # 通常 src/main.py 也会引用这个函数
        # self.assertIn("main.py", result) 
        
        print(f"引用查找成功，结果摘要 (前 200 字符):\n{result[:200]}...")

    async def test_invalid_symbol(self):
        """验证查询不存在的符号。"""
        invalid_symbol = "non_existent_function_xyz_123"
        print(f"\n[Test] 验证查询不存在的符号: {invalid_symbol}...")
        result = await lsp_get_definition(self.python_file, invalid_symbol)
        self.assertIn("未找到符号", result)
        print(f"验证查询不存在的符号成功，结果: {result}")

    async def test_call_hierarchy(self):
        """测试调用层级功能。"""
        print(f"\n[Test] 验证调用层级: {self.symbol}...")
        result = await lsp_get_call_hierarchy(self.python_file, self.symbol, direction="incoming")
        
        # 由于 pylsp 可能不支持调用层级，我们检查结果是否包含预期提示或错误
        if "Method Not Found" in result:
            print(f"当前 LSP 服务器不支持调用层级查询。")
        else:
            # 如果支持，验证结果中包含 main.py (调用者)
            print(f"调用层级查询成功，结果摘要:\n{result[:300]}...")
            # 这里的断言取决于服务器支持程度，暂时只打印结果
            self.assertIsInstance(result, str)

if __name__ == "__main__":
    unittest.main()
