# 信用卡 RAG Pipeline

一個為多 Agent 信用卡問答系統建立的 RAG（檢索增強生成）Pipeline。本專案聚焦於**資料前處理與語意搜尋層**，也就是決定 LLM 在回答使用者問題時能看到哪些資訊的關鍵環節。

本專案為國泰世華銀行信用卡問答系統的團隊專案之一，我負責的部分涵蓋從原始資料結構化到語意搜尋評估的完整 Pipeline。

---

## 我做了什麼

- **Chunking Pipeline**（`convert_to_jsonl.py`）：將原始 JSON（4 張卡片、5 種文件類型）轉換成語意完整的知識片段，經過兩個版本的迭代改進
- **向量索引建置**（`build_index.py`）：使用 BGE-M3 對每個 chunk 做 embedding，並存入 FAISS 索引
- **語意搜尋**（`rag_search.py`）：支援 metadata filter 與 fallback 機制的向量搜尋
- **評估框架**（`evaluate.py`）：30 個測試案例，測量 Recall@3 和 Recall@5

---

## Pipeline 流程

```
官網原始資料（手動複製）
        ↓  自訂 GPT + 結構化 Prompt
原始 JSON（4 張卡 × 5 種文件類型）
        ↓  convert_to_jsonl.py
cards_rag.jsonl（121 個 chunks）
        ↓  build_index.py + BGE-M3
FAISS 向量索引
        ↓  rag_search.py
搜尋結果 → LLM
```

---

## 評估結果

| 版本 | Recall@3 | Recall@5 |
|------|----------|----------|
| 初版（手刻 cosine，v1） | 基準值 | 基準值 |
| FAISS + metadata filter | 90% | 90% |
| + post-filter 子卡模糊比對 | **100%** | **100%** |

測試集：30 個問題，涵蓋全部 4 張卡片及跨卡比較情境。

---

## 關鍵設計決策

### 1. 依文件類型設計不同的 text 模板

每個 chunk 對應一個語意單元，例如卡片基本資料、權益方案、使用規則、首刷禮或通用規則。這樣的設計避免不同性質的資訊混在同一個 chunk 裡，提升搜尋精準度。

### 2. Text 模板的迭代改進（v1 → v2）

**v1** 針對每種文件類型手動定義哪些欄位要進入 text，結構清楚但偶爾會漏掉欄位。

**v2** 加入遞迴展開函式 `flatten_to_text()` 作為保底機制，確保不論 JSON 結構如何變化，所有欄位都會被納入 text，不會有資訊遺漏。

### 3. 子卡模糊比對的 post-filter

亞洲萬里通聯名卡有四個子卡等級（世界卡、鈦商卡、白金卡、里享卡）。FAISS 的完全比對 filter 會把子卡的 chunk 過濾掉，導致搜尋失敗。解決方式是先撈 `top_k × 3` 筆結果，再用包含比對（`in`）做 post-filter：

```python
# FAISS 完全比對會失敗：
# "國泰亞洲萬里通聯名卡" ≠ "國泰亞洲萬里通聯名卡世界卡"

# 改用 post-filter 包含比對：
results = [r for r in candidates if card_name in r.metadata.get("card_name", "")]
```

### 4. 評估驅動的迭代優化

Recall@5 初始為 90%，分析 3 個未命中的案例後，找到兩個根本原因：FAISS filter 的子卡比對問題，以及 text 模板對方案語意描述不夠清楚。兩者都透過改善 Pipeline 解決，而不是調整測試門檻。

---

## 資料收集方式

原始資料從國泰世華銀行官網手動複製，再透過自訂 GPT 搭配固定 JSON schema 的 Prompt 進行結構化。

Prompt 包含 13 條輸出規則，重點包含：
- 只能根據原始內容填寫，不可推測或編造
- 回饋數字保留原始單位（`"2%"` 不改成 `0.02`）
- 每個區塊的 `doc_type` 固定填入對應值
- `valid_period` 統一使用 `YYYY/MM/DD-YYYY/MM/DD` 格式

完整 Prompt 與 Schema 請見 [`data_collection_prompt.md`](./data_collection_prompt.md)。

---

## 技術選型

| 元件 | 工具 |
|------|------|
| Embedding 模型 | BGE-M3（`BAAI/bge-m3`） |
| 向量資料庫 | FAISS |
| Embedding 介面 | LangChain（`langchain-huggingface`） |
| 執行環境 | Python 3.11+ |

---

## 執行方式

```bash
# 安裝依賴套件
pip install -r requirements.txt

# Step 1：將 JSON 轉換成 JSONL chunks
python convert_to_jsonl.py

# Step 2：驗證 chunk 品質
python validate_jsonl.py

# Step 3：建立 FAISS 索引（第一次執行需要幾分鐘）
python build_index.py

# Step 4：測試搜尋功能
python rag_search.py

# Step 5：執行評估
python evaluate.py
```

---

## 檔案結構

```
credit-card-rag-pipeline/
├── data_collection_prompt.md   # LLM 結構化 Prompt 與 JSON Schema
├── convert_to_jsonl.py         # Chunking Pipeline（v2）
├── validate_jsonl.py           # JSONL 輸出品質驗證
├── build_index.py              # FAISS 索引建置
├── rag_search.py               # 語意搜尋 + metadata filter
├── evaluate.py                 # Recall@k 評估（30 個測試案例）
├── requirements.txt
└── credit_card_llm_json/
    └── cube.json        # （資料有著作權疑慮故不上傳）
```

---

## 已知限制

- **關鍵字比對評估**：Recall@k 只檢查關鍵字是否出現在結果中，不評估語意是否真的正確。更嚴謹的評估應採用人工標注或 LLM-as-judge 方法。
- **自行設計的測試集**：測試問題是在已知資料內容的情況下設計的，可能高估對口語化或模糊問題的實際表現。
- **未評估端對端品質**：本 Pipeline 只評估搜尋層，LLM 拿到這些資料後能不能正確回答，不在本次評估範圍內。
