import unittest
import tempfile
import os
from src.database.db_manager import DatabaseManager

class TestDatabaseManager(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_reader.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_document_crud_and_position(self):
        doc = self.db.get_or_create_document(
            file_hash="abc123hash",
            file_path="/tmp/galois.pdf",
            title="Galois Theory",
            total_pages=42,
        )
        self.assertIsNotNone(doc["id"])
        self.assertEqual(doc["current_page"], 0)

        # Update position
        self.db.update_reading_position(doc["id"], current_page=15, zoom_level=1.25)
        updated_doc = self.db.get_document_by_hash("abc123hash")
        self.assertEqual(updated_doc["current_page"], 15)
        self.assertEqual(updated_doc["zoom_level"], 1.25)

    def test_bookmarks(self):
        doc = self.db.get_or_create_document(
            file_hash="hash456", file_path="/tmp/test.pdf", title="Test Doc", total_pages=10
        )
        bm_id = self.db.add_bookmark(doc["id"], page_number=5, label="Important Proof")
        bms = self.db.get_bookmarks(doc["id"])
        self.assertEqual(len(bms), 1)
        self.assertEqual(bms[0]["label"], "Important Proof")

        self.db.delete_bookmark(bm_id)
        self.assertEqual(len(self.db.get_bookmarks(doc["id"])), 0)

    def test_notes(self):
        doc = self.db.get_or_create_document(
            file_hash="hash789", file_path="/tmp/test2.pdf", title="Test Doc 2", total_pages=10
        )
        note_id = self.db.add_note(
            doc_id=doc["id"],
            page_number=2,
            note_text="Check equation 3",
            x=10.0,
            y=20.0,
            width=100.0,
            height=50.0,
        )
        notes = self.db.get_notes(doc["id"])
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["note_text"], "Check equation 3")
        self.assertEqual(notes[0]["x"], 10.0)

        self.db.update_note(note_id, "Check equation 3 (verified)")
        updated_notes = self.db.get_notes(doc["id"])
        self.assertEqual(updated_notes[0]["note_text"], "Check equation 3 (verified)")

        self.db.delete_note(note_id)
        self.assertEqual(len(self.db.get_notes(doc["id"])), 0)

    def test_highlights_and_study_lists(self):
        doc = self.db.get_or_create_document(
            file_hash="hashHL", file_path="/tmp/hermitian.pdf", title="Hermitian Matrix", total_pages=20
        )

        # Highlight CRUD
        hl_id = self.db.add_highlight(
            doc_id=doc["id"],
            page_number=6,
            rects=[[50.0, 100.0, 200.0, 120.0]],
            color="#FFF59D",
            style="highlight",
            selected_text="Hermitian matrix of second kind",
            comment_text="Key theorem for paper",
        )
        hls = self.db.get_highlights(doc["id"])
        self.assertEqual(len(hls), 1)
        self.assertEqual(hls[0]["selected_text"], "Hermitian matrix of second kind")
        self.assertEqual(hls[0]["comment_text"], "Key theorem for paper")

        # Study List CRUD
        sl_id = self.db.create_study_list("Linear Algebra Prep", "Notes for exam")
        self.db.add_document_to_study_list(sl_id, doc["id"])

        sl_docs = self.db.get_study_list_documents(sl_id)
        self.assertEqual(len(sl_docs), 1)
        self.assertEqual(sl_docs[0]["title"], "Hermitian Matrix")

        self.db.update_study_list_notes(sl_id, "# Notes\n$\\alpha + \\beta = 0$")
        notes_md = self.db.get_study_list_notes(sl_id)
        self.assertIn("\\alpha", notes_md)

if __name__ == "__main__":
    unittest.main()
