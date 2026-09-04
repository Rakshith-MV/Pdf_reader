import unittest
import tempfile
import os
import pymupdf as fitz
from PySide6.QtWidgets import QApplication
from src.reader.document import DocumentReader

app = QApplication.instance() or QApplication([])

class TestDocumentReader(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.pdf_path = os.path.join(self.tmp_dir.name, "sample.pdf")

        doc = fitz.open()
        page1 = doc.new_page(width=600, height=800)
        page1.insert_text((50, 100), "Hello ReadEra Desktop Reader", fontsize=18)
        page1.insert_text((50, 150), "Galois Theory Notes on Page 1", fontsize=14)

        page2 = doc.new_page(width=600, height=800)
        page2.insert_text((50, 100), "Page 2 text content with Galois Theory", fontsize=14)

        doc.set_toc([[1, "Chapter 1", 1], [1, "Chapter 2", 2]])
        doc.save(self.pdf_path)
        doc.close()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_reader_properties_and_rendering(self):
        reader = DocumentReader(self.pdf_path)
        try:
            self.assertEqual(reader.total_pages, 2)

            # Test TOC
            toc = reader.get_toc()
            self.assertEqual(len(toc), 2)
            self.assertEqual(toc[0][1], "Chapter 1")

            # Test High-DPI Page Rendering & Themes
            pixmap = reader.render_page(0, zoom=1.0, theme="sepia")
            self.assertFalse(pixmap.isNull())
            self.assertGreater(pixmap.width(), 0)

            # Test Word Extraction for text selection
            words = reader.get_words(0)
            self.assertGreater(len(words), 0)

            # Test Search
            results = reader.search_all_pages("Galois")
            self.assertEqual(len(results), 2)
        finally:
            reader.close()

if __name__ == "__main__":
    unittest.main()
