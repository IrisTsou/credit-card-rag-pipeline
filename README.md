[繁體中文版](./README_zh.md)

# Credit Card RAG Pipeline

A retrieval-augmented generation (RAG) pipeline built for a multi-agent credit card advisory system. This repo focuses on the **data preparation and retrieval layer** — the part that determines what information the LLM sees when answering user questions.

Built as part of a team project for Cathay United Bank's credit card Q&A system. My contribution covers the full pipeline from raw data structuring to semantic search evaluation.

---

## What I Built

- **Chunking pipeline** (`convert_to_jsonl.py`): converts raw JSON (4 card products, 5 document types) into semantically meaningful text chunks, with two iterations of improvement
- **Vector index** (`build_index.py`): embeds chunks using BGE-M3 and stores them in a FAISS index
- **Semantic search** (`rag_search.py`): retrieves relevant chunks with metadata filtering and fallback logic
- **Evaluation framework** (`evaluate.py`): 30 test cases measuring Recall@3 and Recall@5

---

## Pipeline Overview

```
Official website (manual copy)
        ↓  GPT with structured prompt
Raw JSON (4 cards × 5 doc types)
        ↓  convert_to_jsonl.py
cards_rag.jsonl (121 chunks)
        ↓  build_index.py + BGE-M3
FAISS vector index
        ↓  rag_search.py
Search results → LLM
```

---

## Evaluation Results

| Version                             | Recall@3 | Recall@5 |
| ----------------------------------- | -------- | -------- |
| Initial (brute-force cosine, v1)    | baseline | baseline |
| FAISS + metadata filter             | 90%      | 90%      |
| + post-filter for sub-card matching | **100%** | **100%** |

Test set: 30 questions covering all 4 card products and cross-card comparisons.

---

## Key Design Decisions

### 1. Document-type-aware chunking

Each chunk corresponds to one semantic unit — a card profile, a benefit scheme, a rule, a welcome offer, or a global rule. This prevents unrelated information from being mixed in a single chunk and improves retrieval precision.

### 2. Structured text templates (v1 → v2)

**v1** manually defined which fields to include in the text for each document type. Simple and readable, but some fields were occasionally missed.

**v2** added a recursive `flatten_to_text()` fallback that expands any remaining fields into the text, ensuring nothing is lost regardless of JSON structure variations.

### 3. Post-filter for sub-card matching

The Asia Miles card family has four tiers (World, Titanium Business, Platinum, Li Xiang). FAISS's exact-match filter would exclude sub-card chunks when searching by the parent card name. The fix: retrieve `top_k × 3` results first, then apply substring matching (`card_name in result.card_name`) as a post-filter.

```python
# FAISS exact match fails for sub-cards:
# "國泰亞洲萬里通聯名卡" ≠ "國泰亞洲萬里通聯名卡世界卡"

# Post-filter with substring match:
results = [r for r in candidates if card_name in r.metadata.get("card_name", "")]
```

### 4. Iterative evaluation-driven improvement

Recall@5 started at 90%. Analysis of the 3 misses revealed two root causes: a FAISS filter bug (sub-card matching) and a text template that lacked semantic clarity for scheme descriptions. Both were fixed by improving the pipeline, not by adjusting test thresholds.

---

## Data Collection

Raw data was manually copied from the Cathay United Bank official website and structured using a custom GPT with a fixed JSON schema prompt.

The prompt enforces 13 output rules including:

- No hallucination — only fill fields explicitly stated in the source
- Preserve original reward values and units (`"2%"` not `0.02`)
- Fixed `doc_type` values per section
- Consistent `valid_period` format (`YYYY/MM/DD-YYYY/MM/DD`)

See [`data_collection_prompt.md`](./data_collection_prompt.md) for the full prompt and schema.

A sample output is provided in [`credit_card_llm_json/cube_sample.json`](./credit_card_llm_json/cube_sample.json).

---

## Tech Stack

| Component           | Tool                                |
| ------------------- | ----------------------------------- |
| Embedding model     | BGE-M3 (`BAAI/bge-m3`)              |
| Vector store        | FAISS                               |
| Embedding interface | LangChain (`langchain-huggingface`) |
| Runtime             | Python 3.11+                        |

---

## How to Run

```bash
# Install dependencies
pip install -r requirements.txt

# Step 1: Convert JSON to JSONL chunks
python convert_to_jsonl.py

# Step 2: Validate chunk quality
python validate_jsonl.py

# Step 3: Build FAISS index (takes a few minutes on first run)
python build_index.py

# Step 4: Test search
python rag_search.py

# Step 5: Run evaluation
python evaluate.py
```

---

## File Structure

```
credit-card-rag-pipeline/
├── data_collection_prompt.md   # LLM structuring prompt + JSON schema
├── convert_to_jsonl.py         # Chunking pipeline (v2)
├── validate_jsonl.py           # Quality checks for JSONL output
├── build_index.py              # FAISS index builder
├── rag_search.py               # Semantic search with metadata filter
├── evaluate.py                 # Recall@k evaluation (30 test cases)
├── requirements.txt
└── credit_card_llm_json/
    └── cube_sample.json        # Sample data (full data not included)
```

---

## Known Limitations

- **Keyword-based evaluation**: Recall@k checks for keyword presence in results, not whether the answer is semantically correct. A more rigorous evaluation would use human judgment or an LLM-as-judge approach.
- **Self-designed test set**: Test questions were designed with knowledge of the data, which may overestimate real-world performance on ambiguous or colloquial queries.
- **No end-to-end evaluation**: This pipeline is evaluated at the retrieval level only. Final answer quality depends on the LLM using these results, which is not measured here.
