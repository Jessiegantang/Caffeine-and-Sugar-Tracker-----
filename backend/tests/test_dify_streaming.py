import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

import main
from db.database import AgentTrace, ChatLog, SessionLocal
from services import dify_companion_service


class DifyStreamingTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "COMPANION_PROVIDER": "dify",
            "DIFY_BASE_URL": "https://api.dify.ai/v1",
            "DIFY_API_KEY": "test-secret-key",
            "DIFY_USER_ID": "test-user",
            "DRINKMIND_OFFLINE": "false",
        }

    def test_dify_sse_chunks_are_forwarded_and_completed(self):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.iter_lines.return_value = [
            f'data: {json.dumps({"event": "message", "answer": "hello "})}',
            f'data: {json.dumps({"event": "message", "answer": "world"})}',
            f'data: {json.dumps({"event": "message_end"})}',
        ]
        stream_context = MagicMock()
        stream_context.__enter__.return_value = response

        with patch.dict(os.environ, self.env, clear=False), patch.object(
            dify_companion_service.httpx,
            "stream",
            return_value=stream_context,
        ) as stream:
            events = list(dify_companion_service.stream_dify_companion_turn(
                "question",
                [],
                {"today_caffeine_mg": 0, "today_sugar_g": 0},
            ))

        self.assertEqual([event["type"] for event in events], ["delta", "delta", "complete"])
        self.assertEqual("".join(event["text"] for event in events[:-1]), "hello world")
        self.assertEqual(events[-1]["turn"]["text"], "hello world")
        self.assertEqual(stream.call_args.kwargs["json"]["response_mode"], "streaming")

    def test_drink_form_json_is_not_streamed_to_the_frontend(self):
        answer = (
            '[DRINK_FORM]{"intent":"log_drink","message":"ready",'
            '"drink":{"name":"test drink","type":"coffee","volume":300,'
            '"sugar":"none","time":"now"}}'
        )
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.iter_lines.return_value = [
            f'data: {json.dumps({"event": "message", "answer": part})}'
            for part in ("[DRINK_", "FORM]", answer[len("[DRINK_FORM]"):])
        ]
        stream_context = MagicMock()
        stream_context.__enter__.return_value = response

        with patch.dict(os.environ, self.env, clear=False), patch.object(
            dify_companion_service.httpx,
            "stream",
            return_value=stream_context,
        ):
            events = list(dify_companion_service.stream_dify_companion_turn(
                "log a drink",
                [],
                {"today_caffeine_mg": 0, "today_sugar_g": 0},
            ))

        self.assertEqual([event["type"] for event in events], ["replace", "complete"])
        self.assertEqual(events[0]["text"], "ready")
        self.assertEqual(events[-1]["turn"]["parsed_intake"]["volume"], 300)


class StreamingChatEndpointTests(unittest.TestCase):
    client = TestClient(main.app)
    date = "2099-03-01"
    message = "stream endpoint test"

    def tearDown(self):
        db = SessionLocal()
        try:
            db.query(ChatLog).filter(ChatLog.date == self.date).delete(synchronize_session=False)
            db.query(AgentTrace).filter(
                AgentTrace.user_input == self.message
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

    def test_endpoint_returns_sse_delta_then_done_metadata(self):
        turn = {
            "response_type": "chat_message",
            "text": "hello world",
            "parsed_intake": None,
            "provider": "dify",
            "fallback_reason": None,
        }
        upstream_events = iter([
            {"type": "delta", "text": "hello "},
            {"type": "delta", "text": "world"},
            {"type": "complete", "turn": turn},
        ])
        with patch("services.chat_service.dify_available", return_value=True), patch(
            "services.chat_service.stream_dify_companion_turn",
            return_value=upstream_events,
        ), patch("services.chat_service.extract_memory_updates", return_value={}):
            response = self.client.post("/api/chat/stream", json={
                "date": self.date,
                "message": self.message,
            })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
        events = [
            json.loads(line[6:])
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        self.assertEqual([event["type"] for event in events], ["delta", "delta", "done"])
        self.assertEqual(events[-1]["data"]["response"], "hello world")
        self.assertEqual(events[-1]["data"]["provider"], "dify")


if __name__ == "__main__":
    unittest.main()
