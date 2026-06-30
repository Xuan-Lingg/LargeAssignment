"""
策略路由器
实现双重判断机制：UI 预设 + LLM 语义校验
"""
import json
import re
from typing import Optional
from dataclasses import dataclass


# 四种策略定义
STRATEGIES = {
    "decompose": "实验报告拆解指导",
    "evaluate": "完整报告评估打分",
    "explain": "单个实验知识点讲解",
    "auto": "自动检测",
}

STRATEGY_DESCRIPTIONS = {
    "decompose": "报告有空白待填充，需要写作指导、知识点梳理和步骤建议",
    "evaluate": "报告内容完整，需要按评分标准进行多维度打分和评语",
    "explain": "针对某个具体实验或知识点进行深度讲解",
    "auto": "让 AI 自动判断最合适的处理方式",
}


@dataclass
class StrategyResult:
    """策略路由结果"""
    strategy: str          # 最终策略 key: decompose / evaluate / explain
    is_match: bool         # 与用户选择是否一致
    confidence: float      # 置信度 0-1
    reason: str            # 判断理由
    recommended: str       # 推荐策略 key


class StrategyRouter:
    """
    策略路由器：负责用户策略选择与报告内容的匹配校验。
    双重判断：UI 层面预设 + LLM 语义二次校验。
    """

    # ----------------------------------------------------------------
    # 静态方法：快速规则判断（不依赖 LLM，零成本）
    # ----------------------------------------------------------------

    @staticmethod
    def quick_check(report_text: str) -> str:
        """
        基于规则快速判断报告状态，不需要 LLM。
        可用于 UI 初始化时给用户一个默认建议。
        """
        text = report_text.strip()
        length = len(text)

        # 空报告
        if length < 100:
            return "decompose"

        # 检测空白占位符特征（待完成报告常见标志）
        placeholder_markers = [
            "（请在此处", "（此处写", "【请补充】", "（待填写）",
            "TODO", "待完成", "（选填）", "（可选）",
            "（请在此处详细描述",  # 来自课程报告模板
        ]
        placeholder_count = sum(1 for m in placeholder_markers if m in text)

        # 检测完整性特征
        completeness_markers = [
            "摘要", "评分明细", "总结", "不足与改进",
            "系统界面", "示例结果",
        ]
        completeness_count = sum(1 for m in completeness_markers if m in text)

        # 判断逻辑
        if placeholder_count >= 2:
            return "decompose"
        elif length > 3000 and completeness_count >= 4:
            return "evaluate"
        elif placeholder_count >= 1 and length < 2000:
            return "decompose"
        else:
            return "auto"  # 不确定时走 LLM

    # ----------------------------------------------------------------
    # LLM 语义校验
    # ----------------------------------------------------------------

    @staticmethod
    def validate(
        user_strategy: str,
        report_content: str,
        llm=None,
    ) -> StrategyResult:
        """
        LLM 二次校验：判断用户选择的策略是否与报告内容匹配。
        """
        from core.prompts import build_validation_prompt

        if llm is None:
            # 无 LLM 时，仅用规则判断
            quick = StrategyRouter.quick_check(report_content)
            return StrategyResult(
                strategy=quick,
                is_match=(user_strategy == quick or user_strategy == "auto"),
                confidence=0.5,
                reason="（无 LLM，仅基于规则判断）",
                recommended=quick,
            )

        prompt = build_validation_prompt(user_strategy, report_content)

        try:
            response = llm.invoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)
            data = StrategyRouter._parse_json(text)
        except Exception as e:
            # LLM 调用失败，回退到规则判断
            quick = StrategyRouter.quick_check(report_content)
            return StrategyResult(
                strategy=quick,
                is_match=False,
                confidence=0.3,
                reason=f"LLM 校验失败({e})，使用规则判断",
                recommended=quick,
            )

        is_match = data.get("is_match", True)
        recommended = data.get("recommended_strategy", user_strategy)
        reason = data.get("reason", "")

        # 将中文策略名映射回 key
        recommended_key = StrategyRouter._strategy_name_to_key(recommended)

        final = recommended_key if not is_match else user_strategy
        if user_strategy == "auto":
            final = recommended_key
            is_match = True

        return StrategyResult(
            strategy=final,
            is_match=is_match,
            confidence=0.85,
            reason=reason,
            recommended=recommended_key,
        )

    # ----------------------------------------------------------------
    # 自动检测（LLM 判断最合适的策略）
    # ----------------------------------------------------------------

    @staticmethod
    def auto_detect(report_content: str, llm=None) -> StrategyResult:
        """LLM 自动分析报告特征，判断最合适的策略"""
        from core.prompts import build_auto_detect_prompt

        if llm is None:
            quick = StrategyRouter.quick_check(report_content)
            return StrategyResult(
                strategy=quick,
                is_match=True,
                confidence=0.5,
                reason="（无 LLM，基于规则判断）",
                recommended=quick,
            )

        prompt = build_auto_detect_prompt(report_content)

        try:
            response = llm.invoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)
            data = StrategyRouter._parse_json(text)
        except Exception:
            quick = StrategyRouter.quick_check(report_content)
            return StrategyResult(
                strategy=quick,
                is_match=True,
                confidence=0.3,
                reason="LLM 判断失败，使用规则判断",
                recommended=quick,
            )

        strategy_name = data.get("strategy", "实验报告拆解指导")
        strategy_key = StrategyRouter._strategy_name_to_key(strategy_name)
        confidence = data.get("confidence", 0.5)
        reason = data.get("reason", "")

        return StrategyResult(
            strategy=strategy_key,
            is_match=True,
            confidence=confidence,
            reason=reason,
            recommended=strategy_key,
        )

    # ----------------------------------------------------------------
    # 工具方法
    # ----------------------------------------------------------------

    @staticmethod
    def _parse_json(text: str) -> dict:
        """从 LLM 回复中提取 JSON（容忍前后多余文本）"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 尝试提取 { ... } 块
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return {}

    @staticmethod
    def _strategy_name_to_key(name: str) -> str:
        """将中文策略名映射为 key"""
        name_lower = name.lower()
        if "拆解" in name_lower or "指导" in name_lower or "decompose" in name_lower:
            return "decompose"
        elif "评估" in name_lower or "打分" in name_lower or "评分" in name_lower or "evaluate" in name_lower:
            return "evaluate"
        elif "知识点" in name_lower or "讲解" in name_lower or "explain" in name_lower:
            return "explain"
        elif "自动" in name_lower or "auto" in name_lower:
            return "auto"
        else:
            return "decompose"  # 默认

    @staticmethod
    def get_strategy_label(key: str) -> str:
        """获取策略的中文显示名称"""
        return STRATEGIES.get(key, "未知策略")
