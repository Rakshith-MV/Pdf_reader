import unittest
import tempfile
import os
from PySide6.QtWidgets import QApplication
from src.database.db_manager import DatabaseManager
from src.ui.focus_widget import FocusDashboardWidget

app = QApplication.instance() or QApplication([])

class TestFocusDashboard(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_focus.db")
        self.db = DatabaseManager(self.db_path)
        self.widget = FocusDashboardWidget(self.db)

    def tearDown(self):
        self.widget.close()
        self.tmp_dir.cleanup()

    def test_log_focus_session_and_stats(self):
        sl_id = self.db.create_study_list("Mathematics")
        self.db.log_focus_session(sl_id, 25)

        stats = self.db.get_focus_stats()
        self.assertEqual(stats["today_minutes"], 25)
        self.assertEqual(stats["study_list_minutes"].get(sl_id), 25)

    def test_focus_widget_initialization(self):
        self.assertIsNotNone(self.widget.card_timer)
        self.assertIsNotNone(self.widget.card_progress)
        self.assertIsNotNone(self.widget.card_tasks)

if __name__ == "__main__":
    unittest.main()
