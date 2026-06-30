# 实验报告助手

基于大语言模型的实验报告指导与评估系统，深圳大学《大模型技术及开发》课程项目。

## 功能

| 功能 | 说明 |
|------|------|
| 实验报告拆解指导 | 上传待完成报告 → 结合课堂 PPT 知识库 → 拆分实验 → 生成知识点、步骤、要点 + 流程图 |
| 完整报告评估打分 | 上传已完成报告 → 按课程 6 大评分标准逐维度打分 → 雷达图 + 改进建议 |
| 知识点深度讲解 | 针对指定实验或知识点 → 检索 PPT → 结构化讲解 + 思维导图 |

## 技术栈

- **LLM**：DeepSeek-V4-Flash
- **前端**：Streamlit
- **编排**：LangChain + LangGraph
- **向量库**：ChromaDB
- **Embedding**：bge-large-zh-v1.5（本地）
- **文档解析**：python-pptx / python-docx / PyMuPDF

## 快速开始

### 1. 安装依赖

```bash
# Python 3.11 推荐
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 API Key
# DEEPSEEK_API_KEY=sk-xxxxxxxx
# GOOGLE_API_KEY=xxxxxxxxxx
```

### 3. 准备数据

将文件放入对应目录：

```
data/
├── raw_docs/
│   ├── ppt/                  ← 放课堂 PPT（.pptx / .pdf）
│   └── sample_reports/       ← 放历史优秀报告（.docx / .pdf）
└── reference_reports/
    └── metadata.json         ← 编辑参考报告评分（可选）
```

### 4. 构建知识库

```bash
python scripts/build_knowledge_base.py
```

首次运行会下载 Embedding 模型（约 1.3GB），之后离线使用。

### 5. 启动应用

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501`。

## 使用流程

1. **加载报告**：左侧上传 .docx/.pdf/.md 文件，或从知识库文档列表点击 📎 加载
2. **选择策略**：
   - 自动检测（推荐）
   - 实验报告拆解指导
   - 完整报告评估打分
   - 单个实验知识点讲解
3. **开始处理**：点击按钮，等待 AI 分析
4. **查看结果**：Markdown 内容 + Mermaid 流程图 + 雷达图（评分模式）

## 添加高分参考报告

```bash
python scripts/add_reference_report.py <报告文件路径> --score 95 --comment "整体优秀"
```

## 项目结构

```
├── app.py                      # Streamlit 前端界面
├── requirements.txt
├── .env.example                # 环境变量模板
│
├── config/
│   └── settings.py             # 全局配置
│
├── core/
│   ├── agent.py                # 中央调度 Agent
│   ├── prompts.py              # 系统提示词
│   └── document_parser.py      # 文档解析器（6 种格式）
│
├── modules/
│   ├── rag_engine.py           # RAG 知识库引擎
│   ├── tools.py                # 工具集（搜索/流程图/评分/语法）
│   ├── strategy_router.py      # 策略路由（双重校验）
│   ├── report_analyzer.py      # 报告结构分析器
│   └── evaluator.py            # 评估打分引擎
│
├── scripts/
│   ├── build_knowledge_base.py # 构建知识库
│   ├── add_reference_report.py # 添加参考报告
│   ├── prepare_finetune_data.py# 准备微调数据
│   └── test_api.py             # API 连通性测试
│
├── data/                       # 数据目录
└── outputs/                    # 输出产物
```

## 常见问题

**Q: 旧版 .doc 文件解析失败？**
用 Word/WPS 另存为 .docx 格式再导入。

**Q: 首次启动卡住？**
Embedding 模型首次下载需 1-5 分钟，之后秒加载。若 API 超时，检查网络和 API Key。

**Q: 知识库为空？**
先运行 `python scripts/build_knowledge_base.py` 构建索引。

## 许可证

课程项目，仅供学习交流。
