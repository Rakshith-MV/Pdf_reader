import unittest
import time
from src.reader.performance_metrics import PerformanceMetrics


class TestPerformanceMetrics(unittest.TestCase):

    def setUp(self):
        self.metrics = PerformanceMetrics()

    def test_cache_hit_rate(self):
        self.assertEqual(self.metrics.image_cache_hit_rate, 0.0)
        self.metrics.record_cache_hit()
        self.metrics.record_cache_hit()
        self.metrics.record_cache_miss()
        self.assertAlmostEqual(self.metrics.image_cache_hit_rate, 66.67, places=1)

    def test_scroll_event_timing(self):
        self.metrics.record_scroll_event(10.0)
        self.metrics.record_scroll_event(20.0)
        self.assertEqual(self.metrics.avg_scroll_time_ms, 15.0)

    def test_summary_dictionary(self):
        self.metrics.start_document_load()
        time.sleep(0.01)
        self.metrics.mark_first_page_rendered()
        summary = self.metrics.get_summary()
        self.assertIn("time_to_first_page_ms", summary)
        self.assertGreater(summary["time_to_first_page_ms"], 0)


if __name__ == "__main__":
    unittest.main()
