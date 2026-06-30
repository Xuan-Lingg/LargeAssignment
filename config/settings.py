"""
全局配置文件
所有路径、模型名称、参数统一管理
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 项目根目录
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# DeepSeek 配置（主 LLM — 对话 / 分析 / 生成）
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

# ============================================================
# Google Gemini 配置（多模态 / 流程图 Nano Banana 等）
# ============================================================
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")

# ============================================================
# Embedding 配置（使用本地模型，无需外部 API）
# ============================================================
LOCAL_EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"

# ============================================================
# ChromaDB 配置
# ============================================================
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.join(PROJECT_ROOT, "data", "vector_db"))
COURSE_COLLECTION = "course_knowledge"
REFERENCE_COLLECTION = "reference_reports"
CHUNK_SIZE = 512        # 分块大小（tokens）
CHUNK_OVERLAP = 128     # 分块重叠（tokens）
RETRIEVAL_TOP_K = 5     # 检索返回条数

# ============================================================
# 搜索配置
# ============================================================
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ============================================================
# 数据路径
# ============================================================
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RAW_DOCS_DIR = os.path.join(DATA_DIR, "raw_docs")
PPT_DIR = os.path.join(RAW_DOCS_DIR, "ppt")
SAMPLE_REPORTS_DIR = os.path.join(RAW_DOCS_DIR, "sample_reports")  # 历史优秀学生报告
REFERENCE_DIR = os.path.join(DATA_DIR, "reference_reports")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
INCOMPLETE_UPLOADS_DIR = os.path.join(UPLOADS_DIR, "incomplete")
COMPLETED_UPLOADS_DIR = os.path.join(UPLOADS_DIR, "completed")
METADATA_FILE = os.path.join(REFERENCE_DIR, "metadata.json")

# ============================================================
# 输出路径
# ============================================================
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")
FLOWCHART_DIR = os.path.join(OUTPUTS_DIR, "flowcharts")
EVALUATION_DIR = os.path.join(OUTPUTS_DIR, "evaluations")

# ============================================================
# 评分维度权重（对应课程考核标准）
# ============================================================
SCORE_DIMENSIONS = {
    "项目目标与任务分解": {"max": 10, "weight": 1.0},
    "系统架构设计图及模块功能概述": {"max": 10, "weight": 1.0},
    "关键技术与工具": {"max": 10, "weight": 1.0},
    "关键模块代码实现": {"max": 20, "weight": 1.0},
    "系统界面实现及示例结果": {"max": 20, "weight": 1.0},
    "现场演示": {"max": 30, "weight": 1.0},
}

TOTAL_SCORE = 100
