import os
from typing import Optional, List, Dict, Any, Tuple
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon, QShortcut
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QApplication,
    QMenu,
    QStackedWidget,
    QPushButton,
    QLabel,
    QFrame,
)
from src.database.db_manager import DatabaseManager
from src.reader.document import DocumentReader
from src.utils.hashing import get_file_hash
from src.utils.debouncer import Debouncer
from src.ui.library_view import LibraryView
from src.ui.viewer_widget import PDFViewerWidget
from src.ui.sidebar_widget import SidebarWidget
from src.ui.bottom_bar import BottomBarWidget, TopBarWidget
from src.ui.home_widget import HomeWidget

DARK_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #121212;
    color: #E0E0E0;
    font-family: "Segoe UI", Roboto, sans-serif;
}
QMenuBar {
    background-color: #1e1e1e;
    color: #E0E0E0;
    border-bottom: 1px solid #2d2d2d;
}
QMenuBar::item:selected {
    background-color: #333333;
}
QMenu {
    background-color: #1e1e1e;
    color: #E0E0E0;
    border: 1px solid #333333;
}
QMenu::item:selected {
    background-color: #2196F3;
    color: white;
}
QSplitter::handle {
    background-color: #2a2a2a;
}
"""

class MainWindow(QMainWindow):
    """Main desktop window with full-height reading viewport, themes, and highlight toggling."""

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_reader: Optional[DocumentReader] = None
        self.current_doc_id: Optional[int] = None
        self.current_theme: str = "day"

        # Search state
        self.search_query: str = ""
        self.search_results: List[Dict[str, Any]] = []
        self.search_flat_matches: List[Tuple[int, Tuple[float, float, float, float]]] = []
        self.current_search_idx: int = -1

        # Debouncer for saving reading state
        self.position_debouncer = Debouncer(300, self._save_reading_position, self)

        self.setWindowTitle("ReadEra Desktop Reader - Home")
        self.setMinimumSize(960, 600)
        self.resize(1320, 860)
        self.setStyleSheet(DARK_STYLESHEET)
        if os.path.exists("logo.png"):
            self.setWindowIcon(QIcon("logo.png"))

        # Root Central Container
        self.root_widget = QWidget(self)
        root_layout = QVBoxLayout(self.root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Central Stacked Widget
        self.main_stack = QStackedWidget(self.root_widget)

        # Stack View 0: Standalone Home Widget (Full Screen Dashboard)
        self.home_view = HomeWidget(self.db_manager, self.main_stack)
        self.home_view.open_document_requested.connect(self.open_document)
        self.home_view.open_file_requested.connect(self._on_menu_open)
        self.home_view.scan_folder_requested.connect(lambda: self.library_view._on_scan_folder_dialog())
        self.main_stack.addWidget(self.home_view)

        # Stack View 1: Reader Splitter
        self.reader_splitter = QSplitter(Qt.Horizontal, self.main_stack)
        self.reader_splitter.setChildrenCollapsible(True)

        # 1. Left Library Panel
        self.library_view = LibraryView(self.db_manager, self.reader_splitter)
        self.library_view.document_selected.connect(self.open_document)
        self.library_view.toggle_panel_requested.connect(self._toggle_library_panel)
        self.library_view.home_requested.connect(self._show_home_view)
        self.reader_splitter.addWidget(self.library_view)

        # 2. Main Center Viewer Container (Top Control Bar + PDF Viewer)
        self.center_container = QWidget(self.reader_splitter)
        center_layout = QVBoxLayout(self.center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # Top Control Bar (positioned at TOP of reading viewport)
        self.top_bar = TopBarWidget(self.center_container)
        self.bottom_bar = self.top_bar  # Backward compatibility alias
        self.top_bar.home_requested.connect(self._show_home_view)
        self.top_bar.prev_page_requested.connect(self.viewer_widget_prev_page if hasattr(self, 'viewer_widget_prev_page') else lambda: self.viewer_widget.prev_page())
        self.top_bar.next_page_requested.connect(lambda: self.viewer_widget.next_page())
        self.top_bar.page_jump_requested.connect(lambda p: self.viewer_widget.set_page(p))
        self.top_bar.zoom_in_requested.connect(lambda: self.viewer_widget.set_zoom(self.viewer_widget.zoom_level * 1.15))
        self.top_bar.zoom_out_requested.connect(lambda: self.viewer_widget.set_zoom(self.viewer_widget.zoom_level / 1.15))
        self.top_bar.fit_width_requested.connect(lambda: self.viewer_widget.fit_width())
        self.top_bar.fit_page_requested.connect(lambda: self.viewer_widget.fit_page())
        self.top_bar.search_requested.connect(self.perform_search)
        self.top_bar.next_search_match_requested.connect(self.next_search_match)
        self.top_bar.prev_search_match_requested.connect(self.prev_search_match)
        self.top_bar.toggle_left_panel_requested.connect(self._toggle_library_panel)
        self.top_bar.toggle_right_panel_requested.connect(self._toggle_right_sidebar)

        # Synchronize Timer between FocusDashboardWidget (Home View) and TopBarWidget (Reader View)
        focus_dash = self.home_view.focus_dashboard
        focus_dash.timer_tick_signal.connect(self.top_bar.sync_timer_state)
        self.top_bar.timer_button_clicked.connect(focus_dash.handle_topbar_timer_click)

        center_layout.addWidget(self.top_bar)

        self.viewer_widget = PDFViewerWidget(self.center_container)
        self.viewer_widget.page_changed.connect(self._on_page_changed)
        self.viewer_widget.zoom_changed.connect(self._on_zoom_changed)
        self.viewer_widget.region_note_requested.connect(self._on_region_note_requested)
        self.viewer_widget.add_highlight_signal.connect(self._on_add_highlight_requested)
        center_layout.addWidget(self.viewer_widget)

        self.reader_splitter.addWidget(self.center_container)

        # 3. Right Sidebar Panel
        self.sidebar_widget = SidebarWidget(self.db_manager, self.reader_splitter)
        self.sidebar_widget.jump_to_page.connect(self.viewer_widget.set_page)
        self.sidebar_widget.bookmark_added.connect(self.library_view.refresh_library)
        self.sidebar_widget.note_added.connect(self.library_view.refresh_library)
        self.sidebar_widget.toggle_panel_requested.connect(self._toggle_right_sidebar)
        self.reader_splitter.addWidget(self.sidebar_widget)

        self.reader_splitter.setSizes([300, 720, 300])
        self.main_stack.addWidget(self.reader_splitter)

        root_layout.addWidget(self.main_stack)
        self.setCentralWidget(self.root_widget)

        # Create Actions and Menus
        self._create_actions()
        self._create_menus()

        # Keyboard Shortcuts
        self._setup_shortcuts()

        # Always start at the Home page on application launch!
        QTimer.singleShot(50, self._load_initial_document)

    def _create_actions(self):
        self.act_home = QAction("🏠 &Home View", self, shortcut="F2", triggered=self._show_home_view)
        self.act_open = QAction("&Open File...", self, shortcut=QKeySequence.Open, triggered=self._on_menu_open)
        self.act_scan = QAction("&Scan Directory...", self, triggered=lambda: self.library_view._on_scan_folder_dialog())
        self.act_exit = QAction("E&xit", self, shortcut=QKeySequence.Quit, triggered=self.close)

        self.act_toggle_lib = QAction("Toggle &Library Panel", self, shortcut="F9", triggered=self._toggle_library_panel)
        self.act_toggle_sidebar = QAction("Toggle Right &Sidebar", self, shortcut="F10", triggered=self._toggle_right_sidebar)
        self.act_continuous = QAction("Continuous &Vertical Scroll", self, checkable=True, triggered=self._toggle_continuous_scroll)
        self.act_continuous.setChecked(True)

        # Paper Color Themes
        self.act_theme_day = QAction("Paper Theme: &Day (White)", self, triggered=lambda: self._set_paper_theme("day"))
        self.act_theme_dark = QAction("Paper Theme: &Dark", self, triggered=lambda: self._set_paper_theme("dark"))
        self.act_theme_twilight = QAction("Paper Theme: &Twilight", self, triggered=lambda: self._set_paper_theme("twilight"))
        self.act_theme_sepia = QAction("Paper Theme: &Sepia", self, triggered=lambda: self._set_paper_theme("sepia"))
        self.act_theme_sepia_contrast = QAction("Paper Theme: Sepia &Contrast", self, triggered=lambda: self._set_paper_theme("sepia_contrast"))

        self.act_add_bm = QAction("Add &Bookmark", self, shortcut="Ctrl+B", triggered=self.sidebar_widget._on_add_bookmark_clicked)
        self.act_add_note = QAction("Add &Note", self, shortcut="Ctrl+N", triggered=self.sidebar_widget._on_add_note_clicked)
        self.act_find = QAction("&Find Text...", self, shortcut=QKeySequence.Find, triggered=self._focus_search)

    def _create_menus(self):
        menubar = self.menuBar()
        menubar.setVisible(False)

        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.act_home)
        file_menu.addAction(self.act_open)
        file_menu.addAction(self.act_scan)
        file_menu.addSeparator()
        file_menu.addAction(self.act_exit)

        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.act_home)
        view_menu.addAction(self.act_toggle_lib)
        view_menu.addAction(self.act_toggle_sidebar)
        view_menu.addAction(self.act_continuous)
        view_menu.addSeparator()

        theme_menu = view_menu.addMenu("Paper &Color Themes")
        theme_menu.addAction(self.act_theme_day)
        theme_menu.addAction(self.act_theme_dark)
        theme_menu.addAction(self.act_theme_twilight)
        theme_menu.addAction(self.act_theme_sepia)
        theme_menu.addAction(self.act_theme_sepia_contrast)

        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addAction(self.act_continuous)
        tools_theme_menu = tools_menu.addMenu("Paper Color Themes")
        tools_theme_menu.addAction(self.act_theme_day)
        tools_theme_menu.addAction(self.act_theme_dark)
        tools_theme_menu.addAction(self.act_theme_twilight)
        tools_theme_menu.addAction(self.act_theme_sepia)
        tools_theme_menu.addAction(self.act_theme_sepia_contrast)
        tools_menu.addSeparator()
        tools_menu.addAction(self.act_add_bm)
        tools_menu.addAction(self.act_add_note)
        tools_menu.addAction(self.act_find)

        # Populate 3-line "☰ More" menu on top bar
        more = self.top_bar.more_menu
        more.clear()
        more.addAction(self.act_home)
        more.addAction(self.act_open)
        more.addAction(self.act_scan)
        more.addSeparator()
        more_themes = more.addMenu("🎨 Paper Color Themes")
        more_themes.addAction(self.act_theme_day)
        more_themes.addAction(self.act_theme_dark)
        more_themes.addAction(self.act_theme_twilight)
        more_themes.addAction(self.act_theme_sepia)
        more_themes.addAction(self.act_theme_sepia_contrast)
        more.addAction(self.act_continuous)
        more.addSeparator()
        more.addAction(self.act_add_bm)
        more.addAction(self.act_add_note)
        more.addAction(self.act_find)
        more.addSeparator()
        more.addAction(self.act_exit)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Left"), self, self.viewer_widget.prev_page)
        QShortcut(QKeySequence("Right"), self, self.viewer_widget.next_page)
        QShortcut(QKeySequence("PgUp"), self, self.viewer_widget.prev_page)
        QShortcut(QKeySequence("PgDown"), self, self.viewer_widget.next_page)
        QShortcut(QKeySequence("Ctrl+1"), self, self.viewer_widget.fit_width)
        QShortcut(QKeySequence("Ctrl+2"), self, self.viewer_widget.fit_page)

    def _load_initial_document(self):
        # Always start app directly at the Home page dashboard!
        self._show_home_view()

    @Slot(str)
    def open_document(self, file_path: str):
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", f"Cannot open file: {file_path}")
            return

        self.position_debouncer.flush()

        try:
            if self.current_reader:
                self.current_reader.close()

            file_hash = get_file_hash(file_path)
            reader = DocumentReader(file_path)
            doc_record = self.db_manager.get_or_create_document(
                file_hash=file_hash,
                file_path=file_path,
                title=reader.title,
                total_pages=reader.total_pages,
            )

            self.current_reader = reader
            self.current_doc_id = doc_record["id"]
            saved_page = doc_record.get("current_page", 0)
            saved_zoom = doc_record.get("zoom_level", 1.0)

            self.setWindowTitle(f"{reader.title} - ReadEra Desktop")

            self.viewer_widget.set_document(
                reader, initial_page=saved_page, initial_zoom=saved_zoom, theme=self.current_theme
            )
            self.sidebar_widget.load_document_data(
                doc_id=self.current_doc_id,
                current_page=saved_page,
                toc=reader.get_toc(),
            )
            self.bottom_bar.set_document_state(saved_page, reader.total_pages, saved_zoom)

            self._update_all_annotations()
            self.library_view.refresh_library()
            self.home_view.refresh_home()

            # Switch to Reader View (Stack Index 1)
            self._show_reader_view()

        except Exception as e:
            QMessageBox.critical(self, "Error Opening File", f"Failed to load document:\n{str(e)}")

    def _show_home_view(self):
        self.home_view.refresh_home()
        self.main_stack.setCurrentIndex(0)
        self.setWindowTitle("ReadEra Desktop Reader - Home")

    def _show_reader_view(self):
        if self.current_reader:
            self.main_stack.setCurrentIndex(1)
            self.setWindowTitle(f"{self.current_reader.title} - ReadEra Desktop")

    def _update_all_annotations(self):
        if self.current_doc_id:
            notes = self.db_manager.get_notes(self.current_doc_id)
            highlights = self.db_manager.get_highlights(self.current_doc_id)
            self.viewer_widget.set_document_annotations(notes, highlights)

    @Slot(int)
    def _on_page_changed(self, page_num: int):
        self.sidebar_widget.set_current_page(page_num)
        if self.current_reader:
            self.bottom_bar.set_document_state(
                page_num, self.current_reader.total_pages, self.viewer_widget.zoom_level
            )
        self.position_debouncer.trigger(page_num, self.viewer_widget.zoom_level)

    @Slot(float)
    def _on_zoom_changed(self, zoom: float):
        if self.current_reader:
            self.bottom_bar.set_document_state(
                self.viewer_widget.current_page, self.current_reader.total_pages, zoom
            )
        self.position_debouncer.trigger(self.viewer_widget.current_page, zoom)

    def _save_reading_position(self, page_num: int, zoom: float):
        if self.current_doc_id is not None:
            self.db_manager.update_reading_position(self.current_doc_id, page_num, zoom)

    @Slot(int, float, float, float, float)
    def _on_region_note_requested(self, page_num: int, x: float, y: float, w: float, h: float):
        self.sidebar_widget.tabs.setCurrentIndex(2)
        self.sidebar_widget.add_region_note(page_num, x, y, w, h)

    @Slot(int, list, str, str, str, str)
    def _on_add_highlight_requested(
        self, page_num: int, rects: list, color: str, style: str, text: str, comment: str
    ):
        if not self.current_doc_id or not rects:
            return

        # Toggle unhighlight logic: check if overlapping highlight exists
        existing_hls = self.db_manager.get_highlights(self.current_doc_id, page_number=page_num)
        toggled_off = False

        for hl in existing_hls:
            hl_rects = hl.get("rects", [])
            overlap = False
            for (hx0, hy0, hx1, hy1) in hl_rects:
                for (rx0, ry0, rx1, ry1) in rects:
                    if not (hx1 < rx0 or hx0 > rx1 or hy1 < ry0 or hy0 > ry1):
                        overlap = True
                        break
                if overlap:
                    break

            if overlap:
                self.db_manager.delete_highlight(hl["id"])
                toggled_off = True

        if not toggled_off:
            self.db_manager.add_highlight(
                doc_id=self.current_doc_id,
                page_number=page_num,
                rects=rects,
                color=color,
                style=style,
                selected_text=text,
                comment_text=comment,
            )

        self._update_all_annotations()
        self.sidebar_widget.refresh_highlights()

    def _set_paper_theme(self, theme: str):
        self.current_theme = theme
        self.viewer_widget.set_theme(theme)

    def _toggle_continuous_scroll(self, checked: bool):
        self.viewer_widget.toggle_continuous_scroll(checked)

    def _toggle_library_panel(self):
        if self.main_stack.currentIndex() == 0 and self.current_reader:
            self._show_reader_view()
        is_vis = self.library_view.isVisible()
        self.library_view.setVisible(not is_vis)
        if not is_vis:
            self.reader_splitter.setSizes([300, 720, 300])

    def _toggle_right_sidebar(self):
        if self.main_stack.currentIndex() == 0 and self.current_reader:
            self._show_reader_view()
        is_vis = self.sidebar_widget.isVisible()
        self.sidebar_widget.setVisible(not is_vis)
        if not is_vis:
            self.reader_splitter.setSizes([300, 720, 300])

    @Slot(str)
    def perform_search(self, query: str):
        self.search_query = query
        self.search_results = []
        self.search_flat_matches = []
        self.current_search_idx = -1

        if not self.current_reader or not query:
            self.viewer_widget.set_search_highlights({})
            self.bottom_bar.set_search_results_status(0, 0)
            return

        self.search_results = self.current_reader.search_all_pages(query)
        search_boxes_by_page = {}
        for item in self.search_results:
            p_num = item["page"]
            search_boxes_by_page[p_num] = item["boxes"]
            for box in item["boxes"]:
                self.search_flat_matches.append((p_num, box))

        self.viewer_widget.set_search_highlights(search_boxes_by_page)

        total = len(self.search_flat_matches)
        if total > 0:
            self.current_search_idx = 0
            self._jump_to_current_search_match()
        else:
            self.bottom_bar.set_search_results_status(0, 0)

    def next_search_match(self):
        if not self.search_flat_matches:
            return
        self.current_search_idx = (self.current_search_idx + 1) % len(self.search_flat_matches)
        self._jump_to_current_search_match()

    def prev_search_match(self):
        if not self.search_flat_matches:
            return
        self.current_search_idx = (self.current_search_idx - 1) % len(self.search_flat_matches)
        self._jump_to_current_search_match()

    def _jump_to_current_search_match(self):
        if 0 <= self.current_search_idx < len(self.search_flat_matches):
            p_num, box = self.search_flat_matches[self.current_search_idx]
            self.viewer_widget.set_page(p_num)
            self.bottom_bar.set_search_results_status(self.current_search_idx, len(self.search_flat_matches))

    def _focus_search(self):
        if self.main_stack.currentIndex() == 0 and self.current_reader:
            self._show_reader_view()
        self.bottom_bar.search_input.setFocus()
        self.bottom_bar.search_input.selectAll()

    def _on_menu_open(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Document", "", "Documents (*.pdf *.epub *.mobi *.xps *.cbz)"
        )
        if file_path:
            self.open_document(file_path)

    def closeEvent(self, event):
        self.position_debouncer.flush()
        if self.current_reader:
            self.current_reader.close()
        event.accept()
