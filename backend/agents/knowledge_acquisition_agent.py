import datetime
import base64
import json
import os
import re
import uuid
from urllib.parse import urlparse

from database import DrinkKnowledge, NutritionEvidence, ProductCandidate


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
    "coffee": ["咖啡", "拿铁", "美式", "摩卡", "espresso", "latte", "americano", "coffee"],
    "milktea": ["奶茶", "厚乳", "奶盖", "milk tea"],
    "fruittea": ["果茶", "柠檬茶", "葡萄", "桃", "芒果", "fruit tea"],
    "tea": ["绿茶", "红茶", "乌龙", "茶"],
    "soda": ["气泡", "汽水", "soda"],
    "alcohol": ["啤酒", "鸡尾酒", "酒", "beer", "cocktail"],
}


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
        confidence=float(payload.get("confidence") or 0.6),
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
    confidence = score_evidence(payload.get("source_type") or "manual", extracted, raw_text)
    evidence = NutritionEvidence(
        id=payload.get("id") or f"ev_{uuid.uuid4().hex[:10]}",
        candidate_id=candidate_id,
        source_url=payload.get("source_url") or candidate.source_url,
        source_type=payload.get("source_type") or "manual",
        raw_evidence=raw_text,
        extracted_json=json.dumps(extracted, ensure_ascii=False),
        confidence=confidence,
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
    if extracted.get("abv") is not None:
        kb.abv = float(extracted.get("abv"))
    elif not duplicate:
        kb.abv = 0.0
    kb.source = f"reviewed:{evidence.source_type}:{merged_scope}"
    new_confidence = adjust_confidence_for_scope(float(evidence.confidence or 0.5), extracted)
    kb.confidence = min(max(float(kb.confidence or 0.0), new_confidence), 0.95)
    kb.updated_at = datetime.datetime.now().isoformat()
    if not duplicate:
        db.add(kb)

    evidence.status = "approved"
    candidate.status = "imported"
    candidate.updated_at = datetime.datetime.now().isoformat()
    db.commit()
    db.refresh(kb)
    return kb


def analyze_image_with_vision(image_bytes: bytes, content_type: str, filename: str | None = None) -> dict:
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
                "Do not invent missing values. Use null for unknown volume, caffeine, sugar, or abv. "
                "For each item include: brand, name, type, volume, caffeine, sugar, abv, volume_note, raw_evidence, confidence. "
                "type must be one of coffee, teacoffee, tea, milktea, fruittea, soda, alcohol. "
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
                        "For caffeine tables, every row that looks like 产品名 + 数字mg is one item, including the right-side column."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                },
            ]),
        ])
        parsed = _parse_json_object(response.content)
        items = normalize_image_items(parsed.get("items", []), parsed.get("brand"))
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


def normalize_image_items(items: list[dict], default_brand: str | None = None) -> list[dict]:
    normalized = []
    for item in items:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        brand = normalize_brand(item.get("brand") or default_brand or infer_brand(name))
        extracted = {
            "volume": _safe_float(item.get("volume")),
            "caffeine": _safe_float(item.get("caffeine")),
            "sugar": _safe_float(item.get("sugar")),
            "abv": _safe_float(item.get("abv")),
        }
        normalized.append({
            "brand": brand,
            "name": name,
            "type": item.get("type") or infer_type(name),
            **extracted,
            "nutrition_scope": nutrition_scope(extracted),
            "volume_note": item.get("volume_note"),
            "raw_evidence": item.get("raw_evidence") or _format_raw_evidence(item),
            "confidence": round(max(0.1, min(float(item.get("confidence") or 0.65), 0.95)), 2),
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
            "confidence": item.get("confidence") or 0.65,
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
    brand = infer_brand(text)
    cleaned = text
    for alias in BRAND_ALIASES:
        cleaned = re.sub(re.escape(alias), "", cleaned, flags=re.IGNORECASE)
    name_match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]+(?:拿铁|美式|奶茶|果茶|柠檬茶|咖啡|茶|气泡水|啤酒))", cleaned)
    name = name_match.group(1) if name_match else ""
    return {
        "brand": normalize_brand(brand),
        "name": name,
        "type": infer_type(name or text),
    }


def extract_nutrition_fields(raw_text: str) -> dict:
    text = raw_text.replace("：", ":")
    return {
        "volume": _extract_number(text, [r"(\d+(?:\.\d+)?)\s*ml", r"容量\s*:?\s*(\d+(?:\.\d+)?)"]),
        "caffeine": _extract_number(text, [r"咖啡因\s*:?\s*(\d+(?:\.\d+)?)\s*mg", r"caffeine\s*:?\s*(\d+(?:\.\d+)?)\s*mg"]),
        "sugar": _extract_number(text, [r"糖分\s*:?\s*(\d+(?:\.\d+)?)\s*g", r"糖\s*:?\s*(\d+(?:\.\d+)?)\s*g", r"sugar\s*:?\s*(\d+(?:\.\d+)?)\s*g"]),
        "abv": _extract_number(text, [r"酒精度\s*:?\s*(\d+(?:\.\d+)?)\s*%", r"abv\s*:?\s*(\d+(?:\.\d+)?)\s*%"]),
    }


def item_to_evidence_text(item: dict) -> str:
    parts = [item.get("raw_evidence") or item.get("name") or ""]
    if item.get("volume") is not None:
        parts.append(f"容量: {item.get('volume')}ml")
    if item.get("caffeine") is not None:
        parts.append(f"咖啡因: {item.get('caffeine')}mg")
    if item.get("sugar") is not None:
        parts.append(f"糖分: {item.get('sugar')}g")
    if item.get("abv") is not None:
        parts.append(f"酒精度: {item.get('abv')}%")
    return " ".join(str(part) for part in parts if part)


def nutrition_scope(extracted: dict) -> str:
    has_caffeine = extracted.get("caffeine") is not None
    has_sugar = extracted.get("sugar") is not None
    has_abv = extracted.get("abv") is not None
    if has_caffeine and not has_sugar and not has_abv:
        return "caffeine_only"
    if has_sugar and not has_caffeine and not has_abv:
        return "sugar_only"
    if has_abv and not has_caffeine and not has_sugar:
        return "alcohol_only"
    if has_caffeine and has_sugar:
        return "caffeine_sugar"
    if has_caffeine or has_sugar or has_abv:
        return "partial"
    return "unknown"


def merge_nutrition_scopes(existing_source: str | None, extracted: dict) -> str:
    fields = set()
    existing = existing_source or ""
    has_existing_scope = any(scope in existing for scope in [
        "complete", "caffeine_sugar", "caffeine_only", "sugar_only", "alcohol_only", "partial", "unknown"
    ])
    if existing_source and not has_existing_scope:
        fields.update(["caffeine", "sugar"])
    if "complete" in existing or "caffeine_sugar" in existing:
        fields.update(["caffeine", "sugar"])
    if "caffeine_only" in existing:
        fields.add("caffeine")
    if "sugar_only" in existing:
        fields.add("sugar")
    if "alcohol_only" in existing:
        fields.add("abv")

    if extracted.get("caffeine") is not None:
        fields.add("caffeine")
    if extracted.get("sugar") is not None:
        fields.add("sugar")
    if extracted.get("abv") is not None:
        fields.add("abv")

    if {"caffeine", "sugar"}.issubset(fields):
        return "caffeine_sugar"
    if fields == {"caffeine"}:
        return "caffeine_only"
    if fields == {"sugar"}:
        return "sugar_only"
    if fields == {"abv"}:
        return "alcohol_only"
    if fields:
        return "partial"
    return "unknown"


def adjust_confidence_for_scope(confidence: float, extracted: dict) -> float:
    scope = nutrition_scope(extracted)
    if scope in {"caffeine_only", "sugar_only", "alcohol_only"}:
        return max(0.1, confidence - 0.08)
    if scope == "unknown":
        return max(0.1, confidence - 0.2)
    return confidence


def score_evidence(source_type: str, extracted: dict, raw_text: str) -> float:
    base = {
        "official": 0.88,
        "nutrition_label": 0.82,
        "community_measurement": 0.62,
        "manual": 0.58,
        "image_upload": 0.68,
        "official_image": 0.78,
        "nutrition_label_image": 0.82,
        "community_screenshot": 0.55,
    }.get(source_type, 0.5)
    fields = sum(1 for key in ["volume", "caffeine", "sugar", "abv"] if extracted.get(key) is not None)
    if fields >= 3:
        base += 0.08
    elif fields >= 2:
        base += 0.04
    if len(raw_text) < 20:
        base -= 0.1
    return round(max(0.1, min(base, 0.95)), 2)


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
    for drink_type, keywords in TYPE_KEYWORDS.items():
        if any(keyword.lower() in lower or keyword in text for keyword in keywords):
            return drink_type
    return "coffee"


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
    if item.get("abv") is not None:
        fields.append(f"酒精度 {item.get('abv')}%")
    return " ".join(fields)


def _extract_number(text: str, patterns: list[str]):
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _has_minimum_nutrition(extracted: dict) -> bool:
    return extracted.get("caffeine") is not None or extracted.get("sugar") is not None or extracted.get("abv") is not None
