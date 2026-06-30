"""
报告结构分析器
负责：识别报告结构、拆解实验模块、检测完成度
"""
import re
from typing import List
from dataclasses import dataclass, field


@dataclass
class Experiment:
    """单个实验/模块信息"""
    name: str                           # 实验名称
    index: int                          # 序号
    content: str                        # 这部分报告的内容
    has_content: bool                   # 是否已填写内容
    completeness: float                 # 完成度 0-1
    key_sections: List[str] = field(default_factory=list)  # 需要的子章节


@dataclass
class ReportStructure:
    """报告整体结构"""
    title: str                          # 报告标题
    total_chars: int                    # 总字符数
    experiments: List[Experiment]       # 实验/模块列表
    completeness: float                 # 整体完成度 0-1
    sections: List[str]                 # 识别到的章节标题


class ReportAnalyzer:
    """
    分析实验报告的结构，识别其中的实验模块和完成度。
    支持多种报告格式（课程项目报告、通用实验报告）。
    """

    # 常见的实验/章节标记正则
    EXPERIMENT_PATTERNS = [
        # 数字编号：实验一、实验1、Experiment 1
        re.compile(r"(?:实验|Experiment\s*|Lab\s*)([一二三四五六七八九十\d]+)"),
        # Markdown 标题：## 实验N
        re.compile(r"^#{1,3}\s*实验\s*([一二三四五六七八九十\d]+)", re.MULTILINE),
        # 数字序号开头的大标题
        re.compile(r"^#{1,2}\s*\d+[.、]\s*(.+)", re.MULTILINE),
    ]

    # 完成度检测的占位符标记
    PLACEHOLDER_MARKERS = [
        "（请在此处", "（此处写", "【请补充】", "（待填写）",
        "TODO", "待完成", "（选填）", "（可选）",
        "请在此处详细描述",
    ]

    # 内容充实的最小字符阈值
    MIN_CONTENT_LENGTH = 80

    @classmethod
    def analyze(cls, report_text: str) -> ReportStructure:
        """分析报告整体结构"""
        # 尝试提取标题（第一行非空）
        lines = [l.strip() for l in report_text.split("\n") if l.strip()]
        title = lines[0] if lines else "未命名报告"
        if len(title) > 80:
            title = title[:80] + "..."

        # 拆解实验模块
        experiments = cls._extract_experiments(report_text)

        # 如果没有识别到明确实验，按章节拆分
        if not experiments:
            experiments = cls._extract_by_sections(report_text)

        # 如果还是没有，把整个报告当作一个模块
        if not experiments:
            experiments = [Experiment(
                name="完整报告",
                index=1,
                content=report_text,
                has_content=len(report_text) > cls.MIN_CONTENT_LENGTH,
                completeness=cls._calc_completeness(report_text),
            )]

        # 整体完成度
        if experiments:
            overall = sum(e.completeness for e in experiments) / len(experiments)
        else:
            overall = 0.0

        # 章节列表
        sections = cls._extract_section_titles(report_text)

        return ReportStructure(
            title=title,
            total_chars=len(report_text),
            experiments=experiments,
            completeness=round(overall, 2),
            sections=sections,
        )

    @classmethod
    def get_empty_experiments(cls, report_text: str) -> List[Experiment]:
        """获取所有未完成/空白较多的实验模块"""
        structure = cls.analyze(report_text)
        return [e for e in structure.experiments if e.completeness < 0.5]

    @classmethod
    def get_completed_experiments(cls, report_text: str) -> List[Experiment]:
        """获取已完成/内容较充实的实验模块"""
        structure = cls.analyze(report_text)
        return [e for e in structure.experiments if e.completeness >= 0.5]

    # ----------------------------------------------------------------
    # 私有方法
    # ----------------------------------------------------------------

    @classmethod
    def _extract_experiments(cls, text: str) -> List[Experiment]:
        """按实验标记正则提取各个实验模块"""
        # 找所有实验标记的位置
        matches = []
        for pattern in cls.EXPERIMENT_PATTERNS:
            for m in pattern.finditer(text):
                matches.append((m.start(), m.group()))

        if len(matches) < 2:
            return []

        # 按位置排序，提取每段内容
        matches.sort()
        experiments = []
        for i, (pos, label) in enumerate(matches):
            start = pos
            end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()

            name = cls._clean_experiment_name(label)
            has_content = len(content) > cls.MIN_CONTENT_LENGTH
            experiments.append(Experiment(
                name=name,
                index=i + 1,
                content=content,
                has_content=has_content,
                completeness=cls._calc_completeness(content),
            ))

        return experiments

    @classmethod
    def _extract_by_sections(cls, text: str) -> List[Experiment]:
        """按 Markdown 标题或数字序号拆分章节"""
        # 匹配 ## 标题或 一、二、三 这类中文序号
        section_pattern = re.compile(
            r"(?:^#{1,3}\s+.+$)|(?:^[（(]?[一二三四五六七八九十\d]+[）).、]\s*.+$)",
            re.MULTILINE,
        )

        positions = [(m.start(), m.group().strip()) for m in section_pattern.finditer(text)]

        if len(positions) < 2:
            return []

        experiments = []
        for i, (pos, label) in enumerate(positions):
            start = pos
            end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
            content = text[start:end].strip()
            has_content = len(content) > cls.MIN_CONTENT_LENGTH
            experiments.append(Experiment(
                name=cls._clean_experiment_name(label),
                index=i + 1,
                content=content,
                has_content=has_content,
                completeness=cls._calc_completeness(content),
            ))

        return experiments

    @classmethod
    def _calc_completeness(cls, text: str) -> float:
        """基于占位符密度和内容长度估算完成度"""
        if not text:
            return 0.0

        # 占位符计数
        placeholder_count = sum(text.count(m) for m in cls.PLACEHOLDER_MARKERS)

        # 内容长度因子（越长越完整，max 3000 字符封顶）
        length_factor = min(len(text) / 3000, 1.0)

        # 占位符惩罚
        placeholder_penalty = min(placeholder_count * 0.15, 0.6)

        completeness = length_factor - placeholder_penalty
        return max(0.0, min(completeness, 1.0))

    @classmethod
    def _extract_section_titles(cls, text: str) -> List[str]:
        """提取所有章节标题"""
        pattern = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)
        return [m.group(1).strip() for m in pattern.finditer(text)]

    @staticmethod
    def _clean_experiment_name(raw: str) -> str:
        """清理实验名称，去掉 markdown 标记符号"""
        name = raw.strip().lstrip("#").strip()
        # 限制长度
        return name[:60] if len(name) > 60 else name
