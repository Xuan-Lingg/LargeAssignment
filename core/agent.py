"""
中央调度 Agent
使用 LangChain ReAct 模式，将 LLM + 工具 + RAG + 策略路由整合为统一入口。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from config.settings import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    GOOGLE_API_KEY,
    GEMINI_MODEL,
    GEMINI_BASE_URL,
)
from modules.strategy_router import StrategyRouter, StrategyResult
from modules.report_analyzer import ReportAnalyzer, ReportStructure
from modules.rag_engine import RAGEngine
from modules.tools import create_langchain_tools


@dataclass
class AgentResponse:
    """Agent 统一响应"""
    success: bool
    strategy: str
    content: str
    report_structure: Optional[ReportStructure] = None
    mermaid_code: Optional[str] = None
    score_data: Optional[dict] = None


class ReportAssistantAgent:
    """
    实验报告助手 — 中央 Agent。
    整合 LLM + 工具 + RAG + 策略路由，对外提供统一接口。
    """

    def __init__(self):
        """初始化所有依赖：LLM、RAG 引擎、工具"""
        import logging
        logging.basicConfig(level=logging.INFO)
        self._logger = logging.getLogger("Agent")

        # --- 主 LLM: DeepSeek（对话、分析、生成、Mermaid 流程图） ---
        self._logger.info(f"正在连接 DeepSeek: {DEEPSEEK_MODEL} ...")
        self._llm = ChatOpenAI(
            model=DEEPSEEK_MODEL,
            base_url=DEEPSEEK_BASE_URL,
            api_key=DEEPSEEK_API_KEY,
            temperature=0.3,
            max_tokens=4096,
            timeout=120,          # 连接超时 120 秒
            request_timeout=300,  # 请求超时 300 秒（长报告需要）
            max_retries=2,        # 自动重试 2 次
        )
        self._logger.info("DeepSeek 连接已配置")

        # --- 多模态: Gemini（仅按需加载） ---
        # Gemini 2.5 Flash 只有文本能力，Nano Banana 等才有多模态
        # 此处仅存储配置，不创建连接，避免 API Key 验证拖慢启动
        self._gemini = None
        self._gemini_available = self._check_gemini_multimodal()

        # --- RAG 引擎 ---
        self._logger.info("正在加载 RAG 引擎...")
        self._rag = RAGEngine()
        self._logger.info("RAG 引擎就绪")

        # --- 策略路由器 ---
        self._router = StrategyRouter()

        # --- 工具集 ---
        self._tools = create_langchain_tools(llm=self._llm)
        self._logger.info("工具集已加载")

        # --- 初始化 LangChain Agent（带工具） ---
        self._logger.info("正在编译 LangGraph Agent (首次可能较慢)...")
        from langgraph.prebuilt import create_react_agent
        from core.prompts import AGENT_SYSTEM_PROMPT

        self._agent = create_react_agent(
            model=self._llm,
            tools=self._tools,
        )
        self._logger.info("LangGraph Agent 就绪")

    # ----------------------------------------------------------------
    # Gemini 多模态判断与懒加载
    # ----------------------------------------------------------------

    def _check_gemini_multimodal(self) -> bool:
        """判断 Gemini 配置是否支持多模态（Nano Banana / Pro Vision）"""
        # 只有明确配置了多模态模型才启用 Gemini
        multimodal_models = ["nano-banana", "gemini-pro-vision", "gemini-2.0-flash"]
        model_lower = GEMINI_MODEL.lower()
        for mm in multimodal_models:
            if mm in model_lower:
                return True
        self._logger.info(
            f"Gemini ({GEMINI_MODEL}) 非多模态模型，流程图将使用 DeepSeek + Mermaid 渲染"
        )
        return False

    def _get_gemini(self):
        """懒加载 Gemini 客户端（仅多模态模型时创建）"""
        if not self._gemini_available:
            return None
        if self._gemini is None:
            self._logger.info(f"正在连接 Gemini: {GEMINI_MODEL} ...")
            self._gemini = ChatOpenAI(
                model=GEMINI_MODEL,
                base_url=GEMINI_BASE_URL,
                api_key=GOOGLE_API_KEY,
                temperature=0.3,
                max_tokens=4096,
                timeout=15,
                request_timeout=30,
            )
            self._logger.info("Gemini 连接已配置")
        return self._gemini

    # ----------------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------------

    def process(
        self,
        report_content: str,
        user_strategy: str = "auto",
        user_query: str = "",
    ) -> AgentResponse:
        """
        核心入口：处理用户请求。
        Args:
            report_content: 上传的报告文本
            user_strategy: 用户选择的策略（decompose/evaluate/explain/auto）
            user_query: 用户附加的文字说明（如"请重点看实验三"）
        Returns:
            AgentResponse
        """
        # Step 1: 分析报告结构
        structure = ReportAnalyzer.analyze(report_content)

        # Step 2: 策略路由
        if user_strategy == "auto":
            strategy_result = self._router.auto_detect(report_content, llm=self._llm)
        else:
            strategy_result = self._router.validate(user_strategy, report_content, llm=self._llm)

        # Step 3: 按策略执行
        if strategy_result.strategy == "decompose":
            return self._handle_decompose(report_content, structure, user_query)
        elif strategy_result.strategy == "evaluate":
            return self._handle_evaluate(report_content, structure, user_query)
        elif strategy_result.strategy == "explain":
            return self._handle_explain(report_content, structure, user_query)
        else:
            return AgentResponse(
                success=False,
                strategy=strategy_result.strategy,
                content=f"无法识别的策略: {strategy_result.strategy}",
            )

    # ----------------------------------------------------------------
    # 策略处理
    # ----------------------------------------------------------------

    def _handle_decompose(
        self, report_content: str, structure: ReportStructure, query: str
    ) -> AgentResponse:
        """处理「实验报告拆解指导」"""
        from core.prompts import build_decompose_prompt

        # RAG 检索课程知识
        rag_context = self._rag.retrieve_combined(
            query=structure.title,
            top_k=5,
        )

        # 构建 Prompt
        prompt = build_decompose_prompt(
            rag_context=rag_context,
            report_content=report_content,
        )

        # 调用 LLM
        response = self._llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # 尝试生成流程图
        mermaid_code = None
        if structure.experiments:
            exp_names = "、".join([e.name for e in structure.experiments[:3]])
            from modules.tools import generate_flowchart
            mermaid_code = generate_flowchart(
                f"实验报告结构：{structure.title}，包含实验：{exp_names}",
                llm=self._llm,
            )
            # 如果生成失败（返回的是错误图），不传 mermaid_code
            if "生成失败" in mermaid_code or "需要 LLM" in mermaid_code:
                mermaid_code = None

        return AgentResponse(
            success=True,
            strategy="decompose",
            content=content,
            report_structure=structure,
            mermaid_code=mermaid_code,
        )

    def _handle_evaluate(
        self, report_content: str, structure: ReportStructure, query: str
    ) -> AgentResponse:
        """处理「完整报告评估打分」"""
        from core.prompts import build_evaluation_prompt

        # RAG 检索评分标准和高分范例
        rag_context = self._rag.retrieve_combined(
            query=f"评分标准 报告评估 {structure.title}",
            top_k=5,
        )

        # 构建 Prompt
        prompt = build_evaluation_prompt(
            rag_context=rag_context,
            report_content=report_content,
        )

        # 调用 LLM
        response = self._llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # 尝试解析评分 JSON
        import json
        score_data = None
        try:
            # 提取 JSON
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
            if match:
                score_data = json.loads(match.group(1).strip())
            elif "{" in content:
                start = content.index("{")
                end = content.rindex("}") + 1
                score_data = json.loads(content[start:end])
        except Exception:
            score_data = None

        return AgentResponse(
            success=True,
            strategy="evaluate",
            content=content,
            report_structure=structure,
            score_data=score_data,
        )

    def _handle_explain(
        self, report_content: str, structure: ReportStructure, query: str
    ) -> AgentResponse:
        """处理「单个实验知识点讲解」"""
        from core.prompts import build_knowledge_prompt

        # 构建搜索 query
        search_query = query if query else structure.title

        # RAG 检索
        rag_context = self._rag.retrieve_combined(
            query=search_query,
            top_k=5,
        )

        # 构建 Prompt
        prompt = build_knowledge_prompt(
            rag_context=rag_context,
            query=search_query,
        )

        # 调用 LLM
        response = self._llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # 尝试生成思维导图
        from modules.tools import generate_flowchart
        mermaid_code = generate_flowchart(
            f"知识点思维导图，主题：{search_query}，使用 mindmap 布局",
            llm=self._llm,
        )
        if "生成失败" in mermaid_code or "需要 LLM" in mermaid_code:
            mermaid_code = None

        return AgentResponse(
            success=True,
            strategy="explain",
            content=content,
            report_structure=structure,
            mermaid_code=mermaid_code,
        )

    # ----------------------------------------------------------------
    # 便捷方法
    # ----------------------------------------------------------------

    def quick_analyze(self, report_text: str) -> ReportStructure:
        """快速分析报告结构（不消耗 LLM token）"""
        return ReportAnalyzer.analyze(report_text)

    def quick_strategy_check(self, report_text: str) -> str:
        """快速策略建议（不消耗 LLM token）"""
        return StrategyRouter.quick_check(report_text)
