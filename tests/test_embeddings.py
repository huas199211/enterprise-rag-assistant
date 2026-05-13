import math
import unittest

from app.embeddings import _local_embed_text, tokenize


class EmbeddingsTest(unittest.TestCase):
    def test_tokenize_expands_chinese_bigrams(self) -> None:
        tokens = tokenize("差旅报销")

        self.assertIn("差旅报销", tokens)
        self.assertIn("差旅", tokens)
        self.assertIn("旅报", tokens)
        self.assertIn("报销", tokens)

    def test_local_embedding_uses_configured_dimensions_and_normalizes(self) -> None:
        vector = _local_embed_text("差旅报销需要审批", 32)

        self.assertEqual(32, len(vector))
        self.assertAlmostEqual(1.0, math.sqrt(sum(value * value for value in vector)), places=6)


if __name__ == "__main__":
    unittest.main()
