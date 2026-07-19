import os
import re

from knowledge.knowledge_acquisition_agent import (
    extract_nutrition_fields,
    infer_brand,
    infer_type,
    normalize_image_items,
    parse_candidate_from_text,
)


def analyze_text_with_agent(text: str, source_type: str = "manual_text") -> dict:
    """Extract beverage nutrition evidence from pasted text.

    The frontend treats this like image analysis: review returned items before
    staging them into the acquisition queue.
    """
    llm_result = _analyze_text_with_llm(text, source_type)
    if llm_result is not None:
        return llm_result

    items = normalize_image_items(_fallback_text_items(text), None)
    return {
        "text_agent_configured": False,
        "source_type": source_type or "manual_text",
        "evidence_type": "pasted_text",
        "message": "Text agent LLM is not configured; used backend rule fallback.",
        "items": items,
    }


def _analyze_text_with_llm(text: str, source_type: str) -> dict | None:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if (
        not api_key
        or api_key.startswith("dummy_")
        or os.getenv("DRINKMIND_OFFLINE", "").lower() in {"true", "1", "yes"}
        or os.getenv("ENABLE_LLM", "").lower() not in {"true", "1", "yes"}
    ):
        return None

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        model_name = os.getenv("TEXT_ACQUISITION_MODEL_NAME") or os.getenv("MODEL_NAME", "gpt-4o-mini")
        base_url = os.getenv("BASE_URL")
        timeout = float(os.getenv("TEXT_ACQUISITION_TIMEOUT", "15"))
        kwargs = {"model": model_name, "api_key": api_key, "temperature": 0, "timeout": timeout}
        if base_url:
            kwargs["base_url"] = base_url
        text_llm = ChatOpenAI(**kwargs)

        response = text_llm.invoke([
            SystemMessage(content=(
                "You are DrinkMind Text Evidence Agent. Extract beverage nutrition evidence from pasted text. "
                "The text may be OCR output, a nutrition table, a menu, a product page excerpt, or user notes. "
                "Return strict JSON only. Do not invent missing values. Use null for unknown volume, caffeine, or sugar. "
                "Return one item per beverage product. For each item include: brand, name, type, volume, caffeine, sugar, "
                "For markdown tables, return one item per table row and ignore non-product explanatory rows. "
                "If the text gives a range such as 150-200mg and also says average/best about 170mg, use 170 as the numeric value. "
                "If only a range is provided, use the midpoint as the numeric value and preserve the original range in raw_evidence. "
                "If values are per 100ml rather than per cup, keep the numeric value and explain that basis in volume_note "
                "and raw_evidence; do not scale unless the text explicitly gives both basis and serving volume. "
                "If a line has only caffeine or only sugar, still return the item with the other field null."
            )),
            HumanMessage(content=(
                "Analyze this pasted text and return JSON in this exact shape: "
                "{\"source_type\":\"manual_text\",\"evidence_type\":\"nutrition_text|menu_text|ocr_text|mixed\","
                "\"brand\":string|null,\"items\":[...]}\n\n"
                f"source_type hint: {source_type or 'manual_text'}\n"
                f"text:\n{text}"
            )),
        ])
        parsed = _parse_json_object(response.content)
        items = normalize_image_items(parsed.get("items", []), parsed.get("brand"))
        return {
            "text_agent_configured": True,
            "source_type": parsed.get("source_type") or source_type or "manual_text",
            "evidence_type": parsed.get("evidence_type") or "mixed",
            "brand": parsed.get("brand"),
            "items": items,
        }
    except Exception:
        return None


def _fallback_text_items(text: str) -> list[dict]:
    table_items = _parse_markdown_table_items(text)
    if table_items:
        return _dedupe_text_items(table_items)

    delimited_items = _parse_delimited_table_items(text)
    if delimited_items:
        return _dedupe_text_items(delimited_items)

    chunks = _split_text_evidence_chunks(text)
    items = []
    for chunk in chunks:
        candidate = parse_candidate_from_text(chunk)
        extracted = extract_nutrition_fields(chunk)
        if not candidate.get("name") and not _has_minimum_nutrition(extracted):
            continue
        name = candidate.get("name") or _extract_explicit_name(chunk)
        if not name:
            continue
        item = {
            "brand": candidate.get("brand") or infer_brand(chunk),
            "name": name,
            "type": candidate.get("type") or infer_type(name),
            **extracted,
            "volume_note": _extract_volume_note(chunk),
            "raw_evidence": chunk.strip(),
        }
        items.append(item)
    return _dedupe_text_items(items)


def _parse_markdown_table_items(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return []

    default_brand = infer_brand(text) or _extract_brand_from_title(text)
    default_volume = _extract_default_volume(text)
    items = []
    header = None
    indexes = None

    for line in lines:
        cells = _split_markdown_row(line)
        if len(cells) < 2 or _is_markdown_separator_row(cells):
            continue
        if header is None:
            header = cells
            indexes = _markdown_table_indexes(header)
            continue
        if not indexes or indexes["name"] is None:
            continue

        name_cell = cells[indexes["name"]] if indexes["name"] < len(cells) else ""
        caffeine_cell = cells[indexes["caffeine"]] if indexes["caffeine"] is not None and indexes["caffeine"] < len(cells) else ""
        sugar_cell = cells[indexes["sugar"]] if indexes["sugar"] is not None and indexes["sugar"] < len(cells) else ""
        volume_cell = cells[indexes["volume"]] if indexes["volume"] is not None and indexes["volume"] < len(cells) else ""

        caffeine = _extract_representative_number(caffeine_cell, ["mg", "毫克"])
        sugar = _extract_representative_number(sugar_cell, ["g", "克"])
        volume = _extract_representative_number(volume_cell, ["ml", "毫升"]) or default_volume

        if caffeine is None and sugar is None:
            continue

        for name in _split_product_names(name_cell):
            items.append({
                "brand": default_brand,
                "name": name,
                "type": infer_type(name),
                "volume": volume,
                "caffeine": caffeine,
                "sugar": sugar,
                "volume_note": "per_serving" if volume else None,
                "raw_evidence": _clean_markdown_text(" | ".join([name_cell, caffeine_cell, sugar_cell])),
            })
    return items


def _parse_delimited_table_items(text: str) -> list[dict]:
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip()]
    header_index = None
    header = None
    indexes = None

    for index, line in enumerate(lines):
        if "\t" not in line:
            continue
        cells = [_clean_markdown_text(cell) for cell in line.split("\t")]
        maybe_indexes = _markdown_table_indexes(cells)
        if maybe_indexes["name"] is not None and (maybe_indexes["caffeine"] is not None or maybe_indexes["sugar"] is not None):
            header_index = index
            header = cells
            indexes = maybe_indexes
            break

    if header_index is None or header is None or indexes is None:
        return []

    column_count = len(header)
    default_brand = infer_brand(text) or _extract_brand_from_title(text)
    default_volume = _extract_default_volume(text)
    rows = _read_wrapped_delimited_rows(lines[header_index + 1:], column_count)
    items = []

    for cells in rows:
        name_cell = cells[indexes["name"]] if indexes["name"] < len(cells) else ""
        caffeine_cell = cells[indexes["caffeine"]] if indexes["caffeine"] is not None and indexes["caffeine"] < len(cells) else ""
        sugar_cell = cells[indexes["sugar"]] if indexes["sugar"] is not None and indexes["sugar"] < len(cells) else ""
        volume_cell = cells[indexes["volume"]] if indexes["volume"] is not None and indexes["volume"] < len(cells) else ""

        caffeine = _extract_representative_number(caffeine_cell, ["mg", "毫克"])
        sugar = _extract_representative_number(sugar_cell, ["g", "克"])
        volume = _extract_representative_number(volume_cell, ["ml", "毫升"]) or default_volume
        if caffeine is None and sugar is None:
            continue

        for name in _split_product_names(name_cell):
            items.append({
                "brand": default_brand,
                "name": name,
                "type": infer_type(name),
                "volume": volume,
                "caffeine": caffeine,
                "sugar": sugar,
                "volume_note": "per_serving" if volume else None,
                "raw_evidence": _clean_markdown_text(" | ".join([name_cell, caffeine_cell, sugar_cell])),
            })
    return items


def _read_wrapped_delimited_rows(lines: list[str], column_count: int) -> list[list[str]]:
    rows = []
    buffer = ""
    for line in lines:
        candidate = f"{buffer} {line}".strip() if buffer else line
        cells = [_clean_markdown_text(cell) for cell in candidate.split("\t")]
        if len(cells) >= column_count:
            rows.append(cells[:column_count])
            overflow = "\t".join(cells[column_count:]).strip()
            buffer = overflow
        else:
            buffer = candidate
    if buffer:
        cells = [_clean_markdown_text(cell) for cell in buffer.split("\t")]
        if len(cells) >= 2:
            rows.append(cells)
    return rows


def _split_markdown_row(line: str) -> list[str]:
    return [_clean_markdown_text(cell) for cell in line.strip().strip("|").split("|")]


def _clean_markdown_text(value: str) -> str:
    text = re.sub(r"<br\s*/?>", " ", str(value), flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def _is_markdown_separator_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells if cell.strip())


def _markdown_table_indexes(header: list[str]) -> dict:
    indexes = {"name": None, "caffeine": None, "sugar": None, "volume": None}
    for index, cell in enumerate(header):
        normalized = cell.lower()
        if indexes["name"] is None and any(token in normalized for token in ["饮品", "名字", "名称", "品类", "name"]):
            indexes["name"] = index
        if indexes["caffeine"] is None and any(token in normalized for token in ["咖啡因", "caffeine"]):
            indexes["caffeine"] = index
        if indexes["sugar"] is None and any(token in normalized for token in ["糖分", "糖含量", "含糖", "sugar"]):
            indexes["sugar"] = index
        if indexes["volume"] is None and any(token in normalized for token in ["容量", "规格", "volume"]):
            indexes["volume"] = index
    return indexes


def _split_product_names(value: str) -> list[str]:
    cleaned = re.sub(r"\([^)]*\)|（[^）]*）", " ", _clean_markdown_text(value))
    names = [part.strip(" /、，,") for part in re.split(r"\s*/\s*|、", cleaned) if part.strip(" /、，,")]
    return names or ([cleaned.strip()] if cleaned.strip() else [])


def _extract_representative_number(text: str, units: list[str]) -> float | None:
    cleaned = _clean_markdown_text(text).replace(",", "")
    unit_pattern = "|".join(re.escape(unit) for unit in units)
    average_pattern = rf"(?:平均值|均值|约|大约|best|avg|average)[^\d]{{0,8}}(\d+(?:\.\d+)?)\s*(?:{unit_pattern})?"
    average = re.search(average_pattern, cleaned, flags=re.I)
    if average:
        return float(average.group(1))

    range_pattern = rf"(\d+(?:\.\d+)?)\s*[-–—~至到]\s*(\d+(?:\.\d+)?)\s*(?:{unit_pattern})?"
    range_match = re.search(range_pattern, cleaned, flags=re.I)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return round((low + high) / 2, 1)

    unit_number = re.search(rf"(\d+(?:\.\d+)?)\s*(?:{unit_pattern})", cleaned, flags=re.I)
    if unit_number:
        return float(unit_number.group(1))
    plain_number = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    return float(plain_number.group(1)) if plain_number else None


def _extract_default_volume(text: str) -> float | None:
    patterns = [
        r"(?:基于|默认|大杯|每杯)[^。\n]{0,20}?约?\s*(\d+(?:\.\d+)?)\s*(?:ml|毫升)",
        r"(\d+(?:\.\d+)?)\s*(?:ml|毫升)[^。\n]{0,12}?(?:每杯|大杯)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return float(match.group(1))
    return None


def _extract_brand_from_title(text: str) -> str | None:
    match = re.search(r"([\u4e00-\u9fffA-Za-z0-9]+(?:咖啡|茶|茶姬|冰城))常见", text)
    return match.group(1) if match else None


def _split_text_evidence_chunks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    if len(lines) > 1:
        chunks = []
        buffer = []
        for line in lines:
            buffer.append(line)
            if _has_minimum_nutrition(extract_nutrition_fields(" ".join(buffer))):
                chunks.append(" ".join(buffer))
                buffer = []
        if buffer:
            chunks.append(" ".join(buffer))
        return chunks
    parts = re.split(r"[；;]\s*", normalized)
    return [part.strip() for part in parts if part.strip()] or [text.strip()]


def _extract_explicit_name(text: str) -> str:
    match = re.search(r"(?:饮品名称|产品名称|候选饮品|名称|name)\s*:?\s*([^,，;；\n]+)", text, flags=re.I)
    return match.group(1).strip() if match else ""


def _extract_volume_note(text: str) -> str | None:
    if re.search(r"每\s*100\s*ml|/100\s*ml|per\s*100\s*ml", text, flags=re.I):
        return "per_100ml"
    if re.search(r"每杯|per\s*serving|每份", text, flags=re.I):
        return "per_serving"
    return None


def _dedupe_text_items(items: list[dict]) -> list[dict]:
    merged = {}
    for item in items:
        key = (item.get("brand") or "", item.get("name") or "")
        existing = merged.get(key)
        if not existing:
            merged[key] = item
            continue
        for field in ["volume", "caffeine", "sugar", "volume_note"]:
            if existing.get(field) is None and item.get(field) is not None:
                existing[field] = item.get(field)
        existing["raw_evidence"] = " ".join(filter(None, [existing.get("raw_evidence"), item.get("raw_evidence")]))
    return list(merged.values())


def _parse_json_object(content: str) -> dict:
    import json

    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        text = match.group(0)
    return json.loads(text)


def _has_minimum_nutrition(extracted: dict) -> bool:
    return extracted.get("caffeine") is not None or extracted.get("sugar") is not None
