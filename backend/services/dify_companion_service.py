import json
import os
from typing import Any, Dict, List

import httpx

from agents.companion_agent import generate_companion_response as generate_local_companion_response


DEFAULT_DIFY_BASE_URL = "https://api.dify.ai/v1"
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_HISTORY_MESSAGES = 8
MAX_HISTORY_CHARACTERS = 6000
DRINK_FORM_MARKER = "[DRINK_FORM]"
ALLOWED_DRINK_TYPES = {
    "coffee",
    "teacoffee",
    "tea",
    "milktea",
    "fruittea",
    "soda",
    "other",
}
ALLOWED_SUGAR_LEVELS = {"none", "three", "half", "seven", "full", "unknown"}


class DifyCompanionError(RuntimeError):
    """A safe, user-independent Dify integration error."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"true", "1", "yes"}


def dify_requested() -> bool:
    return os.getenv("COMPANION_PROVIDER", "local").strip().lower() == "dify"


def dify_available() -> bool:
    if _env_truthy("DRINKMIND_OFFLINE"):
        return False
    return dify_requested() and bool(os.getenv("DIFY_API_KEY", "").strip())


def _timeout_seconds() -> float:
    try:
        configured = float(os.getenv("DIFY_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    except ValueError:
        configured = DEFAULT_TIMEOUT_SECONDS
    return max(5.0, min(configured, 180.0))


def _history_text(history: List[Dict[str, str]]) -> str:
    lines = []
    for message in history[-MAX_HISTORY_MESSAGES:]:
        role = "用户" if message.get("role") == "user" else "助手"
        content = str(message.get("content") or "").strip()
        if content:
            lines.append(f"{role}：{content}")
    text = "\n".join(lines) or "无"
    return text[-MAX_HISTORY_CHARACTERS:]


def _build_inputs(history: List[Dict[str, str]], context: Dict[str, Any]) -> dict:
    inputs = {
        "today_caffeine_mg": float(context.get("today_caffeine_mg") or 0),
        "today_sugar_g": float(context.get("today_sugar_g") or 0),
        "user_preferences": json.dumps(
            context.get("user_preferences") or {},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "recent_history": _history_text(history),
    }
    sleep_hours = context.get("last_night_sleep_hours")
    if isinstance(sleep_hours, (int, float)):
        inputs["sleep_hours"] = float(sleep_hours)
    return inputs


def call_dify_companion(
    user_message: str,
    history: List[Dict[str, str]],
    context: Dict[str, Any],
) -> str:
    api_key = os.getenv("DIFY_API_KEY", "").strip()
    if not api_key:
        raise DifyCompanionError("not_configured")

    base_url = os.getenv("DIFY_BASE_URL", DEFAULT_DIFY_BASE_URL).strip().rstrip("/")
    user_id = os.getenv("DIFY_USER_ID", "drinkmind-local-user").strip() or "drinkmind-local-user"
    payload = {
        "inputs": _build_inputs(history, context),
        "query": user_message,
        "response_mode": "blocking",
        "user": user_id,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            f"{base_url}/chat-messages",
            json=payload,
            headers=headers,
            timeout=_timeout_seconds(),
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise DifyCompanionError("timeout") from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code in {401, 403}:
            code = "authentication_failed"
        elif status_code == 429:
            code = "rate_limited"
        else:
            code = "upstream_http_error"
        raise DifyCompanionError(code) from exc
    except httpx.HTTPError as exc:
        raise DifyCompanionError("connection_failed") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise DifyCompanionError("invalid_response") from exc

    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise DifyCompanionError("empty_answer")
    return answer.strip()


def parse_dify_answer(answer: str) -> dict:
    """Convert a Dify answer into the stable local chat contract."""
    text = str(answer or "").strip()
    if not text.startswith(DRINK_FORM_MARKER):
        return {
            "response_type": "chat_message",
            "text": text,
            "parsed_intake": None,
        }

    payload_text = text[len(DRINK_FORM_MARKER):].strip()
    if payload_text.startswith("```json"):
        payload_text = payload_text[len("```json"):].strip()
    elif payload_text.startswith("```"):
        payload_text = payload_text[len("```"):].strip()
    if payload_text.endswith("```"):
        payload_text = payload_text[:-3].strip()

    try:
        payload = json.loads(payload_text)
    except (TypeError, ValueError) as exc:
        raise DifyCompanionError("invalid_drink_form_json") from exc

    if not isinstance(payload, dict) or payload.get("intent") != "log_drink":
        raise DifyCompanionError("invalid_drink_form_contract")
    drink = payload.get("drink")
    if not isinstance(drink, dict):
        raise DifyCompanionError("invalid_drink_form_contract")

    name = str(drink.get("name") or "").strip()
    brand = str(drink.get("brand") or "").strip()
    drink_type = str(drink.get("type") or "").strip().lower()
    sugar = str(drink.get("sugar") or "").strip().lower()
    time_value = str(drink.get("time") or "now").strip() or "now"
    volume_value = drink.get("volume")

    if len(name) < 2:
        raise DifyCompanionError("invalid_drink_form_name")
    if brand.lower() in {"none", "null", "unknown"}:
        brand = ""
    if drink_type not in ALLOWED_DRINK_TYPES:
        raise DifyCompanionError("invalid_drink_form_type")
    if sugar not in ALLOWED_SUGAR_LEVELS:
        raise DifyCompanionError("invalid_drink_form_sugar")
    if isinstance(volume_value, bool):
        raise DifyCompanionError("invalid_drink_form_volume")
    try:
        volume = int(volume_value)
    except (TypeError, ValueError) as exc:
        raise DifyCompanionError("invalid_drink_form_volume") from exc
    if volume < 10 or volume > 2000:
        raise DifyCompanionError("invalid_drink_form_volume")
    if not _valid_drink_time(time_value):
        raise DifyCompanionError("invalid_drink_form_time")

    parsed_intake = {
        "intent": "log_drink",
        "brand": brand or None,
        "name": name,
        "type": drink_type,
        "volume": volume,
        "sugar": sugar,
        "time": time_value,
        "missing_fields": [],
        "follow_up": None,
    }
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        message = "我已经整理好饮品信息，请确认后添加到当天记录。"
    return {
        "response_type": "drink_form",
        "text": message.strip(),
        "parsed_intake": parsed_intake,
    }


def _valid_drink_time(value: str) -> bool:
    if value in {"now", "morning", "afternoon", "evening"}:
        return True
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return False
    hour, minute = (int(part) for part in parts)
    return 0 <= hour <= 23 and 0 <= minute <= 59


def generate_dify_turn(
    user_message: str,
    history: List[Dict[str, str]],
    context: Dict[str, Any],
) -> dict:
    """Call Dify without falling back so the caller can restore the full local route."""
    if not dify_available():
        raise DifyCompanionError("not_available")
    turn = parse_dify_answer(call_dify_companion(user_message, history, context))
    return {
        **turn,
        "provider": "dify",
        "fallback_reason": None,
    }


def generate_companion_response(
    user_message: str,
    history: List[Dict[str, str]],
    context: Dict[str, Any],
) -> dict:
    """Return a companion response with a local fallback and trace-safe metadata."""
    if not dify_available():
        return {
            "text": generate_local_companion_response(user_message, history, context),
            "provider": "local",
            "fallback_reason": None,
        }

    try:
        return generate_dify_turn(user_message, history, context)
    except DifyCompanionError as exc:
        return {
            "text": generate_local_companion_response(user_message, history, context),
            "provider": "local",
            "fallback_reason": exc.code,
        }
