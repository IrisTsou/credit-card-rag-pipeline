# 將 credit_card_llm_json 中的 .json 轉換成 cards_rag.jsonl
# v2：在 v1 模板基礎上改善 benefit_rule 和 global_rule 的 text 可讀性
import json
import os
from pathlib import Path


# ==========================================
# 基本工具
# ==========================================

def make_id(*parts) -> str:
    cleaned = []
    for p in parts:
        if p is None:
            continue
        s = str(p).strip().replace(" ", "").replace("：", "_").replace(":", "_")
        cleaned.append(s.lower())
    return "_".join(cleaned)


# ==========================================
# profile → chunk
# ==========================================

def profile_to_chunk(profile: dict, source_file: str) -> dict:
    card_name = profile.get("card_name", "")
    issuer = profile.get("issuer", "")
    doc_type = profile.get("doc_type", "credit_card_profile")

    # 年費
    annual_fee = profile.get("annual_fee")
    if isinstance(annual_fee, dict):
        primary = annual_fee.get("primary", "")
        supplementary = annual_fee.get("supplementary")
        annual_fee_str = f"正卡年費 {primary}"
        if supplementary:
            annual_fee_str += f"，附卡 {supplementary}"
        annual_fee_str += "。"
        if annual_fee.get("waiver"):
            annual_fee_str += f"年費減免條件：{annual_fee['waiver']}。"
    else:
        annual_fee_str = f"{annual_fee}。" if annual_fee else "年費依銀行公告。"

    # 申辦資格
    eligibility = profile.get("eligibility") or {}
    age = eligibility.get("age", "")
    employment = eligibility.get("employment", "")
    income_req = eligibility.get("income_requirement") or profile.get("income_requirement", "")
    clean_conds = [c.rstrip("。") for c in [age, employment, income_req] if c]

    # 回饋概述
    base_reward = profile.get("base_reward")
    reward_unit = profile.get("reward_unit")

    # 其他欄位
    segments = profile.get("target_users") or profile.get("user_segments") or []
    positioning = profile.get("positioning")

    # 組 text
    text_parts = [f"{issuer}發行的「{card_name}」基本資料：", annual_fee_str]

    if clean_conds:
        text_parts.append("申辦資格包含：" + "、".join(clean_conds) + "。")

    if base_reward:
        if reward_unit:
            text_parts.append(f"回饋概述：{base_reward}（回饋單位：{reward_unit}）。")
        else:
            text_parts.append(f"回饋概述：{base_reward}。")

    if segments:
        text_parts.append("適合族群例如：" + "；".join(segments) + "。")

    if positioning:
        text_parts.append(f"卡片定位：{positioning}。")

    text = "".join(text_parts)

    metadata = {
        "card_family": profile.get("card_family") or card_name,
        "tier": profile.get("tier"),
        "reward_type": profile.get("reward_unit", "other"),
        "source_file": source_file,
        "source_path": ["credit_card_profile"],
        "raw": profile,
    }

    return {
        "id": make_id(card_name, "profile"),
        "text": text,
        "card_name": card_name,
        "issuer": issuer,
        "doc_type": doc_type,
        "scheme_name": None,
        "rule_type": None,
        "metadata": metadata,
    }


# ==========================================
# benefit_scheme → chunks
# ==========================================

def scheme_to_chunks(schemes: list, card_name: str, issuer: str, source_file: str) -> list:
    chunks = []

    for i, s in enumerate(schemes):
        scheme_card_name = s.get("card_name") or card_name
        scheme_name = s.get("scheme_name", "")
        surface_desc = s.get("surface_desc", "")
        valid_period = s.get("valid_period")
        reward_unit = s.get("reward_unit", "")

        # valid_period 處理（亞萬卡會是 dict）
        valid_period_str = None
        if isinstance(valid_period, dict):
            parts = []
            if valid_period.get("general_spending"):
                parts.append(f"一般消費里程累積期間：{valid_period['general_spending']}")
            if valid_period.get("accelerator"):
                parts.append(f"哩程加速器指定通路期間：{valid_period['accelerator']}")
            valid_period_str = "；".join(parts)
        else:
            valid_period_str = valid_period

        # 組 text
        text = f"{scheme_card_name}權益方案「{scheme_name}」：{surface_desc}"

        if valid_period_str:
            text += f"（適用期間：{valid_period_str}）"

        if reward_unit:
            text += f"（回饋單位：{reward_unit}）"

        # reward_levels
        reward_levels = s.get("reward_levels")
        if isinstance(reward_levels, dict) and reward_levels:
            lv_text = "、".join([f"{k} {v}" for k, v in reward_levels.items()])
            text += f" 回饋分級：{lv_text}。"

        # channel_groups 攤平進 text 和 channels_flat
        channel_groups = s.get("channel_groups") or {}
        channels_flat = []
        if isinstance(channel_groups, dict) and channel_groups:
            group_texts = []
            for group_name, shops in channel_groups.items():
                if isinstance(shops, list):
                    shop_list = "、".join(shops)
                    channels_flat.extend([f"{group_name}-{shop}" for shop in shops])
                else:
                    shop_list = str(shops)
                    channels_flat.append(f"{group_name}-{shops}")
                group_texts.append(f"{group_name}：{shop_list}")
            text += " 指定通路包含：" + "；".join(group_texts) + "。"

        # notes
        notes = s.get("notes")
        if notes:
            if isinstance(notes, list):
                notes_str = "；".join([str(x).rstrip("。") for x in notes if x])
            else:
                notes_str = str(notes).rstrip("。")
            if notes_str:
                text += f" 注意事項：{notes_str}。"

        metadata = {
            "card_family": s.get("card_family") or scheme_card_name,
            "reward_type": s.get("reward_unit", "other"),
            "channels_flat": channels_flat,
            "valid_period": valid_period_str or valid_period,
            "source_file": source_file,
            "source_path": ["benefit_scheme", i],
            "raw": s,
        }

        chunks.append({
            "id": make_id(scheme_card_name, "scheme", scheme_name or i),
            "text": text,
            "card_name": scheme_card_name,
            "issuer": issuer,
            "doc_type": s.get("doc_type", "benefit_scheme"),
            "scheme_name": scheme_name,
            "rule_type": None,
            "metadata": metadata,
        })

    return chunks


# ==========================================
# benefit_rule → chunks
# v2 改動：英文 key 改成中文標籤，text 更自然，embedding 品質會更好
# ==========================================

# v1 直接用英文 key（include / exclude / conditions）
# v2 改成中文，讓 embedding 語意更準確
KEY_LABEL_MAP = {
    "include": "適用範圍",
    "exclude": "排除範圍",
    "conditions": "條件說明",
    "benefits": "權益內容",
    "lounges": "貴賓室資訊",
    "sharing_rule": "共用規則",
    "how_to_use": "使用方式",
    "offers": "優惠內容",
}

def rule_to_chunks(rules: list, card_name: str, issuer: str, source_file: str) -> list:
    chunks = []

    for i, r in enumerate(rules):
        doc_type = r.get("doc_type", "benefit_rule")
        scheme_name = r.get("scheme_name")
        scheme_id = r.get("scheme_id")
        rule_type = r.get("rule_type")

        text_parts = [f"{card_name}"]
        if scheme_name:
            text_parts.append(f"「{scheme_name}」")
        elif scheme_id:
            text_parts.append(f"（方案ID：{scheme_id}）")
        if rule_type:
            text_parts.append(f"{rule_type}：")

        # v2：用中文標籤取代英文 key
        for key, label in KEY_LABEL_MAP.items():
            val = r.get(key)
            if val:
                if isinstance(val, list):
                    text_parts.append(f"{label}：" + "；".join(map(str, val)) + "。")
                elif isinstance(val, dict):
                    dict_text = "；".join([f"{k}：{v}" for k, v in val.items()])
                    text_parts.append(f"{label}：{dict_text}。")
                else:
                    text_parts.append(f"{label}：{val}。")

        text = "".join(text_parts)

        metadata = {
            "card_family": r.get("card_family") or card_name,
            "reward_type": "other",
            "valid_period": r.get("valid_period"),
            "source_file": source_file,
            "source_path": ["benefit_rule", i],
            "raw": r,
        }

        chunks.append({
            "id": make_id(card_name, "rule", scheme_name or scheme_id, f"idx{i}"),
            "text": text,
            "card_name": card_name,
            "issuer": issuer,
            "doc_type": doc_type,
            "scheme_name": scheme_name,
            "rule_type": rule_type,
            "metadata": metadata,
        })

    return chunks


# ==========================================
# global_rule → chunks
# v2 改動：conditions 改成 key：value 格式，語意更完整
# ==========================================

def global_rule_to_chunks(global_rules, card_name: str, issuer: str, source_file: str) -> list:
    chunks = []

    flat_rules = []
    if isinstance(global_rules, dict):
        flat_rules = [global_rules]
    elif isinstance(global_rules, list):
        for item in global_rules:
            if isinstance(item, list):
                flat_rules.extend([x for x in item if isinstance(x, dict)])
            elif isinstance(item, dict):
                flat_rules.append(item)

    for i, r in enumerate(flat_rules):
        if not isinstance(r, dict):
            continue

        doc_type = r.get("doc_type", "global_rule")
        rule_name = r.get("rule_name", "")
        rule_text = r.get("rule_text", "")
        valid_period = r.get("valid_period")
        conditions = r.get("conditions") or {}
        note = r.get("note")

        text_parts = []
        if card_name:
            text_parts.append(f"{card_name}")
        if rule_name:
            text_parts.append(f"「{rule_name}」：")
        if rule_text:
            text_parts.append(rule_text)

        # v2：conditions 改成 key：value，讓語意完整
        # v1 只取 value，不知道每個值在說什麼
        if isinstance(conditions, dict) and conditions:
            cond_lines = [
                f"{k}：{v}"
                for k, v in conditions.items()
                if v is not None and v != ""
            ]
            if cond_lines:
                text_parts.append(" 條件包含：" + "；".join(cond_lines) + "。")

        if valid_period:
            text_parts.append(f"（適用期間：{valid_period}）")
        if note:
            text_parts.append(f" 備註：{note}")

        text = "".join(text_parts)

        metadata = {
            "card_family": card_name,
            "reward_type": "other",
            "valid_period": valid_period,
            "source_file": source_file,
            "source_path": ["global_rule", i],
            "raw": r,
        }

        chunks.append({
            "id": make_id(card_name, "global_rule", rule_name or f"idx{i}"),
            "text": text,
            "card_name": card_name,
            "issuer": issuer,
            "doc_type": doc_type,
            "scheme_name": None,
            "rule_type": None,
            "metadata": metadata,
        })

    return chunks


# ==========================================
# welcome_offer → chunks
# ==========================================

def welcome_to_chunks(welcome, card_name: str, issuer: str, source_file: str) -> list:
    chunks = []
    welcome_list = [welcome] if isinstance(welcome, dict) else (welcome or [])

    for i, w in enumerate(welcome_list):
        if not isinstance(w, dict):
            continue

        offer_name = w.get("offer_name", "新戶禮")
        period = w.get("valid_period")
        conditions = w.get("conditions") or w.get("requirements") or []
        reward = w.get("reward")

        text_parts = [f"{card_name} {offer_name}："]

        if isinstance(conditions, list) and conditions:
            text_parts.append("達成條件：" + "；".join(map(str, conditions)) + "。")

        if isinstance(reward, dict):
            text_parts.append("回饋內容：" + "、".join([f"{k}: {v}" for k, v in reward.items()]) + "。")
        elif reward:
            text_parts.append(f"回饋內容：{reward}。")

        if period:
            text_parts.append(f"活動期間：{period}。")

        text = "".join(text_parts)

        metadata = {
            "card_family": card_name,
            "reward_type": "mixed",
            "valid_period": period,
            "source_file": source_file,
            "source_path": ["welcome_offer", i],
            "raw": w,
        }

        chunks.append({
            "id": make_id(card_name, "welcome", i),
            "text": text,
            "card_name": card_name,
            "issuer": issuer,
            "doc_type": "welcome_offer",
            "scheme_name": None,
            "rule_type": None,
            "metadata": metadata,
        })

    return chunks


# ==========================================
# 單檔轉換（新 schema 一律有 card_name，只需要一個情況）
# ==========================================

def convert_file(path: str) -> list:
    path_obj = Path(path)
    with open(path_obj, "r", encoding="utf-8") as f:
        data = json.load(f)

    source_file = path_obj.name
    chunks = []

    if not (isinstance(data, dict) and "card_name" in data):
        print(f"⚠️  {source_file} 缺少 card_name，跳過")
        return chunks

    card_name = data.get("card_name")
    issuer = data.get("issuer", "國泰世華銀行")

    profile = data.get("credit_card_profile")
    if isinstance(profile, dict):
        if not profile.get("card_name"):
            profile["card_name"] = card_name
        if not profile.get("issuer"):
            profile["issuer"] = issuer
        chunks.append(profile_to_chunk(profile, source_file))
    elif isinstance(profile, list):
        for p in profile:
            if not p.get("card_name"):
                p["card_name"] = card_name
            if not p.get("issuer"):
                p["issuer"] = issuer
            chunks.append(profile_to_chunk(p, source_file))

    if "benefit_scheme" in data:
        chunks += scheme_to_chunks(data["benefit_scheme"], card_name, issuer, source_file)

    if "benefit_rule" in data:
        chunks += rule_to_chunks(data["benefit_rule"], card_name, issuer, source_file)

    if "welcome_offer" in data:
        chunks += welcome_to_chunks(data["welcome_offer"], card_name, issuer, source_file)

    if "global_rule" in data:
        chunks += global_rule_to_chunks(data["global_rule"], card_name, issuer, source_file)

    return chunks


# ==========================================
# 主程式
# ==========================================

def main():
    base_dir = "credit_card_llm_json"

    input_files = [
        "cube.json",
        "shopee.json",
        "world.json",
        "mile.json",
    ]

    all_chunks = []
    for fname in input_files:
        path = os.path.join(base_dir, fname)
        file_chunks = convert_file(path)
        print(f"{path} → {len(file_chunks)} chunks")
        all_chunks.extend(file_chunks)

    print(f"\n總共 chunk 數量：{len(all_chunks)}")

    output_path = "cards_rag.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"輸出完成：{output_path}")


if __name__ == "__main__":
    main()