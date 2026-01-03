import os
import threading
import logging
from typing import List, Optional
import chromadb
from llama_index.core import (
    VectorStoreIndex, 
    SimpleDirectoryReader, 
    StorageContext, 
    load_index_from_storage,
    Settings
)
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.node_parser import CodeSplitter, SentenceSplitter
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 保存索引的全局变量
_index = None
_index_lock = threading.Lock()

def _initialize_settings():
    """初始化 LlamaIndex 设置"""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    base_url = os.getenv("DASHSCOPE_BASE_URL")
    embed_model=os.getenv("EMBEDDING_MODEL_ID")
    llm_model=os.getenv("DEFAULT_MODEL_ID")
    
    if not api_key or not base_url or not embed_model or not llm_model:
        logger.error("DASHSCOPE_API_KEY 或 DASHSCOPE_BASE_URL 或 embed_model 或 llm_model 未设置，无法初始化 LlamaIndex")
        return False
        
    Settings.llm = OpenAI(
        model=llm_model,
        api_key=api_key,
        api_base=base_url,
        temperature=0.1
    )
    Settings.embed_model = OpenAIEmbedding(
        model_name=embed_model,
        api_key=api_key,
        api_base=base_url
    )
    return True

def load_ignore_patterns(project_root: str) -> List[str]:
    """从 .gitignore 加载忽略模式"""
    patterns = ['.venv', '.git', '.ca', '.cache', 'node_modules', '__pycache__']
    gitignore_path = os.path.join(project_root, ".gitignore")
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # 去除路径末尾的斜杠
                    pattern = line.rstrip('/')
                    patterns.append(pattern)
    return list(set(patterns))

def build_index(project_root: str):
    """
    构建项目的代码索引，并存储在 ChromaDB 中。
    """
    global _index
    
    if not _initialize_settings():
        return
        
    db_path = os.path.join(project_root, ".ca", "chroma_db")
    
    with _index_lock:
        try:
            # 初始化 ChromaDB
            db = chromadb.PersistentClient(path=db_path)
            chroma_collection = db.get_or_create_collection("code_index")
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            # 检查是否已经有索引
            if chroma_collection.count() > 0:
                logger.info(f"正在从 {db_path} 加载现有 ChromaDB 索引 (count: {chroma_collection.count()})...")
                _index = VectorStoreIndex.from_vector_store(
                    vector_store, storage_context=storage_context
                )
                logger.info("索引加载成功。")
            else:
                logger.info("正在构建新索引并存入 ChromaDB...")
                
                ignore_patterns = load_ignore_patterns(project_root)
                logger.info(f"使用忽略模式: {ignore_patterns}")

                reader = SimpleDirectoryReader(
                    input_dir=project_root,
                    recursive=True,
                    required_exts=['.py', '.js', '.ts', '.tsx', '.md', '.sh', '.go', '.java', '.html'],
                    exclude=ignore_patterns
                )
                documents = reader.load_data()
                
                # 定义不同语言的解析器
                parsers = {
                    ".py": CodeSplitter.from_defaults(language="python", chunk_lines=40),
                    ".js": CodeSplitter.from_defaults(language="javascript", chunk_lines=40),
                    ".ts": CodeSplitter.from_defaults(language="typescript", chunk_lines=40),
                    ".tsx": CodeSplitter.from_defaults(language="typescript", chunk_lines=40),
                    ".sh": CodeSplitter.from_defaults(language="bash", chunk_lines=40),
                    ".go": CodeSplitter.from_defaults(language="golang", chunk_lines=40),
                    ".java": CodeSplitter.from_defaults(language="java", chunk_lines=40),
                    ".html": CodeSplitter.from_defaults(language="html", chunk_lines=40),
                }
                
                nodes = []
                for doc in documents:
                    file_path = doc.metadata.get("file_path", "")
                    file_ext = os.path.splitext(file_path)[1].lower()
                    
                    # 根据后缀选择解析器，如果没有匹配的，回退到普通 SentenceSplitter
                    parser = parsers.get(file_ext)
                    if parser:
                        try:
                            nodes.extend(parser.get_nodes_from_documents([doc]))
                        except Exception as e:
                            logger.warning(f"使用 CodeSplitter 处理 {file_path} 出错，回退到 SentenceSplitter: {e}")
                            nodes.extend(SentenceSplitter().get_nodes_from_documents([doc]))
                    else:
                        nodes.extend(SentenceSplitter().get_nodes_from_documents([doc]))
                
                _index = VectorStoreIndex(nodes, storage_context=storage_context)
                logger.info(f"索引构建完成并存入 ChromaDB，路径: {db_path}")
        except Exception as e:
            logger.error(f"构建或加载 ChromaDB 索引时出错: {e}")

def build_index_async(project_root: str):
    """
    异步构建索引，不阻塞主线程。
    """
    thread = threading.Thread(target=build_index, args=(project_root,), daemon=True)
    thread.start()
    logger.info("已启动异步索引构建任务 (使用 ChromaDB)。")

def code_search(query: str) -> str:
    """
    基于 LlamaIndex 和 ChromaDB 的代码搜索工具。
    
    Args:
        query: 搜索词或自然语言问题
        
    Returns:
        搜索结果，包含相关的代码片段和文件路径
    """
    global _index
    
    if _index is None:
        return "索引尚未就绪，请稍后再试。正在后台构建索引..."
        
    try:
        query_engine = _index.as_query_engine(similarity_top_k=5)
        response = query_engine.query(query)
        return str(response)
    except Exception as e:
        return f"搜索时出错: {e}"
