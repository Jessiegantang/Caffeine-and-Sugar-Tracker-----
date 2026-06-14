import json
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .llm_config import llm, llm_enabled


DISABLED_COMPANION_RESPONSE = "我现在先用本地规则帮你判断。"
ERROR_COMPANION_RESPONSE = "抱歉，回答生成失败了，请稍后再试。"

SYMPTOM_KEYWORDS = ["干呕", "恶心", "想吐", "反胃", "胃不舒服", "胃疼", "心慌", "头晕", "难受", "不舒服"]


def generate_companion_response(user_message: str, history: List[Dict[str, str]], context: Dict[str, Any]) -> str:
    if not llm_enabled():
        return _local_companion_response(user_message, context)

    try:
        sys_prompt = (
            "You are DrinkMind Companion, a warm AI beverage health companion.\n"
            "You are not a strict health coach. You understand drinks, health, and the user's mood.\n"
            "Conversation style:\n"
            "- Friendly, relaxed, and natural.\n"
            "- When the user wants milk tea or coffee, do not block them reflexively. Suggest lighter options when useful.\n"
            "- Pay attention to fatigue, sleep, caffeine timing, and sugar intake.\n"
            "Current user context:\n"
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
        return ERROR_COMPANION_RESPONSE


def _local_companion_response(user_message: str, context: Dict[str, Any]) -> str:
    if any(keyword in user_message for keyword in SYMPTOM_KEYWORDS):
        return (
            "听起来这杯饮品已经让你有点不舒服了，先别继续喝了，喝几口温水，休息一下。"
            "如果干呕、心慌、胃痛或头晕持续，建议及时找医生或身边的人帮忙。"
        )

    caffeine = float(context.get("today_caffeine_mg") or 0)
    sugar = float(context.get("today_sugar_g") or 0)
    if caffeine > 400 or sugar > 50:
        return "按今天已记录的摄入量看，建议先暂停咖啡因或高糖饮品，换成水或无糖低刺激饮品更稳。"
    if caffeine > 200 or sugar > 25:
        return "今天还有一点空间，但建议选低糖、低咖啡因的饮品，别再叠加强刺激的咖啡或奶茶。"
    return "目前摄入量还算可控。如果只是想解馋，可以选小杯、低糖或无糖，慢慢喝。"
