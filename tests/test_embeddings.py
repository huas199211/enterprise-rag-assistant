import math
import unittest
from unittest.mock import Mock, patch

from app.embeddings import _extract_dense_vector, _hash_embed_text, embed_text, tokenize


class EmbeddingsTest(unittest.TestCase):
    def test_tokenize_expands_chinese_bigrams(self) -> None:
        tokens = tokenize("差旅报销")

        self.assertIn("差旅报销", tokens)
        self.assertIn("差旅", tokens)
        self.assertIn("旅报", tokens)
        self.assertIn("报销", tokens)

    def test_hash_embedding_uses_configured_dimensions_and_normalizes(self) -> None:
        vector = _hash_embed_text("差旅报销需要审批", 32)

        self.assertEqual(32, len(vector))
        self.assertAlmostEqual(1.0, math.sqrt(sum(value * value for value in vector)), places=6)

    def test_local_provider_uses_bge_m3_dense_embedding(self) -> None:
        model = Mock()
        model.encode.return_value = {"dense_vecs": [[3, 4, 0]]}
        config = {
            "embedding_provider": "local",
            "embedding_model": "BAAI/bge-m3",
            "embedding_dimensions": 3,
            "embedding_timeout_seconds": 60,
            "bge_m3_use_fp16": False,
            "bge_m3_batch_size": 12,
            "bge_m3_max_length": 8192,
        }

        with patch("app.embeddings._runtime_embedding_config", return_value=config), patch("app.embeddings._load_bge_m3_model", return_value=model):
            vector = embed_text("差旅报销需要审批")

        self.assertEqual([0.6, 0.8, 0.0], vector)
        model.encode.assert_called_once_with(
            ["差旅报销需要审批"],
            batch_size=12,
            max_length=8192,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )

    def test_extract_dense_vector_accepts_single_vector_shape(self) -> None:
        self.assertEqual([1.0, 2.0, 3.0], _extract_dense_vector({"dense_vecs": [1, 2, 3]}))


if __name__ == "__main__":
    unittest.main()
