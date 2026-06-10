import re
import uuid

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from database import DrinkKnowledge
from local_estimator import estimate_nutrition
from .llm_config import llm, llm_enabled
from .rag_store import vectorstore


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
    if not llm_enabled():
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

    if not llm_enabled():
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
