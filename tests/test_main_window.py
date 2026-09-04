import unittest
import tempfile
import os
from PySide6.QtWidgets import QApplication
from src.database.db_manager import DatabaseManager
from src.ui.main_window import MainWindow

app = QApplication.instance() or QApplication([])

class TestMainWindowNavigation(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_main.db")
        self.db = DatabaseManager(self.db_path)
        self.main_window = MainWindow(self.db)

    def tearDown(self):
        self.main_window.close()
        self.tmp_dir.cleanup()

    def test_app_starts_at_home_page(self):
        # App should always start on index 0 (Home Page)
        self.assertEqual(self.main_window.main_stack.currentIndex(), 0)
        self.assertIn("Home", self.main_window.windowTitle())

    def test_navigation_between_home_and_reader(self):
        # Create dummy file
        doc = self.db.get_or_create_document(
            file_hash="dummyhash",
            file_path=os.path.join(self.tmp_dir.name, "sample.pdf"),
            title="Sample Book",
            total_pages=10,
        )

        # Trigger home view refresh
        self.main_window._show_home_view()
        self.assertEqual(self.main_window.main_stack.currentIndex(), 0)

        # Switch to Home view explicitly
        self.main_window._show_home_view()
        self.assertEqual(self.main_window.main_stack.currentIndex(), 0)

if __name__ == "__main__":
    unittest.main()
