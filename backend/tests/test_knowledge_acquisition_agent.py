import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

import main
from knowledge.knowledge_acquisition_agent import is_allowed_source, normalize_image_items, normalize_type
from db.database import DrinkKnowledge, NutritionEvidence, ProductCandidate, SessionLocal


class KnowledgeAcquisitionAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._previous_enable_llm = os.environ.get("ENABLE_LLM")
        os.environ["ENABLE_LLM"] = "false"
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        if cls._previous_enable_llm is None:
            os.environ.pop("ENABLE_LLM", None)
        else:
            os.environ["ENABLE_LLM"] = cls._previous_enable_llm

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
                    or "Test Text Latte" in row.raw_evidence
                    or "Test Text Tea" in row.raw_evidence
                    or "生椰拿铁" in row.raw_evidence
                ):
                    db.delete(row)
            for row in db.query(ProductCandidate).filter(
                ProductCandidate.name.in_([
                    "Test Acquisition Latte",
                    "Test Image Latte",
                    "Test Caffeine Only Americano",
                    "Test Sugar Only Tea",
                    "Test Merge Drink",
                    "Test Text Latte",
                    "Test Text Tea",
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
                    "Test Text Latte",
                    "Test Text Tea",
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
                "raw_evidence": "Test Image Latte 500ml caffeine 88mg sugar 12g",
            }],
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["staged"][0]["candidate"]["name"], "Test Image Latte")
        self.assertEqual(body["staged"][0]["evidence"]["extracted"]["caffeine"], 88.0)
        self.assertEqual(body["staged"][0]["evidence"]["extracted"]["sugar"], 12.0)

    def test_image_items_use_context_and_range_midpoints(self):
        items = normalize_image_items([{
            "brand": None,
            "name": "\u4e94\u5e38\u7c73\u4e73\u62ff\u94c1",
            "type": "milktea",
            "volume": None,
            "caffeine": "100 - 180 mg",
            "sugar": "10 - 15 g",
        }], context_text="\u56fe\u4e2d\u996e\u54c1\u90fd\u662f\u5e93\u8fea\u5496\u5561\uff0c\u7ea6 450ml")

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["brand"], "\u5e93\u8fea\u5496\u5561")
        self.assertEqual(item["type"], "coffee")
        self.assertEqual(item["volume"], 450.0)
        self.assertEqual(item["caffeine"], 140.0)
        self.assertEqual(item["sugar"], 12.5)
        self.assertEqual(item["caffeine_range"], {"min": 100.0, "max": 180.0})
        self.assertEqual(item["sugar_range"], {"min": 10.0, "max": 15.0})
        self.assertTrue(any("\u54c1\u724c\u6765\u81ea\u4e0a\u4e0b\u6587" in note for note in item["normalization_notes"]))

    def test_model_type_is_corrected_for_latte_names(self):
        self.assertEqual(normalize_type("milktea", "\u4e94\u5e38\u7c73\u4e73\u62ff\u94c1"), "coffee")
        self.assertEqual(normalize_type("milktea", "\u751f\u6930\u62ff\u94c1"), "coffee")
        self.assertEqual(normalize_type("coffee", "\u73cd\u73e0\u5976\u8336"), "milktea")
        self.assertEqual(normalize_type("coffee", "\u67e0\u6aac\u679c\u8336"), "fruittea")

    def test_coconut_and_ambiguous_ice_drinks_are_classified(self):
        self.assertEqual(normalize_type("soda", "\u5de7\u514b\u529b\u5e93\u53ef\u51b0"), "other")
        self.assertEqual(normalize_type("soda", "\u751f\u6930\u62ff\u94c1\u5e93\u53ef\u51b0"), "coffee")
        self.assertEqual(normalize_type("soda", "\u8292\u8292\u751f\u6253\u6930\u5e93\u53ef\u51b0"), "fruittea")
        self.assertEqual(normalize_type("soda", "\u62b9\u8336\u8309\u9999\u5e93\u53ef\u51b0"), "tea")
        self.assertEqual(normalize_type("soda", "\u6d77\u5c9b\u6930\u6930\u5e93\u53ef\u51b0"), "fruittea")
        self.assertEqual(normalize_type("soda", "\u67da\u89c1\u8309\u8389\u5e93\u53ef\u51b0"), "fruittea")

    def test_inequality_nutrition_values_are_preserved(self):
        items = normalize_image_items([{
            "brand": "\u5e93\u8fea\u5496\u5561",
            "name": "\u5de7\u514b\u529b\u5e93\u53ef\u51b0",
            "type": "soda",
            "caffeine": "< 10 (\u53ef\u53ef\u5fae\u91cf)",
            "sugar": "30+ (\u6781\u9ad8)",
        }])

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["type"], "other")
        self.assertEqual(item["caffeine"], 10.0)
        self.assertEqual(item["sugar"], 30.0)
        self.assertTrue(any("\u5496\u5561\u56e0\u539f\u503c" in note for note in item["normalization_notes"]))
        self.assertTrue(any("\u7cd6\u5206\u539f\u503c" in note for note in item["normalization_notes"]))

    def test_pasted_text_agent_returns_review_items(self):
        response = self.client.post("/api/knowledge/acquisition/text/analyze", json={
            "source_type": "manual_text",
            "text": (
                "品牌: TestBrand 名称: Test Text Latte 容量 500ml 咖啡因 120mg 糖分 18g\n"
                "品牌: TestBrand 名称: Test Text Tea 容量 500ml 咖啡因 30mg 糖分 6g"
            ),
        })

        self.assertEqual(response.status_code, 200)
        body = response.json()
        names = [item["name"] for item in body["items"]]
        self.assertIn("Test Text Latte", names)
        self.assertIn("Test Text Tea", names)
        latte = next(item for item in body["items"] if item["name"] == "Test Text Latte")
        self.assertEqual(latte["brand"], "TestBrand")
        self.assertEqual(latte["volume"], 500.0)
        self.assertEqual(latte["caffeine"], 120.0)
        self.assertEqual(latte["sugar"], 18.0)

    def test_pasted_text_items_can_be_staged(self):
        analyze_response = self.client.post("/api/knowledge/acquisition/text/analyze", json={
            "text": "品牌: TestBrand 名称: Test Text Latte 容量 500ml 咖啡因 120mg 糖分 18g",
        })
        self.assertEqual(analyze_response.status_code, 200)

        stage_response = self.client.post("/api/knowledge/acquisition/image/import", json={
            "source_type": "manual_text",
            "items": analyze_response.json()["items"],
        })

        self.assertEqual(stage_response.status_code, 200)
        body = stage_response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["staged"][0]["candidate"]["name"], "Test Text Latte")
        self.assertEqual(body["staged"][0]["evidence"]["extracted"]["caffeine"], 120.0)

    def test_pasted_markdown_table_returns_product_rows(self):
        text = """
        ### 库迪咖啡常见饮品咖啡因与糖分一览表
        *(注：以下每杯含量估算基于大杯（约 450ml），且均以“不额外加糖”作为默认基准)*

        | 饮品品类 / 名字 | 咖啡因含量 (毫克/杯) | 糖分含量 (克/杯) | 热量 (千卡) | 数据解析与来源说明 |
        | :--- | :--- | :--- | :--- | :--- |
        | **经典美式 / 铂金精品美式** | **150 - 200 mg** <br>(平均值约 170mg) | **0 g** | **10 - 15 kcal** | 纯咖啡 |
        | **生椰拿铁** | **150 - 180 mg** | **15 - 25 g** <br>(来自椰乳自带糖分) | **240 - 350 kcal** | 椰乳自带糖 |
        | **太妃丝滑拿铁 / 榛果拿铁**| **120 - 150 mg** | **18 - 28 g** | **约 200 - 230 kcal**| 含调味糖浆 |
        """
        response = self.client.post("/api/knowledge/acquisition/text/analyze", json={"text": text})

        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        by_name = {item["name"]: item for item in items}
        self.assertIn("经典美式", by_name)
        self.assertIn("铂金精品美式", by_name)
        self.assertIn("生椰拿铁", by_name)
        self.assertEqual(by_name["经典美式"]["brand"], "库迪咖啡")
        self.assertEqual(by_name["经典美式"]["volume"], 450.0)
        self.assertEqual(by_name["经典美式"]["caffeine"], 170.0)
        self.assertEqual(by_name["经典美式"]["sugar"], 0.0)
        self.assertEqual(by_name["生椰拿铁"]["caffeine"], 165.0)
        self.assertEqual(by_name["生椰拿铁"]["sugar"], 20.0)

    def test_pasted_tabular_text_with_wrapped_cells_returns_product_rows(self):
        text = """由于库迪国内官方未提供统一的营养成分计算器，以下数据综合估算：

库迪咖啡常见饮品咖啡因与糖分一览表
(注：以下每杯含量估算基于大杯（约 450ml），且均以“不额外加糖”作为默认基准)

饮品品类 / 名字	咖啡因含量 (毫克/杯)	糖分含量 (克/杯)	热量 (千卡)	数据解析与来源说明
经典美式 / 铂金精品美式	150 - 200 mg
(平均值约 170mg)	0 g	10 - 15 kcal	符合无糖标准。
经典拿铁	120 - 160 mg
(平均值约 140mg)	8 - 12 g
(全为牛奶中天然乳糖)	170 - 196 kcal	默认不加糖，但牛奶自带乳糖。
生椰拿铁	150 - 180 mg	15 - 25 g
(来自椰乳自带糖分)	240 - 350 kcal	椰乳自带糖。
柚见美式 / 香柠美式	100 - 150 mg	12 - 20 g
(来自柚子糖浆/果汁)	80 - 100 kcal	柚子酱/柠檬糖浆含糖。
"""
        response = self.client.post("/api/knowledge/acquisition/text/analyze", json={"text": text})

        self.assertEqual(response.status_code, 200)
        by_name = {item["name"]: item for item in response.json()["items"]}
        self.assertIn("经典美式", by_name)
        self.assertIn("铂金精品美式", by_name)
        self.assertIn("经典拿铁", by_name)
        self.assertIn("柚见美式", by_name)
        self.assertIn("香柠美式", by_name)
        self.assertEqual(by_name["经典美式"]["brand"], "库迪咖啡")
        self.assertEqual(by_name["经典美式"]["volume"], 450.0)
        self.assertEqual(by_name["经典美式"]["caffeine"], 170.0)
        self.assertEqual(by_name["经典拿铁"]["caffeine"], 140.0)
        self.assertEqual(by_name["经典拿铁"]["sugar"], 10.0)
        self.assertEqual(by_name["柚见美式"]["sugar"], 16.0)

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

if __name__ == "__main__":
    unittest.main()
