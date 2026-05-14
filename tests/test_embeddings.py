import unittest
from unittest.mock import patch

from app.embeddings import embed_text, tokenize


class EmbeddingsTest(unittest.TestCase):
    def test_tokenize_expands_chinese_bigrams(self) -> None:
        tokens = tokenize("差旅报销")

        self.assertIn("差旅报销", tokens)
        self.assertIn("差旅", tokens)
        self.assertIn("旅报", tokens)
        self.assertIn("报销", tokens)

    def test_embed_text_calls_api_and_returns_normalized_vector(self) -> None:
        config = {
            "embedding_model": "text-embedding-v3",
            "embedding_dimensions": 3,
            "embedding_base_url": "https://api.example.com/v1",
            "embedding_api_key": "test-key",
            "embedding_timeout_seconds": 10,
        }
        mock_response = {"data": [{"embedding": [3.0, 0.0, 4.0]}]}

        with (
            patch("app.embeddings._runtime_embedding_config", return_value=config),
            patch("app.embeddings.httpx.Client") as mock_client,
        ):
            mock_client.return_value.__enter__.return_value.post.return_value.json.return_value = mock_response
            mock_client.return_value.__enter__.return_value.post.return_value.raise_for_status.return_value = None
            vector = embed_text("差旅报销需要审批")

        self.assertEqual(len(vector), 3)
        norm = 5.0  # sqrt(3^2 + 0^2 + 4^2)
        self.assertEqual([0.6, 0.0, 0.8], vector)

    def test_embed_text_raises_on_dimension_mismatch(self) -> None:
        config = {
            "embedding_model": "text-embedding-v3",
            "embedding_dimensions": 3,
            "embedding_base_url": "https://api.example.com/v1",
            "embedding_api_key": "test-key",
            "embedding_timeout_seconds": 10,
        }
        mock_response = {"data": [{"embedding": [1.0, 2.0, 3.0, 4.0]}]}

        with (
            patch("app.embeddings._runtime_embedding_config", return_value=config),
            patch("app.embeddings.httpx.Client") as mock_client,
        ):
            mock_client.return_value.__enter__.return_value.post.return_value.json.return_value = mock_response
            mock_client.return_value.__enter__.return_value.post.return_value.raise_for_status.return_value = None
            with self.assertRaises(ValueError) as cm:
                embed_text("差旅报销需要审批")

        self.assertIn("维度不匹配", str(cm.exception))

    def test_embed_text_raises_on_missing_config(self) -> None:
        config = {
            "embedding_model": "text-embedding-v3",
            "embedding_dimensions": 3,
            "embedding_base_url": "",
            "embedding_api_key": "",
            "embedding_timeout_seconds": 10,
        }

        with patch("app.embeddings._runtime_embedding_config", return_value=config):
            with self.assertRaises(RuntimeError) as cm:
                embed_text("差旅报销需要审批")

        self.assertIn("未配置", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
