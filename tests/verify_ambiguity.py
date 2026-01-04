import asyncio
import os
import sys

# 将项目根目录添加到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.lsp_tools import lsp_get_definition, find_symbol_positions
from src.tools.lsp_manager import lsp_manager

async def test_ambiguity():
    test_file = os.path.abspath("tests/ambiguity_test.py")
    
    print("\n--- 验证歧义处理 (Python) ---")
    
    # 1. 直接搜索 X (不带行号)
    # 应该跳到第 5 行 (def X)，因为它是显式声明
    print("[Test] 搜索符号 'X' (不指定行号)...")
    positions = find_symbol_positions(test_file, "X")
    print(f"找到的位置: {[f'L{p.line+1}' for p in positions]}")
    
    if positions and positions[0].line == 4:
        print("成功: 优先匹配了全局函数声明 (L5)。")
    else:
        print(f"失败: 第一个匹配项是 L{positions[0].line+1 if positions else 'None'}，预期是 L5。")

    # 2. 查询 X 的定义
    result = await lsp_get_definition(test_file, "X")
    print(f"LSP 查询结果:\n{result}")

    await lsp_manager.shutdown_all()

if __name__ == "__main__":
    asyncio.run(test_ambiguity())
