from typing import List, Dict, Any, Tuple, Optional
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QIcon, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QInputDialog,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
)
from src.database.db_manager import DatabaseManager
from src.ui.math_notes_editor import MathNotesEditor

class SidebarWidget(QWidget):
    """Collapsible right panel with Outline, Bookmarks, Notes, Highlights, and Math Notes tabs."""

    jump_to_page = Signal(int)
    note_added = Signal()
    bookmark_added = Signal()
    highlight_added = Signal()
    toggle_panel_requested = Signal()

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_doc_id: Optional[int] = None
        self.current_page: int = 0

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Header Bar with Collapse Button
        self.header_bar = QWidget()
        self.header_bar.setStyleSheet(
            "QWidget { background-color: #1a1a1a; border-bottom: 1px solid #333; } "
            "QPushButton { background: transparent; border: none; color: #aaa; font-size: 14px; font-weight: bold; } "
            "QPushButton:hover { color: #2196F3; }"
        )
        h_layout = QHBoxLayout(self.header_bar)
        h_layout.setContentsMargins(6, 6, 10, 6)

        self.btn_collapse = QPushButton("▶")
        self.btn_collapse.setToolTip("Collapse Right Sidebar Panel (F10)")
        self.btn_collapse.setFixedWidth(24)
        self.btn_collapse.clicked.connect(self.toggle_panel_requested.emit)
        h_layout.addWidget(self.btn_collapse)

        h_layout.addStretch()

        lbl_hdr = QLabel("Outline & Notes")
        lbl_hdr.setStyleSheet("font-weight: bold; color: #eee; font-size: 12px;")
        h_layout.addWidget(lbl_hdr)

        outer_layout.addWidget(self.header_bar)

        # Main Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #333; background: #1e1e1e; } "
            "QTabBar::tab { background: #2a2a2a; color: #bbb; padding: 7px 9px; border-top-left-radius: 4px; border-top-right-radius: 4px; font-size: 11px; } "
            "QTabBar::tab:selected { background: #1e1e1e; color: #2196F3; font-weight: bold; border-bottom: 2px solid #2196F3; }"
        )

        # Tab 1: Outline / Table of Contents
        self.outline_tree = QTreeWidget()
        self.outline_tree.setHeaderHidden(True)
        self.outline_tree.setStyleSheet("QTreeWidget { background-color: #1e1e1e; color: #ddd; border: none; }")
        self.outline_tree.itemClicked.connect(self._on_outline_item_clicked)
        self.tabs.addTab(self.outline_tree, "Outline")

        # Tab 2: Bookmarks
        self.bookmarks_widget = QWidget()
        b_layout = QVBoxLayout(self.bookmarks_widget)
        b_layout.setContentsMargins(6, 6, 6, 6)

        self.btn_add_bookmark = QPushButton("+ Bookmark Page")
        self.btn_add_bookmark.setStyleSheet(
            "QPushButton { background-color: #388E3C; color: white; border-radius: 4px; padding: 5px; font-weight: bold; } "
            "QPushButton:hover { background-color: #2E7D32; }"
        )
        self.btn_add_bookmark.clicked.connect(self._on_add_bookmark_clicked)
        b_layout.addWidget(self.btn_add_bookmark)

        self.bookmarks_list = QListWidget()
        self.bookmarks_list.setStyleSheet("QListWidget { background-color: #1e1e1e; color: #ddd; border: none; }")
        self.bookmarks_list.itemDoubleClicked.connect(self._on_bookmark_double_clicked)
        self.bookmarks_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bookmarks_list.customContextMenuRequested.connect(self._show_bookmark_context_menu)
        b_layout.addWidget(self.bookmarks_list)

        self.tabs.addTab(self.bookmarks_widget, "Bookmarks")

        # Tab 3: Notes
        self.notes_widget = QWidget()
        n_layout = QVBoxLayout(self.notes_widget)
        n_layout.setContentsMargins(6, 6, 6, 6)

        self.btn_add_note = QPushButton("+ Page Note")
        self.btn_add_note.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; border-radius: 4px; padding: 5px; font-weight: bold; } "
            "QPushButton:hover { background-color: #1976D2; }"
        )
        self.btn_add_note.clicked.connect(self._on_add_note_clicked)
        n_layout.addWidget(self.btn_add_note)

        self.notes_list = QListWidget()
        self.notes_list.setStyleSheet("QListWidget { background-color: #1e1e1e; color: #ddd; border: none; }")
        self.notes_list.itemDoubleClicked.connect(self._on_note_double_clicked)
        n_layout.addWidget(self.notes_list)

        self.tabs.addTab(self.notes_widget, "Notes")

        # Tab 4: Highlights & Underlines List
        self.highlights_widget = QWidget()
        h_layout = QVBoxLayout(self.highlights_widget)
        h_layout.setContentsMargins(6, 6, 6, 6)

        lbl_hl = QLabel("Saved Highlights & Comments")
        lbl_hl.setStyleSheet("font-weight: bold; color: #FFF59D; font-size: 11px;")
        h_layout.addWidget(lbl_hl)

        self.highlights_list = QListWidget()
        self.highlights_list.setStyleSheet("QListWidget { background-color: #1e1e1e; color: #ddd; border: none; }")
        self.highlights_list.itemDoubleClicked.connect(self._on_highlight_double_clicked)
        h_layout.addWidget(self.highlights_list)

        self.tabs.addTab(self.highlights_widget, "Highlights")

        # Tab 5: Running Math Notes Editor
        self.math_notes_tab = MathNotesEditor(self.db_manager)
        self.math_notes_tab.jump_to_page_requested.connect(self.jump_to_page.emit)
        self.tabs.addTab(self.math_notes_tab, "Math Notes")

        outer_layout.addWidget(self.tabs)

    def load_document_data(
        self, doc_id: int, current_page: int, toc: List[Tuple[int, str, int]] = None
    ):
        self.current_doc_id = doc_id
        self.current_page = current_page
        self._populate_outline(toc or [])
        self.refresh_bookmarks()
        self.refresh_notes()
        self.refresh_highlights()

    def set_current_page(self, page_num: int):
        self.current_page = page_num

    def _populate_outline(self, toc: List[Tuple[int, str, int]]):
        self.outline_tree.clear()
        if not toc:
            item = QTreeWidgetItem(["(No Outline / TOC found)"])
            self.outline_tree.addTopLevelItem(item)
            return

        parents = {0: self.outline_tree}
        for level, title, page_1based in toc:
            page_0based = max(0, page_1based - 1)
            tree_item = QTreeWidgetItem([f"{title} (p. {page_1based})"])
            tree_item.setData(0, Qt.UserRole, page_0based)

            parent_level = level - 1
            while parent_level > 0 and parent_level not in parents:
                parent_level -= 1

            parent_node = parents.get(parent_level, self.outline_tree)
            if parent_node == self.outline_tree:
                self.outline_tree.addTopLevelItem(tree_item)
            else:
                parent_node.addChild(tree_item)

            parents[level] = tree_item

        self.outline_tree.expandAll()

    def refresh_bookmarks(self):
        self.bookmarks_list.clear()
        if not self.current_doc_id:
            return
        bms = self.db_manager.get_bookmarks(self.current_doc_id)
        for bm in bms:
            item = QListWidgetItem(f"Page {bm['page_number'] + 1}: {bm['label']}")
            item.setData(Qt.UserRole, bm)
            self.bookmarks_list.addItem(item)

    def refresh_notes(self):
        self.notes_list.clear()
        if not self.current_doc_id:
            return
        notes = self.db_manager.get_notes(self.current_doc_id)
        for n in notes:
            region_str = " (Region)" if n.get("x") is not None else ""
            item = QListWidgetItem(f"Page {n['page_number'] + 1}{region_str}: {n['note_text']}")
            item.setData(Qt.UserRole, n)
            self.notes_list.addItem(item)

    def refresh_highlights(self):
        self.highlights_list.clear()
        if not self.current_doc_id:
            return
        hls = self.db_manager.get_highlights(self.current_doc_id)
        for hl in hls:
            st = hl.get("style", "highlight").capitalize()
            txt = hl.get("selected_text", "")
            if len(txt) > 30:
                txt = txt[:30] + "..."
            cmt = hl.get("comment_text", "")
            cmt_str = f" [{cmt}]" if cmt else ""

            item_text = f"P.{hl['page_number'] + 1} ({st}): \"{txt}\"{cmt_str}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, hl)
            self.highlights_list.addItem(item)

    @Slot(QTreeWidgetItem, int)
    def _on_outline_item_clicked(self, item: QTreeWidgetItem, column: int):
        page_num = item.data(0, Qt.UserRole)
        if page_num is not None:
            self.jump_to_page.emit(page_num)

    @Slot()
    def _on_add_bookmark_clicked(self):
        if not self.current_doc_id:
            return
        default_label = f"Bookmark Page {self.current_page + 1}"
        label, ok = QInputDialog.getText(
            self, "Add Bookmark", "Bookmark Label:", QLineEdit.Normal, default_label
        )
        if ok and label.strip():
            bm_label = label.strip()
            self.db_manager.add_bookmark(self.current_doc_id, self.current_page, bm_label)
            self.refresh_bookmarks()
            self.bookmark_added.emit()
            # Automatically insert usable markdown link into Math Notes (.md file)!
            self.math_notes_tab.insert_bookmark_link(self.current_page, bm_label)

    def _show_bookmark_context_menu(self, pos):
        item = self.bookmarks_list.itemAt(pos)
        if not item:
            return
        bm = item.data(Qt.UserRole)
        if not bm:
            return

        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1e1e1e; color: #E0E0E0; border: 1px solid #333; }")
        act_jump = menu.addAction("📖 Jump to Bookmark Page")
        act_insert_link = menu.addAction("🔗 Insert Link into Math Notes (.md)")
        act_delete = menu.addAction("🗑️ Delete Bookmark")

        action = menu.exec_(self.bookmarks_list.mapToGlobal(pos))
        if action == act_jump:
            self.jump_to_page.emit(bm["page_number"])
        elif action == act_insert_link:
            self.math_notes_tab.insert_bookmark_link(bm["page_number"], bm["label"])
            self.tabs.setCurrentIndex(4)
        elif action == act_delete:
            self.db_manager.delete_bookmark(bm["id"])
            self.refresh_bookmarks()

    def add_region_note(self, page_num: int, x: float, y: float, w: float, h: float):
        if not self.current_doc_id:
            return
        note_text, ok = QInputDialog.getMultiLineText(
            self, "Add Region Note", f"Enter note for region on Page {page_num + 1}:"
        )
        if ok and note_text.strip():
            self.db_manager.add_note(
                doc_id=self.current_doc_id,
                page_number=page_num,
                note_text=note_text.strip(),
                x=x,
                y=y,
                width=w,
                height=h,
            )
            self.refresh_notes()
            self.note_added.emit()

    @Slot()
    def _on_add_note_clicked(self):
        self.add_page_note_for_page(self.current_page)

    def add_page_note_for_page(self, page_num: int):
        if not self.current_doc_id:
            return
        note_text, ok = QInputDialog.getMultiLineText(
            self, "Add Page Note", f"Enter note for Page {page_num + 1}:"
        )
        if ok and note_text.strip():
            self.db_manager.add_note(
                doc_id=self.current_doc_id,
                page_number=page_num,
                note_text=note_text.strip(),
            )
            self.refresh_notes()
            self.note_added.emit()

    def _on_bookmark_double_clicked(self, item: QListWidgetItem):
        bm = item.data(Qt.UserRole)
        if bm:
            self.jump_to_page.emit(bm["page_number"])

    def _on_note_double_clicked(self, item: QListWidgetItem):
        n = item.data(Qt.UserRole)
        if n:
            self.jump_to_page.emit(n["page_number"])

    def _on_highlight_double_clicked(self, item: QListWidgetItem):
        hl = item.data(Qt.UserRole)
        if hl:
            self.jump_to_page.emit(hl["page_number"])
