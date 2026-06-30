# -*- coding: utf-8 -*-
"""
一次性知识库构建脚本
- course_knowledge: 扫描 data/raw_docs/ppt/ 的 PPT/PDF
- reference_reports: 从 data/reference_reports/metadata.json 读取文件路径并入库
运行方式: python scripts/build_knowledge_base.py
"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    PPT_DIR,
    REFERENCE_DIR,
    COURSE_COLLECTION,
    REFERENCE_COLLECTION,
    METADATA_FILE,
)
from modules.rag_engine import RAGEngine


def main():
    print("=" * 60)
    print("  实验报告助手 - 知识库构建工具")
    print("=" * 60)

    engine = RAGEngine()

    # Step 1: 课程知识库 (PPT)
    print("\n[Step 1] 构建课程知识库 (course_knowledge) ...\n")
    ppt_count = _build_dir(engine, PPT_DIR, COURSE_COLLECTION, "PPT")

    if ppt_count == 0:
        print("\n[WARN] 未找到任何 PPT 文件。")
        print(f"  请将 PPT/PDF 文件放入: {PPT_DIR}")
    else:
        print(f"\n[OK] 课程知识库构建完成: {ppt_count} chunks")

    # Step 2: 参考报告库 (从 metadata.json 读取文件列表)
    print("\n[Step 2] 构建参考报告库 (reference_reports) ...\n")
    ref_count = _build_from_metadata(engine)

    if ref_count == 0:
        print("\n[INFO] metadata.json 中无参考报告。")
        print(f"  使用: python scripts/add_reference_report.py <文件路径> --score 95")

    # Step 3: 汇总
    print("\n" + "=" * 60)
    stats_course = engine.get_collection_stats(COURSE_COLLECTION)
    stats_ref = engine.get_collection_stats(REFERENCE_COLLECTION)
    print(f"  Collection '{COURSE_COLLECTION}': {stats_course['count']} chunks")
    print(f"  Collection '{REFERENCE_COLLECTION}': {stats_ref['count']} chunks")
    print("=" * 60)
    print("  构建完成！启动: streamlit run app.py")
    print("=" * 60)


def _build_dir(engine, directory, collection, label) -> int:
    """扫描目录，入库"""
    if not os.path.isdir(directory):
        print(f"  [{label}] 目录不存在: {directory}")
        return 0
    try:
        return engine.build_index(directory, collection)
    except Exception as e:
        print(f"  [{label}] 构建失败: {e}")
        return 0


def _build_from_metadata(engine) -> int:
    """从 metadata.json 读取文件路径，逐个入库"""
    if not os.path.isfile(METADATA_FILE):
        print(f"  metadata.json 不存在: {METADATA_FILE}")
        return 0

    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    total = 0
    for filename, info in metadata.items():
        if filename.startswith("_"):
            continue

        file_path = info.get("file_path", "")
        if not file_path:
            print(f"  [跳过] {filename}: 缺少 file_path")
            continue

        # 如果是相对路径，转为绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.path.dirname(METADATA_FILE), "..", "..", file_path)
            file_path = os.path.normpath(file_path)

        if not os.path.isfile(file_path):
            print(f"  [跳过] {filename}: 文件不存在 ({file_path})")
            continue

        try:
            count = engine.add_document(file_path, REFERENCE_COLLECTION)
            total += count
        except Exception as e:
            print(f"  [失败] {filename}: {e}")

    return total


if __name__ == "__main__":
    main()
