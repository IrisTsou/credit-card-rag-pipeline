# 將 cards_rag.jsonl 建立成 FAISS 向量索引
import json
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


JSONL_PATH = "cards_rag.jsonl"
INDEX_PATH = "cards_rag_faiss_index"
BGE_MODEL = "BAAI/bge-m3"


def load_documents(jsonl_path: str) -> list[Document]:
    """
    讀取 JSONL，把每個 chunk 轉成 LangChain Document。
    page_content = text（用來做 embedding）
    metadata = 搜尋時可以用來 filter 的欄位
    """
    documents = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            chunk = json.loads(line)

            # metadata 只放需要 filter 的欄位
            metadata = {
                "id":           chunk.get("id", ""),
                "card_name":    chunk.get("card_name", ""),
                "doc_type":     chunk.get("doc_type", ""),
                "scheme_name":  chunk.get("scheme_name") or "",
                "issuer":       chunk.get("issuer", ""),
                "valid_period": chunk["metadata"].get("valid_period") or "",
                # channels_flat 轉成逗號字串，FAISS filter 只支援純量
                "channels_flat": ",".join(
                    chunk["metadata"].get("channels_flat") or []
                ),
            }

            documents.append(
                Document(page_content=chunk["text"], metadata=metadata)
            )

    return documents


def build_faiss_index(documents: list[Document], index_path: str) -> None:
    """用 BGE-M3 對所有 document 做 embedding，建立 FAISS 索引並存檔"""

    print(f"載入 embedding 模型：{BGE_MODEL}")
    embeddings = HuggingFaceEmbeddings(
        model_name=BGE_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    print(f"建立 FAISS 索引（共 {len(documents)} 個 chunks）...")
    vectorstore = FAISS.from_documents(documents, embeddings)
    vectorstore.save_local(index_path)
    print(f"索引建立完成：{index_path}/")


def main():
    documents = load_documents(JSONL_PATH)
    print(f"讀取完成：{len(documents)} 個 chunks")

    # 簡單驗證：確認每個 document 都有 card_name
    missing = [d for d in documents if not d.metadata.get("card_name")]
    if missing:
        print(f"⚠️ 有 {len(missing)} 個 chunk 缺少 card_name，請先檢查 JSONL")
        return

    build_faiss_index(documents, INDEX_PATH)


if __name__ == "__main__":
    main()