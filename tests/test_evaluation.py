import unittest

from app.evaluation import _average, _citation_accuracy, _group_summary, _infer_question_type, _percentile, _ratio


class EvaluationMetricsTest(unittest.TestCase):
    def test_ratio_handles_empty_denominator(self) -> None:
        self.assertEqual(0.0, _ratio(3, 0))

    def test_average_handles_empty_values(self) -> None:
        self.assertEqual(0.0, _average([]))
        self.assertEqual(2.0, _average([1, 2, 3]))

    def test_percentile_handles_empty_and_single_value(self) -> None:
        self.assertEqual(0, _percentile([], 95))
        self.assertEqual(120, _percentile([120], 95))

    def test_percentile_returns_integer_latency(self) -> None:
        self.assertIsInstance(_percentile([100, 200, 300, 400, 500], 95), int)

    def test_citation_accuracy_checks_source_range(self) -> None:
        self.assertEqual(1.0, _citation_accuracy("答案 [来源1]", 1))
        self.assertEqual(0.0, _citation_accuracy("答案 [来源2]", 1))

    def test_infer_question_type(self) -> None:
        self.assertEqual("标准查询", _infer_question_type("住宿标准是多少？"))
        self.assertEqual("规则判断", _infer_question_type("是否可以报销？"))

    def test_group_summary_aggregates_metrics(self) -> None:
        summary = _group_summary(
            [
                {"type": "规则判断", "keyword_score": 1.0, "source_keyword_score": 1.0, "citation_accuracy": 1.0, "is_refusal": False},
                {"type": "规则判断", "keyword_score": 0.0, "source_keyword_score": 0.5, "citation_accuracy": 1.0, "is_refusal": True},
            ]
        )

        self.assertEqual(2, summary["规则判断"]["count"])
        self.assertEqual(0.5, summary["规则判断"]["avg_keyword_score"])


if __name__ == "__main__":
    unittest.main()
