import asyncio
import os
import re
from typing import List, Optional, Dict, Any
from urllib.parse import unquote
from pathlib import Path
from lsprotocol.types import (
    Position,
    Location,
    TextDocumentIdentifier,
    ReferenceParams,
    ReferenceContext,
    DefinitionParams,
    TextDocumentPositionParams,
    DidOpenTextDocumentParams,
    TextDocumentItem,
    CallHierarchyPrepareParams,
    CallHierarchyIncomingCallsParams,
    CallHierarchyOutgoingCallsParams,
)
from src.tools.lsp_manager import lsp_manager

def uri_to_path(uri: str) -> str:
    """用健壮的方式将 file:// URI 转换为系统路径。"""
    if not uri.startswith("file://"):
        return uri
    
    # 移除 file:// 前缀
    path_encoded = uri[7:]
    # 解码 URL 编码字符（如 %20）
    path_decoded = unquote(path_encoded)
    
    # 针对 Windows 路径的特殊处理 (file:///C:/...)
    if os.name == 'nt':
        if path_decoded.startswith('/') and len(path_decoded) > 2 and path_decoded[2] == ':':
            path_decoded = path_decoded[1:]
    
    return str(Path(path_decoded))

def find_symbol_positions(file_path: str, symbol_name: str) -> List[Position]:
    """
    在文件中查找符号出现的所有位置，并按声明优先级排序。
    返回 List[Position]。
    注意：LSP 的行号从 0 开始。
    """
    positions = []
    if not os.path.exists(file_path):
        return positions
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        # 优先级 1: 声明语句 (export, class, function, const, let, var, import)
        patterns = [
            r'\bexport\s+(?:default\s+)?(?:class|function|const|let|var)\s+' + re.escape(symbol_name) + r'\b',
            r'\b(?:class|function|const|let|var|def|async def)\s+' + re.escape(symbol_name) + r'\b',
            r'\bimport\s+.*?\b' + re.escape(symbol_name) + r'\b',
            r'\b(?:export\s+default\s+)' + re.escape(symbol_name) + r'\b',
        ]
        
        seen_lines = set()

        for p in patterns:
            for i, line in enumerate(lines):
                if i in seen_lines: continue
                match = re.search(p, line)
                if match:
                    # 尝试定位符号本身的起点
                    inner_match = re.search(r'\b' + re.escape(symbol_name) + r'\b', line)
                    positions.append(Position(line=i, character=inner_match.start() if inner_match else match.start()))
                    seen_lines.add(i)
        
        # 优先级 2: 普通边界匹配 (非声明的使用处)
        for i, line in enumerate(lines):
            if i in seen_lines: continue
            match = re.search(r'\b' + re.escape(symbol_name) + r'\b', line)
            if match:
                positions.append(Position(line=i, character=match.start()))
                seen_lines.add(i)
                
    except Exception:
        pass
    return positions

def find_symbol_position(file_path: str, symbol_name: str) -> Optional[Position]:
    """旧接口包装器：返回找到的第一个（也是最优的）位置。"""
    positions = find_symbol_positions(file_path, symbol_name)
    return positions[0] if positions else None

async def _get_definition_internal(file_path: str, line: int, character: int) -> str:
    abs_path = os.path.abspath(file_path)
    lang_id = lsp_manager.get_language_id(abs_path)
    if not lang_id:
        return f"无法识别文件类型: {file_path}"
        
    client = await lsp_manager.get_client(lang_id)
    if not client:
        return f"无法启动 {lang_id} 的 LSP 接口。"
        
    params = DefinitionParams(
        text_document=TextDocumentIdentifier(uri=f"file://{abs_path}"),
        position=Position(line=line, character=character)
    )
    
    # 发送 didOpen 通知以确保服务器已加载文件
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        client.text_document_did_open(DidOpenTextDocumentParams(
            text_document=TextDocumentItem(
                uri=f"file://{abs_path}",
                language_id=lang_id,
                version=1,
                text=content
            )
        ))
    except:
        pass
    
    try:
        result = await client.text_document_definition_async(params)
        if not result:
            return "未找到定义。"
            
        if isinstance(result, list):
            locs = result
        else:
            locs = [result]
            
        output = []
        for loc in locs:
            # lsprotocol result might be Location or LocationLink
            uri = getattr(loc, 'uri', getattr(getattr(loc, 'target_uri', None), 'uri', None))
            range_obj = getattr(loc, 'range', getattr(loc, 'target_range', None))
            
            if uri and range_obj:
                path = uri_to_path(uri)
                output.append(f"文件: {path}, 行: {range_obj.start.line + 1}, 列: {range_obj.start.character + 1}")
        
        return "\n".join(output) if output else "未找到定义。"
    except Exception as e:
        return f"查询定义出错: {str(e)}"

async def _find_references_internal(file_path: str, line: int, character: int) -> str:
    abs_path = os.path.abspath(file_path)
    lang_id = lsp_manager.get_language_id(abs_path)
    if not lang_id:
        return f"无法识别文件类型: {file_path}"
        
    client = await lsp_manager.get_client(lang_id)
    if not client:
        return f"无法启动 {lang_id} 的 LSP 接口。"
        
    params = ReferenceParams(
        text_document=TextDocumentIdentifier(uri=f"file://{abs_path}"),
        position=Position(line=line, character=character),
        context=ReferenceContext(include_declaration=True)
    )
    
    # 发送 didOpen 通知
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        client.text_document_did_open(DidOpenTextDocumentParams(
            text_document=TextDocumentItem(
                uri=f"file://{abs_path}",
                language_id=lang_id,
                version=1,
                text=content
            )
        ))
    except:
        pass
    
    try:
        result = await client.text_document_references_async(params)
        if not result:
            return "未找到引用。"
            
        output = []
        for loc in result:
            path = uri_to_path(loc.uri)
            output.append(f"文件: {path}, 行: {loc.range.start.line + 1}, 列: {loc.range.start.character + 1}")
            
        return "\n".join(output) if output else "未找到引用。"
    except Exception as e:
        return f"查询引用出错: {str(e)}"

async def _get_call_hierarchy_internal(file_path: str, line: int, character: int, direction: str = "incoming") -> str:
    abs_path = os.path.abspath(file_path)
    lang_id = lsp_manager.get_language_id(abs_path)
    if not lang_id:
        return f"无法识别文件类型: {file_path}"
        
    client = await lsp_manager.get_client(lang_id)
    if not client:
        return f"无法启动 {lang_id} 的 LSP 接口。"
        
    prepare_params = CallHierarchyPrepareParams(
        text_document=TextDocumentIdentifier(uri=f"file://{abs_path}"),
        position=Position(line=line, character=character)
    )
    
    # 发送 didOpen 通知
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        client.text_document_did_open(DidOpenTextDocumentParams(
            text_document=TextDocumentItem(
                uri=f"file://{abs_path}",
                language_id=lang_id,
                version=1,
                text=content
            )
        ))
    except:
        pass
    
    try:
        # 1. 准备调用层级
        items = await client.text_document_prepare_call_hierarchy_async(prepare_params)
        if not items:
            return "未找到调用层级信息。"
        
        item = items[0]
        output = [f"符号: {item.name} ({item.kind.name if hasattr(item.kind, 'name') else item.kind})", f"位置: {uri_to_path(item.uri)}:{item.range.start.line + 1}"]
        
        if direction == "incoming":
            output.append("\n--- 入站调用 (被谁调用) ---")
            calls = await client.call_hierarchy_incoming_calls_async(CallHierarchyIncomingCallsParams(item=item))
            if not calls:
                output.append("没有找到入站调用。")
            else:
                for call in calls:
                    from_item = call.from_
                    from_path = uri_to_path(from_item.uri)
                    # call.from_ranges 是调用发生的位置
                    ranges_str = ", ".join([f"L{r.start.line+1}" for r in call.from_ranges])
                    output.append(f"- {from_item.name} ({from_path} - {ranges_str})")
        else:
            output.append("\n--- 出站调用 (调用了谁) ---")
            calls = await client.call_hierarchy_outgoing_calls_async(CallHierarchyOutgoingCallsParams(item=item))
            if not calls:
                output.append("没有找到出站调用。")
            else:
                for call in calls:
                    to_item = call.to
                    to_path = uri_to_path(to_item.uri)
                    ranges_str = ", ".join([f"L{r.start.line+1}" for r in call.from_ranges])
                    output.append(f"- {to_item.name} ({to_path} - {ranges_str})")
                    
        return "\n".join(output)
    except Exception as e:
        return f"查询调用层级出错: {str(e)}"

# 对外暴露的工具函数

async def lsp_get_definition(file_path: str, symbol_name: str, line: int = -1, character: int = -1) -> str:
    """
    通过 LSP 查询符号的定义位置。
    如果已知行号和列号，请提供；否则将自动在文件中搜索符号名。
    
    Args:
        file_path: 文件路径
        symbol_name: 符号名
        line: 行号（可选，从1开始。如果为-1则自动搜索）
        character: 列号（可选，从1开始）
    """
    if line == -1:
        positions = find_symbol_positions(file_path, symbol_name)
        if not positions:
            return f"在文件 {file_path} 中未找到符号 '{symbol_name}'。"
        
        best_pos = positions[0]
        l, c = best_pos.line, best_pos.character
        
        result = await _get_definition_internal(file_path, l, c)
        
        # 如果有多个位置且第一个没结果，可以提示
        if len(positions) > 1 and "未找到" in result:
            other_locs = ", ".join([f"L{p.line+1}" for p in positions[1:5]])
            return f"{result} (在该文件声明处未找到定义，但该符号还出现在: {other_locs})"
        return result
    else:
        l, c = line - 1, character - 1
        return await _get_definition_internal(file_path, l, c)

async def lsp_find_references(file_path: str, symbol_name: str, line: int = -1, character: int = -1) -> str:
    """
    通过 LSP 查询符号的所有引用位置。
    如果已知行号和列号，请提供；否则将自动在文件中搜索符号名。
    
    Args:
        file_path: 文件路径
        symbol_name: 符号名
        line: 行号（可选，从1开始）
        character: 列号（可选，从1开始）
    """
    if line == -1:
        positions = find_symbol_positions(file_path, symbol_name)
        if not positions:
            return f"在文件 {file_path} 中未找到符号 '{symbol_name}'。"
        
        best_pos = positions[0]
        l, c = best_pos.line, best_pos.character
        
        result = await _find_references_internal(file_path, l, c)
        
        if len(positions) > 1 and "未找到" in result:
            other_locs = ", ".join([f"L{p.line+1}" for p in positions[1:5]])
            return f"{result} (在该文件声明处未找到引用，但该符号还出现在: {other_locs})"
        return result
    else:
        l, c = line - 1, character - 1
        return await _find_references_internal(file_path, l, c)

async def lsp_get_call_hierarchy(file_path: str, symbol_name: str, direction: str = "incoming", line: int = -1, character: int = -1) -> str:
    """
    通过 LSP 查询符号的调用层级关系。
    
    Args:
        file_path: 文件路径
        symbol_name: 符号名
        direction: 查询方向，"incoming" (被谁调用) 或 "outgoing" (调用了谁)
        line: 行号（可选，从1开始）
        character: 列号（可选，从1开始）
    """
    if line == -1:
        positions = find_symbol_positions(file_path, symbol_name)
        if not positions:
            return f"在文件 {file_path} 中未找到符号 '{symbol_name}'。"
        
        best_pos = positions[0]
        l, c = best_pos.line, best_pos.character
        
        result = await _get_call_hierarchy_internal(file_path, l, c, direction)
        
        if len(positions) > 1 and "未找到" in result:
            other_locs = ", ".join([f"L{p.line+1}" for p in positions[1:5]])
            return f"{result} (在该文件声明处未找到调用层级，但该符号还出现在: {other_locs})"
        return result
    else:
        l, c = line - 1, character - 1
        return await _get_call_hierarchy_internal(file_path, l, c, direction)

def get_lsp_tools() -> list:
    """返回所有 LSP 工具函数。"""
    return [lsp_get_definition, lsp_find_references, lsp_get_call_hierarchy]
