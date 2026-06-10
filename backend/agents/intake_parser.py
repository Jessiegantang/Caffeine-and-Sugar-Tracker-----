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
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_fields: List[str] = Field(default_factory=list)
    follow_up: str | None = Field(default=None, description="Question to ask when fields are missing.")


SUGAR_ALIASES = [
    ("none", ["无糖", "不加糖", "零糖", "0糖", "不另外加糖", "鏃犵硸", "涓嶅姞绯?", "闆剁硸", "0绯?", "涓嶅彟澶栧姞绯?"]),
    ("three", ["三分糖", "3分糖", "少糖", "涓夊垎绯?", "3鍒嗙硸", "灏戠硸"]),
    ("half", ["半糖", "五分糖", "5分糖", "鍗婄硸", "浜斿垎绯?", "5鍒嗙硸"]),
    ("seven", ["七分糖", "7分糖", "涓冨垎绯?", "7鍒嗙硸"]),
    ("full", ["全糖", "正常糖", "满糖", "鍏ㄧ硸", "姝ｅ父绯?", "婊＄硸"]),
]

KNOWN_BRANDS = [
    "瑞幸咖啡", "瑞幸", "库迪咖啡", "库迪", "星巴克", "喜茶", "奈雪", "蜜雪冰城",
    "霸王茶姬", "茶百道", "沪上阿姨", "古茗", "一点点", "可口可乐", "百事可乐",
    "鐟炲垢鍜栧暋", "鐟炲垢", "搴撹开鍜栧暋", "搴撹开", "鏄熷反鍏?", "鍠滆尪", "濂堥洩", "铚滈洩鍐板煄",
    "闇哥帇鑼跺К", "鑼剁櫨閬?", "娌笂闃垮Ж", "鍙よ寳", "涓€鐐圭偣", "鍙彛鍙箰", "鐧句簨鍙箰",
]

SIZE_ALIASES = [
    (250, ["小杯", "小瓶", "灏忔澂", "灏忕摱"]),
    (330, ["听装", "罐装", "一罐", "鍚", "缃愯", "涓€缃?"]),
    (350, ["中杯", "中瓶", "涓澂", "涓摱"]),
    (500, ["大杯", "大瓶", "标准杯", "一杯", "澶ф澂", "澶х摱", "鏍囧噯鏉?", "涓€鏉?"]),
    (650, ["超大杯", "特大杯", "瓒呭ぇ鏉?", "鐗瑰ぇ鏉?"]),
]


def _infer_intake_type(text: str, name: str | None) -> str:
    source = f"{text} {name or ''}"
    if any(word in source for word in ["奶茶", "拿铁", "生椰", "厚乳", "牛乳", "鲜奶", "濂惰尪", "鎷块搧", "鐢熸ぐ", "鍘氫钩", "鐗涗钩", "椴滃ザ"]):
        return "milktea" if "咖啡" not in source and "拿铁" not in source and "鍜栧暋" not in source and "鎷块搧" not in source else "coffee"
    if any(word in source for word in ["咖啡", "拿铁", "美式", "摩卡", "冷萃", "espresso", "latte", "鍜栧暋", "鎷块搧", "缇庡紡", "鎽╁崱", "鍐疯悆"]):
        return "coffee"
    if any(word in source for word in ["果茶", "柠檬茶", "水果茶", "杨枝甘露", "鏋滆尪", "鏌犳鑼?", "姘存灉鑼?", "鏉ㄦ灊鐢橀湶"]):
        return "fruittea"
    if any(word in source for word in ["茶", "乌龙", "绿茶", "红茶", "鑼?", "涔岄緳", "缁胯尪", "绾㈣尪"]):
        return "tea"
    if any(word in source for word in ["可乐", "汽水", "苏打", "鍙箰", "姹芥按", "鑻忔墦"]):
        return "soda"
    if any(word in source for word in ["啤酒", "鸡尾酒", "酒", "鍟ら厭", "楦″熬閰?", "閰?"]):
        return "alcohol"
    return "coffee"


def _infer_volume(text: str) -> int | None:
    match = re.search(r"(\d{2,4})\s*(?:ml|毫升|姣崌|mL|ML)", text)
    if match:
        return int(match.group(1))
    for volume, aliases in SIZE_ALIASES:
        if any(alias in text for alias in aliases):
            return volume
    return None


def _infer_sugar(text: str) -> str | None:
    for value, aliases in SUGAR_ALIASES:
        if any(alias in text for alias in aliases):
            return value
    return None


def _infer_time(text: str) -> str:
    match = re.search(r"(\d{1,2})[:锛氱偣](\d{1,2})?", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    if any(word in text for word in ["刚刚", "刚才", "现在", "刚喝", "刚买", "鍒氬垰", "鍒氭墠", "鐜板湪", "鍒氬枬", "鍒氫拱"]):
        return "now"
    if "下午" in text or "涓嬪崍" in text:
        return "afternoon"
    if "上午" in text or "涓婂崍" in text:
        return "morning"
    if "晚上" in text or "鏅氫笂" in text:
        return "evening"
    return "now"


def _infer_brand(text: str) -> str | None:
    for brand in KNOWN_BRANDS:
        if brand in text:
            if brand in ["瑞幸", "鐟炲垢"]:
                return "瑞幸咖啡" if brand == "瑞幸" else "鐟炲垢鍜栧暋"
            if brand in ["库迪", "搴撹开"]:
                return "库迪咖啡" if brand == "库迪" else "搴撹开鍜栧暋"
            return brand
    return None


def _infer_name(text: str, brand: str | None) -> str | None:
    cleaned = text
    for token in ["我", "刚刚", "刚才", "刚", "喝了", "喝", "买了", "买", "一杯", "一瓶", "一罐", "了", "鎴?", "鍒氬垰", "鍒氭墠", "鍒?", "鍠濅簡", "鍠?", "涔颁簡", "涔?", "涓€鏉?", "涓€鐡?", "涓€缃?", "浜?"]:
        cleaned = cleaned.replace(token, " ")
    if brand:
        cleaned = cleaned.replace(brand, " ")
        if brand == "瑞幸咖啡":
            cleaned = cleaned.replace("瑞幸", " ")
        if brand == "库迪咖啡":
            cleaned = cleaned.replace("库迪", " ")
        if brand == "鐟炲垢鍜栧暋":
            cleaned = cleaned.replace("鐟炲垢", " ")
        if brand == "搴撹开鍜栧暋":
            cleaned = cleaned.replace("搴撹开", " ")
    for _, aliases in SUGAR_ALIASES:
        for alias in aliases:
            cleaned = cleaned.replace(alias, " ")
    for _, aliases in SIZE_ALIASES:
        for alias in aliases:
            cleaned = cleaned.replace(alias, " ")
    cleaned = re.sub(r"\d{2,4}\s*(?:ml|毫升|姣崌|mL|ML)", " ", cleaned)
    parts = [p.strip(" ，。；;、锛?銆?锛?锛?") for p in re.split(r"[,，。；;、锛屻€傦紱;銆乗s]+", cleaned) if p.strip(" ，。；;、锛?銆?锛?锛?")]
    candidates = [p for p in parts if len(p) >= 2 and p not in ["今天", "下午", "上午", "晚上", "现在", "浠婂ぉ", "涓嬪崍", "涓婂崍", "鏅氫笂", "鐜板湪"]]
    if not candidates:
        return None
    return max(candidates, key=len)


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
        return "浣犲枬鐨勬槸涓澂銆佸ぇ鏉紝杩樻槸鍙互鍛婅瘔鎴戝ぇ姒傚灏?ml锛?"
    if "sugar" in missing_fields:
        return "杩欐澂鐨勭敎搴︽槸鏃犵硸銆佷笁鍒嗙硸銆佸崐绯栥€佷竷鍒嗙硸杩樻槸鍏ㄧ硸锛?"
    if "name" in missing_fields:
        return "杩欐澂楗搧鍙粈涔堝悕瀛楋紵"
    return "鎴戣繕闇€瑕佷竴鐐逛俊鎭墠鑳藉府浣犺褰曡繖鏉ギ鍝併€?"


def _parse_intake_locally(user_message: str) -> dict:
    text = user_message.strip()
    log_keywords = ["喝", "买", "来一杯", "记录", "加一条", "点了", "刚刚", "刚才", "鍠?", "涔?", "鏉ヤ竴鏉?", "璁板綍", "鍔犱竴鏉?", "鐐逛簡", "鍒氬垰", "鍒氭墠"]
    intent = "log_drink" if any(keyword in text for keyword in log_keywords) else "ask_advice"
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
        "confidence": 0.72 if intent == "log_drink" else 0.55,
    }
    result["missing_fields"] = _build_missing_fields(result) if intent == "log_drink" else []
    result["follow_up"] = _build_follow_up(result["missing_fields"])
    if result["missing_fields"]:
        result["confidence"] = min(result["confidence"], 0.62)
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
                "Type must be one of coffee, milktea, tea, fruittea, soda, alcohol.",
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
        if result["missing_fields"]:
            result["confidence"] = min(float(result.get("confidence") or 0.7), 0.68)
        return result
    except Exception as e:
        print(f"[Intake Parser] Falling back to local parser: {e}", flush=True)
        return local_result


def parse_intake(user_message: str) -> dict:
    return parse_intake_message(user_message)
