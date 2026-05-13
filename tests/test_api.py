import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


class ApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_get_config_returns_runtime_config(self) -> None:
        config = {"top_k": 5, "min_score": 0.08, "rerank_provider": "local"}

        with patch("app.api.routes.get_runtime_config", return_value=config):
            response = self.client.get("/api/config")

        self.assertEqual(200, response.status_code)
        self.assertEqual(config, response.json())

    def test_save_config_rejects_invalid_chunk_overlap(self) -> None:
        response = self.client.post("/api/config", json={"chunk_size": 500, "chunk_overlap": 500})

        self.assertEqual(400, response.status_code)
        self.assertIn("片段重叠长度必须小于片段长度", response.json()["detail"])

    def test_save_config_updates_runtime_config(self) -> None:
        updated = {"top_k": 8, "rerank": True}

        with patch("app.api.routes.update_runtime_config", return_value=updated) as update_runtime_config:
            response = self.client.post("/api/config", json=updated)

        self.assertEqual(200, response.status_code)
        self.assertEqual(updated, response.json())
        update_runtime_config.assert_called_once_with(updated)

    def test_chat_returns_answer_payload(self) -> None:
        answer_question = AsyncMock(
            return_value={
                "conversation_id": "c1",
                "message_id": "m1",
                "answer": "根据制度，需要提交差旅申请。",
                "sources": [],
                "latency_ms": 12,
                "min_score": 0.08,
            }
        )

        with patch("app.api.routes.answer_question", answer_question):
            response = self.client.post("/api/chat", json={"question": "出差前需要提交什么？"})

        self.assertEqual(200, response.status_code)
        self.assertEqual("根据制度，需要提交差旅申请。", response.json()["answer"])
        answer_question.assert_awaited_once()

    def test_upload_document_returns_ingest_result(self) -> None:
        ingest_upload = AsyncMock(return_value={"document_id": 1, "filename": "制度.txt", "chunk_count": 1, "status": "indexed"})

        with patch("app.api.routes.ingest_upload", ingest_upload):
            response = self.client.post(
                "/api/documents/upload",
                files={"file": ("制度.txt", b"test", "text/plain")},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("indexed", response.json()["status"])
        ingest_upload.assert_awaited_once()

    def test_list_documents_returns_repository_items(self) -> None:
        documents = [{"id": 1, "filename": "制度.txt", "status": "indexed"}]

        with patch("app.api.routes.list_documents_repository", return_value=documents):
            response = self.client.get("/api/documents")

        self.assertEqual(200, response.status_code)
        self.assertEqual(documents, response.json())

    def test_reindex_document_returns_result(self) -> None:
        result = {"document_id": 1, "filename": "制度.txt", "chunk_count": 2, "status": "indexed"}

        with patch("app.api.routes.reindex_document", return_value=result):
            response = self.client.post("/api/documents/1/reindex")

        self.assertEqual(200, response.status_code)
        self.assertEqual(result, response.json())

    def test_feedback_creates_record(self) -> None:
        with patch("app.api.routes.create_feedback") as create_feedback:
            response = self.client.post("/api/feedback", json={"message_id": "m1", "rating": "up", "comment": "准确"})

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True}, response.json())
        create_feedback.assert_called_once_with("m1", "up", "准确")

    def test_logs_returns_repository_items(self) -> None:
        logs = [{"id": "m1", "question": "问题", "answer": "答案", "sources": []}]

        with patch("app.api.routes.list_message_logs", return_value=logs) as list_message_logs:
            response = self.client.get("/api/logs?limit=10")

        self.assertEqual(200, response.status_code)
        self.assertEqual(logs, response.json())
        list_message_logs.assert_called_once_with(10)

    def test_evaluate_returns_metrics(self) -> None:
        run_evaluation = AsyncMock(
            return_value={
                "count": 35,
                "avg_keyword_score": 0.9,
                "avg_source_keyword_score": 0.8,
                "retrieval_hit_rate": 1.0,
                "refusal_rate": 0.1,
                "p95_latency_ms": 3000,
                "latency_ms": 5000,
                "results": [],
            }
        )

        with patch("app.api.routes.run_evaluation", run_evaluation):
            response = self.client.post("/api/evaluate")

        self.assertEqual(200, response.status_code)
        self.assertEqual(35, response.json()["count"])
        run_evaluation.assert_awaited_once()

if __name__ == "__main__":
    unittest.main()
