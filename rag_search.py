# FAISS 向量搜尋，搭配 BGE-M3 embedding 與 metadata filter
import json
from typing import Any

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


INDEX_PATH = "cards_rag_faiss_index"
BGE_MODEL  = "BAAI/bge-m3"
DEFAULT_TOP_K = 5

# ==========================================
# 全域單例：只初始化一次，避免重複載入模型
# ==========================================

_embeddings: HuggingFaceEmbeddings | None = None
_faiss_db: FAISS | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        print(f"載入 embedding 模型：{BGE_MODEL}")
        _embeddings = HuggingFaceEmbeddings(
            model_name=BGE_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def load_index() -> None:
    """載入 FAISS 索引到記憶體，只執行一次"""
    global _faiss_db
    if _faiss_db is not None:
        return

    try:
        _faiss_db = FAISS.load_local(
            folder_path=INDEX_PATH,
            embeddings=_get_embeddings(),
            allow_dangerous_deserialization=True,
        )
        print(f"FAISS 索引載入完成：{INDEX_PATH}")
    except Exception as e:
        print(f"❌ 載入 FAISS 索引失敗：{e}")
        print(f"請先執行 build_index.py 建立索引")
        _faiss_db = None


# ==========================================
# 核心搜尋函式
# ==========================================

def search_chunks(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    card_name: str | None = None,
    doc_type: str | None = None,
    scheme_name: str | None = None,
) -> str:
    """
    語意搜尋 + metadata filter，回傳整理好的字串供 LLM 使用。

    Args:
        query:       使用者問題
        top_k:       回傳筆數
        card_name:   只搜特定卡片，例如 "國泰CUBE卡"
        doc_type:    只搜特定文件類型，例如 "benefit_scheme"
        scheme_name: 只搜特定方案，例如 "玩數位"

    Returns:
        整理好的 Markdown 字串，直接可以丟給 LLM
    """
    load_index()

    if _faiss_db is None:
        return "❌ 索引未載入，請先執行 build_index.py"

    # 建立 filter dict（只加有值的條件）
    metadata_filter: dict[str, Any] = {}
    if card_name:
        metadata_filter["card_name"] = card_name.strip()
    if doc_type:
        metadata_filter["doc_type"] = doc_type.strip()
    if scheme_name:
        metadata_filter["scheme_name"] = scheme_name.strip()

    # 第一次搜尋（帶 filter）
    try:
        results = _faiss_db.similarity_search(
            query,
            k=top_k,
            filter=metadata_filter if metadata_filter else None,
        )
    except Exception as e:
        print(f"❌ FAISS 搜尋失敗：{e}")
        return "❌ 搜尋發生錯誤"

    # Fallback：有 filter 但沒有結果 → 放寬條件再搜一次
    if not results and metadata_filter:
        print(f"⚠️  filter {metadata_filter} 無結果，放寬條件重新搜尋")
        try:
            results = _faiss_db.similarity_search(query, k=top_k)
        except Exception as e:
            print(f"❌ Fallback 搜尋失敗：{e}")
            return "❌ 搜尋發生錯誤"

    if not results:
        return "查無相關資料，請嘗試更換關鍵字。"

    # 整理成 Markdown 格式給 LLM 讀
    return _format_results(results)


def _format_results(results) -> str:
    """把 FAISS 搜尋結果整理成 LLM 容易讀的 Markdown 格式"""
    chunks = []

    for i, doc in enumerate(results, 1):
        meta = doc.metadata
        card    = meta.get("card_name", "未知卡片")
        dtype   = meta.get("doc_type", "")
        scheme  = meta.get("scheme_name", "")
        period  = meta.get("valid_period", "")

        # 標題：卡片名稱 + 方案名稱（如果有）
        if scheme:
            title = f"{card} - {scheme} ({dtype})"
        else:
            title = f"{card} ({dtype})"

        # 組裝單個 chunk
        lines = [f"### 資料來源 {i}：{title}"]
        if period:
            lines.append(f"- 適用期間：{period}")
        lines.append(f"- 內容：{doc.page_content}")

        chunks.append("\n".join(lines))

    return "\n\n---\n\n".join(chunks)


# ==========================================
# 本地測試
# ==========================================

if __name__ == "__main__":
    print("=== RAG Search 本地測試 ===\n")

    test_queries = [
        ("CUBE卡玩數位方案有哪些通路？", {"card_name": "國泰CUBE卡", "doc_type": "benefit_scheme"}),
        ("蝦皮聯名卡年費多少？",          {"card_name": "國泰蝦皮購物聯名卡"}),
        ("世界卡機場接送資格？",           {"card_name": "國泰世界卡"}),
        ("亞洲萬里通卡如何累積里程？",     {}),
        ("Netflix 有沒有回饋？",           {}),
    ]

    for query, filters in test_queries:
        print(f"問題：{query}")
        print(f"Filter：{filters}")
        result = search_chunks(query, top_k=3, **filters)
        print(result[:400])
        print("\n" + "="*60 + "\n")