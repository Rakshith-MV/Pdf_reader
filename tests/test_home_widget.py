import unittest
import tempfile
import os
from PySide6.QtWidgets import QApplication
from src.database.db_manager import DatabaseManager
from src.ui.home_widget import HomeWidget, BookCardWidget

app = QApplication.instance() or QApplication([])

class TestHomeWidget(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_home.db")
        self.db = DatabaseManager(self.db_path)

        # Create dummy documents
        self.doc1 = self.db.get_or_create_document(
            file_hash="hash1",
            file_path=os.path.join(self.tmp_dir.name, "math.pdf"),
            title="Mathematica Secret World",
            total_pages=150,
        )
        self.doc2 = self.db.get_or_create_document(
            file_hash="hash2",
            file_path=os.path.join(self.tmp_dir.name, "sherlock.pdf"),
            title="Adventures of Sherlock Holmes",
            total_pages=300,
        )

        # Create a study list
        self.sl_id = self.db.create_study_list("Study List 1", "My initial list")
        self.db.add_document_to_study_list(self.sl_id, self.doc1["id"])

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_book_card_widget(self):
        card = BookCardWidget(self.doc1)
        self.assertEqual(card.title_label.text(), "Mathematica Secret World")
        self.assertIn("p. 1/150", card.meta_label.text())

    def test_home_widget_rendering_and_filtering(self):
        home = HomeWidget(self.db)
        home.refresh_home()

        # Check stats text
        self.assertIn("2 Books", home.lbl_stats.text())
        self.assertIn("1 Study Lists", home.lbl_stats.text())

        # Test filtering
        home.search_input.setText("Sherlock")
        visible_cards = [c for c in home.all_card_widgets if c.isVisible()]
        self.assertTrue(all("Sherlock" in c.doc_data["title"] for c in visible_cards))

if __name__ == "__main__":
    unittest.main()
