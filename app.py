"""
实验报告助手 — Streamlit 前端界面
"""
import sys
import os

# 确保项目根目录在 path 中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
import plotly.graph_objects as go

from core.document_parser import DocumentParser
from core.agent import ReportAssistantAgent


# ================================================================
# 页面配置
# ================================================================
st.set_page_config(
    page_title="实验报告助手",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================================================================
# 自定义 CSS
# ================================================================
st.markdown("""
<style>
    .report-container {
        max-height: 400px;
        overflow-y: auto;
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 16px;
        background: #fafafa;
    }
    .score-card {
        text-align: center;
        padding: 16px;
        border-radius: 12px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin: 8px 0;
    }
    .score-card h2 {
        margin: 0;
        font-size: 2.5rem;
    }
    .strategy-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.85rem;
        background: #e8f0fe;
        color: #1a73e8;
    }
</style>
""", unsafe_allow_html=True)


# ================================================================
# 工具函数
# ================================================================

@st.cache_resource
def get_agent() -> ReportAssistantAgent:
    """缓存 Agent 实例（整个会话生命周期）"""
    return ReportAssistantAgent()


def render_mermaid(mermaid_code: str, height: int = 400):
    """使用 Mermaid.js CDN 渲染流程图"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <script>mermaid.initialize({{startOnLoad: true, theme: 'default'}});</script>
        <style>
            body {{ margin: 0; padding: 12px; font-family: sans-serif; }}
        </style>
    </head>
    <body>
        <div class="mermaid">
{mermaid_code}
        </div>
    </body>
    </html>
    """
    st.components.v1.html(html, height=height, scrolling=True)


def render_radar_chart(scores: dict, dimensions_config: dict):
    """
    渲染评分雷达图。
    各维度满分不同（10~30），统一归一化为百分比，使图形边长比例有意义。
    """
    dims = []
    pct_values = []

    for dim_name, score in scores.items():
        cfg = dimensions_config.get(dim_name, {})
        max_val = cfg.get("max", 10)
        # 归一化为 0-100 百分比
        pct = (score / max_val * 100) if max_val > 0 else 0
        pct = max(0, min(pct, 100))
        dims.append(dim_name)
        pct_values.append(pct)

    # 闭合
    dims_closed = dims + [dims[0]]
    pct_closed = pct_values + [pct_values[0]]

    fig = go.Figure()
    # 得分（百分比）
    fig.add_trace(go.Scatterpolar(
        r=pct_closed,
        theta=dims_closed,
        fill='toself',
        name='得分 (%)',
        line=dict(color='#667eea', width=2),
        fillcolor='rgba(102, 126, 234, 0.3)',
    ))
    # 满分参考线 (100%)
    fig.add_trace(go.Scatterpolar(
        r=[100] * len(dims_closed),
        theta=dims_closed,
        fill=None,
        name='满分 (100%)',
        line=dict(color='#ddd', width=1, dash='dash'),
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 110],
                tickmode='array',
                tickvals=[0, 25, 50, 75, 100],
                ticktext=['0%', '25%', '50%', '75%', '100%'],
            )
        ),
        showlegend=False,
        height=420,
        margin=dict(l=60, r=60, t=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def display_score_summary(score_data: dict, dimensions_config: dict):
    """展示评分总结卡片 + 雷达图（各维度百分比进度条）"""
    if not score_data or "scores" not in score_data:
        return

    scores = score_data.get("scores", {})
    if not scores:
        return

    # 计算实际总分（各维度得分之和，满分为100）
    total = sum(
        min(scores.get(dim, 0), cfg.get("max", 10))
        for dim, cfg in dimensions_config.items()
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        # 总分大卡片
        st.markdown(f"""
        <div class="score-card">
            <div style="font-size:0.9rem; opacity:0.85;">评估总分</div>
            <h2>{total:.1f}<span style="font-size:1rem;"> / 100</span></h2>
        </div>
        """, unsafe_allow_html=True)

        # 分维度明细（带进度条）
        for dim, cfg in dimensions_config.items():
            score = scores.get(dim, 0)
            max_val = cfg["max"]
            pct = min(score / max_val, 1.0) if max_val > 0 else 0

            # 颜色：>=80% 绿，>=50% 蓝，<50% 橙
            if pct >= 0.8:
                color = "#27ae60"
            elif pct >= 0.5:
                color = "#667eea"
            else:
                color = "#e67e22"

            st.markdown(f"""
            <div style="margin-bottom:8px;">
                <div style="display:flex; justify-content:space-between; font-size:0.85rem;">
                    <span>{dim}</span>
                    <span><b>{score}/{max_val}</b> ({pct*100:.0f}%)</span>
                </div>
                <div style="background:#eee; border-radius:4px; height:6px;">
                    <div style="background:{color}; width:{pct*100}%; height:6px; border-radius:4px;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        if len(scores) >= 3:
            render_radar_chart(scores, dimensions_config)


# ================================================================
# 主界面
# ================================================================

def main():
    st.title("📝 实验报告助手")
    st.caption("基于大语言模型的实验报告指导与评估系统 — 深圳大学《大模型技术及开发》课程项目")

    # -- 初始化 session_state --
    defaults = {
        "report_text": "",
        "report_filename": "",
        "report_parsed": False,
        "result": None,
        "processing": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ================================================================
    # 辅助：扫描 data 目录下的可用文档
    # ================================================================
    @st.cache_data(ttl=60)
    def list_available_docs():
        """扫描知识库中的可处理文档列表"""
        docs = []
        base = os.path.join(os.path.dirname(__file__), "data", "raw_docs")
        for root, _, files in os.walk(base):
            for f in files:
                if f.startswith("~$") or f == ".gitkeep":
                    continue
                ext = os.path.splitext(f)[1].lower()
                if ext in [".pdf", ".docx", ".doc", ".md", ".txt", ".pptx"]:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, os.path.dirname(__file__))
                    folder = os.path.relpath(os.path.dirname(full), base)
                    docs.append({
                        "name": f,
                        "path": rel,
                        "folder": folder,
                        "size": os.path.getsize(full),
                    })
        return docs

    # ================================================================
    # 左侧边栏
    # ================================================================
    with st.sidebar:
        # 字体放大 CSS
        st.markdown("""
        <style>
        .stSidebar [data-testid="stMarkdownContainer"] p,
        .stSidebar .stRadio label,
        .stSidebar .stSelectbox label,
        .stSidebar .stTextArea label,
        .stSidebar .stFileUploader label {
            font-size: 0.95rem !important;
        }
        .stSidebar h2, .stSidebar h3 {
            font-size: 1.1rem !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # ---- 第一部分：知识库文档浏览 ----
        st.header("📚 知识库文档")
        available_docs = list_available_docs()

        if available_docs:
            # 按文件夹分组
            folders = {}
            for d in available_docs:
                folders.setdefault(d["folder"], []).append(d)

            for folder, files in sorted(folders.items()):
                with st.expander(f"📁 {folder} ({len(files)}个)", expanded=False):
                    for doc in files:
                        col_a, col_b = st.columns([4, 1])
                        with col_a:
                            st.caption(f"• {doc['name']}")
                        with col_b:
                            if st.button("📎", key=f"load_{doc['path']}", help=f"加载 {doc['name']}"):
                                try:
                                    full_path = os.path.join(os.path.dirname(__file__), doc["path"])
                                    text = DocumentParser.parse(full_path)
                                    st.session_state.report_text = text
                                    st.session_state.report_filename = doc["name"]
                                    st.session_state.report_parsed = True
                                    st.session_state.result = None
                                except Exception as e:
                                    st.error(f"加载失败: {e}")
        else:
            st.caption("（知识库为空，请将 PPT/报告放入 data/raw_docs/）")

        st.divider()

        # ---- 第二部分：上传文件 ----
        st.header("📂 上传实验报告")

        uploaded_file = st.file_uploader(
            "选择文件上传",
            type=["pdf", "docx", "doc", "md", "txt", "pptx"],
            help="支持 PDF、Word、Markdown、TXT 等格式。旧版 .doc 请先转为 .docx。",
            key="file_uploader",
        )

        if uploaded_file is not None:
            import tempfile
            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name
            try:
                text = DocumentParser.parse(tmp_path)
                st.session_state.report_text = text
                st.session_state.report_filename = uploaded_file.name
                st.session_state.report_parsed = True
                st.session_state.result = None
            except Exception as e:
                st.error(f"文件解析失败: {e}")
                st.session_state.report_parsed = False
            finally:
                os.unlink(tmp_path)

        # 粘贴文本
        with st.expander("或直接粘贴报告文本"):
            pasted = st.text_area("粘贴报告内容", height=150, key="paste_area")
            if st.button("使用粘贴内容", key="btn_paste"):
                if pasted.strip():
                    st.session_state.report_text = pasted.strip()
                    st.session_state.report_filename = "粘贴文本"
                    st.session_state.report_parsed = True
                    st.session_state.result = None
                    st.success("已加载")

        st.divider()

        # ---- 第三部分：策略选择 ----
        st.header("🎯 处理策略")
        strategy_labels = {
            "decompose": "实验报告拆解指导",
            "evaluate": "完整报告评估打分",
            "explain": "单个实验知识点讲解",
            "auto": "自动检测（推荐）",
        }
        strategy = st.radio(
            "选择策略",
            options=list(strategy_labels.keys()),
            format_func=lambda x: strategy_labels[x],
            index=3,
            key="strategy_select",
        )

        st.divider()

        # ---- 第四部分：补充说明 ----
        st.header("💬 补充说明（可选）")
        user_query = st.text_area(
            "额外的要求或问题",
            placeholder="如：请重点看实验三... / 我的报告主要问题在哪？...",
            height=80,
            key="user_query",
        )

        st.divider()

        # ---- 第五部分：执行 ----
        can_process = st.session_state.report_parsed and not st.session_state.processing
        if st.button("开始处理", type="primary", use_container_width=True, disabled=not can_process):
            st.session_state.processing = True
            st.session_state.result = None
            st.rerun()

        # 状态
        if st.session_state.report_parsed:
            text_len = len(st.session_state.report_text)
            st.success(f"已加载: {st.session_state.report_filename} ({text_len} 字符)")
            agent = get_agent()
            quick = agent.quick_strategy_check(st.session_state.report_text)
            quick_label = strategy_labels.get(quick, quick)
            st.caption(f"系统初步建议: {quick_label}")
        else:
            st.info("请上传报告或从知识库选择文档")

    # ================================================================
    # 主区域
    # ================================================================
    tab1, tab2 = st.tabs(["📄 分析结果", "📋 原始报告"])

    with tab2:
        if st.session_state.report_parsed:
            with st.expander(st.session_state.report_filename, expanded=True):
                st.markdown(f"```\n{st.session_state.report_text[:5000]}\n```")
                if len(st.session_state.report_text) > 5000:
                    st.caption(f"...（共 {len(st.session_state.report_text)} 字符，仅展示前 5000）")
        else:
            st.info("请先在左侧上传报告文件。")

    with tab1:
        # --- 处理逻辑 ---
        if st.session_state.processing:
            with st.spinner("正在处理中，请稍候..."):
                try:
                    agent = get_agent()
                    result = agent.process(
                        report_content=st.session_state.report_text,
                        user_strategy=strategy,
                        user_query=user_query,
                    )
                    st.session_state.result = result
                except Exception as e:
                    st.error(f"处理失败: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                    st.session_state.result = None
                finally:
                    st.session_state.processing = False
            # 不再 st.rerun()，自然流转到结果展示

        # --- 展示结果 ---
        result = st.session_state.result

        if result is None:
            if st.session_state.report_parsed:
                st.info("请选择策略后点击「开始处理」")
            return

        if not result.success:
            st.error(str(result.content)[:500])
            return

        # 用 try 包裹整个展示，防止渲染错误导致页面崩溃
        try:
            # 策略标签
            strategy_name = {
                "decompose": "实验报告拆解指导",
                "evaluate": "完整报告评估打分",
                "explain": "单个实验知识点讲解",
            }.get(result.strategy, result.strategy)
            st.markdown(f"**处理策略**: <span class='strategy-badge'>{strategy_name}</span>", unsafe_allow_html=True)
            st.divider()

            # --- 评估打分特殊展示 ---
            if result.strategy == "evaluate" and result.score_data:
                from config.settings import SCORE_DIMENSIONS
                try:
                    display_score_summary(result.score_data, SCORE_DIMENSIONS)
                except Exception as e:
                    st.warning(f"评分展示异常: {e}")
                st.divider()
                st.subheader("详细评语")
                # 只显示文字评语部分，不显示原始 JSON
                overall = result.score_data.get("overall_comment", "")
                strengths = result.score_data.get("strengths", [])
                weaknesses = result.score_data.get("weaknesses", [])
                suggestions = result.score_data.get("suggestions", [])

                if overall:
                    st.markdown(f"**总评**：{overall}")
                c1, c2 = st.columns(2)
                with c1:
                    if strengths:
                        st.markdown("**优点**")
                        for s in strengths:
                            st.markdown(f"- {s}")
                with c2:
                    if weaknesses:
                        st.markdown("**不足**")
                        for w in weaknesses:
                            st.markdown(f"- {w}")
                if suggestions:
                    with st.expander("改进建议"):
                        for i, s in enumerate(suggestions, 1):
                            st.markdown(f"{i}. {s}")
                # 原始返回放在折叠区
                with st.expander("查看原始返回数据"):
                    st.json(result.score_data)
            else:
                # 非评估模式：显示完整内容
                content = str(result.content) if result.content else "（无内容）"
                st.markdown(content)

            # --- 流程图/思维导图 ---
            if result.mermaid_code:
                st.divider()
                st.subheader("可视化图表")
                with st.expander("展开查看流程图 / 思维导图", expanded=True):
                    render_mermaid(result.mermaid_code)
                    with st.expander("查看 Mermaid 源码"):
                        st.code(result.mermaid_code, language="mermaid")

            # --- 报告结构信息 ---
            if result.report_structure:
                with st.expander("报告结构分析详情", expanded=False):
                    rs = result.report_structure
                    st.text(f"报告标题: {rs.title}")
                    st.text(f"总字符数: {rs.total_chars}")
                    st.text(f"整体完成度: {rs.completeness * 100:.0f}%")
                    st.text(f"识别到 {len(rs.experiments)} 个实验/模块")
                    for exp in rs.experiments:
                        icon = "OK" if exp.has_content else "--"
                        st.text(f"  {icon} {exp.name} (完成度 {exp.completeness*100:.0f}%)")

        except Exception as e:
            st.error(f"结果展示异常: {e}")
            # 至少显示原始内容
            with st.expander("查看原始返回内容"):
                st.text(str(result.content)[:2000] if result.content else "无")


if __name__ == "__main__":
    main()
