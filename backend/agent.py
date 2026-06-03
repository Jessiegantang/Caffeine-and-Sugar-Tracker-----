import os
import json
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


def enrich_drink_data(r: dict, db) -> dict:
    """
    同步估算饮品的成分。流程：
    1. 查 SQLite 精确匹配
    2. 查 Chroma 模糊检索
    3. 查 Local Estimator 经验估算
    全程不调用大模型 API。极速返回。
    """
    if r.get("data_source") not in ["用户录入", "本地算法估算"]:
        return r  # 已经有确定数据的饮品不重复计算

    brand = r.get("brand", "")
    name = r.get("name", "")
    drink_type = r.get("type", "coffee")
    volume = r.get("volume", 500)
    sugar_level = r.get("sugar", "unknown")
    
    SWEETNESS_MULTIPLIERS = {
        'none': 0.0,
        'three': 0.3,
        'half': 0.5,
        'seven': 0.7,
        'full': 1.0,
        'unknown': 1.0
    }
    
    # 1. 精确匹配 SQLite
    sql_match = db.query(DrinkKnowledge).filter(
        DrinkKnowledge.brand == brand,
        DrinkKnowledge.name == name
    ).first()
    
    if sql_match:
        db_volume = sql_match.volume if sql_match.volume else 500
        ratio = volume / db_volume
        
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
                brand_match = brand and (brand in meta.get("brand", "") or meta.get("brand", "") in brand)
                
                # Overlap requirement: at least 1 character in common for short names, 2 for longer.
                # Or just score is extremely good.
                if brand_match and (overlap >= 1 or score < 0.3):
                    db_volume = meta.get("volume", 500)
                    ratio = volume / db_volume
                    
                    db_full_sugar = meta.get("sugar", 0) * ratio
                    multiplier = SWEETNESS_MULTIPLIERS.get(sugar_level, 1.0)
                    natural_sugar = db_full_sugar * 0.2
                    added_sugar = db_full_sugar * 0.8 * multiplier

                    r["caffeine"] = round(meta.get("caffeine", 0) * ratio, 1)
                    r["sugarContent"] = round(natural_sugar + added_sugar, 1)
                    r["data_source"] = "RAG 向量检索匹配"
                    r["confidence"] = 0.8
                    r["reasoning"] = [f"RAG 匹配到相近文档: {meta.get('brand')} {meta.get('name')} (Score: {score:.2f}, Applied '{sugar_level}')"]
                    return r
                else:
                    print(f"[RAG Skip] 拒绝了离谱匹配: 搜索 '{name}', 匹配到 '{db_name}'", flush=True)
        except Exception as e:
            print(f"[RAG Error] {e}")

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
