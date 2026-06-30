"""
RAG 知识库引擎
负责：文本分块 → Embedding → ChromaDB 存储 → 语义检索
两个 Collection：course_knowledge（PPT/指导书）、reference_reports（高分报告）
"""
import os
import sys
from typing import List, Optional

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import (
    CHROMA_PERSIST_DIR,
    COURSE_COLLECTION,
    REFERENCE_COLLECTION,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    RETRIEVAL_TOP_K,
    LOCAL_EMBEDDING_MODEL,
)
from core.document_parser import DocumentParser


class RAGEngine:
    """
    RAG 引擎：将文档向量化存入 ChromaDB，并提供语义检索能力。
    管理两个 Collection：
      - course_knowledge: PPT + 实验指导书
      - reference_reports: 已完成高分报告
    """

    def __init__(self, persist_dir: Optional[str] = None):
        """
        初始化：加载 Embedding 模型 + 连接 ChromaDB
        """
        persist_dir = persist_dir or CHROMA_PERSIST_DIR
        os.makedirs(persist_dir, exist_ok=True)

        # --- ChromaDB 客户端 ---
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # --- 本地 Embedding 模型 ---
        print(f"[RAG] 正在加载 Embedding 模型: {LOCAL_EMBEDDING_MODEL} ...")
        self._embedding_model = SentenceTransformer(LOCAL_EMBEDDING_MODEL)
        print("[RAG] Embedding 模型加载完成。")

        # --- 文本分块器 ---
        # 使用 tiktoken 的 cl100k_base 编码器（BGE 也是相近 token 计数）
        self._splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", "。", "；", "，", " ", ""],
        )

    # ----------------------------------------------------------------
    # 公有接口：构建索引
    # ----------------------------------------------------------------

    def build_index(self, docs_dir: str, collection_name: str) -> int:
        """
        扫描目录下所有文档，解析、分块、向量化、入库
        Args:
            docs_dir: 文档目录路径
            collection_name: 目标 Collection 名称
        Returns:
            入库的 chunk 总数
        """
        if not os.path.isdir(docs_dir):
            raise NotADirectoryError(f"目录不存在: {docs_dir}")

        # 1. 批量解析文档
        print(f"[RAG] 扫描目录: {docs_dir}")
        from core.document_parser import batch_parse
        results = batch_parse(docs_dir)
        if not results:
            print(f"[RAG] 警告：目录下未找到可解析的文档。")
            return 0

        print(f"[RAG] 解析到 {len(results)} 个文档")

        # 2. 获取或创建 Collection
        collection = self._get_or_create_collection(collection_name)

        # 3. 逐文档分块 + 入库
        total_chunks = 0
        for doc_info in results:
            chunks = self._split_text(doc_info["text"])
            if not chunks:
                continue

            ids = []
            documents = []
            metadatas = []
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_info['file_name']}_{i}"
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append({
                    "source": doc_info["file_name"],
                    "format": doc_info["format"],
                    "chunk_index": i,
                })

            # 4. 生成 Embedding 并写入 ChromaDB
            embeddings = self._embed(chunks)
            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            total_chunks += len(chunks)
            print(f"  [RAG] {doc_info['file_name']}: {len(chunks)} 个 chunk 已入库")

        print(f"[RAG] 索引构建完成，共 {total_chunks} 个 chunk 写入 Collection '{collection_name}'")
        return total_chunks

    def add_document(self, file_path: str, collection_name: str) -> int:
        """
        增量添加单个文档到 Collection
        Args:
            file_path: 文档路径
            collection_name: 目标 Collection
        Returns:
            入库的 chunk 数
        """
        doc_info = DocumentParser.parse_with_metadata(file_path)
        chunks = self._split_text(doc_info["text"])
        if not chunks:
            return 0

        collection = self._get_or_create_collection(collection_name)

        ids = []
        documents = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            ids.append(f"{doc_info['file_name']}_{i}")
            documents.append(chunk)
            metadatas.append({
                "source": doc_info["file_name"],
                "format": doc_info["format"],
                "chunk_index": i,
            })

        embeddings = self._embed(chunks)
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        print(f"[RAG] {doc_info['file_name']}: {len(chunks)} chunk 已添加到 '{collection_name}'")
        return len(chunks)

    # ----------------------------------------------------------------
    # 公有接口：检索
    # ----------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        collection_name: str,
        top_k: int = RETRIEVAL_TOP_K,
    ) -> List[dict]:
        """
        语义检索，返回最相关的文本块
        Args:
            query: 查询文本
            collection_name: 目标 Collection
            top_k: 返回条数
        Returns:
            [{"content": str, "source": str, "score": float}, ...]
        """
        collection = self._get_or_create_collection(collection_name)

        query_embedding = self._embed([query])[0]
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                output.append({
                    "content": results["documents"][0][i],
                    "source": results["metadatas"][0][i].get("source", "未知"),
                    "chunk_index": results["metadatas"][0][i].get("chunk_index", 0),
                    "distance": results["distances"][0][i],
                })

        return output

    def retrieve_combined(
        self,
        query: str,
        top_k: int = RETRIEVAL_TOP_K,
    ) -> str:
        """
        从两个 Collection 同时检索，合并为单段上下文字符串。
        用于注入 Agent 的 Prompt。
        """
        course_results = self.retrieve(query, COURSE_COLLECTION, top_k)
        ref_results = self.retrieve(query, REFERENCE_COLLECTION, top_k)

        parts = []

        if course_results:
            parts.append("【课程知识库相关内容】")
            for i, r in enumerate(course_results, 1):
                parts.append(f"--- 来源: {r['source']} (相关度: {r['distance']:.4f}) ---\n{r['content']}")

        if ref_results:
            parts.append("\n【高分报告参考范例】")
            for i, r in enumerate(ref_results, 1):
                parts.append(f"--- 来源: {r['source']} (相关度: {r['distance']:.4f}) ---\n{r['content']}")

        return "\n\n".join(parts) if parts else "（未检索到相关内容）"

    def get_collection_stats(self, collection_name: str) -> dict:
        """获取 Collection 统计信息"""
        collection = self._get_or_create_collection(collection_name)
        return {
            "name": collection_name,
            "count": collection.count(),
        }

    # ----------------------------------------------------------------
    # 私有方法
    # ----------------------------------------------------------------

    def _get_or_create_collection(self, name: str):
        """获取或创建 Collection"""
        return self._client.get_or_create_collection(name=name)

    def _split_text(self, text: str) -> List[str]:
        """文本分块"""
        if not text or len(text) < 50:
            return []
        chunks = self._splitter.split_text(text)
        # 过滤过短的 chunk
        return [c for c in chunks if len(c) >= 20]

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """将文本列表转为 Embedding 向量列表"""
        embeddings = self._embedding_model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()
