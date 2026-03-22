# evaluate.py
# 評估 RAG 搜尋品質，計算 Recall@k
# 使用方式：python evaluate.py
from rag_search import search_chunks, load_index


# ==========================================
# 測試案例
# 每個案例包含：
#   query      : 使用者問題
#   expected   : 正確答案應該包含的關鍵字（出現在搜尋結果的 text 裡就算命中）
#   filters    : 搜尋時的 metadata filter（可選）
# ==========================================

TEST_CASES = [
    # --- 國泰CUBE卡 ---
    {
        "query": "CUBE卡玩數位方案有哪些通路？",
        "expected": ["Netflix", "Spotify", "蝦皮購物", "ChatGPT"],
        "filters": {"card_name": "國泰CUBE卡", "doc_type": "benefit_scheme"},
    },
    {
        "query": "CUBE卡樂饗購方案百貨通路有哪些？",
        "expected": ["新光三越", "SOGO", "微風廣場"],
        "filters": {"card_name": "國泰CUBE卡", "scheme_name": "樂饗購"},
    },
    {
        "query": "CUBE卡趣旅行方案航空公司有哪些？",
        "expected": ["中華航空", "長榮航空", "星宇航空"],
        "filters": {"card_name": "國泰CUBE卡", "scheme_name": "趣旅行"},
    },
    {
        "query": "CUBE卡集精選方案超商通路？",
        "expected": ["7-ELEVEN", "全家便利商店"],
        "filters": {"card_name": "國泰CUBE卡", "scheme_name": "集精選"},
    },
    {
        "query": "CUBE卡年費多少？有沒有免年費條件？",
        "expected": ["NT$ 1,800", "首年免年費"],
        "filters": {"card_name": "國泰CUBE卡", "doc_type": "credit_card_profile"},
    },
    {
        "query": "CUBE卡方案可以每天切換嗎？",
        "expected": ["每日限變更一次", "當日零時"],
        "filters": {"card_name": "國泰CUBE卡", "doc_type": "global_rule"},
    },
    {
        "query": "CUBE卡回饋等級怎麼分？L1 L2 L3 差別？",
        "expected": ["Level 1", "Level 2", "Level 3"],
        "filters": {"card_name": "國泰CUBE卡"},
    },
    {
        "query": "CUBE卡分期付款有回饋嗎？",
        "expected": ["0.3%", "分期付款"],
        "filters": {"card_name": "國泰CUBE卡"},
    },
    {
        "query": "Netflix 刷 CUBE 卡有回饋嗎？",
        "expected": ["Netflix", "數位"],
        "filters": {"card_name": "國泰CUBE卡", "doc_type": "benefit_scheme"}, 
    },
    {
        "query": "CUBE卡新戶首刷禮條件是什麼？",
        "expected": ["首刷禮", "新戶"],
        "filters": {"card_name": "國泰CUBE卡", "doc_type": "welcome_offer"},
    },

    # --- 國泰蝦皮購物聯名卡 ---
    {
        "query": "蝦皮聯名卡年費多少？",
        "expected": ["NT$ 1,800", "首年免年費"],
        "filters": {"card_name": "國泰蝦皮購物聯名卡", "doc_type": "credit_card_profile"},
    },
    {
        "query": "蝦皮卡站內回饋最高多少？",
        "expected": ["4%", "蝦皮"],
        "filters": {"card_name": "國泰蝦皮購物聯名卡"},
    },
    {
        "query": "蝦皮聯名卡站外消費有回饋嗎？",
        "expected": ["0.5%", "站外"],
        "filters": {"card_name": "國泰蝦皮購物聯名卡"},
    },
    {
        "query": "蝦皮卡免運券怎麼拿？",
        "expected": ["免運券"],
        "filters": {"card_name": "國泰蝦皮購物聯名卡"},
    },
    {
        "query": "蝦皮超級品牌日有加碼嗎？",
        "expected": ["超級品牌日"],
        "filters": {"card_name": "國泰蝦皮購物聯名卡"},
    },

    # --- 國泰世界卡 ---
    {
        "query": "世界卡年費多少？",
        "expected": ["NT$20,000"],
        "filters": {"card_name": "國泰世界卡", "doc_type": "credit_card_profile"},
    },
    {
        "query": "世界卡機場接送資格是什麼？",
        "expected": ["機場接送", "國際線"],
        "filters": {"card_name": "國泰世界卡"},
    },
    {
        "query": "世界卡全球機場貴賓室怎麼用？",
        "expected": ["貴賓室"],
        "filters": {"card_name": "國泰世界卡"},
    },
    {
        "query": "世界卡頂級餐廳優惠怎麼用？",
        "expected": ["美饌", "餐廳"],
        "filters": {"card_name": "國泰世界卡"},
    },
    {
        "query": "世界卡申辦資格年收入要多少？",
        "expected": ["申辦", "資格"],
        "filters": {"card_name": "國泰世界卡", "doc_type": "credit_card_profile"},
    },

    # --- 國泰亞洲萬里通聯名卡 ---
    {
        "query": "亞洲萬里通卡如何累積里程？",
        "expected": ["里數", "NT$30"],
        "filters": {"card_name": "國泰亞洲萬里通聯名卡", "scheme_name": "一般消費累積亞洲萬里通里數"},
    },
    {
        "query": "亞萬卡哩程加速器有哪些通路？",
        "expected": ["哩程加速器", "海外消費"],
        "filters": {"card_name": "國泰亞洲萬里通聯名卡"},
    },
    {
        "query": "亞萬卡全球機場貴賓室怎麼使用？",
        "expected": ["貴賓室"],
        "filters": {"card_name": "國泰亞洲萬里通聯名卡"},
    },
    {
        "query": "亞萬卡海外網路漫遊優惠怎麼使用？",
        "expected": ["漫遊"],
        "filters": {"card_name": "國泰亞洲萬里通聯名卡"},
    },
    {
        "query": "亞萬里享卡年費多少？",
        "expected": ["里享卡"],
        "filters": {"card_name": "國泰亞洲萬里通聯名卡"},
    },

    # --- 跨卡比較 ---
    {
        "query": "哪張卡在日本消費有回饋？",
        "expected": ["日本", "海外"],
        "filters": {},
    },
    {
        "query": "海外消費哪張卡最划算？",
        "expected": ["海外"],
        "filters": {},
    },
    {
        "query": "網購哪張卡回饋最高？",
        "expected": ["蝦皮", "4%"],
        "filters": {},
    },
    {
        "query": "申辦信用卡年收入門檻是多少？",
        "expected": ["年收入", "NT$"],
        "filters": {},
    },
    {
        "query": "哪張卡有機場貴賓室？",
        "expected": ["貴賓室"],
        "filters": {},
    },
]


# ==========================================
# 評估函式
# ==========================================

def evaluate_recall(test_cases: list, k: int = 5) -> dict:
    """
    計算 Recall@k：
    搜尋結果的前 k 筆裡，只要有任一筆的 text 包含所有 expected 關鍵字，就算命中。
    """
    hits = 0
    misses = []

    for case in test_cases:
        query    = case["query"]
        expected = case["expected"]
        filters  = case.get("filters", {})

        result_text = search_chunks(query, top_k=k, **filters)

        # 判斷是否命中：所有 expected 關鍵字都出現在結果裡
        is_hit = all(kw in result_text for kw in expected)

        if is_hit:
            hits += 1
        else:
            misses.append({
                "query":    query,
                "expected": expected,
                "got":      result_text[:200],
            })

    recall = hits / len(test_cases)
    return {
        "total":  len(test_cases),
        "hits":   hits,
        "misses": len(misses),
        "recall": recall,
        "miss_details": misses,
    }


def print_report(result: dict, k: int) -> None:
    print("\n" + "=" * 60)
    print(f"RAG 評估報告 (Recall@{k})")
    print("=" * 60)
    print(f"總測試數：{result['total']}")
    print(f"命中數  ：{result['hits']}")
    print(f"未命中  ：{result['misses']}")
    print(f"Recall@{k}：{result['recall']:.1%}")

    if result["miss_details"]:
        print("\n--- 未命中的問題 ---")
        for i, miss in enumerate(result["miss_details"], 1):
            print(f"\n[{i}] 問題：{miss['query']}")
            print(f"    期望關鍵字：{miss['expected']}")
            print(f"    實際結果（前200字）：{miss['got']}")

    print("\n" + "=" * 60)


# ==========================================
# 主程式
# ==========================================

if __name__ == "__main__":
    print("載入索引中...")
    load_index()

    for k in [3, 5]:
        result = evaluate_recall(TEST_CASES, k=k)
        print_report(result, k=k)

    # 檢查
    from rag_search import search_chunks, load_index

    load_index()

    print("\n=== 亞萬累積里程 ===")
    result = search_chunks("亞洲萬里通卡如何累積里程？", top_k=5, 
                        card_name="國泰亞洲萬里通聯名卡", doc_type="benefit_scheme")
    print(result)
