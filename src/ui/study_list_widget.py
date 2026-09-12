import os
from typing import List, Dict, Any, Optional
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QInputDialog,
    QMessageBox,
    QFileDialog,
    QMenu,
    QToolButton,
)
from src.database.db_manager import DatabaseManager
from src.reader.document import DocumentReader
from src.utils.hashing import get_file_hash

class StudyListWidget(QWidget):
    """Widget for managing Study Lists (collections/tags of documents & folders)."""

    study_list_selected = Signal(int)       # study_list_id
    open_document_requested = Signal(str)    # file_path

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_study_list_id: Optional[int] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header
        header = QLabel("Study Lists")
        header_font = QFont("Segoe UI", 13, QFont.Bold)
        header.setFont(header_font)
        layout.addWidget(header)

        # Actions
        btn_layout = QHBoxLayout()
        self.btn_create = QPushButton("+ New List")
        self.btn_create.setStyleSheet(
            "QPushButton { background-color: #388E3C; color: white; border-radius: 4px; padding: 6px; font-weight: bold; } "
            "QPushButton:hover { background-color: #2E7D32; }"
        )
        self.btn_create.clicked.connect(self._on_create_study_list)
        btn_layout.addWidget(self.btn_create)

        self.btn_open_file = QToolButton()
        self.btn_open_file.setText("Open file ▾")
        self.btn_open_file.setToolTip("Open a file from the selected Study List")
        self.btn_open_file.setPopupMode(QToolButton.InstantPopup)
        self.btn_open_file.setStyleSheet(
            "QToolButton { background-color: #424242; color: white; border-radius: 4px; padding: 6px; } "
            "QToolButton:hover { background-color: #616161; }"
        )
        self.open_file_menu = QMenu(self.btn_open_file)
        self.open_file_menu.aboutToShow.connect(self._populate_open_file_menu)
        self.btn_open_file.setMenu(self.open_file_menu)
        btn_layout.addWidget(self.btn_open_file)

        layout.addLayout(btn_layout)

        # Study Lists Selector List
        self.lists_widget = QListWidget()
        self.lists_widget.setStyleSheet(
            "QListWidget { background-color: #1e1e1e; color: #ddd; border: 1px solid #333; border-radius: 6px; } "
            "QListWidget::item:selected { background-color: #2a2a2a; border-left: 3px solid #388E3C; }"
        )
        self.lists_widget.itemClicked.connect(self._on_list_clicked)
        self.lists_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lists_widget.customContextMenuRequested.connect(self._show_list_context_menu)
        layout.addWidget(self.lists_widget)

        # Sub-header: Documents in active study list (with Add File(s) button on right)
        doc_hdr_layout = QHBoxLayout()
        self.doc_header = QLabel("Documents in List:")
        self.doc_header.setStyleSheet("font-weight: bold; color: #aaa; margin-top: 6px;")
        doc_hdr_layout.addWidget(self.doc_header)

        doc_hdr_layout.addStretch()

        self.btn_add_files = QPushButton("+ Add File(s)...")
        self.btn_add_files.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 11px; } "
            "QPushButton:hover { background-color: #1e88e5; }"
        )
        self.btn_add_files.clicked.connect(self._on_add_files_to_study_list)
        doc_hdr_layout.addWidget(self.btn_add_files)

        layout.addLayout(doc_hdr_layout)

        self.doc_list_widget = QListWidget()
        self.doc_list_widget.setStyleSheet(
            "QListWidget { background-color: #1a1a1a; color: #eee; border: 1px solid #333; border-radius: 6px; }"
        )
        self.doc_list_widget.itemDoubleClicked.connect(self._on_doc_double_clicked)
        layout.addWidget(self.doc_list_widget)

        self.refresh_study_lists()

    def refresh_study_lists(self):
        previous_id = self.current_study_list_id
        self.lists_widget.clear()
        lists = self.db_manager.get_study_lists()
        for sl in lists:
            item = QListWidgetItem(f"📚 {sl['name']}")
            item.setData(Qt.UserRole, sl)
            self.lists_widget.addItem(item)

        if lists:
            selected_row = next(
                (index for index, study_list in enumerate(lists) if study_list["id"] == previous_id), 0
            )
            self.lists_widget.setCurrentRow(selected_row)
            self._select_study_list(self.lists_widget.item(selected_row), announce=False)
        else:
            self.current_study_list_id = None
            self.doc_list_widget.clear()

    @Slot()
    def _on_create_study_list(self):
        name, ok = QInputDialog.getText(self, "Create Study List", "Study List Name:")
        if ok and name.strip():
            desc, _ = QInputDialog.getText(self, "Description", "Description (optional):")
            self.db_manager.create_study_list(name.strip(), desc.strip() if desc else "")
            self.refresh_study_lists()

    def _on_list_clicked(self, item: QListWidgetItem):
        self._select_study_list(item, announce=True)

    def _select_study_list(self, item: QListWidgetItem, announce: bool):
        if not item:
            return
        sl = item.data(Qt.UserRole)
        self.current_study_list_id = sl["id"]
        self.doc_header.setText(f"Documents in '{sl['name']}':")
        self.refresh_study_list_documents()
        if announce:
            self.study_list_selected.emit(self.current_study_list_id)

    def _populate_open_file_menu(self):
        self.open_file_menu.clear()
        if not self.current_study_list_id:
            action = self.open_file_menu.addAction("Select a Study List first")
            action.setEnabled(False)
            return

        documents = self.db_manager.get_study_list_documents(self.current_study_list_id)
        if not documents:
            action = self.open_file_menu.addAction("This Study List is empty")
            action.setEnabled(False)
            return

        for document in documents:
            title = document.get("title") or os.path.basename(document.get("file_path", "Document"))
            action = self.open_file_menu.addAction(f"📄 {title}")
            action.triggered.connect(
                lambda checked=False, path=document.get("file_path", ""): self.open_document_requested.emit(path)
            )

    def refresh_study_list_documents(self):
        self.doc_list_widget.clear()
        if not self.current_study_list_id:
            return
        docs = self.db_manager.get_study_list_documents(self.current_study_list_id)
        for d in docs:
            item = QListWidgetItem(f"📄 {d['title']}")
            item.setData(Qt.UserRole, d)
            self.doc_list_widget.addItem(item)

    def add_current_document_to_active_list(self, doc_id: int):
        if self.current_study_list_id and doc_id:
            self.db_manager.add_document_to_study_list(self.current_study_list_id, doc_id)
            self.refresh_study_list_documents()
            self.study_list_selected.emit(self.current_study_list_id)

    def _on_doc_double_clicked(self, item: QListWidgetItem):
        doc = item.data(Qt.UserRole)
        file_path = doc.get("file_path")
        if file_path and os.path.exists(file_path):
            self.open_document_requested.emit(file_path)

    @Slot()
    def _on_add_files_to_study_list(self):
        if not self.current_study_list_id:
            QMessageBox.warning(self, "No Study List Selected", "Please select or create a Study List first.")
            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Document File(s) to Add to Study List",
            "",
            "Documents (*.pdf *.epub *.mobi *.xps *.cbz)"
        )
        if not file_paths:
            return

        added_count = 0
        for fp in file_paths:
            if os.path.exists(fp):
                try:
                    file_hash = get_file_hash(fp)
                    reader = DocumentReader(fp)
                    doc_record = self.db_manager.get_or_create_document(
                        file_hash=file_hash,
                        file_path=fp,
                        title=reader.title,
                        total_pages=reader.total_pages,
                    )
                    reader.close()
                    self.db_manager.add_document_to_study_list(
                        self.current_study_list_id, doc_record["id"]
                    )
                    added_count += 1
                except Exception:
                    continue

        self.refresh_study_list_documents()
        self.study_list_selected.emit(self.current_study_list_id)
        QMessageBox.information(
            self, "Documents Added", f"Added {added_count} document(s) to active Study List!"
        )

    def _show_list_context_menu(self, pos):
        item = self.lists_widget.itemAt(pos)
        if not item:
            return
        sl = item.data(Qt.UserRole)
        sl_id = sl["id"]

        menu = QMenu(self)
        delete_act = menu.addAction("Delete Study List")

        action = menu.exec_(self.lists_widget.mapToGlobal(pos))
        if action == delete_act:
            self.db_manager.delete_study_list(sl_id)
            self.refresh_study_lists()
