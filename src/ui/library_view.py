import os
from typing import List, Dict, Any, Optional
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon, QPixmap, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QProgressBar,
    QFileDialog,
    QMenu,
    QMessageBox,
    QTabWidget,
)
from src.database.db_manager import DatabaseManager
from src.reader.document import DocumentReader
from src.utils.hashing import get_file_hash
from src.ui.study_list_widget import StudyListWidget
from src.ui.home_widget import HomeWidget

class DocumentListItemWidget(QWidget):
    """Custom list item widget displaying cover, title, reading progress, and timestamp."""

    def __init__(self, doc_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.doc_data = doc_data

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # Thumbnail Label
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(45, 65)
        self.cover_label.setStyleSheet("background-color: #3a3a3a; border-radius: 4px;")
        self.cover_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.cover_label)

        # Info Layout
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)

        self.title_label = QLabel(doc_data.get("title", "Untitled"))
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(9)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        info_layout.addWidget(self.title_label)

        # Progress info
        cur_p = doc_data.get("current_page", 0) + 1
        tot_p = max(1, doc_data.get("total_pages", 1))
        pct = int((cur_p / tot_p) * 100)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(pct)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #333; border: None; border-radius: 2px; } "
            "QProgressBar::chunk { background-color: #2196F3; border-radius: 2px; }"
        )
        info_layout.addWidget(self.progress_bar)

        meta_text = f"p. {cur_p}/{tot_p} ({pct}%) • {doc_data.get('last_opened', '')[:10]}"
        self.meta_label = QLabel(meta_text)
        self.meta_label.setStyleSheet("color: #888888; font-size: 10px;")
        info_layout.addWidget(self.meta_label)

        layout.addLayout(info_layout)
        self.load_thumbnail()

    def load_thumbnail(self):
        file_path = self.doc_data.get("file_path")
        if file_path and os.path.exists(file_path):
            try:
                reader = DocumentReader(file_path)
                pixmap = reader.render_cover(45, 65)
                reader.close()
                if not pixmap.isNull():
                    self.cover_label.setPixmap(pixmap)
                    return
            except Exception:
                pass
        self.cover_label.setText("PDF")


class LibraryView(QWidget):
    """Sidebar / Standalone Library view displaying catalog and Study Lists with header toggle."""

    document_selected = Signal(str)
    toggle_panel_requested = Signal()
    home_requested = Signal()

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Header Bar with Home & Collapse Buttons
        self.header_bar = QWidget()
        self.header_bar.setStyleSheet(
            "QWidget { background-color: #1a1a1a; border-bottom: 1px solid #333; } "
            "QPushButton { background: #2a2a2a; border: 1px solid #3a3a3a; color: #ddd; border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: bold; } "
            "QPushButton:hover { background-color: #2196F3; color: white; }"
        )
        h_layout = QHBoxLayout(self.header_bar)
        h_layout.setContentsMargins(8, 6, 6, 6)

        self.btn_home = QPushButton("🏠 Home")
        self.btn_home.setStyleSheet("background-color: #2196F3; color: white; border: none;")
        self.btn_home.setToolTip("Go to Home Dashboard (F2)")
        self.btn_home.clicked.connect(self.home_requested.emit)
        h_layout.addWidget(self.btn_home)

        if os.path.exists("logo.png"):
            lbl_logo = QLabel()
            pix = QPixmap("logo.png").scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl_logo.setPixmap(pix)
            h_layout.addWidget(lbl_logo)

        lbl_hdr = QLabel("Library")
        lbl_hdr.setStyleSheet("font-weight: bold; color: #eee; font-size: 12px;")
        h_layout.addWidget(lbl_hdr)

        h_layout.addStretch()

        self.btn_collapse = QPushButton("◀")
        self.btn_collapse.setToolTip("Collapse Library Panel (F9)")
        self.btn_collapse.setFixedWidth(24)
        self.btn_collapse.clicked.connect(self.toggle_panel_requested.emit)
        h_layout.addWidget(self.btn_collapse)

        outer_layout.addWidget(self.header_bar)

        # Main Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #333; background: #121212; } "
            "QTabBar::tab { background: #2a2a2a; color: #bbb; padding: 6px 10px; font-weight: bold; font-size: 11px; } "
            "QTabBar::tab:selected { background: #121212; color: #2196F3; border-bottom: 2px solid #2196F3; }"
        )

        # Tab 1: Library Catalog
        self.catalog_widget = QWidget()
        cat_layout = QVBoxLayout(self.catalog_widget)
        cat_layout.setContentsMargins(8, 8, 8, 8)
        cat_layout.setSpacing(8)

        btn_layout = QHBoxLayout()
        self.btn_open = QPushButton("+ Open File")
        self.btn_open.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; border-radius: 4px; padding: 6px; font-weight: bold; } "
            "QPushButton:hover { background-color: #1e88e5; }"
        )
        self.btn_open.clicked.connect(self._on_open_file_dialog)
        btn_layout.addWidget(self.btn_open)

        self.btn_scan = QPushButton("Scan Folder")
        self.btn_scan.setStyleSheet(
            "QPushButton { background-color: #424242; color: white; border-radius: 4px; padding: 6px; } "
            "QPushButton:hover { background-color: #616161; }"
        )
        self.btn_scan.clicked.connect(self._on_scan_folder_dialog)
        btn_layout.addWidget(self.btn_scan)

        cat_layout.addLayout(btn_layout)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter library...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_list)
        cat_layout.addWidget(self.search_input)

        self.doc_list = QListWidget()
        self.doc_list.setStyleSheet(
            "QListWidget { background-color: #1e1e1e; border: 1px solid #333; border-radius: 6px; } "
            "QListWidget::item:selected { background-color: #2a2a2a; border-left: 3px solid #2196F3; }"
        )
        self.doc_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.doc_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.doc_list.customContextMenuRequested.connect(self._show_context_menu)
        cat_layout.addWidget(self.doc_list)

        self.tabs.addTab(self.catalog_widget, "📚 All Library")

        # Tab 2: Study Lists Manager
        self.study_list_view = StudyListWidget(self.db_manager, self)
        self.study_list_view.open_document_requested.connect(self.document_selected.emit)
        self.tabs.addTab(self.study_list_view, "📝 Study Lists")

        outer_layout.addWidget(self.tabs)
        self.refresh_library()

    def refresh_library(self):
        self.doc_list.clear()
        documents = self.db_manager.get_recent_documents(limit=100)
        for doc in documents:
            item = QListWidgetItem(self.doc_list)
            item.setSizeHint(QSize(0, 78))
            item.setData(Qt.UserRole, doc)

            widget = DocumentListItemWidget(doc, self.doc_list)
            self.doc_list.setItemWidget(item, widget)

        if hasattr(self, 'study_list_view'):
            self.study_list_view.refresh_study_lists()

    def _filter_list(self, text: str):
        text = text.lower().strip()
        for i in range(self.doc_list.count()):
            item = self.doc_list.item(i)
            doc = item.data(Qt.UserRole)
            title = doc.get("title", "").lower()
            path = doc.get("file_path", "").lower()
            item.setHidden(text not in title and text not in path)

    @Slot()
    def _on_open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Document", "", "Documents (*.pdf *.epub *.mobi *.xps *.cbz)"
        )
        if file_path:
            self.document_selected.emit(file_path)

    @Slot()
    def _on_scan_folder_dialog(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder to Scan")
        if not folder_path:
            return

        added_count = 0
        valid_exts = {".pdf", ".epub", ".mobi", ".xps", ".cbz"}

        for root, _, files in os.walk(folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in valid_exts:
                    full_path = os.path.join(root, file)
                    try:
                        file_hash = get_file_hash(full_path)
                        reader = DocumentReader(full_path)
                        title = reader.title
                        total_pages = reader.total_pages
                        reader.close()

                        self.db_manager.get_or_create_document(
                            file_hash=file_hash,
                            file_path=full_path,
                            title=title,
                            total_pages=total_pages,
                        )
                        added_count += 1
                    except Exception:
                        continue

        self.refresh_library()
        QMessageBox.information(
            self, "Scan Complete", f"Scanned folder successfully. Cataloged {added_count} documents."
        )

    def _on_item_double_clicked(self, item: QListWidgetItem):
        doc = item.data(Qt.UserRole)
        file_path = doc.get("file_path")
        if file_path and os.path.exists(file_path):
            self.document_selected.emit(file_path)
        else:
            QMessageBox.warning(
                self, "File Not Found", f"The document file could not be found at:\n{file_path}"
            )

    def _show_context_menu(self, pos):
        item = self.doc_list.itemAt(pos)
        if not item:
            return

        doc = item.data(Qt.UserRole)
        doc_id = doc["id"]
        file_path = doc["file_path"]

        menu = QMenu(self)
        open_action = menu.addAction("Open Document")
        add_to_study_act = menu.addAction("Add to Active Study List")
        copy_action = menu.addAction("Copy Path")
        delete_action = menu.addAction("Remove from Library")

        action = menu.exec_(self.doc_list.mapToGlobal(pos))
        if action == open_action:
            if os.path.exists(file_path):
                self.document_selected.emit(file_path)
        elif action == add_to_study_act:
            self.study_list_view.add_current_document_to_active_list(doc_id)
            QMessageBox.information(self, "Added", "Document added to active Study List!")
        elif action == copy_action:
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText(file_path)
        elif action == delete_action:
            self.db_manager.delete_document(doc_id)
            self.refresh_library()
