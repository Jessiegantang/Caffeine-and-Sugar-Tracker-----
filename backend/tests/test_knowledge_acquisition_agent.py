import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["OPENAI_API_KEY"] = "dummy_test_key"
os.environ["ENABLE_TEXT_EXTRACTION_LLM"] = "false"

from fastapi.testclient import TestClient

import main
from agents.knowledge_acquisition_agent import is_allowed_source
from database import DrinkKnowledge, NutritionEvidence, ProductCandidate, SessionLocal


class KnowledgeAcquisitionAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def tearDown(self):
        db = SessionLocal()
        try:
            for row in db.query(NutritionEvidence).filter(NutritionEvidence.id.like("ev_%")).all():
                if row.raw_evidence and (
                    "Test Acquisition Latte" in row.raw_evidence
                    or "Test Image Latte" in row.raw_evidence
                    or "Test Caffeine Only Americano" in row.raw_evidence
                    or "Test Sugar Only Tea" in row.raw_evidence
                    or "Test Merge Drink" in row.raw_evidence
                    or "Test Discovery" in row.raw_evidence
                ):
                    db.delete(row)
            for row in db.query(ProductCandidate).filter(
                ProductCandidate.name.in_([
                    "Test Acquisition Latte",
                    "Test Image Latte",
                    "Test Caffeine Only Americano",
                    "Test Sugar Only Tea",
                    "Test Merge Drink",
                    "Test Discovery Latte",
                ])
            ).all():
                db.delete(row)
            for row in db.query(DrinkKnowledge).filter(
                DrinkKnowledge.name.in_([
                    "Test Acquisition Latte",
                    "Test Image Latte",
                    "Test Caffeine Only Americano",
                    "Test Sugar Only Tea",
                    "Test Merge Drink",
                    "Test Discovery Latte",
                ])
            ).all():
                db.delete(row)
            db.commit()
        finally:
            db.close()

    def test_blocked_domain_policy_rejects_xiaohongshu(self):
        self.assertFalse(is_allowed_source("https://www.xiaohongshu.com/explore/test"))

        response = self.client.post("/api/knowledge/acquisition/candidates", json={
            "brand": "TestBrand",
            "name": "Test Acquisition Latte",
            "source_url": "https://www.xiaohongshu.com/explore/test",
        })

        self.assertEqual(response.status_code, 400)

    def test_manual_evidence_can_be_reviewed_into_knowledge_base(self):
        candidate_response = self.client.post("/api/knowledge/acquisition/candidates", json={
            "brand": "TestBrand",
            "name": "Test Acquisition Latte",
            "type": "coffee",
            "source_url": "https://example.com/open-source",
        })
        self.assertEqual(candidate_response.status_code, 200)
        candidate_id = candidate_response.json()["candidate"]["id"]

        evidence_response = self.client.post(f"/api/knowledge/acquisition/candidates/{candidate_id}/evidence", json={
            "source_type": "official",
            "source_url": "https://example.com/open-source",
            "raw_evidence": "Test Acquisition Latte 容量 500ml 咖啡因: 120mg 糖分: 18g",
        })
        self.assertEqual(evidence_response.status_code, 200)
        evidence = evidence_response.json()["evidence"]
        self.assertEqual(evidence["extracted"]["volume"], 500.0)
        self.assertEqual(evidence["extracted"]["caffeine"], 120.0)
        self.assertEqual(evidence["extracted"]["sugar"], 18.0)

        approve_response = self.client.post(f"/api/knowledge/acquisition/evidence/{evidence['id']}/approve")
        self.assertEqual(approve_response.status_code, 200)
        knowledge = approve_response.json()["knowledge"]
        self.assertEqual(knowledge["name"], "Test Acquisition Latte")
        self.assertEqual(knowledge["caffeine"], 120.0)
        self.assertEqual(knowledge["baseSugar"], 18.0)

        list_response = self.client.get("/api/knowledge/acquisition/candidates")
        self.assertEqual(list_response.status_code, 200)
        listed_names = [row["name"] for row in list_response.json()["candidates"]]
        self.assertNotIn("Test Acquisition Latte", listed_names)

    def test_image_items_can_be_staged_as_candidates_and_evidence(self):
        response = self.client.post("/api/knowledge/acquisition/image/import", json={
            "source_type": "image_upload",
            "items": [{
                "brand": "TestBrand",
                "name": "Test Image Latte",
                "type": "coffee",
                "volume": 500,
                "caffeine": 88,
                "sugar": 12,
                "confidence": 0.72,
                "raw_evidence": "Test Image Latte 500ml caffeine 88mg sugar 12g",
            }],
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["staged"][0]["candidate"]["name"], "Test Image Latte")
        self.assertEqual(body["staged"][0]["evidence"]["extracted"]["caffeine"], 88.0)
        self.assertEqual(body["staged"][0]["evidence"]["extracted"]["sugar"], 12.0)

    def test_caffeine_only_image_evidence_can_be_imported(self):
        response = self.client.post("/api/knowledge/acquisition/image/import", json={
            "source_type": "image_upload",
            "items": [{
                "brand": "TestBrand",
                "name": "Test Caffeine Only Americano",
                "type": "coffee",
                "volume": None,
                "caffeine": 150,
                "sugar": None,
                "confidence": 0.7,
                "raw_evidence": "Test Caffeine Only Americano caffeine 150mg",
            }],
        })

        self.assertEqual(response.status_code, 200)
        evidence = response.json()["staged"][0]["evidence"]
        self.assertEqual(evidence["extracted"]["caffeine"], 150.0)
        self.assertIsNone(evidence["extracted"]["sugar"])

        approve_response = self.client.post(f"/api/knowledge/acquisition/evidence/{evidence['id']}/approve")
        self.assertEqual(approve_response.status_code, 200)
        knowledge = approve_response.json()["knowledge"]
        self.assertEqual(knowledge["name"], "Test Caffeine Only Americano")
        self.assertEqual(knowledge["caffeine"], 150.0)
        self.assertEqual(knowledge["baseSugar"], 0.0)
        self.assertIn("caffeine_only", knowledge["source"])

    def test_sugar_only_image_evidence_can_be_imported(self):
        response = self.client.post("/api/knowledge/acquisition/image/import", json={
            "source_type": "image_upload",
            "items": [{
                "brand": "TestBrand",
                "name": "Test Sugar Only Tea",
                "type": "tea",
                "volume": 500,
                "caffeine": None,
                "sugar": 16,
                "confidence": 0.7,
                "raw_evidence": "Test Sugar Only Tea volume 500ml sugar 16g",
            }],
        })

        self.assertEqual(response.status_code, 200)
        evidence = response.json()["staged"][0]["evidence"]
        self.assertIsNone(evidence["extracted"]["caffeine"])
        self.assertEqual(evidence["extracted"]["sugar"], 16.0)

        approve_response = self.client.post(f"/api/knowledge/acquisition/evidence/{evidence['id']}/approve")
        self.assertEqual(approve_response.status_code, 200)
        knowledge = approve_response.json()["knowledge"]
        self.assertEqual(knowledge["caffeine"], 0.0)
        self.assertEqual(knowledge["baseSugar"], 16.0)
        self.assertIn("sugar_only", knowledge["source"])

    def test_partial_evidence_merges_by_scaling_to_existing_volume(self):
        caffeine_response = self.client.post("/api/knowledge/acquisition/image/import", json={
            "source_type": "image_upload",
            "items": [{
                "brand": "TestBrand",
                "name": "Test Merge Drink",
                "type": "coffee",
                "volume": 500,
                "caffeine": 150,
                "sugar": None,
                "confidence": 0.7,
                "raw_evidence": "Test Merge Drink volume 500ml caffeine 150mg",
            }],
        })
        self.assertEqual(caffeine_response.status_code, 200)
        caffeine_evidence = caffeine_response.json()["staged"][0]["evidence"]
        first_approve = self.client.post(f"/api/knowledge/acquisition/evidence/{caffeine_evidence['id']}/approve")
        self.assertEqual(first_approve.status_code, 200)
        first_knowledge = first_approve.json()["knowledge"]

        sugar_response = self.client.post("/api/knowledge/acquisition/image/import", json={
            "source_type": "image_upload",
            "items": [{
                "brand": "TestBrand",
                "name": "Test Merge Drink",
                "type": "coffee",
                "volume": 650,
                "caffeine": None,
                "sugar": 26,
                "confidence": 0.7,
                "raw_evidence": "Test Merge Drink volume 650ml sugar 26g",
            }],
        })
        self.assertEqual(sugar_response.status_code, 200)
        sugar_evidence = sugar_response.json()["staged"][0]["evidence"]
        second_approve = self.client.post(f"/api/knowledge/acquisition/evidence/{sugar_evidence['id']}/approve")
        self.assertEqual(second_approve.status_code, 200)
        merged = second_approve.json()["knowledge"]

        self.assertEqual(merged["id"], first_knowledge["id"])
        self.assertEqual(merged["volume"], 500)
        self.assertEqual(merged["caffeine"], 150.0)
        self.assertEqual(merged["baseSugar"], 20.0)
        self.assertIn("caffeine_sugar", merged["source"])

    def test_bulk_delete_evidence_hides_rows(self):
        response = self.client.post("/api/knowledge/acquisition/image/import", json={
            "source_type": "image_upload",
            "items": [{
                "brand": "TestBrand",
                "name": "Test Image Latte",
                "type": "coffee",
                "volume": 500,
                "caffeine": 88,
                "sugar": 12,
                "confidence": 0.72,
                "raw_evidence": "Test Image Latte bulk delete 500ml caffeine 88mg sugar 12g",
            }],
        })

        self.assertEqual(response.status_code, 200)
        evidence_id = response.json()["staged"][0]["evidence"]["id"]
        delete_response = self.client.post("/api/knowledge/acquisition/evidence/bulk/delete", json={
            "ids": [evidence_id],
        })
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["deleted"], 1)

        list_response = self.client.get("/api/knowledge/acquisition/evidence")
        listed_ids = [row["id"] for row in list_response.json()["evidence"]]
        self.assertNotIn(evidence_id, listed_ids)

    @patch("agents.knowledge_acquisition_agent.parse_candidate_from_text", return_value={
        "brand": "TestBrand",
        "name": "Test Discovery Latte",
        "type": "coffee",
    })
    @patch("agents.knowledge_acquisition_agent._robots_allowed", return_value={"allowed": True, "reason": "allowed"})
    @patch("agents.knowledge_acquisition_agent._fetch_public_page")
    @patch("agents.knowledge_acquisition_agent._safe_search")
    def test_autonomous_discovery_fetches_allowed_page_into_review_queue(
        self, mock_search, mock_fetch, _mock_robots, _mock_parse
    ):
        mock_search.return_value = [{
            "title": "Test Discovery Latte",
            "body": "official nutrition caffeine 120mg sugar 18g volume 500ml",
            "href": "https://example.com/test-discovery-latte",
        }]
        mock_fetch.return_value = {
            "ok": True,
            "url": "https://example.com/test-discovery-latte",
            "title": "Test Discovery Latte",
            "text": "Test Discovery Latte volume 500ml caffeine 120mg sugar 18g",
        }

        with patch.dict(os.environ, {"ENABLE_WEB_DISCOVERY": "true"}):
            response = self.client.post("/api/knowledge/acquisition/discover", json={
                "query": "Test Discovery Latte",
                "mode": "autonomous",
                "max_results": 1,
                "max_pages": 1,
            })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "autonomous")
        self.assertEqual(len(body["fetched_pages"]), 1)
        self.assertGreaterEqual(len(body["candidates"]), 1)
        self.assertGreaterEqual(len(body["evidence"]), 1)

    @patch("agents.knowledge_acquisition_agent.extract_items_from_text", return_value=[{
        "brand": "TestBrand",
        "name": "Test Discovery Latte",
        "type": "coffee",
        "volume": 500,
        "caffeine": 132,
        "sugar": 15,
        "raw_evidence": "LLM extracted Test Discovery Latte volume 500ml caffeine 132mg sugar 15g",
        "confidence": 0.72,
        "extraction_method": "llm_text",
    }])
    @patch("agents.knowledge_acquisition_agent._safe_search")
    def test_safe_discovery_can_stage_llm_extracted_text_items(self, mock_search, _mock_extract):
        mock_search.return_value = [{
            "title": "Test Discovery Latte nutrition",
            "body": "The page includes product nutrition details.",
            "href": "https://example.com/test-discovery-latte-llm",
        }]

        with patch.dict(os.environ, {"ENABLE_WEB_DISCOVERY": "true"}):
            response = self.client.post("/api/knowledge/acquisition/discover", json={
                "query": "Test Discovery Latte nutrition",
                "mode": "safe",
                "max_results": 1,
            })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["mode"], "safe")
        self.assertEqual(body["candidates"][0]["discovery_method"], "safe_search_metadata:llm_text")
        self.assertEqual(body["evidence"][0]["extracted"]["caffeine"], 132.0)
        self.assertEqual(body["evidence"][0]["extracted"]["sugar"], 15.0)

    @patch("agents.knowledge_acquisition_agent._safe_search", return_value=[])
    def test_discovery_reports_empty_search_diagnostics(self, _mock_search):
        with patch.dict(os.environ, {"ENABLE_WEB_DISCOVERY": "true"}):
            response = self.client.post("/api/knowledge/acquisition/discover", json={
                "query": "No Result Drink",
                "mode": "autonomous",
                "max_results": 1,
                "max_pages": 1,
            })

        self.assertEqual(response.status_code, 200)
        errors = response.json()["errors"]
        self.assertTrue(any(error["error"] == "search_returned_no_results" for error in errors))


if __name__ == "__main__":
    unittest.main()
