import os
import json
import re
import uuid
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from dotenv import load_dotenv

from database import SessionLocal, DrinkLog, DrinkKnowledge
from local_estimator import estimate_nutrition

load_dotenv()

base_url = os.getenv("BASE_URL")
api_key = os.getenv("OPENAI_API_KEY", "dummy_key_if_none")
model_name = os.getenv("MODEL_NAME", "gpt-3.5-turbo")


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"true", "1", "yes"}


def _llm_enabled() -> bool:
    if _env_truthy("DRINKMIND_OFFLINE"):
        return False
    current_api_key = os.getenv("OPENAI_API_KEY", "")
    if not current_api_key or current_api_key.startswith("dummy_"):
        return False
    return _env_truthy("ENABLE_LLM")

if base_url:
    llm = ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url)
    embeddings = OpenAIEmbeddings(model="text-embedding-v3", api_key=api_key, base_url=base_url, check_embedding_ctx_length=False)
else:
    llm = ChatOpenAI(model=model_name, api_key=api_key)
    embeddings = OpenAIEmbeddings(model="text-embedding-v3", api_key=api_key, check_embedding_ctx_length=False)

chroma_path = os.path.join(os.path.dirname(__file__), "chroma_db")
if os.path.exists(chroma_path):
    vectorstore = Chroma(persist_directory=chroma_path, embedding_function=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 1})
else:
    vectorstore = None
    retriever = None

from langchain_core.documents import Document

def sync_chroma_document(kb_id, data: dict):
    if not vectorstore: return
    delete_chroma_document(kb_id)
    content = f"品牌: {data.get('brand', '')}\n名称: {data.get('name', '')}\n杯型: {data.get('volume', 500)}ml\n咖啡因含量: {data.get('caffeine', 0)}mg\n糖分含量: {data.get('baseSugar', 0)}g"
    doc = Document(
        page_content=content,
        metadata={
            "id": kb_id,
            "brand": data.get("brand", ""),
            "name": data.get("name", ""),
            "caffeine": data.get("caffeine", 0),
            "sugar": data.get("baseSugar", 0),
            "source": data.get("source", "知识库"),
            "confidence": data.get("confidence", 0.9)
        }
    )
    vectorstore.add_documents([doc], ids=[kb_id])
    print(f"[Chroma Sync] Synced {kb_id} to ChromaDB")

def delete_chroma_document(kb_id):
    if not vectorstore: return
    try:
        vectorstore.delete(ids=[kb_id])
        print(f"[Chroma Sync] Deleted {kb_id} from ChromaDB")
    except Exception:
        pass


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
    ("none", ["无糖", "不加糖", "零糖", "0糖", "不另外加糖"]),
    ("three", ["三分糖", "3分糖", "少糖"]),
    ("half", ["半糖", "五分糖", "5分糖"]),
    ("seven", ["七分糖", "7分糖"]),
    ("full", ["全糖", "正常糖", "满糖"]),
]

KNOWN_BRANDS = [
    "瑞幸咖啡", "瑞幸", "库迪咖啡", "库迪", "星巴克", "喜茶", "奈雪", "蜜雪冰城",
    "霸王茶姬", "茶百道", "沪上阿姨", "古茗", "一点点", "可口可乐", "百事可乐"
]

BRAND_CANONICAL_KEYS = {
    "瑞幸咖啡": "luckin",
    "瑞幸": "luckin",
    "luckin coffee": "luckin",
    "luckin": "luckin",
    "库迪咖啡": "cotti",
    "库迪": "cotti",
    "cotti coffee": "cotti",
    "cotti": "cotti",
    "星巴克": "starbucks",
    "starbucks": "starbucks",
    "喜茶": "heytea",
    "heytea": "heytea",
    "奈雪": "nayuki",
    "奈雪的茶": "nayuki",
    "nayuki": "nayuki",
}

SIZE_ALIASES = [
    (250, ["小杯", "小瓶"]),
    (330, ["听装", "罐装", "一罐"]),
    (350, ["中杯", "中瓶"]),
    (500, ["大杯", "大瓶", "标准杯", "一杯"]),
    (650, ["超大杯", "特大杯"]),
]


def _infer_intake_type(text: str, name: str | None) -> str:
    source = f"{text} {name or ''}"
    if any(word in source for word in ["奶茶", "拿铁", "生椰", "厚乳", "牛乳", "鲜奶"]):
        return "milktea" if "咖啡" not in source and "拿铁" not in source else "coffee"
    if any(word in source for word in ["咖啡", "拿铁", "美式", "摩卡", "冷萃", "espresso", "latte"]):
        return "coffee"
    if any(word in source for word in ["果茶", "柠檬茶", "水果茶", "杨枝甘露"]):
        return "fruittea"
    if any(word in source for word in ["茶", "乌龙", "绿茶", "红茶"]):
        return "tea"
    if any(word in source for word in ["可乐", "汽水", "苏打"]):
        return "soda"
    if any(word in source for word in ["啤酒", "鸡尾酒", "酒"]):
        return "alcohol"
    return "coffee"


def _infer_volume(text: str) -> int | None:
    match = re.search(r"(\d{2,4})\s*(?:ml|毫升|mL|ML)", text)
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
    match = re.search(r"(\d{1,2})[:：点](\d{1,2})?", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    if any(word in text for word in ["刚刚", "刚才", "现在", "刚喝", "刚买"]):
        return "now"
    if "下午" in text:
        return "afternoon"
    if "上午" in text:
        return "morning"
    if "晚上" in text:
        return "evening"
    return "now"


def _infer_brand(text: str) -> str | None:
    for brand in KNOWN_BRANDS:
        if brand in text:
            if brand == "瑞幸":
                return "瑞幸咖啡"
            if brand == "库迪":
                return "库迪咖啡"
            return brand
    return None


def _infer_name(text: str, brand: str | None) -> str | None:
    cleaned = text
    for token in ["我", "刚刚", "刚才", "刚", "喝了", "喝", "买了", "买", "一杯", "一瓶", "一罐", "了"]:
        cleaned = cleaned.replace(token, " ")
    if brand:
        cleaned = cleaned.replace(brand, " ")
        if brand == "瑞幸咖啡":
            cleaned = cleaned.replace("瑞幸", " ")
        if brand == "库迪咖啡":
            cleaned = cleaned.replace("库迪", " ")
    for _, aliases in SUGAR_ALIASES:
        for alias in aliases:
            cleaned = cleaned.replace(alias, " ")
    for _, aliases in SIZE_ALIASES:
        for alias in aliases:
            cleaned = cleaned.replace(alias, " ")
    cleaned = re.sub(r"\d{2,4}\s*(?:ml|毫升|mL|ML)", " ", cleaned)
    parts = [p.strip(" ，,。.？?！!") for p in re.split(r"[,，。；;、\s]+", cleaned) if p.strip(" ，,。.？?！!")]
    candidates = [p for p in parts if len(p) >= 2 and p not in ["今天", "下午", "上午", "晚上", "现在"]]
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
        return "你喝的是中杯、大杯，还是可以告诉我大概多少 ml？"
    if "sugar" in missing_fields:
        return "这杯的甜度是无糖、三分糖、半糖、七分糖还是全糖？"
    if "name" in missing_fields:
        return "这杯饮品叫什么名字？"
    return "我还需要一点信息才能帮你记录这杯饮品。"


def _parse_intake_locally(user_message: str) -> dict:
    text = user_message.strip()
    log_keywords = ["喝", "买", "来一杯", "记录", "加一条", "点了", "刚刚", "刚才"]
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
    if not _llm_enabled():
        return local_result

    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are DrinkMind Intake Parser. Extract a drink logging intent from Chinese natural language. "
             "Return structured fields only. Do not invent unknown required fields. "
             "Sugar must be one of none, three, half, seven, full, unknown. "
             "Type must be one of coffee, milktea, tea, fruittea, soda, alcohol."),
            ("user", "{message}")
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


def _knowledge_scope(source: str | None) -> str:
    source = source or ""
    if "caffeine_sugar" in source:
        return "caffeine_sugar"
    if "caffeine_only" in source:
        return "caffeine_only"
    if "sugar_only" in source:
        return "sugar_only"
    if "alcohol_only" in source:
        return "alcohol_only"
    if "partial" in source:
        return "partial"
    return "complete"


def _normalize_match_name(name: str | None) -> str:
    normalized = re.sub(r"\s+", "", name or "").lower()
    for token in ["咖啡", "饮品", "冷饮", "热饮", "标准杯", "默认杯型"]:
        normalized = normalized.replace(token, "")
    return normalized


def _brand_key(brand: str | None) -> str:
    normalized = re.sub(r"\s+", " ", (brand or "").strip().lower())
    if normalized in BRAND_CANONICAL_KEYS:
        return BRAND_CANONICAL_KEYS[normalized]
    compact = normalized.replace(" ", "")
    for alias, key in BRAND_CANONICAL_KEYS.items():
        alias_norm = alias.lower()
        if alias_norm.replace(" ", "") == compact:
            return key
    return compact


def _find_sql_knowledge_match(db, brand: str, name: str):
    exact = db.query(DrinkKnowledge).filter(
        DrinkKnowledge.brand == brand,
        DrinkKnowledge.name == name
    ).first()
    if exact:
        return exact

    query_name = _normalize_match_name(name)
    if not query_name:
        return None
    query_brand_key = _brand_key(brand)
    all_rows = db.query(DrinkKnowledge).all()
    brand_rows = [row for row in all_rows if _brand_key(row.brand) == query_brand_key]
    for row in brand_rows:
        row_name = _normalize_match_name(row.name)
        if row_name and (row_name == query_name or row_name in query_name or query_name in row_name):
            return row
    return None


def _knowledge_field_known(scope: str, field_name: str, value=None) -> bool:
    if scope == "complete":
        return True
    if scope == "caffeine_sugar":
        return field_name in {"caffeine", "sugar"}
    if scope == "caffeine_only":
        return field_name == "caffeine"
    if scope == "sugar_only":
        return field_name == "sugar"
    if scope == "alcohol_only":
        return field_name == "abv"
    if scope == "partial":
        return value is not None and float(value or 0) > 0
    return False


def _sugar_from_knowledge(base_sugar: float, ratio: float, sugar_level: str, multipliers: dict) -> float:
    db_full_sugar = float(base_sugar or 0) * ratio
    multiplier = multipliers.get(sugar_level, 1.0)
    natural_sugar = db_full_sugar * 0.2
    added_sugar = db_full_sugar * 0.8 * multiplier
    return round(natural_sugar + added_sugar, 1)


def _estimate_nutrition_with_fallback(brand: str, name: str, drink_type: str, volume: int, sugar_level: str) -> dict:
    if not _llm_enabled():
        local_est = estimate_nutrition(brand, name, drink_type, volume, sugar_level)
        return {
            "caffeine": local_est["caffeine"],
            "sugar": local_est["sugar"],
            "source": local_est["source"],
            "method": "LOCAL",
            "confidence": local_est["confidence"],
            "reasoning": "; ".join(local_est["reasoning"]),
        }

    try:
        class HybridAIEstimation(BaseModel):
            caffeine: float = Field(description="Estimated caffeine in mg.")
            sugar: float = Field(description="Estimated sugar in g.")
            reasoning: str = Field(description="Short reason for the estimate.")

        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are DrinkMind nutrition estimator. Estimate caffeine and sugar for a beverage. "
             "Use common nutrition assumptions: espresso is about 75mg caffeine per shot; milk has lactose; "
             "coconut milk, oat milk, fruit tea, and juice bases can contain natural sugar even when no extra sugar is added. "
             "Return conservative numeric estimates."),
            ("user", "brand: {brand}\nname: {name}\ntype: {drink_type}\nvolume: {volume}ml\nsweetness: {sugar_level}")
        ])
        res = (prompt | llm.with_structured_output(HybridAIEstimation, method="function_calling")).invoke({
            "brand": brand,
            "name": name,
            "drink_type": drink_type,
            "volume": volume,
            "sugar_level": sugar_level,
        })
        return {
            "caffeine": round(res.caffeine, 1),
            "sugar": round(res.sugar, 1),
            "source": "AI model estimate",
            "method": "LLM",
            "confidence": 0.75,
            "reasoning": res.reasoning,
        }
    except Exception as e:
        print(f"[Hybrid AI Estimation Error] {e}", flush=True)
        local_est = estimate_nutrition(brand, name, drink_type, volume, sugar_level)
        return {
            "caffeine": local_est["caffeine"],
            "sugar": local_est["sugar"],
            "source": local_est["source"],
            "method": "LOCAL",
            "confidence": local_est["confidence"],
            "reasoning": "; ".join(local_est["reasoning"]),
        }


def _apply_hybrid_knowledge_result(r: dict, *, known: dict, ratio: float, source_label: str, method_prefix: str,
                                   matched_id: str | None, retrieval_score, sugar_level: str,
                                   multipliers: dict, brand: str, name: str, drink_type: str, volume: int) -> dict:
    scope = _knowledge_scope(known.get("source"))
    caffeine_known = _knowledge_field_known(scope, "caffeine", known.get("caffeine"))
    sugar_known = _knowledge_field_known(scope, "sugar", known.get("sugar"))

    if caffeine_known and sugar_known:
        r["caffeine"] = round(float(known.get("caffeine") or 0) * ratio, 1)
        r["sugarContent"] = _sugar_from_knowledge(known.get("sugar") or 0, ratio, sugar_level, multipliers)
        r["data_source"] = source_label
        r["confidence"] = known.get("confidence") or 0.8
        r["reasoning"] = [f"{method_prefix} complete match (scaled to {volume}ml, applied sugar level '{sugar_level}')"]
        r["estimation_method"] = method_prefix
        r["matched_knowledge_id"] = matched_id
        r["retrieval_score"] = retrieval_score
        return r

    estimate = _estimate_nutrition_with_fallback(brand, name, drink_type, volume, sugar_level)
    r["caffeine"] = round(float(known.get("caffeine") or 0) * ratio, 1) if caffeine_known else estimate["caffeine"]
    r["sugarContent"] = _sugar_from_knowledge(known.get("sugar") or 0, ratio, sugar_level, multipliers) if sugar_known else estimate["sugar"]
    r["data_source"] = f"{source_label} + {estimate['source']}"
    r["confidence"] = round(min(float(known.get("confidence") or 0.7), float(estimate.get("confidence") or 0.7)), 2)
    r["reasoning"] = [
        f"{method_prefix} partial match scope={scope}; known fields: caffeine={caffeine_known}, sugar={sugar_known}.",
        f"Estimated missing fields via {estimate['method']}: {estimate['reasoning']}",
    ]
    r["estimation_method"] = f"HYBRID_{method_prefix}_{estimate['method']}"
    r["matched_knowledge_id"] = matched_id
    r["retrieval_score"] = retrieval_score
    return r


def enrich_drink_data(r: dict, db) -> dict:
    if "caffeine" not in r and "sugarContent" not in r:
        r["data_source"] = "用户录入"
    if r.get("data_source") in [None, "", "用户录入", "本地算法估算", "Local Estimator (Dynamic DB)"]:
        r["data_source"] = "用户录入"
    """
    同步估算饮品的成分。流程：
    1. 查 SQLite 精确匹配
    2. 查 Chroma 模糊检索
    3. 查 Local Estimator 经验估算
    全程不调用大模型 API。极速返回。
    """
    if r.get("data_source") not in ["用户录入", "本地算法估算"]:
        if "caffeine" in r or "sugarContent" in r:
            return r  # 已经有确定数据的饮品不重复计算

    brand = r.get("brand", "")
    name = r.get("name", "")
    drink_type = r.get("type", "coffee")
    volume = r.get("volume", 500)
    sugar_level = r.get("sugar", "unknown")
    r["agent_trace_id"] = r.get("agent_trace_id") or f"trace_{uuid.uuid4().hex[:12]}"
    
    SWEETNESS_MULTIPLIERS = {
        'none': 0.0,
        'three': 0.3,
        'half': 0.5,
        'seven': 0.7,
        'full': 1.0,
        'unknown': 1.0
    }
    
    # 1. 精确匹配 SQLite
    sql_match = _find_sql_knowledge_match(db, brand, name)
    
    if sql_match:
        db_volume = sql_match.volume if sql_match.volume else 500
        ratio = volume / db_volume
        scope = _knowledge_scope(sql_match.source)
        if scope != "complete":
            return _apply_hybrid_knowledge_result(
                r,
                known={
                    "caffeine": sql_match.caffeine,
                    "sugar": sql_match.baseSugar,
                    "source": sql_match.source,
                    "confidence": sql_match.confidence,
                },
                ratio=ratio,
                source_label=sql_match.source,
                method_prefix="SQL_EXACT_MATCH",
                matched_id=sql_match.id,
                retrieval_score=None,
                sugar_level=sugar_level,
                multipliers=SWEETNESS_MULTIPLIERS,
                brand=brand,
                name=name,
                drink_type=drink_type,
                volume=volume,
            )
        
        # 假设数据库存的 baseSugar 是全糖状态
        db_full_sugar = sql_match.baseSugar * ratio
        multiplier = SWEETNESS_MULTIPLIERS.get(sugar_level, 1.0)
        
        # 粗略假设基础自然糖分约占全糖的20%，剩下的80%受甜度控制，避免出现0糖幻觉
        natural_sugar = db_full_sugar * 0.2
        added_sugar = db_full_sugar * 0.8 * multiplier
        
        r["caffeine"] = round(sql_match.caffeine * ratio, 1)
        r["sugarContent"] = round(natural_sugar + added_sugar, 1)
        r["data_source"] = sql_match.source
        r["confidence"] = sql_match.confidence
        r["reasoning"] = [f"SQL Exact Match (Scaled to {volume}ml, Applied sugar level '{sugar_level}')"]
        r["estimation_method"] = "SQL_EXACT_MATCH"
        r["matched_knowledge_id"] = sql_match.id
        r["retrieval_score"] = None
        return r

    # 2. RAG Chroma 向量匹配
    if vectorstore:
        try:
            docs_and_scores = vectorstore.similarity_search_with_score(f"{brand} {name}", k=1)
            if docs_and_scores:
                best_doc, score = docs_and_scores[0]
                meta = best_doc.metadata
                db_name = meta.get("name", "")
                
                # 计算名字的重合度（不包含品牌）
                query_chars = set(name.replace(" ", ""))
                db_chars = set(db_name.replace(" ", ""))
                overlap = len(query_chars.intersection(db_chars))
                
                # 只有当品牌相似度高，且名字有一定重叠，或向量距离极小时才采纳
                brand_match = brand and _brand_key(brand) == _brand_key(meta.get("brand", ""))
                
                # Overlap requirement: at least 1 character in common for short names, 2 for longer.
                # Or just score is extremely good.
                if brand_match and (overlap >= 1 or score < 0.3):
                    db_volume = meta.get("volume", 500)
                    ratio = volume / db_volume
                    scope = _knowledge_scope(meta.get("source"))
                    if scope != "complete":
                        return _apply_hybrid_knowledge_result(
                            r,
                            known={
                                "caffeine": meta.get("caffeine", 0),
                                "sugar": meta.get("sugar", 0),
                                "source": meta.get("source"),
                                "confidence": 0.8,
                            },
                            ratio=ratio,
                            source_label="RAG vector match",
                            method_prefix="RAG_MATCH",
                            matched_id=meta.get("id"),
                            retrieval_score=float(score),
                            sugar_level=sugar_level,
                            multipliers=SWEETNESS_MULTIPLIERS,
                            brand=brand,
                            name=name,
                            drink_type=drink_type,
                            volume=volume,
                        )
                    
                    db_full_sugar = meta.get("sugar", 0) * ratio
                    multiplier = SWEETNESS_MULTIPLIERS.get(sugar_level, 1.0)
                    natural_sugar = db_full_sugar * 0.2
                    added_sugar = db_full_sugar * 0.8 * multiplier

                    r["caffeine"] = round(meta.get("caffeine", 0) * ratio, 1)
                    r["sugarContent"] = round(natural_sugar + added_sugar, 1)
                    r["data_source"] = "RAG 向量检索匹配"
                    r["confidence"] = 0.8
                    r["reasoning"] = [f"RAG 匹配到相近文档: {meta.get('brand')} {meta.get('name')} (Score: {score:.2f}, Applied '{sugar_level}')"]
                    r["estimation_method"] = "RAG_MATCH"
                    r["matched_knowledge_id"] = meta.get("id")
                    r["retrieval_score"] = float(score)
                    return r
                else:
                    print(f"[RAG Skip] 拒绝了离谱匹配: 搜索 '{name}', 匹配到 '{db_name}'", flush=True)
        except Exception as e:
            print(f"[RAG Error] {e}")

    if not _llm_enabled():
        local_est = estimate_nutrition(brand, name, drink_type, volume, sugar_level)
        r["caffeine"] = local_est["caffeine"]
        r["sugarContent"] = local_est["sugar"]
        r["data_source"] = local_est["source"]
        r["confidence"] = local_est["confidence"]
        r["reasoning"] = local_est["reasoning"]
        r["estimation_method"] = "LOCAL_ESTIMATOR"
        r["matched_knowledge_id"] = None
        r["retrieval_score"] = None
        return r

    # 3. AI 大模型常识估算 (Zero-shot fallback)
    try:
        class AIEstimation(BaseModel):
            caffeine: float = Field(description="估计的咖啡因含量 (mg)")
            sugar: float = Field(description="估计的糖分含量 (g)")
            reasoning: str = Field(description="简短的推断理由，比如成分拆解")

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个专业的营养师。用户会提供一杯饮品的品牌、名称、杯型和甜度。\n"
                       "请凭借你的常识，估算其咖啡因(mg)和糖分(g)含量。\n"
                       "注意（非常重要，严禁违背这些营养学常识）：\n"
                       "1. 椰青/椰子水 (Coconut water) 天然含有较高的果糖和葡萄糖，约 4-5g/100ml。一杯 650ml 的椰青美式即使不另外加糖，通常也含有 10-15g 的天然糖分。绝对不能说椰青天然糖分极低！\n"
                       "2. 生椰乳/厚乳 (Coconut milk) 通常是预调风味乳，含有大量额外添加糖，即使无糖选项，其基底糖分也很高（约 7-10g/100ml）。\n"
                       "3. 燕麦奶 (Oat milk) 制作过程中淀粉会分解成麦芽糖，即使无糖，天然糖分也在 3-4g/100ml。\n"
                       "4. 牛奶 (Milk) 含有乳糖，约 5g/100ml。\n"
                       "5. 果茶（如杨枝甘露）本身通常含有较高的果糖，水果本身（如芒果、葡萄、橙子）的糖分也需要计入，通常中杯在 15-30g 之间。\n"
                       "6. 咖啡因：浓缩咖啡 (Espresso) 约 75mg/shot，中杯通常 1-2 shot，大杯 2-3 shot。纯果汁/果茶不含茶底时咖啡因应为 0。\n"
                       "7. 附加糖：根据甜度选择动态调整。三分糖通常加 10g 糖，全糖加 30g 糖。\n"
                       "请务必结合以上基准数据进行推理，给出一个合理的具体数值。"),
            ("user", "品牌: {brand}\n名称: {name}\n类型: {drink_type}\n杯型: {volume}ml\n甜度: {sugar_level}")
        ])
        
        structured_llm = llm.with_structured_output(AIEstimation, method="function_calling")
        chain = prompt | structured_llm
        
        res = chain.invoke({
            "brand": brand,
            "name": name,
            "drink_type": drink_type,
            "volume": volume,
            "sugar_level": sugar_level
        })
        
        r["caffeine"] = round(res.caffeine, 1)
        r["sugarContent"] = round(res.sugar, 1)
        r["data_source"] = "AI 大模型估算"
        r["confidence"] = 0.75
        r["reasoning"] = [f"AI 估算: {res.reasoning}"]
        r["estimation_method"] = "LLM_ESTIMATION"
        r["matched_knowledge_id"] = None
        r["retrieval_score"] = None
        return r
    except Exception as e:
        print(f"[AI Estimation Error] {e}", flush=True)

    # 4. Local Estimator 兜底 (如果大模型也挂了)
    local_est = estimate_nutrition(brand, name, drink_type, volume, sugar_level)
    r["caffeine"] = local_est["caffeine"]
    r["sugarContent"] = local_est["sugar"]
    r["data_source"] = local_est["source"]
    r["confidence"] = local_est["confidence"]
    r["reasoning"] = local_est["reasoning"]
    r["estimation_method"] = "LOCAL_ESTIMATOR"
    r["matched_knowledge_id"] = None
    r["retrieval_score"] = None
    
    return r


class InsightItem(BaseModel):
    level: str = Field(description="警告级别: info, warning, success, danger")
    icon: str = Field(description="合适的 Emoji 图标")
    title: str = Field(description="洞察标题，简短")
    message: str = Field(description="有温度的伴侣提示文案")

class ReportOutput(BaseModel):
    insights: List[InsightItem] = Field(description="1到3条洞察列表")

def generate_health_report(logs: list, report_type: str) -> dict:
    if not logs:
        return {"insights": []}
    if not _llm_enabled():
        return {"insights": []}
        
    system_prompt = f"""你是一个名为 DrinkMind Companion 的贴心饮品伴侣。你的目标是基于用户的饮品记录，提供有温度的【{report_type}】摄入分析。
绝对不要像个死板的健身教练一样说教、命令或指责用户。
保持语气轻松、自然、像个懂健康的好朋友。

分析维度：
- 咖啡因摄入量与饮用时间（下午过晚饮用可能会影响睡眠）
- 糖分摄入总和（是否需要注意控糖）
- 如果连续多天饮用咖啡，提醒一下可能产生耐受性，建议适当“咖啡因断食”。

返回要求：
- 请提取出 1 到 3 条核心洞察。
- 每条洞察包含 level（如 info, warning, success, danger），title，message，icon。
- 保证严格符合 JSON 结构。"""
    
    user_prompt = "这是近期的饮品记录：\n{logs_text}\n请生成洞察报告。"
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])
    
    structured_llm = llm.with_structured_output(ReportOutput, method="function_calling")
    chain = prompt | structured_llm
    
    result = chain.invoke({"logs_text": json.dumps(logs, ensure_ascii=False)})
    return result.dict()


def generate_companion_response(user_message: str, history: List[Dict[str, str]], context: Dict[str, Any]) -> str:
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    
    if not _llm_enabled():
        return "LLM companion is disabled in the current environment."

    try:
        sys_prompt = (
            "你是一个名叫 DrinkMind Companion 的 AI 饮品健康陪伴伴侣。\n"
            "你不是一个严格监督的健康教练，而是一个懂饮品、懂健康、懂用户情绪的贴心朋友。\n"
            "你的沟通风格：\n"
            "- 语气轻松、像朋友一样自然对话，可以用一些 Emoji。\n"
            "- 当用户想喝奶茶时，不要一味阻拦，可以幽默地建议换成三分糖，或者因为前几天控制得好给予肯定。\n"
            "- 关注用户的疲劳状态和睡眠。如果昨天没睡好，温柔地建议喝一些舒缓的饮品而不是高咖啡因的猛药。\n"
            "这是当前的用户偏好与数据上下文：\n"
            f"{json.dumps(context, ensure_ascii=False)}\n"
        )
        
        messages = [SystemMessage(content=sys_prompt)]
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))
                
        messages.append(HumanMessage(content=user_message))
        
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        print(f"[Agent Error] Companion Chat failed: {e}")
        return "抱歉，我的大脑好像有点短路了，请稍后再试！"
