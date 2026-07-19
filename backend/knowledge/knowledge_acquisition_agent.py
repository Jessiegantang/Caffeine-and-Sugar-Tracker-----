import datetime
import base64
import json
import os
import re
import uuid
from urllib.parse import urlparse

from db.database import DrinkKnowledge, NutritionEvidence, ProductCandidate


BLOCKED_DOMAINS = {
    "xiaohongshu.com",
    "xhslink.com",
}

BRAND_ALIASES = {
    "瑞幸": "瑞幸咖啡",
    "luckin": "瑞幸咖啡",
    "星巴克": "星巴克",
    "starbucks": "星巴克",
    "喜茶": "喜茶",
    "heytea": "喜茶",
    "奈雪": "奈雪的茶",
    "nayuki": "奈雪的茶",
    "库迪": "库迪咖啡",
    "cotti": "库迪咖啡",
}

TYPE_KEYWORDS = {
    "coffee": ["咖啡", "拿铁", "美式", "摩卡", "澳白", "冷萃", "dirty", "espresso", "latte", "americano", "coffee"],
    "teacoffee": ["茶咖", "咖茶"],
    "milktea": ["奶茶", "奶盖", "珍珠", "波波", "milk tea"],
    "fruittea": ["果茶", "柠檬茶", "葡萄", "桃", "芒果", "柚", "椰", "椰椰", "果汁", "fruit tea"],
    "tea": ["绿茶", "红茶", "乌龙", "茉莉", "茶"],
    "soda": ["气泡", "汽水", "soda"],
    "other": ["冰沙", "沙冰", "库可冰", "可可", "巧克力", "雪冰", "冰"],
}

VALID_TYPES = set(TYPE_KEYWORDS)


def create_manual_candidate(db, payload: dict) -> ProductCandidate:
    candidate = ProductCandidate(
        id=payload.get("id") or f"cand_{uuid.uuid4().hex[:10]}",
        brand=normalize_brand(payload.get("brand") or infer_brand(payload.get("name", ""))),
        name=(payload.get("name") or "").strip(),
        type=payload.get("type") or infer_type(payload.get("name", "")),
        source_url=payload.get("source_url"),
        source_title=payload.get("source_title"),
        source_snippet=payload.get("source_snippet"),
        discovery_method=payload.get("discovery_method") or "manual",
        status=payload.get("status") or "pending_review",
        updated_at=datetime.datetime.now().isoformat(),
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def add_nutrition_evidence(db, candidate_id: str, payload: dict) -> NutritionEvidence:
    candidate = db.query(ProductCandidate).filter(ProductCandidate.id == candidate_id).first()
    if not candidate:
        raise ValueError("Candidate not found")

    raw_text = payload.get("raw_evidence") or ""
    extracted = extract_nutrition_fields(raw_text)
    evidence = NutritionEvidence(
        id=payload.get("id") or f"ev_{uuid.uuid4().hex[:10]}",
        candidate_id=candidate_id,
        source_url=payload.get("source_url") or candidate.source_url,
        source_type=payload.get("source_type") or "manual",
        raw_evidence=raw_text,
        extracted_json=json.dumps(extracted, ensure_ascii=False),
        status="pending_review",
    )
    db.add(evidence)
    candidate.status = "evidence_ready"
    candidate.updated_at = datetime.datetime.now().isoformat()
    db.commit()
    db.refresh(evidence)
    return evidence


def approve_evidence_to_knowledge(db, evidence_id: str) -> DrinkKnowledge:
    evidence = db.query(NutritionEvidence).filter(NutritionEvidence.id == evidence_id).first()
    if not evidence:
        raise ValueError("Evidence not found")
    candidate = db.query(ProductCandidate).filter(ProductCandidate.id == evidence.candidate_id).first()
    if not candidate:
        raise ValueError("Candidate not found")

    extracted = json.loads(evidence.extracted_json or "{}")
    if not _has_minimum_nutrition(extracted):
        raise ValueError("Evidence does not contain enough nutrition fields to import")

    duplicate = find_duplicate_knowledge(db, candidate.brand, candidate.name)
    kb_id = duplicate.id if duplicate else f"kb_{uuid.uuid4().hex[:10]}"
    kb = duplicate or DrinkKnowledge(id=kb_id)
    target_volume = int((duplicate.volume if duplicate else None) or extracted.get("volume") or 500)
    source_volume = float(extracted.get("volume") or target_volume or 500)
    volume_ratio = target_volume / source_volume if source_volume else 1.0
    merged_scope = merge_nutrition_scopes(kb.source if duplicate else None, extracted)

    kb.brand = candidate.brand or ""
    kb.name = candidate.name
    kb.type = candidate.type or infer_type(candidate.name)
    kb.volume = target_volume
    if extracted.get("caffeine") is not None:
        kb.caffeine = round(float(extracted.get("caffeine")) * volume_ratio, 1)
    elif not duplicate:
        kb.caffeine = 0.0
    if extracted.get("sugar") is not None:
        kb.baseSugar = round(float(extracted.get("sugar")) * volume_ratio, 1)
    elif not duplicate:
        kb.baseSugar = 0.0
    kb.source = f"reviewed:{evidence.source_type}:{merged_scope}"
    kb.updated_at = datetime.datetime.now().isoformat()
    if not duplicate:
        db.add(kb)

    evidence.status = "approved"
    candidate.status = "imported"
    candidate.updated_at = datetime.datetime.now().isoformat()
    db.commit()
    db.refresh(kb)
    return kb


def analyze_image_with_vision(
    image_bytes: bytes,
    content_type: str,
    filename: str | None = None,
    context_text: str = "",
) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("dummy_"):
        return {
            "vision_configured": False,
            "message": "Vision API is not configured. Set OPENAI_API_KEY and VISION_MODEL_NAME or MODEL_NAME.",
            "items": [],
        }

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        model_name = os.getenv("VISION_MODEL_NAME") or os.getenv("MODEL_NAME", "gpt-4o-mini")
        base_url = os.getenv("BASE_URL")
        kwargs = {"model": model_name, "api_key": api_key, "temperature": 0}
        if base_url:
            kwargs["base_url"] = base_url
        vision_llm = ChatOpenAI(**kwargs)

        encoded = base64.b64encode(image_bytes).decode("ascii")
        mime = content_type or "image/jpeg"
        response = vision_llm.invoke([
            SystemMessage(content=(
                "You are DrinkMind Image Evidence Agent. Extract beverage nutrition evidence from a user-uploaded image. "
                "The image may contain one product or many products. Return strict JSON only. "
                "Do not invent missing values. Use null for unknown volume, caffeine, or sugar. "
                "For each item include: brand, name, type, volume, caffeine, sugar, volume_note, raw_evidence. "
                "type must be one of coffee, teacoffee, tea, milktea, fruittea, soda, other. "
                "Classify latte-style products such as 米乳拿铁, 生椰拿铁, 厚乳拿铁, 生酪拿铁 as coffee unless the name explicitly says 茶咖. "
                "Classify coconut or fruit flavored non-coffee ice drinks such as 海岛椰椰库可冰 and 柚见茉莉库可冰 as fruittea. "
                "Use other for ambiguous dessert/smoothie drinks such as 巧克力库可冰 when they are not coffee, tea, milk tea, fruit tea, or soda. "
                "Use user context when it states shared brand, default volume, serving basis, or notes. "
                "If a numeric field is shown as a range, return the range text instead of dropping it. "
                "If the image is a caffeine table, return one item per visible row. "
                "Important layout rule: many Chinese beverage tables have two independent product/value column groups, "
                "for example left name+mg and right name+mg. Scan all columns from top to bottom, left group and right group, "
                "and never stop after the first column group. If sugar is not shown, set sugar to null and still return the item."
            )),
            HumanMessage(content=[
                {
                    "type": "text",
                    "text": (
                        "Analyze this image and return JSON in this exact shape: "
                        "{\"source_type\":\"image_upload\",\"evidence_type\":\"caffeine_table|nutrition_label|menu|mixed\","
                        "\"brand\":string|null,\"items\":[...]}. "
                        "For caffeine tables, every row that looks like 产品名 + 数字mg is one item, including the right-side column. "
                        f"User context: {context_text[:2000] if context_text else 'none'}"
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                },
            ]),
        ])
        parsed = _parse_json_object(response.content)
        items = normalize_image_items(parsed.get("items", []), parsed.get("brand"), context_text)
        return {
            "vision_configured": True,
            "filename": filename,
            "source_type": parsed.get("source_type") or "image_upload",
            "evidence_type": parsed.get("evidence_type") or "mixed",
            "brand": normalize_brand(parsed.get("brand")),
            "items": items,
        }
    except Exception as e:
        return {
            "vision_configured": True,
            "message": f"Vision analysis failed: {e}",
            "items": [],
        }


def normalize_image_items(
    items: list[dict],
    default_brand: str | None = None,
    context_text: str = "",
) -> list[dict]:
    normalized = []
    context_brand = normalize_brand(default_brand or infer_brand(context_text))
    context_volume = _extract_context_volume(context_text)
    context_note = _extract_context_note(context_text)
    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        brand = normalize_brand(item.get("brand") or context_brand or infer_brand(name))
        volume, volume_range = _coerce_numeric_value(item.get("volume"), "volume")
        caffeine, caffeine_range = _coerce_numeric_value(item.get("caffeine"), "caffeine")
        sugar, sugar_range = _coerce_numeric_value(item.get("sugar"), "sugar")
        notes = []
        if volume is None and context_volume is not None:
            volume = context_volume
            notes.append(f"容量来自上下文 {context_volume:g}ml")
        if caffeine_range:
            notes.append(f"咖啡因取范围中值 {caffeine:g}mg")
        if sugar_range:
            notes.append(f"糖分取范围中值 {sugar:g}g")
        caffeine_qualifier_note = _numeric_qualifier_note(item.get("caffeine"), caffeine, "咖啡因", "mg")
        sugar_qualifier_note = _numeric_qualifier_note(item.get("sugar"), sugar, "糖分", "g")
        if caffeine_qualifier_note:
            notes.append(caffeine_qualifier_note)
        if sugar_qualifier_note:
            notes.append(sugar_qualifier_note)
        if brand and not item.get("brand") and context_brand:
            notes.append(f"品牌来自上下文 {brand}")
        extracted = {
            "volume": volume,
            "caffeine": caffeine,
            "sugar": sugar,
        }
        normalized.append({
            "brand": brand,
            "name": name,
            "type": normalize_type(item.get("type"), name, item.get("raw_evidence")),
            **extracted,
            "nutrition_scope": nutrition_scope(extracted),
            "volume_note": item.get("volume_note") or context_note,
            "volume_range": volume_range,
            "caffeine_range": caffeine_range,
            "sugar_range": sugar_range,
            "normalization_notes": notes,
            "raw_evidence": item.get("raw_evidence") or _format_raw_evidence(item),
        })
    return normalized


def stage_image_items(db, items: list[dict], source_type: str = "image_upload") -> dict:
    staged = []
    skipped = []
    for item in items:
        if not item.get("name"):
            skipped.append({"item": item, "reason": "missing_name"})
            continue
        if not _has_minimum_nutrition(item):
            skipped.append({"item": item, "reason": "missing_nutrition"})
            continue
        candidate = create_manual_candidate(db, {
            "brand": item.get("brand"),
            "name": item.get("name"),
            "type": item.get("type") or infer_type(item.get("name", "")),
            "source_url": None,
            "source_title": "Uploaded image evidence",
            "source_snippet": item.get("raw_evidence"),
            "discovery_method": source_type,
        })
        evidence = add_nutrition_evidence(db, candidate.id, {
            "source_type": source_type,
            "source_url": None,
            "raw_evidence": item_to_evidence_text(item),
        })
        staged.append({
            "candidate": serialize_candidate(candidate),
            "evidence": serialize_evidence(evidence),
        })
    return {"count": len(staged), "staged": staged, "skipped": skipped}


def parse_candidate_from_text(text: str) -> dict:
    brand = infer_brand(text) or _extract_explicit_brand(text)
    explicit_name = _extract_explicit_name(text)
    if explicit_name:
        explicit_name = re.split(r"\s+(?:容量|咖啡因|糖分|糖|caffeine|sugar)", explicit_name, flags=re.I)[0].strip()
        return {
            "brand": normalize_brand(brand),
            "name": explicit_name,
            "type": infer_type(explicit_name or text),
        }
    cleaned = text
    if brand:
        cleaned = cleaned.replace(brand, "")
    for alias in BRAND_ALIASES:
        cleaned = re.sub(re.escape(alias), "", cleaned, flags=re.IGNORECASE)
    name_match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]+(?:拿铁|美式|奶茶|果茶|柠檬茶|咖啡|茶|气泡水))", cleaned)
    name = name_match.group(1) if name_match else ""
    return {
        "brand": normalize_brand(brand),
        "name": name,
        "type": infer_type(name or text),
    }


def _extract_explicit_brand(text: str) -> str:
    match = re.search(r"(?:品牌|brand)\s*:?\s*([^,，;；\n\s]+)", text, flags=re.I)
    return match.group(1).strip() if match else ""


def _extract_explicit_name(text: str) -> str:
    match = re.search(r"(?:饮品名称|产品名称|候选饮品|名称|name)\s*:?\s*([^,，;；\n]+)", text, flags=re.I)
    return match.group(1).strip() if match else ""


def extract_nutrition_fields(raw_text: str) -> dict:
    text = raw_text.replace("：", ":")
    return {
        "volume": _extract_number(text, [r"(\d+(?:\.\d+)?)\s*ml", r"容量\s*:?\s*(\d+(?:\.\d+)?)"]),
        "caffeine": _extract_number(text, [
            r"咖啡因\s*:?\s*[<≤]\s*(\d+(?:\.\d+)?)\s*mg",
            r"咖啡因\s*:?\s*(\d+(?:\.\d+)?)\s*(?:\+|以上|及以上)?\s*mg",
            r"caffeine\s*:?\s*[<≤]\s*(\d+(?:\.\d+)?)\s*mg",
            r"caffeine\s*:?\s*(\d+(?:\.\d+)?)\s*(?:\+|above|or more)?\s*mg",
        ]),
        "sugar": _extract_number(text, [
            r"糖分\s*:?\s*[<≤]\s*(\d+(?:\.\d+)?)\s*g",
            r"糖分\s*:?\s*(\d+(?:\.\d+)?)\s*(?:\+|以上|及以上)?\s*g",
            r"糖\s*:?\s*[<≤]\s*(\d+(?:\.\d+)?)\s*g",
            r"糖\s*:?\s*(\d+(?:\.\d+)?)\s*(?:\+|以上|及以上)?\s*g",
            r"sugar\s*:?\s*[<≤]\s*(\d+(?:\.\d+)?)\s*g",
            r"sugar\s*:?\s*(\d+(?:\.\d+)?)\s*(?:\+|above|or more)?\s*g",
        ]),
    }


def item_to_evidence_text(item: dict) -> str:
    parts = [item.get("raw_evidence") or item.get("name") or ""]
    if item.get("volume") is not None:
        parts.append(f"容量: {item.get('volume')}ml")
    if item.get("volume_range"):
        parts.append(f"容量原范围: {_range_to_text(item.get('volume_range'))}ml")
    if item.get("caffeine") is not None:
        parts.append(f"咖啡因: {item.get('caffeine')}mg")
    if item.get("caffeine_range"):
        parts.append(f"咖啡因原范围: {_range_to_text(item.get('caffeine_range'))}mg")
    if item.get("sugar") is not None:
        parts.append(f"糖分: {item.get('sugar')}g")
    if item.get("sugar_range"):
        parts.append(f"糖分原范围: {_range_to_text(item.get('sugar_range'))}g")
    if item.get("volume_note"):
        parts.append(f"口径: {item.get('volume_note')}")
    for note in item.get("normalization_notes") or []:
        parts.append(str(note))
    return " ".join(str(part) for part in parts if part)


def nutrition_scope(extracted: dict) -> str:
    has_caffeine = extracted.get("caffeine") is not None
    has_sugar = extracted.get("sugar") is not None
    if has_caffeine and not has_sugar:
        return "caffeine_only"
    if has_sugar and not has_caffeine:
        return "sugar_only"
    if has_caffeine and has_sugar:
        return "caffeine_sugar"
    if has_caffeine or has_sugar:
        return "partial"
    return "unknown"


def merge_nutrition_scopes(existing_source: str | None, extracted: dict) -> str:
    fields = set()
    existing = existing_source or ""
    has_existing_scope = any(scope in existing for scope in [
        "complete", "caffeine_sugar", "caffeine_only", "sugar_only", "partial", "unknown"
    ])
    if existing_source and not has_existing_scope:
        fields.update(["caffeine", "sugar"])
    if "complete" in existing or "caffeine_sugar" in existing:
        fields.update(["caffeine", "sugar"])
    if "caffeine_only" in existing:
        fields.add("caffeine")
    if "sugar_only" in existing:
        fields.add("sugar")

    if extracted.get("caffeine") is not None:
        fields.add("caffeine")
    if extracted.get("sugar") is not None:
        fields.add("sugar")

    if {"caffeine", "sugar"}.issubset(fields):
        return "caffeine_sugar"
    if fields == {"caffeine"}:
        return "caffeine_only"
    if fields == {"sugar"}:
        return "sugar_only"
    if fields:
        return "partial"
    return "unknown"


def find_duplicate_knowledge(db, brand: str | None, name: str | None):
    if not name:
        return None
    query = db.query(DrinkKnowledge).filter(DrinkKnowledge.name == name)
    if brand:
        query = query.filter(DrinkKnowledge.brand == brand)
    return query.first()


def is_allowed_source(url: str, allowed_domains: list[str] | None = None) -> bool:
    if not url:
        return True
    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if any(domain == blocked or domain.endswith("." + blocked) for blocked in BLOCKED_DOMAINS):
        return False
    if allowed_domains:
        normalized = [d.lower().lstrip("www.") for d in allowed_domains]
        return any(domain == d or domain.endswith("." + d) for d in normalized)
    return True


def infer_brand(text: str) -> str | None:
    lower = (text or "").lower()
    for alias, brand in BRAND_ALIASES.items():
        if alias.lower() in lower or alias in text:
            return brand
    return None


def normalize_brand(brand: str | None) -> str | None:
    if not brand:
        return None
    return BRAND_ALIASES.get(brand.lower(), BRAND_ALIASES.get(brand, brand))


def infer_type(text: str) -> str:
    lower = (text or "").lower()
    if not lower:
        return "other"

    if any(keyword in lower or keyword in text for keyword in ["气泡", "汽水", "soda"]):
        return "soda"
    if any(keyword in lower or keyword in text for keyword in ["茶咖", "咖茶"]):
        return "teacoffee"
    if any(keyword in lower or keyword in text for keyword in ["咖啡", "拿铁", "美式", "摩卡", "澳白", "冷萃", "dirty", "espresso", "latte", "americano", "coffee"]):
        return "coffee"
    if any(keyword in lower or keyword in text for keyword in ["奶茶", "奶盖", "珍珠", "波波", "milk tea"]):
        return "milktea"
    if any(keyword in lower or keyword in text for keyword in ["果茶", "柠檬茶", "葡萄", "桃", "芒果", "柚", "椰", "椰椰", "果汁", "fruit tea"]):
        return "fruittea"
    if any(keyword in lower or keyword in text for keyword in ["绿茶", "红茶", "乌龙", "茉莉", "抹茶", "茶"]):
        return "tea"
    if any(keyword in lower or keyword in text for keyword in ["冰沙", "沙冰", "库可冰", "可可", "巧克力", "雪冰", "冰"]):
        return "other"
    for drink_type, keywords in TYPE_KEYWORDS.items():
        if any(keyword.lower() in lower or keyword in text for keyword in keywords):
            return drink_type
    return "other"


def normalize_type(candidate_type: str | None, name: str = "", raw_text: str | None = None) -> str:
    inferred = infer_type(" ".join(part for part in [name, raw_text or ""] if part))
    if candidate_type not in VALID_TYPES:
        return inferred
    if inferred == "coffee" and _looks_like_coffee_name(name):
        return "coffee"
    if inferred in {"teacoffee", "tea", "milktea", "fruittea", "soda", "other"}:
        return inferred
    return candidate_type or inferred


def _looks_like_coffee_name(name: str) -> bool:
    text = name or ""
    if any(keyword in text for keyword in ["茶咖", "咖茶"]):
        return False
    return any(keyword in text.lower() or keyword in text for keyword in [
        "咖啡", "拿铁", "美式", "摩卡", "澳白", "冷萃", "dirty", "latte", "americano", "espresso"
    ])


def serialize_candidate(candidate: ProductCandidate) -> dict:
    return {column.name: getattr(candidate, column.name) for column in candidate.__table__.columns}


def serialize_evidence(evidence: NutritionEvidence) -> dict:
    data = {column.name: getattr(evidence, column.name) for column in evidence.__table__.columns}
    try:
        data["extracted"] = json.loads(data.get("extracted_json") or "{}")
    except Exception:
        data["extracted"] = {}
    return data


def _parse_json_object(content: str) -> dict:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        text = match.group(0)
    return json.loads(text)


def _extract_context_volume(context_text: str) -> float | None:
    text = context_text or ""
    match = re.search(r"(?:约|大杯|中杯|小杯|每杯|容量)?\s*(\d+(?:\.\d+)?)\s*ml", text, flags=re.I)
    return float(match.group(1)) if match else None


def _extract_context_note(context_text: str) -> str | None:
    text = (context_text or "").strip()
    if not text:
        return None
    notes = []
    volume = _extract_context_volume(text)
    if volume is not None:
        notes.append(f"上下文口径约 {volume:g}ml")
    if "不额外加糖" in text or "不加糖" in text:
        notes.append("不额外加糖口径")
    if "估算" in text:
        notes.append("文本/图片估算值")
    return "；".join(notes) if notes else None


def _coerce_numeric_value(value, field: str) -> tuple[float | None, dict | None]:
    if value in [None, ""]:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None

    text = str(value)
    avg_match = re.search(r"(?:平均值|均值|约|≈|~)\s*(\d+(?:\.\d+)?)", text)
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|–|—|至|到|~|～)\s*(\d+(?:\.\d+)?)", text)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        if high < low:
            low, high = high, low
        if avg_match:
            number = float(avg_match.group(1))
        else:
            number = (low + high) / 2
        return round(number, 2), {"min": low, "max": high}

    inequality_match = re.search(
        r"(?:[<≤]|小于|低于|少于|不超过)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:\+|以上|及以上|起)",
        text,
        flags=re.I,
    )
    if inequality_match:
        number = inequality_match.group(1) or inequality_match.group(2)
        return float(number), None

    unit_patterns = {
        "volume": r"(\d+(?:\.\d+)?)\s*ml",
        "caffeine": r"(\d+(?:\.\d+)?)\s*mg",
        "sugar": r"(\d+(?:\.\d+)?)\s*g",
    }
    match = re.search(unit_patterns.get(field, r"(\d+(?:\.\d+)?)"), text, flags=re.I)
    if match:
        return float(match.group(1)), None
    return _safe_float(value), None


def _numeric_qualifier_note(value, normalized_value, label: str, unit: str) -> str | None:
    if value in [None, ""] or normalized_value is None:
        return None
    text = str(value).strip()
    if re.search(r"[<≤]|小于|低于|少于|不超过", text):
        return f"{label}原值 {text}，按 {normalized_value:g}{unit} 审核"
    if re.search(r"\d+(?:\.\d+)?\s*(?:\+|以上|及以上|起)", text):
        return f"{label}原值 {text}，按 {normalized_value:g}{unit} 审核"
    return None


def _range_to_text(value) -> str:
    if not value:
        return ""
    if isinstance(value, dict):
        low = value.get("min", value.get("low"))
        high = value.get("max", value.get("high"))
        if low is not None and high is not None:
            return f"{low:g}-{high:g}"
    return str(value)


def _safe_float(value):
    if value in [None, ""]:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _format_raw_evidence(item: dict) -> str:
    fields = []
    if item.get("name"):
        fields.append(str(item.get("name")))
    if item.get("volume") is not None:
        fields.append(f"容量 {item.get('volume')}ml")
    if item.get("caffeine") is not None:
        fields.append(f"咖啡因 {item.get('caffeine')}mg")
    if item.get("sugar") is not None:
        fields.append(f"糖分 {item.get('sugar')}g")
    return " ".join(fields)


def _extract_number(text: str, patterns: list[str]):
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _has_minimum_nutrition(extracted: dict) -> bool:
    return extracted.get("caffeine") is not None or extracted.get("sugar") is not None
