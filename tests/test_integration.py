import os
import unittest

from app.db import get_runtime_config, init_db
from app.vector_store import VectorStore


RUN_INTEGRATION_TESTS = os.environ.get("RUN_INTEGRATION_TESTS") == "1"


@unittest.skipUnless(RUN_INTEGRATION_TESTS, "设置 RUN_INTEGRATION_TESTS=1 后运行真实 PostgreSQL/Qdrant 集成测试")
class IntegrationTest(unittest.TestCase):
    def test_database_runtime_config_can_load(self) -> None:
        init_db()
        config = get_runtime_config()

        self.assertIn("top_k", config)
        self.assertIn("rerank_provider", config)

    def test_qdrant_vector_roundtrip(self) -> None:
        store = VectorStore()
        document_id = 999999
        chunk_id = f"doc-{document_id}-chunk-0"

        try:
            store.add(
                chunk_id,
                "集成测试文档：差旅申请需要填写出差目的和预算。",
                {"document_id": document_id, "filename": "integration-test.txt", "chunk_index": 0},
            )
            hits = store.search("差旅预算", top_k=3, rerank=True, document_ids=[document_id])
            self.assertTrue(any(hit.chunk_id == chunk_id for hit in hits))
        finally:
            store.delete_document(document_id)


if __name__ == "__main__":
    unittest.main()
