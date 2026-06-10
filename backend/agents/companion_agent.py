import json
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .llm_config import llm, llm_enabled


DISABLED_COMPANION_RESPONSE = "LLM companion is disabled in the current environment."
ERROR_COMPANION_RESPONSE = "Sorry, my companion response failed. Please try again later."


def generate_companion_response(user_message: str, history: List[Dict[str, str]], context: Dict[str, Any]) -> str:
    if not llm_enabled():
        return DISABLED_COMPANION_RESPONSE

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
