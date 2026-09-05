import unittest
import tempfile
import os
from PySide6.QtWidgets import QApplication
from src.database.db_manager import DatabaseManager
from src.ui.library_view import LibraryView, DocumentListItemWidget

app = QApplication.instance() or QApplication([])

class TestLibraryView(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_lib.db")
        self.db = DatabaseManager(self.db_path)
        self.db.get_or_create_document(
            file_hash="hash123",
            file_path=os.path.join(self.tmp_dir.name, "sample.pdf"),
            title="Test Book Title",
            total_pages=50,
        )
        self.library_view = LibraryView(self.db)

    def tearDown(self):
        self.library_view.close()
        self.tmp_dir.cleanup()

    def test_document_list_item_widget(self):
        doc_data = {
            "file_path": os.path.join(self.tmp_dir.name, "sample.pdf"),
            "title": "Test Book Title",
            "current_page": 5,
            "total_pages": 50,
            "last_opened": "2026-09-05 05:00:00",
        }
        widget = DocumentListItemWidget(doc_data)
        self.assertIsNotNone(widget.title_label)
        self.assertEqual(widget.title_label.text(), "Test Book Title")

    def test_library_view_refresh(self):
        self.library_view.refresh_library()
        self.assertEqual(self.library_view.doc_list.count(), 1)
        item_widget = self.library_view.doc_list.itemWidget(self.library_view.doc_list.item(0))
        self.assertIsInstance(item_widget, DocumentListItemWidget)
        self.assertEqual(item_widget.title_label.text(), "Test Book Title")

if __name__ == "__main__":
    unittest.main()
