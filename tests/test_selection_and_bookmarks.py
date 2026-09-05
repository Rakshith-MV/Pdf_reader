import unittest
import tempfile
import os
from PySide6.QtCore import Qt, QPoint, QUrl
from PySide6.QtWidgets import QApplication
from src.database.db_manager import DatabaseManager
from src.ui.viewer_widget import PageCanvas
from src.ui.math_notes_editor import MathNotesEditor
from src.ui.sidebar_widget import SidebarWidget

app = QApplication.instance() or QApplication([])

class TestSelectionAndBookmarks(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_app.db")
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_linear_sequential_text_selection(self):
        canvas = PageCanvas(0)
        # Dummy words in reading order across 2 lines
        # Line 1: (y=10..20)
        # Line 2: (y=30..40)
        canvas.words = [
            (10.0, 10.0, 40.0, 20.0, "Word1"),
            (50.0, 10.0, 80.0, 20.0, "Word2"),
            (90.0, 10.0, 120.0, 20.0, "Word3"),
            (10.0, 30.0, 40.0, 40.0, "Word4"),
            (50.0, 30.0, 80.0, 40.0, "Word5"),
        ]
        canvas.zoom = 1.0

        # Drag from Word2 on line 1 down to Word4 on line 2
        canvas.select_start = QPoint(60, 15)  # Word2
        canvas.select_current = QPoint(20, 35) # Word4

        canvas._update_text_selection()

        # Selection must be linear/sequential from Word2 to Word4
        expected_text = "Word2 Word3 Word4"
        self.assertEqual(canvas.selected_text, expected_text)

    def test_bookmark_markdown_link(self):
        editor = MathNotesEditor(self.db)
        # Insert bookmark link for Page 5 (0-indexed 4)
        editor.insert_bookmark_link(4, "Theorem 1")

        plain_text = editor.editor.toPlainText()
        self.assertIn("[🔖 Theorem 1 (p. 5)](page:5)", plain_text)

        # Test anchor click handler
        jumped_pages = []
        editor.jump_to_page_requested.connect(lambda p: jumped_pages.append(p))

        editor._on_anchor_clicked(QUrl("page:5"))
        self.assertEqual(len(jumped_pages), 1)
        self.assertEqual(jumped_pages[0], 4)  # 0-indexed page 4

    def test_google_search_toolbar_button(self):
        from src.ui.viewer_widget import PDFViewerWidget
        viewer = PDFViewerWidget()
        viewer.active_selection = (0, "Markov Chains", [])

        # Check button exists on FloatingSelectionToolbar
        self.assertIsNotNone(viewer.toolbar.btn_google)
        self.assertEqual(viewer.toolbar.btn_google.text(), "🔍 Search Google")

        viewer.clear_selection_and_toolbar()
        self.assertIsNone(viewer.active_selection)

    def test_double_click_word_selection(self):
        canvas = PageCanvas(0)
        canvas.words = [
            (10.0, 10.0, 40.0, 20.0, "Hello"),
            (50.0, 10.0, 90.0, 20.0, "World."),
        ]
        canvas.zoom = 1.0
        canvas._select_word_at_pos(QPoint(60, 15))
        self.assertEqual(canvas.selected_text, "World.")

    def test_triple_click_sentence_selection(self):
        canvas = PageCanvas(0)
        canvas.words = [
            (10.0, 10.0, 40.0, 20.0, "First"),
            (50.0, 10.0, 90.0, 20.0, "sentence."),
            (100.0, 10.0, 140.0, 20.0, "Second"),
            (150.0, 10.0, 190.0, 20.0, "sentence."),
        ]
        canvas.zoom = 1.0
        canvas._select_sentence_at_pos(QPoint(25, 15))
        self.assertEqual(canvas.selected_text, "First sentence.")

        canvas._select_sentence_at_pos(QPoint(120, 15))
        self.assertEqual(canvas.selected_text, "Second sentence.")

    def test_timer_synchronization(self):
        from src.ui.focus_widget import FocusDashboardWidget
        from src.ui.bottom_bar import TopBarWidget

        focus_dash = FocusDashboardWidget(self.db)
        top_bar = TopBarWidget()

        focus_dash.timer_tick_signal.connect(top_bar.sync_timer_state)

        # Emit timer tick signal (15 mins left, total 15 mins, running, not paused)
        focus_dash.timer_tick_signal.emit(900, 900, True, False)
        self.assertEqual(top_bar.btn_timer.text(), "⏱️ 15:00")

        # Emit paused state
        focus_dash.timer_tick_signal.emit(900, 900, True, True)
        self.assertEqual(top_bar.btn_timer.text(), "⏸️ 15:00")

        # Emit stopped state
        focus_dash.timer_tick_signal.emit(0, 0, False, False)
        self.assertEqual(top_bar.btn_timer.text(), "⏱️ Timer")

        focus_dash.close()
        top_bar.close()

    def test_math_notes_editor_single_section_toggling(self):
        editor = MathNotesEditor(self.db)
        # Starts in preview mode (stack index 0)
        self.assertEqual(editor.stack.currentIndex(), 0)
        self.assertEqual(editor.btn_toggle_mode.text(), "✏️ Edit Notes")

        # Switch to edit mode
        editor.switch_to_edit_mode()
        self.assertEqual(editor.stack.currentIndex(), 1)
        self.assertEqual(editor.btn_toggle_mode.text(), "✓ Done (Render Math)")

        # Switch back to preview mode
        editor.switch_to_preview_mode()
        self.assertEqual(editor.stack.currentIndex(), 0)
        self.assertEqual(editor.btn_toggle_mode.text(), "✏️ Edit Notes")

    def test_page_canvas_context_menu_signals(self):
        canvas = PageCanvas(3)  # Page 4 (0-indexed 3)
        bm_emitted = []
        note_emitted = []
        canvas.bookmark_page_requested.connect(lambda p: bm_emitted.append(p))
        canvas.page_note_requested.connect(lambda p: note_emitted.append(p))

        canvas.bookmark_page_requested.emit(canvas.page_num)
        canvas.page_note_requested.emit(canvas.page_num)

    def test_study_list_bar_widget(self):
        from src.ui.study_list_bar import StudyListBarWidget
        bar = StudyListBarWidget()
        docs = [
            {"id": 1, "title": "Doc A", "file_path": "/path/a.pdf"},
            {"id": 2, "title": "Doc B", "file_path": "/path/b.pdf"},
        ]
        bar.set_study_list("Math 101", docs, current_doc_id=1)
        self.assertTrue(bar.isVisible())
        self.assertEqual(len(bar.documents), 2)

        requested_paths = []
        bar.open_document_requested.connect(lambda p: requested_paths.append(p))
        bar.open_document_requested.emit("/path/b.pdf")
        self.assertEqual(requested_paths, ["/path/b.pdf"])


if __name__ == "__main__":
    unittest.main()
