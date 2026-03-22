# FAISS 向量搜尋，搭配 BGE-M3 embedding 與 metadata filter
from typing import Any

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


INDEX_PATH    = "cards_rag_faiss_index"
BGE_MODEL     = "BAAI/bge-m3"
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
        print(f"✅ FAISS 索引載入完成：{INDEX_PATH}")
    except Exception as e:
        print(f"❌ 載入 FAISS 索引失敗：{e}")
        print("請先執行 build_index.py 建立索引")
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

    搜尋策略：
    - card_name 使用 post-filter 包含比對：
        亞洲萬里通聯名卡有多個子卡等級（世界卡、鈦商卡、白金卡、里享卡），
        FAISS 完全比對會過濾掉子卡 chunk，因此改用包含比對（in）來處理。
    - doc_type / scheme_name 使用 FAISS 內建完全比對 filter。

    Args:
        query:       使用者問題
        top_k:       回傳筆數
        card_name:   只搜特定卡片，例如 "國泰CUBE卡" 或 "國泰亞洲萬里通聯名卡"
        doc_type:    只搜特定文件類型，例如 "benefit_scheme"
        scheme_name: 只搜特定方案，例如 "玩數位"

    Returns:
        整理好的 Markdown 字串，直接可以丟給 LLM
    """
    load_index()

    if _faiss_db is None:
        return "❌ 索引未載入，請先執行 build_index.py"

    # --- Step 1: 決定 FAISS 內建 filter（doc_type / scheme_name）---
    faiss_filter: dict[str, Any] = {}
    if doc_type:
        faiss_filter["doc_type"] = doc_type.strip()
    if scheme_name:
        faiss_filter["scheme_name"] = scheme_name.strip()

    # --- Step 2: 執行搜尋 ---
    try:
        if card_name:
            # card_name 用 post-filter 包含比對
            # 先撈 top_k * 3 筆，過濾後才能確保有足夠的結果
            candidates = _faiss_db.similarity_search(
                query,
                k=top_k * 3,
                filter=faiss_filter if faiss_filter else None,
            )
            results = [
                r for r in candidates
                if card_name.strip() in r.metadata.get("card_name", "")
            ][:top_k]
        else:
            # 沒有指定卡片，直接用 FAISS filter 搜尋
            results = _faiss_db.similarity_search(
                query,
                k=top_k,
                filter=faiss_filter if faiss_filter else None,
            )
    except Exception as e:
        print(f"❌ FAISS 搜尋失敗：{e}")
        return "❌ 搜尋發生錯誤"

    # --- Step 3: Fallback（有條件但沒結果 → 放寬再搜一次）---
    if not results and (card_name or faiss_filter):
        print(f"⚠️  條件 card_name={card_name}, filter={faiss_filter} 無結果，放寬條件重新搜尋")
        try:
            results = _faiss_db.similarity_search(query, k=top_k)
        except Exception as e:
            print(f"❌ Fallback 搜尋失敗：{e}")
            return "❌ 搜尋發生錯誤"

    if not results:
        return "查無相關資料，請嘗試更換關鍵字。"

    return _format_results(results)


# ==========================================
# 格式化輸出
# ==========================================

def _format_results(results) -> str:
    """把 FAISS 搜尋結果整理成 LLM 容易讀的 Markdown 格式"""
    chunks = []

    for i, doc in enumerate(results, 1):
        meta   = doc.metadata
        card   = meta.get("card_name", "未知卡片")
        dtype  = meta.get("doc_type", "")
        scheme = meta.get("scheme_name", "")
        period = meta.get("valid_period", "")

        title = f"{card} - {scheme} ({dtype})" if scheme else f"{card} ({dtype})"

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
        ("亞洲萬里通卡如何累積里程？",     {"card_name": "國泰亞洲萬里通聯名卡"}),
        ("Netflix 有沒有回饋？",           {}),
    ]

    for query, filters in test_queries:
        print(f"問題：{query}")
        print(f"Filter：{filters}")
        result = search_chunks(query, top_k=3, **filters)
        print(result[:400])
        print("\n" + "=" * 60 + "\n")