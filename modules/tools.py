"""
工具箱
为 Agent 提供可调用的外部工具函数。
所有工具均设计为可被 LangChain @tool 装饰器包装。

工具清单：
  - web_search       DuckDuckGo 联网搜索
  - calculate_score  按评分维度加权计算总分
  - check_grammar    中文语法/表述检查（需 LLM）
  - export_markdown  导出分析结果为 Markdown 文件
  - generate_flowchart 生成 Mermaid 流程图代码（需 LLM）
"""
import os
import sys
import json
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    OUTPUTS_DIR,
    FLOWCHART_DIR,
    EVALUATION_DIR,
    SCORE_DIMENSIONS,
    TOTAL_SCORE,
)


# ================================================================
# 工具 1: 联网搜索
# ================================================================

def web_search(query: str, max_results: int = 5) -> str:
    """
    使用 DuckDuckGo 搜索在线信息，补充 LLM 知识截止日期之后的资料。
    Args:
        query: 搜索关键词
        max_results: 返回条数上限
    Returns:
        格式化的搜索结果文本，或错误提示
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return "[搜索失败] duckduckgo-search 包未安装，请执行: pip install duckduckgo-search"

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return f"[搜索失败] DuckDuckGo 请求异常: {e}"

    if not results:
        return f"[搜索结果] 未找到与 '{query}' 相关的内容。"

    lines = [f"搜索关键词: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "无标题")
        href = r.get("href", "")
        body = r.get("body", "")
        lines.append(f"{i}. {title}")
        lines.append(f"   链接: {href}")
        lines.append(f"   摘要: {body}\n")

    return "\n".join(lines)


# ================================================================
# 工具 2: 评分计算
# ================================================================

def calculate_score(
    dimension_scores: dict,
    total_score: int = TOTAL_SCORE,
) -> dict:
    """
    按评分维度加权求和，返回总分和明细。
    Args:
        dimension_scores: {"维度名": 得分, ...}，未传入的维度按 0 分计
        total_score: 满分值（默认 100）
    Returns:
        {"total": int, "details": {...}, "summary": str}
    """
    details = {}
    earned = 0

    for dim_name, config in SCORE_DIMENSIONS.items():
        score = float(dimension_scores.get(dim_name, 0))
        score = max(0, min(score, config["max"]))  # 裁剪到 [0, max]
        weighted = score * config["weight"]
        details[dim_name] = {
            "score": score,
            "max": config["max"],
            "weight": config["weight"],
            "weighted": weighted,
        }
        earned += weighted

    earned = min(earned, total_score)
    earned = round(earned, 1)

    lines = ["评分明细:"]
    for dim_name, d in details.items():
        lines.append(f"  {dim_name}: {d['score']}/{d['max']} (权重 {d['weight']})")
    lines.append(f"  总分: {earned}/{total_score}")

    return {
        "total": earned,
        "details": details,
        "summary": "\n".join(lines),
    }


# ================================================================
# 工具 3: 语法/表述检查
# ================================================================

CHECK_GRAMMAR_PROMPT = """你是一位中文写作审校专家。请检查以下文本的语法、表述和格式问题。

要求：
1. 只指出真正存在问题的部分
2. 对每个问题给出原文引用、问题类型（语法/表述/格式/逻辑）和修改建议
3. 如果文本整体质量好，请直接说"未发现明显问题"
4. 输出简洁，不要过度批评

待检查文本：
---
{text}
---

请给出检查结果："""


def check_grammar(text: str, llm=None) -> str:
    """
    中文语法和表述检查。使用 LLM 进行审校。
    Args:
        text: 待检查的文本
        llm: LangChain ChatModel 实例（可选，若不传则返回提示）
    Returns:
        审校结果文本
    """
    if not llm:
        return "[语法检查] 需要传入 LLM 实例才能执行。请在 Agent 中调用此工具。"

    prompt = CHECK_GRAMMAR_PROMPT.format(text=text[:8000])  # 限制长度，避免 token 超限
    try:
        response = llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        return f"[语法检查失败] {e}"


# ================================================================
# 工具 4: 导出 Markdown
# ================================================================

def export_markdown(
    content: str,
    filename: str,
    output_dir: Optional[str] = None,
) -> str:
    """
    将内容导出为 Markdown 文件。
    Args:
        content: Markdown 文本内容
        filename: 文件名（不含路径，自动加 .md 后缀）
        output_dir: 输出目录，默认 outputs/evaluations/
    Returns:
        导出文件的绝对路径
    """
    output_dir = output_dir or EVALUATION_DIR
    os.makedirs(output_dir, exist_ok=True)

    if not filename.endswith(".md"):
        filename += ".md"

    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


# ================================================================
# 工具 5: 生成 Mermaid 流程图
# ================================================================

MERMAID_SYSTEM_PROMPT = """你是一位技术图表专家。根据用户描述，生成标准的 Mermaid.js 流程图代码。

要求：
1. 只输出 Mermaid 代码，放在 ```mermaid 代码块内
2. 使用 graph TD（自上而下）或 graph LR（从左到右）布局
3. 节点使用方括号 [步骤] 或圆括号 (状态)，不要使用特殊 Unicode 字符
4. 节点文字简洁（每节点不超过 15 字）
5. 确保语法正确，可直接渲染
6. 如果用户描述不够清晰，生成一个合理的默认流程图"""


def generate_flowchart(description: str, llm=None) -> str:
    """
    根据描述生成 Mermaid 流程图代码。
    Args:
        description: 流程图描述（如"实验三的完整操作流程"）
        llm: LangChain ChatModel 实例
    Returns:
        Mermaid 代码字符串（不含 markdown 包裹）
    """
    if not llm:
        return "graph TD\n  A[Mermaid 流程图] --> B[需要 LLM 实例]"

    from langchain_core.messages import SystemMessage, HumanMessage

    messages = [
        SystemMessage(content=MERMAID_SYSTEM_PROMPT),
        HumanMessage(content=f"请为以下内容生成 Mermaid 流程图：\n{description}"),
    ]

    try:
        response = llm.invoke(messages)
        text = response.content if hasattr(response, "content") else str(response)

        # 提取 ```mermaid ... ``` 代码块
        if "```mermaid" in text:
            start = text.find("```mermaid") + len("```mermaid")
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()

        return text.strip()
    except Exception as e:
        return f"graph TD\n  A[生成失败: {str(e)[:30]}] --> B[请重试]"


# ================================================================
# 批量导出：LangChain Tool 对象列表
# ================================================================

def create_langchain_tools(llm=None):
    """
    创建所有工具的 LangChain @tool 包装版本。
    供 core/agent.py 初始化 Agent 时使用。
    """
    from langchain_core.tools import tool

    @tool
    def web_search_tool(query: str) -> str:
        """联网搜索补充信息。当你需要查找课程资料之外的实时知识时使用。"""
        return web_search(query)

    @tool
    def calculate_score_tool(dimension_scores_json: str) -> str:
        """
        按课程评分标准计算总分。
        输入 JSON 字符串，如: {"项目目标与任务分解": 8, "系统架构设计图及模块功能概述": 9, ...}
        """
        try:
            scores = json.loads(dimension_scores_json)
        except json.JSONDecodeError:
            return "输入格式错误，请提供合法 JSON 字符串。"
        result = calculate_score(scores)
        return result["summary"]

    @tool
    def check_grammar_tool(text: str) -> str:
        """检查中文文本的语法、表述和格式问题。"""
        return check_grammar(text, llm=llm)

    @tool
    def generate_flowchart_tool(description: str) -> str:
        """根据实验描述生成 Mermaid 流程图代码。用于可视化实验步骤。"""
        return generate_flowchart(description, llm=llm)

    @tool
    def export_markdown_tool(content: str, filename: str) -> str:
        """将内容导出为 Markdown 文件。filename 不含路径。"""
        return export_markdown(content, filename)

    return [
        web_search_tool,
        calculate_score_tool,
        check_grammar_tool,
        generate_flowchart_tool,
        export_markdown_tool,
    ]
