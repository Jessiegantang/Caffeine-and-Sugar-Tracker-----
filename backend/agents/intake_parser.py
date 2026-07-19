import re
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .llm_config import llm, llm_enabled


class IntakeParseResult(BaseModel):
    intent: str = Field(description="User intent, such as log_drink or ask_advice.")
    brand: str | None = Field(default=None, description="Drink brand.")
    name: str | None = Field(default=None, description="Drink name.")
    type: str | None = Field(default=None, description="Drink type.")
    volume: int | None = Field(default=None, description="Volume in ml.")
    sugar: str | None = Field(default=None, description="Sugar level: none, three, half, seven, full, unknown.")
    time: str | None = Field(default=None, description="Drink time, now or HH:MM.")
    missing_fields: List[str] = Field(default_factory=list)
    follow_up: str | None = Field(default=None, description="Question to ask when fields are missing.")


SUGAR_ALIASES = [
    ("none", ["\u65e0\u7cd6", "\u4e0d\u52a0\u7cd6", "\u96f6\u7cd6", "0\u7cd6", "\u4e0d\u53e6\u5916\u52a0\u7cd6", "no sugar", "sugar free"]),
    ("three", ["\u4e09\u5206\u7cd6", "3\u5206\u7cd6", "\u5fae\u7cd6", "\u4e09\u5206\u751c", "30%\u7cd6"]),
    ("half", ["\u534a\u7cd6", "\u4e94\u5206\u7cd6", "5\u5206\u7cd6", "50%\u7cd6"]),
    ("seven", ["\u4e03\u5206\u7cd6", "7\u5206\u7cd6", "\u5c11\u7cd6", "70%\u7cd6"]),
    ("full", ["\u5168\u7cd6", "\u6b63\u5e38\u7cd6", "\u6807\u51c6\u7cd6", "100%\u7cd6"]),
]

KNOWN_BRAND_ALIASES = [
    ("\u745e\u5e78\u5496\u5561", ["\u745e\u5e78\u5496\u5561", "\u745e\u5e78", "luckin"]),
    ("\u5e93\u8fea\u5496\u5561", ["\u5e93\u8fea\u5496\u5561", "\u5e93\u8fea", "cotti"]),
    ("\u661f\u5df4\u514b", ["\u661f\u5df4\u514b", "starbucks"]),
    ("Manner Coffee", ["manner coffee", "manner"]),
    ("Tims", ["tims", "\u5929\u597d\u5496\u5561"]),
    ("Costa", ["costa"]),
    ("\u9738\u738b\u8336\u59ec", ["\u9738\u738b\u8336\u59ec"]),
    ("\u8336\u767e\u9053", ["\u8336\u767e\u9053"]),
    ("\u6caa\u4e0a\u963f\u59e8", ["\u6caa\u4e0a\u963f\u59e8"]),
    ("\u53e4\u8317", ["\u53e4\u8317"]),
    ("\u4e00\u70b9\u70b9", ["\u4e00\u70b9\u70b9", "1\u70b9\u70b9"]),
    ("\u559c\u8336", ["\u559c\u8336"]),
    ("\u5948\u96ea\u7684\u8336", ["\u5948\u96ea\u7684\u8336", "\u5948\u96ea"]),
    ("\u871c\u96ea\u51b0\u57ce", ["\u871c\u96ea\u51b0\u57ce", "\u871c\u96ea"]),
    ("\u53ef\u53e3\u53ef\u4e50", ["\u53ef\u53e3\u53ef\u4e50", "\u53ef\u4e50", "coca cola", "coke"]),
    ("\u767e\u4e8b\u53ef\u4e50", ["\u767e\u4e8b\u53ef\u4e50", "pepsi"]),
    ("\u4e09\u5206\u4ed6", ["\u4e09\u5206\u4ed6"]),
    ("\u8309\u8389\u5976\u767d", ["\u8309\u8389\u5976\u767d"]),
]

SIZE_ALIASES = [
    (250, ["\u5c0f\u676f", "\u5c0f\u74f6"]),
    (330, ["\u4e2d\u676f", "\u4e2d\u74f6", "\u7f50"]),
    (350, ["\u6807\u51c6\u676f"]),
    (500, ["\u5927\u676f", "\u5927\u74f6", "\u4e00\u676f"]),
    (650, ["\u8d85\u5927\u676f", "\u5de8\u676f"]),
]

LOG_KEYWORDS = ["\u559d", "\u4e70", "\u6765\u4e00\u676f", "\u8bb0\u5f55", "\u8bb0\u4e00\u4e0b", "\u5e2e\u6211\u8bb0\u4e00\u4e0b", "\u52a0\u4e00\u6761", "\u70b9\u4e86", "\u521a\u521a", "\u521a\u624d"]
ADVICE_KEYWORDS = [
    "\u8fd8\u80fd\u559d", "\u8fd8\u53ef\u4ee5", "\u53ef\u4ee5\u559d", "\u80fd\u559d", "\u5efa\u8bae", "\u63a8\u8350",
    "\u9002\u5408", "\u5065\u5eb7\u5417", "\u600e\u4e48\u529e", "\u9884\u7b97", "\u989d\u5ea6", "\u9ad8\u4e0d\u9ad8", "\u662f\u4e0d\u662f",
    "\u5417", "?",
]
SYMPTOM_KEYWORDS = [
    "\u5e72\u5455", "\u6076\u5fc3", "\u60f3\u5410", "\u53cd\u80c3", "\u80c3\u4e0d\u8212\u670d", "\u80c3\u75bc",
    "\u5fc3\u614c", "\u5934\u6655", "\u96be\u53d7", "\u4e0d\u8212\u670d", "\u62c9\u809a\u5b50", "\u809a\u5b50\u75bc",
]
FILLER_TOKENS = ["\u90a3\u4e2a", "\u8fd9\u4e2a", "\u4e00\u4e2a", "\u7684"]
DRINK_SUFFIXES = [
    "\u6768\u679d\u7518\u9732", "\u751f\u6930\u62ff\u94c1", "\u6930\u5b50\u62ff\u94c1", "\u62ff\u94c1",
    "\u7f8e\u5f0f", "\u5496\u5561", "\u5976\u8336", "\u679c\u8336", "\u67e0\u6aac\u8336",
    "\u8336", "\u53ef\u4e50", "\u6c7d\u6c34", "\u7518\u9732", "\u51b7\u8403",
    "latte", "americano", "coffee",
]


def _infer_intake_type(text: str, name: str | None) -> str:
    source = f"{text} {name or ''}".lower()
    if any(word in source for word in ["\u5496\u5561", "\u7f8e\u5f0f", "\u62ff\u94c1", "\u51b7\u8403", "\u6d53\u7f29", "espresso", "latte", "americano"]):
        return "coffee"
    if any(word in source for word in ["\u5976\u8336", "\u6ce2\u6ce2", "\u73cd\u73e0", "\u6930\u6930", "\u6768\u679d\u7518\u9732", "\u539a\u4e73\u8336"]):
        return "milktea"
    if any(word in source for word in ["\u679c\u8336", "\u6c34\u679c\u8336", "\u67e0\u6aac\u8336", "\u6a59", "\u6851\u845a", "\u679c\u6c41"]):
        return "fruittea"
    if any(word in source for word in ["\u8336", "\u4e4c\u9f99", "\u7eff\u8336", "\u7ea2\u8336", "\u666e\u6d31"]):
        return "tea"
    if any(word in source for word in ["\u53ef\u4e50", "\u6c7d\u6c34", "\u82cf\u6253", "\u6c14\u6ce1\u6c34", "soda"]):
        return "soda"
    return "coffee"


def _infer_volume(text: str) -> int | None:
    match = re.search(r"(\d{2,4})\s*(?:ml|mL|ML|\u6beb\u5347)", text)
    if match:
        return int(match.group(1))
    size_aliases = [
        (len(alias), volume, alias)
        for volume, aliases in SIZE_ALIASES
        for alias in aliases
    ]
    for _, volume, alias in sorted(size_aliases, reverse=True):
        if alias in text:
            return volume
    return None


def _infer_sugar(text: str) -> str | None:
    lowered = text.lower()
    matches: list[tuple[int, str]] = []
    for value, aliases in SUGAR_ALIASES:
        for alias in aliases:
            for match in re.finditer(re.escape(alias.lower()), lowered):
                if _is_negated_sugar(lowered, match.start(), alias.lower()):
                    continue
                matches.append((match.start(), value))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[-1][1]


def _is_negated_sugar(text: str, start: int, alias: str) -> bool:
    if alias.startswith("\u4e0d"):
        return False
    prefix = text[max(0, start - 4):start]
    return prefix.endswith("\u4e0d\u662f") or prefix.endswith("\u4e0d\u8981") or prefix.endswith("\u975e")


def _infer_time(text: str) -> str:
    match = re.search(r"(\d{1,2})[:\uff1a\u70b9](\d{1,2})?", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    if any(word in text for word in ["\u521a\u521a", "\u521a\u624d", "\u73b0\u5728", "\u6b64\u523b"]):
        return "now"
    if "\u4e0b\u5348" in text:
        return "afternoon"
    if "\u4e0a\u5348" in text or "\u65e9\u4e0a" in text:
        return "morning"
    if "\u665a\u4e0a" in text:
        return "evening"
    return "now"


def _has_drink_signal(text: str) -> bool:
    lowered = text.lower()
    has_brand = any(alias.lower() in lowered for _, aliases in KNOWN_BRAND_ALIASES for alias in aliases)
    has_suffix = any(suffix.lower() in lowered for suffix in DRINK_SUFFIXES)
    has_volume = _infer_volume(text) is not None
    has_sugar = _infer_sugar(text) is not None
    return has_suffix and (has_brand or has_volume or has_sugar)


def _infer_brand(text: str) -> str | None:
    lowered = text.lower()
    matches: list[tuple[int, str]] = []
    for brand, aliases in KNOWN_BRAND_ALIASES:
        for alias in aliases:
            alias_lower = alias.lower()
            if alias_lower in lowered:
                matches.append((len(alias_lower), brand))
    if matches:
        matches.sort(reverse=True)
        return matches[0][1]
    return None


def _infer_name(text: str, brand: str | None) -> str | None:
    cleaned = _remove_known_context(text, brand)
    suffix_name = _extract_name_by_suffix(cleaned)
    if suffix_name:
        return _normalize_extracted_name(suffix_name)

    parts = [p.strip(" ,.\uff0c\u3002!\uff01?\uff1f\u3001") for p in re.split(r"[\s,\uff0c\u3002!\uff01?\uff1f\u3001]+", cleaned)]
    candidates = [p for p in parts if len(p) >= 2 and not p.isdigit()]
    if not candidates and brand in {"可口可乐", "百事可乐"} and "可乐" in text:
        return "可乐"
    if not candidates and brand == "Tims" and "咖啡" in text:
        return "咖啡"
    if not candidates:
        return None
    return _normalize_extracted_name(max(candidates, key=len))


def _normalize_extracted_name(name: str) -> str:
    if name.startswith("茶柠檬茶"):
        return "柠檬茶"
    return name


def _remove_known_context(text: str, brand: str | None) -> str:
    cleaned = text
    remove_tokens = [
        "\u6211", "\u521a\u559d\u4e86\u70b9", "\u559d\u4e86\u70b9", "\u521a\u559d\u4e86", "\u521a\u559d", "\u559d\u4e86", "\u4e70\u4e86", "\u70b9\u4e86",
        "\u6765\u4e00\u676f", "\u8bb0\u5f55", "\u52a0\u4e00\u6761", "\u4e00\u676f", "\u4e00\u74f6",
        "\u4eca\u5929", "\u73b0\u5728", "\u521a\u521a", "\u521a\u624d", "\u4e0a\u5348", "\u4e0b\u5348", "\u665a\u4e0a",
    ]
    for token in remove_tokens:
        cleaned = cleaned.replace(token, " ")
    for token in FILLER_TOKENS:
        cleaned = cleaned.replace(token, " ")
    if brand:
        cleaned = cleaned.replace(brand, " ")
    for _, aliases in KNOWN_BRAND_ALIASES:
        for alias in aliases:
            cleaned = re.sub(re.escape(alias), " ", cleaned, flags=re.IGNORECASE)
    for _, aliases in SUGAR_ALIASES:
        for alias in aliases:
            cleaned = re.sub(re.escape(alias), " ", cleaned, flags=re.IGNORECASE)
    for _, aliases in SIZE_ALIASES:
        for alias in aliases:
            cleaned = cleaned.replace(alias, " ")
    cleaned = re.sub(r"\d{2,4}\s*(?:ml|mL|ML|\u6beb\u5347)", " ", cleaned)
    return cleaned


def _extract_name_by_suffix(text: str) -> str | None:
    best: str | None = None
    for suffix in DRINK_SUFFIXES:
        pattern = rf"[\u4e00-\u9fffA-Za-z0-9]{{0,12}}{re.escape(suffix)}"
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            candidate = match.group(0).strip(" ,.\uff0c\u3002!\uff01?\uff1f\u3001")
            if not candidate:
                continue
            if best is None or len(candidate) > len(best):
                best = candidate
    return best


def _build_missing_fields(result: dict) -> list[str]:
    missing = []
    for field_name in ["name", "volume", "sugar"]:
        if result.get(field_name) in [None, "", "unknown"]:
            missing.append(field_name)
    return missing


def _build_follow_up(missing_fields: list[str]) -> str | None:
    if not missing_fields:
        return None
    if "volume" in missing_fields:
        return "\u4f60\u559d\u7684\u662f\u4e2d\u676f\u3001\u5927\u676f\uff0c\u8fd8\u662f\u53ef\u4ee5\u544a\u8bc9\u6211\u5927\u6982\u591a\u5c11 ml\uff1f"
    if "sugar" in missing_fields:
        return "\u8fd9\u676f\u751c\u5ea6\u662f\u65e0\u7cd6\u3001\u4e09\u5206\u7cd6\u3001\u534a\u7cd6\u3001\u4e03\u5206\u7cd6\u8fd8\u662f\u5168\u7cd6\uff1f"
    if "name" in missing_fields:
        return "\u8fd9\u676f\u996e\u54c1\u53eb\u4ec0\u4e48\u540d\u5b57\uff1f"
    return "\u6211\u8fd8\u9700\u8981\u4e00\u70b9\u4fe1\u606f\uff0c\u624d\u80fd\u5e2e\u4f60\u8bb0\u5f55\u8fd9\u676f\u996e\u54c1\u3002"


def _parse_intake_locally(user_message: str) -> dict:
    text = user_message.strip()
    has_explicit_log = any(keyword in text for keyword in LOG_KEYWORDS)
    has_advice_marker = any(keyword in text for keyword in ADVICE_KEYWORDS)
    if has_advice_marker and not any(keyword in text for keyword in ["\u8bb0\u5f55", "\u52a0\u4e00\u6761", "\u8bb0\u4e00\u4e0b", "\u5e2e\u6211\u8bb0\u4e00\u4e0b"]):
        intent = "ask_advice"
    elif has_explicit_log or _has_drink_signal(text):
        intent = "log_drink"
    else:
        intent = "ask_advice"
    if any(keyword in text for keyword in SYMPTOM_KEYWORDS) and not any(keyword in text for keyword in ["\u8bb0\u5f55", "\u52a0\u4e00\u6761"]):
        intent = "ask_advice"
    if intent != "log_drink" and any(keyword in text for keyword in ADVICE_KEYWORDS):
        intent = "ask_advice"
    brand = _infer_brand(text)
    name = _infer_name(text, brand) if intent == "log_drink" else None
    result = {
        "intent": intent,
        "brand": brand,
        "name": name,
        "type": _infer_intake_type(text, name) if intent == "log_drink" else None,
        "volume": _infer_volume(text) if intent == "log_drink" else None,
        "sugar": _infer_sugar(text) if intent == "log_drink" else None,
        "time": _infer_time(text) if intent == "log_drink" else None,
    }
    result["missing_fields"] = _build_missing_fields(result) if intent == "log_drink" else []
    result["follow_up"] = _build_follow_up(result["missing_fields"])
    return result


def parse_intake_message(user_message: str) -> dict:
    local_result = _parse_intake_locally(user_message)
    if local_result["intent"] != "log_drink":
        return local_result
    if not local_result.get("missing_fields"):
        return local_result
    if not llm_enabled():
        return local_result

    try:
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are DrinkMind Intake Parser. Extract a drink logging intent from Chinese natural language. "
                "Return structured fields only. Do not invent unknown required fields. "
                "Sugar must be one of none, three, half, seven, full, unknown. "
                "Type must be one of coffee, milktea, tea, fruittea, soda.",
            ),
            ("user", "{message}"),
        ])
        structured_llm = llm.with_structured_output(IntakeParseResult, method="function_calling")
        parsed = (prompt | structured_llm).invoke({"message": user_message})
        result = parsed.dict()
        for key, value in local_result.items():
            if result.get(key) in [None, "", "unknown"] and value not in [None, "", "unknown"]:
                result[key] = value
        result["intent"] = result.get("intent") or "log_drink"
        result["missing_fields"] = _build_missing_fields(result)
        result["follow_up"] = _build_follow_up(result["missing_fields"])
        return result
    except Exception as e:
        print(f"[Intake Parser] Falling back to local parser: {e}", flush=True)
        return local_result


def parse_intake(user_message: str) -> dict:
    return parse_intake_message(user_message)
