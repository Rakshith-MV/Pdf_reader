import unittest
import time
from PySide6.QtWidgets import QApplication
from src.reader.render_coordinator import RenderCoordinator, RenderRequest

app = QApplication.instance() or QApplication(list())


class TestRenderCoordinator(unittest.TestCase):

    def setUp(self):
        self.coordinator = RenderCoordinator()
        self.coordinator.start()

    def tearDown(self):
        self.coordinator.stop()

    def test_priority_queue_ordering(self):
        req_prio1 = RenderRequest(1, 0, 1.0, "day", 1.0, 1, priority=1, seq=1)
        req_prio3 = RenderRequest(1, 5, 1.0, "day", 1.0, 1, priority=3, seq=2)
        req_prio2 = RenderRequest(1, 2, 1.0, "day", 1.0, 1, priority=2, seq=3)

        self.coordinator.req_queue.put(req_prio3)
        self.coordinator.req_queue.put(req_prio1)
        self.coordinator.req_queue.put(req_prio2)

        first_out = self.coordinator.req_queue.get()
        second_out = self.coordinator.req_queue.get()
        third_out = self.coordinator.req_queue.get()

        self.assertEqual(first_out.priority, 1)
        self.assertEqual(second_out.priority, 2)
        self.assertEqual(third_out.priority, 3)

    def test_stale_generation_id(self):
        self.coordinator.set_generation_id(5)
        # Request with generation_id 2 should be rejected
        self.coordinator.request_page_render(0, 1.0, "day", 1.0, generation_id=2, priority=1)
        self.assertEqual(self.coordinator.req_queue.qsize(), 0)

    def test_duplicate_render_request_is_coalesced(self):
        coordinator = RenderCoordinator()
        coordinator.set_generation_id(5)
        coordinator.request_page_render(0, 1.0, "day", 1.0, generation_id=5, priority=1)
        coordinator.request_page_render(0, 1.0, "day", 1.0, generation_id=5, priority=1)
        self.assertEqual(coordinator.req_queue.qsize(), 1)


if __name__ == "__main__":
    unittest.main()
