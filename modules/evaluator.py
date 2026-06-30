"""
评估打分引擎
负责：多维度评分解析、评分结果结构化、与高分报告对比分析
"""
import sys
import os
import json
import re
from typing import Optional
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import SCORE_DIMENSIONS, TOTAL_SCORE, METADATA_FILE


@dataclass
class DimensionScore:
    """单个维度的评分"""
    name: str
    score: float
    max_score: int
    weight: float
    comment: str = ""


@dataclass
class EvaluationResult:
    """评估结果"""
    total_score: float
    total_max: int
    dimensions: list = field(default_factory=list)
    strengths: list = field(default_factory=list)
    weaknesses: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    overall_comment: str = ""
    reference_comparison: str = ""


class Evaluator:
    """
    评估引擎：解析 LLM 评分输出，计算总分，对比参考报告。
    """

    def __init__(self):
        self._dimensions_config = SCORE_DIMENSIONS
        self._total_score = TOTAL_SCORE

    # ----------------------------------------------------------------
    # 主要接口
    # ----------------------------------------------------------------

    def parse_llm_response(self, raw_response: str) -> EvaluationResult:
        """
        从 LLM 评分回复中解析结构化评估结果。
        能容忍 LLM 输出格式的细微偏差。
        """
        data = self._extract_json(raw_response)

        if not data:
            return self._empty_result("无法解析 LLM 评分输出")

        scores_raw = data.get("scores", {})

        # 解析各维度
        dimensions = []
        for dim_name, config in self._dimensions_config.items():
            score = float(scores_raw.get(dim_name, 0))
            score = max(0, min(score, config["max"]))
            dimensions.append(DimensionScore(
                name=dim_name,
                score=score,
                max_score=config["max"],
                weight=config["weight"],
            ))

        # 加权总分
        total = sum(d.score * d.weight for d in dimensions)
        total = round(min(total, self._total_score), 1)

        return EvaluationResult(
            total_score=total,
            total_max=self._total_score,
            dimensions=dimensions,
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            suggestions=data.get("suggestions", []),
            overall_comment=data.get("overall_comment", ""),
        )

    def compare_with_reference(
        self,
        student_scores: dict,
        reference_report_name: str,
    ) -> str:
        """
        将学生得分与一份高分参考报告对比。
        """
        ref_scores = self._load_reference_scores(reference_report_name)
        if not ref_scores:
            return f"（未找到参考报告 '{reference_report_name}' 的评分数据）"

        lines = [f"与参考报告「{reference_report_name}」的对比：\n"]
        lines.append("| 维度 | 学生得分 | 参考得分 | 差距 |")
        lines.append("|------|---------|---------|------|")

        total_student = 0
        total_ref = 0
        for dim_name, config in self._dimensions_config.items():
            s = student_scores.get(dim_name, 0)
            r = ref_scores.get(dim_name, 0)
            diff = s - r
            sign = "+" if diff > 0 else ""
            lines.append(f"| {dim_name} | {s}/{config['max']} | {r}/{config['max']} | {sign}{diff:.1f} |")
            total_student += min(s, config["max"])
            total_ref += min(r, config["max"])

        lines.append(f"\n学生总分: {total_student:.1f} | 参考总分: {total_ref:.1f} | 差距: {total_student - total_ref:+.1f}")
        return "\n".join(lines)

    def to_radar_data(self, result: EvaluationResult) -> dict:
        """将评估结果转为前端雷达图所需的数据格式"""
        return {
            dim.name: dim.score
            for dim in result.dimensions
        }

    def to_dict(self, result: EvaluationResult) -> dict:
        """转为可 JSON 序列化的字典，供 export_markdown 等使用"""
        return {
            "total_score": result.total_score,
            "total_max": result.total_max,
            "dimensions": [
                {"name": d.name, "score": d.score, "max": d.max_score}
                for d in result.dimensions
            ],
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            "suggestions": result.suggestions,
            "overall_comment": result.overall_comment,
            "reference_comparison": result.reference_comparison,
        }

    # ----------------------------------------------------------------
    # 私有方法
    # ----------------------------------------------------------------

    def _extract_json(self, text: str) -> dict:
        """从 LLM 回复中提取 JSON（与 strategy_router 逻辑一致）"""
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # ```json 代码块
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except (json.JSONDecodeError, TypeError):
                pass

        # 裸 { }
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except (json.JSONDecodeError, TypeError):
                pass

        return {}

    def _load_reference_scores(self, report_name: str) -> dict:
        """加载参考报告的评分（来自 metadata.json）"""
        if not os.path.exists(METADATA_FILE):
            return {}

        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

        # metadata.json 格式: {"报告文件名": {"scores": {...}, "total": ...}, ...}
        entry = metadata.get(report_name, {})
        return entry.get("scores", {})

    def _empty_result(self, message: str) -> EvaluationResult:
        return EvaluationResult(
            total_score=0,
            total_max=self._total_score,
            overall_comment=message,
        )


# ----------------------------------------------------------------
# metadata.json 管理工具
# ----------------------------------------------------------------

def init_metadata_file():
    """如果 metadata.json 不存在，创建空模板"""
    if os.path.exists(METADATA_FILE):
        return

    template = {
        "_说明": "此文件记录已完成高分报告的评分元数据，供评估引擎参考。",
        "_格式": {
            "报告文件名.docx": {
                "scores": {
                    "项目目标与任务分解": 9,
                    "系统架构设计图及模块功能概述": 9,
                    "关键技术与工具": 8,
                    "关键模块代码实现": 18,
                    "系统界面实现及示例结果": 17,
                    "现场演示": 28,
                },
                "total": 89,
                "comment": "整体质量优秀，架构清晰...",
                "highlights": ["RAG 实现完整", "代码规范"],
            },
        },
    }

    os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)


def add_reference_metadata(filename: str, scores: dict, total: float, comment: str = "", highlights: list = None):
    """添加一份参考报告的评分到 metadata.json"""
    init_metadata_file()

    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    data[filename] = {
        "scores": scores,
        "total": total,
        "comment": comment,
        "highlights": highlights or [],
    }

    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
