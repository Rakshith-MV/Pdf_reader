import unittest
from src.ui.viewer_widget import PageLayoutModel


class TestVirtualLayout(unittest.TestCase):

    def test_layout_calculation_and_zoom(self):
        page_sizes = [(600.0, 800.0)] * 300  # 300-page document
        layout = PageLayoutModel(page_sizes, spacing=20, margin_x=30)
        layout.update_zoom(1.0, viewport_width=1000)

        self.assertEqual(len(layout.page_rects), 300)
        self.assertEqual(layout.page_rects[0].top(), 20)
        self.assertEqual(layout.page_rects[0].height(), 800)
        self.assertEqual(layout.page_rects[1].top(), 840)  # 20 + 800 + 20

        # Total document height
        expected_total = 300 * (800 + 20) + 20
        self.assertEqual(layout.total_height, expected_total)

    def test_visible_range_with_overscan(self):
        page_sizes = [(600.0, 800.0)] * 300
        layout = PageLayoutModel(page_sizes, spacing=20, margin_x=30)
        layout.update_zoom(1.0, viewport_width=1000)

        # Viewport at scroll_y=0, height=1000, overscan=1000px
        # Covers Y range 0 to 2000px -> Pages 0, 1, 2
        first_idx, last_idx = layout.get_visible_range(scroll_y=0, viewport_h=1000, overscan_px=1000)

        self.assertEqual(first_idx, 0)
        self.assertLessEqual(last_idx, 5)
        # Verify range count is tiny (~3-6 pages out of 300)
        self.assertLess(last_idx - first_idx + 1, 10)


if __name__ == "__main__":
    unittest.main()
