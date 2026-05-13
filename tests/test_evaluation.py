import unittest

from app.evaluation import _average, _percentile, _ratio


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


if __name__ == "__main__":
    unittest.main()
