import json
import re

with open("cards_rag.jsonl", "r", encoding="utf-8") as f:
    chunks = [json.loads(line) for line in f]

# 檢查 1：每張卡的 chunk 數量分佈
from collections import Counter
print("各卡片 chunk 數量：")
for card, count in Counter(c["card_name"] for c in chunks).items():
    print(f"  {card}: {count}")

# 檢查 2：text 有沒有空的
empty_text = [c["id"] for c in chunks if not c.get("text")]
print(f"\ntext 為空的 chunk：{empty_text if empty_text else '無'}")

empty_card = [c for c in chunks if not c.get("card_name")]
for c in empty_card:
    print(c["id"], c["doc_type"], c["text"][:100])

# 檢查 3：印一個 benefit_scheme 的 text 看看內容對不對
print("\n--- 範例 benefit_scheme ---")
for c in chunks:
    if c["doc_type"] == "benefit_scheme":
        print(c["text"][:300])
        break

# 檢查 4：確認沒有 None 出現在 text 裡
none_in_text = [c["id"] for c in chunks if "None" in c.get("text", "")]
print(f"text 含有 None 的 chunk：{none_in_text if none_in_text else '無'}")

# 檢查 5：確認沒有英文 rule_type 出現在 text 裡
bad_rule = [c["id"] for c in chunks if re.search(r'exclude：|include：', c.get("text", ""))]
print(f"rule_type 未翻譯的 chunk：{bad_rule if bad_rule else '無'}")

