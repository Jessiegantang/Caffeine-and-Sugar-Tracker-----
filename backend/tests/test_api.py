import os
import sys
import unittest
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

import main
from workflows.nutrition_pipeline import estimate_drink_nutrition
from db.database import DrinkKnowledge, DrinkLog, HealthPlan, NutritionEvidence, ProductCandidate, SessionLocal


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def tearDown(self):
        db = SessionLocal()
        try:
            for log in db.query(DrinkLog).filter(DrinkLog.id.in_([
                "test_api_composition_log",
                "test_api_legacy_log",
                "test_api_bad_json_log",
                "test_feedback_log",
                "test_feedback_evidence_log",
                "test_feedback_invalid_log",
            ])).all():
                db.delete(log)
            for row in db.query(NutritionEvidence).filter(NutritionEvidence.id.like("ev_%")).all():
                if row.raw_evidence and (
                    "Feedback Test Drink" in row.raw_evidence
                    or "Feedback Evidence Drink" in row.raw_evidence
                    or "Feedback Invalid Drink" in row.raw_evidence
                    or "test_feedback_log" in row.raw_evidence
                    or "test_feedback_evidence_log" in row.raw_evidence
                    or "test_feedback_invalid_log" in row.raw_evidence
                ):
                    db.delete(row)
            for row in db.query(ProductCandidate).filter(ProductCandidate.name.in_([
                "Feedback Test Drink",
                "Feedback Evidence Drink",
                "Feedback Invalid Drink",
            ])).all():
                db.delete(row)
            for row in db.query(DrinkKnowledge).filter(DrinkKnowledge.name.in_([
                "Feedback Test Drink",
                "Feedback Evidence Drink",
                "Feedback Invalid Drink",
            ])).all():
                db.delete(row)
            for plan in db.query(HealthPlan).filter(HealthPlan.id.like("plan_%")).all():
                if plan.target in {"reduce_sugar", "reduce_caffeine", "work_week_strategy", "balanced_drink_routine"}:
                    db.delete(plan)
            db.commit()
        finally:
            db.close()
        self.client.delete("/api/user/preferences")

    def test_parse_intake_api_returns_structured_json(self):
        response = self.client.post("/api/agent/parse_intake", json={
            "date": "2026-06-04",
            "message": "我刚喝了一杯瑞幸生椰拿铁，大杯，三分糖。",
        })

        self.assertEqual(response.status_code, 200)
        parsed = response.json()["parsed_intake"]
        self.assertEqual(parsed["intent"], "log_drink")
        self.assertEqual(parsed["sugar"], "three")

    def test_agent_act_records_trace(self):
        response = self.client.post("/api/agent/act", json={
            "date": "2026-06-04",
            "message": "我现在还能喝咖啡吗",
        })

        self.assertEqual(response.status_code, 200)
        trace_id = response.json()["agent_state"]["trace_id"]
        traces = self.client.get("/api/agent/traces?limit=5").json()["traces"]
        self.assertTrue(any(trace["id"] == trace_id for trace in traces))

    def test_memory_preferences_can_be_written_and_cleared(self):
        response = self.client.post("/api/agent/act", json={
            "date": "2026-06-04",
            "message": "我想少喝糖，刚喝了一杯瑞幸生椰拿铁，大杯，三分糖。",
        })
        self.assertEqual(response.status_code, 200)

        preferences = self.client.get("/api/user/preferences").json()["preferences"]
        self.assertEqual(preferences["goal"], "reduce_sugar")
        self.assertEqual(preferences["preferred_sugar"], "three")

        clear_response = self.client.delete("/api/user/preferences")
        self.assertEqual(clear_response.status_code, 200)
        self.assertEqual(self.client.get("/api/user/preferences").json()["preferences"], {})

    def test_health_plan_api_creates_and_updates_plan(self):
        response = self.client.post("/api/health/plans", json={
            "date": "2026-06-04",
            "goal": "我想一周内减少奶茶糖分",
        })

        self.assertEqual(response.status_code, 200)
        plan = response.json()["plan"]
        self.assertEqual(plan["target"], "reduce_sugar")
        self.assertEqual(len(plan["plan_content"]), 7)

        progress = self.client.post("/api/health/plans/active/progress?date=2026-06-06").json()["plan"]
        self.assertEqual(progress["current_day"], 3)

    def test_log_drink_api_uses_composition_without_persisting_extra_fields(self):
        response = self.client.post("/api/log_drink", json={
            "id": "test_api_composition_log",
            "date": "2026-06-04",
            "brand": "NoKbApiBrand",
            "name": "coconut latte",
            "type": "coffee",
            "sugar": "three",
            "volume": 500,
            "startTime": "10:00",
            "endTime": "10:15",
            "caffeine": 0,
            "sugarContent": 0,
            "alcoholContent": 0,
            "abv": 0,
        })

        self.assertEqual(response.status_code, 200)
        nutrition = response.json()["nutrition_result"]
        self.assertEqual(nutrition["estimation_method"], "COMPOSITION_ESTIMATION")
        self.assertIn("explainability", nutrition)
        self.assertTrue(nutrition["explainability"]["used_composition"])
        self.assertTrue(nutrition["explainability"]["components"])

        db = SessionLocal()
        try:
            log = db.query(DrinkLog).filter(DrinkLog.id == "test_api_composition_log").first()
            self.assertIsNotNone(log)
            self.assertEqual(log.estimation_method, "COMPOSITION_ESTIMATION")
            self.assertGreater(log.caffeine, 0)
            self.assertGreater(log.sugarContent, 0)
            self.assertTrue(log.composition_json)
            self.assertTrue(log.explainability_json)
            self.assertFalse(hasattr(log, "composition"))
            self.assertFalse(hasattr(log, "explainability"))
        finally:
            db.close()

        logs_response = self.client.get("/api/logs")
        self.assertEqual(logs_response.status_code, 200)
        saved = next(row for row in logs_response.json() if row["id"] == "test_api_composition_log")
        self.assertIsInstance(saved["composition"], dict)
        self.assertIsInstance(saved["explainability"], dict)
        self.assertTrue(saved["explainability"]["components"])

    def test_logs_api_handles_legacy_and_bad_explainability_json(self):
        db = SessionLocal()
        try:
            db.add(DrinkLog(
                id="test_api_legacy_log",
                date="2026-06-04",
                brand="Legacy",
                name="Legacy Americano",
                type="coffee",
                sugar="none",
                volume=500,
                startTime="09:00",
                endTime="09:10",
                caffeine=120,
                sugarContent=0,
                alcoholContent=0,
                abv=0,
                status="active",
            ))
            db.add(DrinkLog(
                id="test_api_bad_json_log",
                date="2026-06-04",
                brand="BadJson",
                name="Bad Json Latte",
                type="coffee",
                sugar="half",
                volume=500,
                startTime="11:00",
                endTime="11:10",
                caffeine=100,
                sugarContent=10,
                alcoholContent=0,
                abv=0,
                status="active",
                composition_json="{bad",
                explainability_json="{bad",
            ))
            db.commit()
        finally:
            db.close()

        response = self.client.get("/api/logs")
        self.assertEqual(response.status_code, 200)
        rows = {row["id"]: row for row in response.json()}
        self.assertIsNone(rows["test_api_legacy_log"]["composition"])
        self.assertIsNone(rows["test_api_legacy_log"]["explainability"])
        self.assertIsNone(rows["test_api_bad_json_log"]["composition"])
        self.assertIsNone(rows["test_api_bad_json_log"]["explainability"])

    def test_nutrition_feedback_updates_log_without_creating_evidence(self):
        db = SessionLocal()
        try:
            db.add(DrinkLog(
                id="test_feedback_log",
                date="2026-06-04",
                brand="OldBrand",
                name="Old Drink",
                type="coffee",
                sugar="unknown",
                volume=450,
                startTime="09:00",
                endTime="09:10",
                caffeine=80,
                sugarContent=8,
                alcoholContent=0,
                abv=0,
                status="active",
                explainability_json=json.dumps({"method": "COMPOSITION_ESTIMATION"}),
            ))
            db.commit()
        finally:
            db.close()

        response = self.client.post("/api/logs/test_feedback_log/nutrition_feedback", json={
            "corrected": {
                "brand": "FeedbackBrand",
                "name": "Feedback Test Drink",
                "type": "coffee",
                "volume": 500,
                "caffeine": 120,
                "sugarContent": 18,
            },
            "source_type": "user_feedback",
            "source_note": "",
            "apply_to_log": True,
            "submit_as_evidence": False,
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["candidate"])
        self.assertIsNone(body["evidence"])
        self.assertEqual(body["log"]["brand"], "FeedbackBrand")
        self.assertEqual(body["log"]["name"], "Feedback Test Drink")
        self.assertEqual(body["log"]["volume"], 500)
        self.assertEqual(body["log"]["caffeine"], 120.0)
        self.assertEqual(body["log"]["sugarContent"], 18.0)
        feedback = body["log"]["explainability"]["feedback"]
        self.assertEqual(feedback["previous"]["caffeine"], 80.0)
        self.assertEqual(feedback["delta"]["caffeine"], 40.0)
        self.assertFalse(feedback["high_delta"])

        db = SessionLocal()
        try:
            self.assertIsNone(db.query(ProductCandidate).filter(ProductCandidate.name == "Feedback Test Drink").first())
            self.assertIsNone(db.query(NutritionEvidence).filter(NutritionEvidence.raw_evidence.contains("Feedback Test Drink")).first())
        finally:
            db.close()

    def test_nutrition_feedback_creates_reviewable_evidence_and_later_sql_match(self):
        db = SessionLocal()
        try:
            db.add(DrinkLog(
                id="test_feedback_evidence_log",
                date="2026-06-04",
                brand="FeedbackBrand",
                name="Feedback Evidence Drink",
                type="coffee",
                sugar="unknown",
                volume=480,
                startTime="10:00",
                endTime="10:10",
                caffeine=40,
                sugarContent=4,
                alcoholContent=0,
                abv=0,
                status="active",
            ))
            db.commit()
        finally:
            db.close()

        response = self.client.post("/api/logs/test_feedback_evidence_log/nutrition_feedback", json={
            "corrected": {
                "brand": "FeedbackBrand",
                "name": "Feedback Evidence Drink",
                "type": "coffee",
                "volume": 500,
                "caffeine": 132,
                "sugarContent": 21,
            },
            "source_type": "user_feedback",
            "source_note": "Package label says caffeine 132mg and sugar 21g.",
            "apply_to_log": True,
            "submit_as_evidence": True,
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        candidate = body["candidate"]
        evidence = body["evidence"]
        self.assertEqual(candidate["name"], "Feedback Evidence Drink")
        self.assertEqual(candidate["status"], "evidence_ready")
        self.assertEqual(evidence["status"], "pending_review")
        self.assertEqual(evidence["source_type"], "user_feedback")
        self.assertEqual(evidence["extracted"]["volume"], 500.0)
        self.assertEqual(evidence["extracted"]["caffeine"], 132.0)
        self.assertEqual(evidence["extracted"]["sugar"], 21.0)

        approve_response = self.client.post(f"/api/knowledge/acquisition/evidence/{evidence['id']}/approve")
        self.assertEqual(approve_response.status_code, 200)
        knowledge = approve_response.json()["knowledge"]
        self.assertEqual(knowledge["name"], "Feedback Evidence Drink")
        self.assertEqual(knowledge["caffeine"], 132.0)
        self.assertEqual(knowledge["baseSugar"], 21.0)

        db = SessionLocal()
        try:
            result = estimate_drink_nutrition({
                "brand": "FeedbackBrand",
                "name": "Feedback Evidence Drink",
                "type": "coffee",
                "sugar": "unknown",
                "volume": 500,
                "data_source": "user_input",
            }, db)
        finally:
            db.close()

        self.assertEqual(result["estimation_method"], "SQL_EXACT_MATCH")
        self.assertEqual(result["matched_knowledge_id"], knowledge["id"])
        self.assertFalse(result["explainability"]["used_composition"])
        self.assertTrue(result["explainability"]["used_knowledge_match"])

    def test_nutrition_feedback_rejects_invalid_ranges(self):
        db = SessionLocal()
        try:
            db.add(DrinkLog(
                id="test_feedback_invalid_log",
                date="2026-06-04",
                brand="FeedbackBrand",
                name="Feedback Invalid Drink",
                type="coffee",
                sugar="unknown",
                volume=500,
                startTime="11:00",
                endTime="11:10",
                caffeine=50,
                sugarContent=5,
                alcoholContent=0,
                abv=0,
                status="active",
            ))
            db.commit()
        finally:
            db.close()

        response = self.client.post("/api/logs/test_feedback_invalid_log/nutrition_feedback", json={
            "corrected": {
                "brand": "FeedbackBrand",
                "name": "Feedback Invalid Drink",
                "type": "coffee",
                "volume": 5,
                "caffeine": 120,
                "sugarContent": 18,
            },
            "source_type": "user_feedback",
            "source_note": "Package label says caffeine 120mg and sugar 18g.",
            "apply_to_log": True,
            "submit_as_evidence": True,
        })

        self.assertEqual(response.status_code, 400)

    def test_nutrition_feedback_requires_source_note_for_evidence(self):
        db = SessionLocal()
        try:
            db.add(DrinkLog(
                id="test_feedback_invalid_log",
                date="2026-06-04",
                brand="FeedbackBrand",
                name="Feedback Invalid Drink",
                type="coffee",
                sugar="unknown",
                volume=500,
                startTime="11:00",
                endTime="11:10",
                caffeine=50,
                sugarContent=5,
                alcoholContent=0,
                abv=0,
                status="active",
            ))
            db.commit()
        finally:
            db.close()

        response = self.client.post("/api/logs/test_feedback_invalid_log/nutrition_feedback", json={
            "corrected": {
                "brand": "FeedbackBrand",
                "name": "Feedback Invalid Drink",
                "type": "coffee",
                "volume": 500,
                "caffeine": 120,
                "sugarContent": 18,
            },
            "source_type": "user_feedback",
            "source_note": "",
            "apply_to_log": True,
            "submit_as_evidence": True,
        })

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
