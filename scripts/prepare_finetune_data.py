"""
准备微调训练数据
从已完成高分报告中提取 报告→评分 的指令微调数据对。
输出 JSONL 格式，可直接用于 LLaMA-Factory 或 Unsloth 训练。

用法: python scripts/prepare_finetune_data.py [--output data/finetune_data.jsonl]
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import REFERENCE_DIR, METADATA_FILE, SCORE_DIMENSIONS, TOTAL_SCORE
from core.document_parser import DocumentParser
from core.prompts import _format_dimensions


def main():
    parser = argparse.ArgumentParser(description="准备微调训练数据")
    parser.add_argument("--output", type=str, default="data/finetune_data.jsonl",
                        help="输出 JSONL 文件路径")
    parser.add_argument("--use-llm", action="store_true",
                        help="使用 LLM 辅助生成评分理由（需要配置 API Key）")
    args = parser.parse_args()

    print("=" * 60)
    print("  微调训练数据准备工具")
    print("=" * 60)

    # 加载 metadata
    if not os.path.exists(METADATA_FILE):
        print(f"错误: 未找到 metadata.json ({METADATA_FILE})")
        print("请先使用 add_reference_report.py 添加参考报告和评分。")
        sys.exit(1)

    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # 过滤掉说明字段
    reports = {k: v for k, v in metadata.items() if not k.startswith("_")}
    print(f"找到 {len(reports)} 份已评分的参考报告")

    # 构造训练数据
    training_data = []
    score_dim_text = _format_dimensions()

    for filename, info in reports.items():
        file_path = os.path.join(REFERENCE_DIR, filename)
        if not os.path.isfile(file_path):
            print(f"  跳过（文件不存在）: {filename}")
            continue

        # 解析报告文本
        try:
            report_text = DocumentParser.parse(file_path)
        except Exception as e:
            print(f"  跳过（解析失败）: {filename} - {e}")
            continue

        scores = info.get("scores", {})
        total = info.get("total", 0)
        comment = info.get("comment", "")

        # 构建训练样本
        instruction = f"请根据以下评分标准，对这份实验报告进行评分。\n\n评分标准：\n{score_dim_text}"

        # 输入：报告内容（截断到前 4000 字以控制 token）
        input_text = report_text[:4000]

        # 输出：评分结果 JSON
        output_data = {
            "scores": scores,
            "strengths": info.get("highlights", []),
            "weaknesses": [],
            "suggestions": [],
            "overall_comment": comment,
        }
        output_text = json.dumps(output_data, ensure_ascii=False)

        training_data.append({
            "instruction": instruction,
            "input": input_text,
            "output": output_text,
        })

        print(f"  ✅ {filename} (总分 {total})")

    # 写入 JSONL
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        for item in training_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print("\n" + "=" * 60)
    print(f"  已生成 {len(training_data)} 条训练数据")
    print(f"  输出文件: {args.output}")
    print("=" * 60)

    # 使用提示
    if len(training_data) >= 5:
        print("\n💡 下一步 — 使用 LLaMA-Factory 进行微调：")
        print("  1. git clone https://github.com/hiyouga/LLaMA-Factory.git")
        print("  2. 将输出文件放入 LLaMA-Factory/data/ 目录")
        print("  3. 编辑 dataset_info.json 注册数据集")
        print("  4. 选择 Qwen2.5-1.5B 模型，进行 LoRA 微调（1-3 epochs）")
    else:
        print("\n⚠ 训练数据不足（建议 ≥5 条），微调效果可能不佳。")


if __name__ == "__main__":
    main()
