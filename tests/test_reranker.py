import unittest

from app.reranker import rerank_hits
from app.vector_store import SearchHit


class RerankerTest(unittest.TestCase):
    def test_local_rerank_adds_metadata_and_orders_hits(self) -> None:
        config = {
            "rerank_provider": "local",
            "rerank_original_score_weight": 0.5,
            "rerank_term_coverage_weight": 0.5,
        }
        hits = [
            SearchHit("a", "采购流程和供应商准入", 0.2, {}),
            SearchHit("b", "差旅申请需要填写出差目的和预算", 0.1, {}),
        ]

        reranked = rerank_hits("出差预算", hits, config)

        self.assertEqual("b", reranked[0].chunk_id)
        self.assertEqual("local", reranked[0].metadata["rerank"]["provider"])

    def test_remote_rerank_without_config_falls_back_to_local(self) -> None:
        config = {
            "rerank_provider": "remote",
            "rerank_base_url": "",
            "rerank_model": "BAAI/bge-reranker-v2-m3",
            "rerank_timeout_seconds": 30,
            "rerank_original_score_weight": 0.5,
            "rerank_term_coverage_weight": 0.5,
        }
        hits = [SearchHit("a", "差旅预算", 0.1, {})]

        reranked = rerank_hits("差旅预算", hits, config)

        self.assertEqual("local", reranked[0].metadata["rerank"]["provider"])


if __name__ == "__main__":
    unittest.main()
