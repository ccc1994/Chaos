import os
import sys
from dotenv import load_dotenv

# 确保可以导入 src 模块
sys.path.append(os.getcwd())

from src.tools.index_tools import build_index, code_search

def test_standalone_index():
    # 1. 加载环境变量
    load_dotenv()
    
    project_root = os.getcwd()
    print(f"--- 正在对项目根目录进行索引: {project_root} ---")
    
    # 2. 同步构建索引
    build_index(project_root)
    
    # 验证索引是否构建成功
    from src.tools.index_tools import _index
    if _index is None:
        print("\n[错误] 索引构建失败，请检查上方日志。")
        sys.exit(1)
        
    print("\n--- 索引构建/加载完成 ---")
    
    # 3. 进行搜索测试
    queries = [
        "LLMMessagesCompressor 的实现逻辑是什么？",
        "如何配置跨语言的代码分割 (CodeSplitter)？",
        "项目中使用了哪些向量数据库？"
    ]
    
    for query in queries:
        print(f"\n查询: {query}")
        print("-" * 30)
        result = code_search(query)
        print(result)
        print("-" * 30)

if __name__ == "__main__":
    test_standalone_index()
