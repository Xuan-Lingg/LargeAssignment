"""
添加高分参考报告到知识库
用法: python scripts/add_reference_report.py <报告文件路径> [--score 总分] [--comment 评语]
示例: python scripts/add_reference_report.py data/reference_reports/实验一_高分.docx --score 92
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import REFERENCE_DIR, METADATA_FILE, REFERENCE_COLLECTION, SCORE_DIMENSIONS
from modules.rag_engine import RAGEngine
from core.document_parser import DocumentParser
from modules.evaluator import add_reference_metadata, init_metadata_file


def main():
    parser = argparse.ArgumentParser(description="添加高分参考报告到知识库")
    parser.add_argument("file_path", help="报告文件路径（支持 pdf/docx/md/txt）")
    parser.add_argument("--score", type=float, default=None, help="报告总分（0-100）")
    parser.add_argument("--comment", type=str, default="", help="评语/备注")
    parser.add_argument("--highlight", type=str, nargs="*", default=[], help="亮点标签")
    parser.add_argument("--scores", type=str, default=None,
                        help='各维度分数 JSON，如: \'{"项目目标与任务分解": 9, "系统架构设计": 8}\'')
    args = parser.parse_args()

    # 检查文件是否存在
    if not os.path.isfile(args.file_path):
        print(f"错误: 文件不存在: {args.file_path}")
        sys.exit(1)

    filename = os.path.basename(args.file_path)

    print("=" * 60)
    print("  添加高分参考报告")
    print("=" * 60)
    print(f"  文件: {filename}")

    # Step 1: 确认文件在 experiment_guides 目录中（不复制，只记录路径）
    file_path_abs = os.path.abspath(args.file_path)
    print(f"  引用路径: {file_path_abs}")

    # Step 2: 解析文件内容
    print(f"\n[解析] 正在解析文档...")
    try:
        text = DocumentParser.parse(file_path_abs)
        print(f"  解析成功: {len(text)} 字符")
    except Exception as e:
        print(f"  解析失败: {e}")
        sys.exit(1)

    # Step 3: 入库到 ChromaDB
    print(f"\n[入库] 正在添加到向量数据库...")
    engine = RAGEngine()
    count = engine.add_document(file_path_abs, REFERENCE_COLLECTION)
    print(f"  已添加 {count} 个 chunk 到 Collection '{REFERENCE_COLLECTION}'")

    # Step 4: 如果提供了分数，写入 metadata.json
    if args.score is not None or args.scores is not None:
        print(f"\n[元数据] 正在记录评分信息...")
        init_metadata_file()

        # 解析维度分数
        dimension_scores = {}
        if args.scores:
            try:
                dimension_scores = json.loads(args.scores)
            except json.JSONDecodeError:
                print(f"  警告: 无法解析 --scores JSON，已忽略")
        elif args.score is not None:
            # 没有各维度明细时，均分
            dim_count = len(SCORE_DIMENSIONS)
            avg = args.score / dim_count
            for name in SCORE_DIMENSIONS:
                dimension_scores[name] = round(avg, 1)

        add_reference_metadata(
            filename=filename,
            scores=dimension_scores,
            total=args.score or 0,
            comment=args.comment,
            highlights=args.highlight,
        )
        print(f"  已写入 metadata.json")

    # 汇总
    print("\n" + "=" * 60)
    stats = engine.get_collection_stats(REFERENCE_COLLECTION)
    print(f"  Collection '{REFERENCE_COLLECTION}': {stats['count']} chunks")
    print("  添加完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
