import os
from typing import List, Dict, Any, Optional
from PySide6.QtCore import Qt, Signal, Slot, QSize, QEvent
from PySide6.QtGui import QFont, QPixmap, QIcon, QColor, QPainter, QBrush, QPen, QAction
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QProgressBar,
    QScrollArea,
    QFrame,
    QGridLayout,
    QMenu,
    QMessageBox,
    QInputDialog,
    QFileDialog,
)
from src.database.db_manager import DatabaseManager
from src.reader.document import DocumentReader
from src.utils.hashing import get_file_hash
from src.ui.focus_widget import FocusDashboardWidget


def get_initials(name: str) -> str:
    """Computes initials for profile avatar badges (e.g., 'Markov chains research' -> 'MC')."""
    words = [w.strip() for w in name.split() if w.strip()]
    if not words:
        return "SL"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


class StudyListProfileCard(QFrame):
    """
    Styled Profile Card representing a Study List with initial avatar badge (e.g. 'MC' for Markov chains research).
    """

    clicked = Signal(int)  # study_list_id

    def __init__(self, study_list_data: Dict[str, Any], is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.sl_id = study_list_data.get("id")
        self.sl_name = study_list_data.get("name", "Study List")
        self.doc_count = study_list_data.get("doc_count", 0)

        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(50)

        border_col = "#2196F3" if is_selected else "#333333"
        bg_col = "#1e293b" if is_selected else "#1a1a1a"

        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {bg_col};
                border: 1.5px solid {border_col};
                border-radius: 8px;
            }}
            QFrame:hover {{
                background-color: #243044;
                border-color: #2196F3;
            }}
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 12, 6)
        layout.setSpacing(10)

        # Initials Avatar Badge (e.g. 'MC' for Markov chains research)
        initials = get_initials(self.sl_name)
        lbl_avatar = QLabel(initials)
        lbl_avatar.setFixedSize(36, 36)
        lbl_avatar.setAlignment(Qt.AlignCenter)
        lbl_avatar.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lbl_avatar.setStyleSheet(
            """
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2196F3, stop:1 #1565C0);
            color: white;
            border-radius: 18px;
            """
        )
        layout.addWidget(lbl_avatar)

        # Name & Doc Count
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        lbl_name = QLabel(self.sl_name)
        lbl_name.setFont(QFont("Segoe UI", 9, QFont.Bold))
        lbl_name.setStyleSheet("color: #FFFFFF;")
        info_layout.addWidget(lbl_name)

        lbl_meta = QLabel(f"{self.doc_count} document(s)")
        lbl_meta.setStyleSheet("color: #94A3B8; font-size: 10px;")
        info_layout.addWidget(lbl_meta)

        layout.addLayout(info_layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.sl_id:
            self.clicked.emit(self.sl_id)
        super().mousePressEvent(event)


class BookCardWidget(QFrame):
    """
    Styled visual card widget representing a book/document, displaying rendered cover image,
    title, reading progress bar, and metadata.
    """

    open_requested = Signal(str)            # file_path
    add_to_study_requested = Signal(int)   # doc_id
    remove_requested = Signal(int)         # doc_id

    def __init__(self, doc_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.doc_data = doc_data
        self.doc_id = doc_data.get("id")
        self.file_path = doc_data.get("file_path", "")

        self.setFixedSize(145, 230)
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)

        self.setStyleSheet(
            """
            BookCardWidget {
                background-color: #1e1e1e;
                border: 1px solid #333333;
                border-radius: 8px;
            }
            BookCardWidget:hover {
                background-color: #262626;
                border: 1.5px solid #2196F3;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 1. Cover Thumbnail Label
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(133, 145)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet(
            "background-color: #2b2b2b; border-radius: 6px; color: #aaaaaa;"
        )
        layout.addWidget(self.cover_label)

        # 2. Title Label
        title_str = doc_data.get("title", "Untitled")
        self.title_label = QLabel(title_str)
        title_font = QFont("Segoe UI", 9)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("color: #eeeeee;")
        self.title_label.setFixedHeight(34)
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self.title_label)

        # 3. Progress Bar & Meta
        cur_p = doc_data.get("current_page", 0) + 1
        tot_p = max(1, doc_data.get("total_pages", 1))
        pct = int((cur_p / tot_p) * 100)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(pct)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background-color: #333333;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 2px;
            }
            """
        )
        layout.addWidget(self.progress_bar)

        self.meta_label = QLabel(f"p. {cur_p}/{tot_p} ({pct}%)")
        self.meta_label.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(self.meta_label)

        self.load_cover_image()

    def load_cover_image(self):
        if self.file_path and os.path.exists(self.file_path):
            try:
                reader = DocumentReader(self.file_path)
                pixmap = reader.render_cover(133, 145)
                reader.close()
                if not pixmap.isNull():
                    self.cover_label.setPixmap(pixmap)
                    return
            except Exception:
                pass

        # Fallback styled book cover card if PDF cover rendering fails or is unavailable
        fallback_pixmap = self._generate_fallback_cover(
            133, 145, self.doc_data.get("title", "Book")
        )
        self.cover_label.setPixmap(fallback_pixmap)

    def _generate_fallback_cover(self, w: int, h: int, title: str) -> QPixmap:
        pix = QPixmap(w, h)
        pix.fill(QColor(42, 54, 70))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(33, 150, 243, 80))
        painter.drawRect(0, 0, 8, h)

        painter.setPen(QPen(QColor(255, 255, 255, 180), 2))
        painter.drawRect(20, 20, w - 40, h - 40)

        painter.setPen(QColor(240, 240, 240))
        font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(font)
        painter.drawText(24, 24, w - 48, h - 48, Qt.TextWordWrap | Qt.AlignCenter, title)
        painter.end()
        return pix

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.file_path and os.path.exists(self.file_path):
                self.open_requested.emit(self.file_path)
            else:
                QMessageBox.warning(
                    self, "File Not Found", f"File does not exist:\n{self.file_path}"
                )
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1e1e1e; color: #E0E0E0; border: 1px solid #333; } "
            "QMenu::item:selected { background-color: #2196F3; color: white; }"
        )
        act_open = menu.addAction("📖 Open Document")
        act_add_study = menu.addAction("📚 Add to Study List...")
        act_remove = menu.addAction("🗑️ Remove from Library")

        action = menu.exec_(event.globalPos())
        if action == act_open:
            if self.file_path and os.path.exists(self.file_path):
                self.open_requested.emit(self.file_path)
        elif action == act_add_study and self.doc_id:
            self.add_to_study_requested.emit(self.doc_id)
        elif action == act_remove and self.doc_id:
            self.remove_requested.emit(self.doc_id)


class HomeWidget(QWidget):
    """
    Home Window dashboard with Study Lists & Collections ON TOP and Recently Opened Files BELOW.
    """

    open_document_requested = Signal(str)
    open_file_requested = Signal()
    scan_folder_requested = Signal()

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.selected_study_list_id: Optional[int] = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 1. Header Banner & Quick Actions
        header_frame = QFrame()
        header_frame.setStyleSheet(
            """
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a2332, stop:1 #121212);
                border: 1px solid #2a3a4e;
                border-radius: 10px;
                padding: 8px;
            }
            """
        )
        h_layout = QVBoxLayout(header_frame)
        h_layout.setContentsMargins(12, 8, 12, 8)
        h_layout.setSpacing(8)

        # Title & Actions
        top_title_layout = QHBoxLayout()
        if os.path.exists("logo.png"):
            lbl_logo = QLabel()
            pix = QPixmap("logo.png").scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl_logo.setPixmap(pix)
            top_title_layout.addWidget(lbl_logo)

        lbl_welcome = QLabel("Home Dashboard")
        lbl_welcome.setFont(QFont("Segoe UI", 14, QFont.Bold))
        lbl_welcome.setStyleSheet("color: #FFFFFF;")
        top_title_layout.addWidget(lbl_welcome)

        top_title_layout.addStretch()

        self.btn_open_file = QPushButton("+ Open File")
        self.btn_open_file.setStyleSheet(
            """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #1e88e5; }
            """
        )
        self.btn_open_file.clicked.connect(self.open_file_requested.emit)
        top_title_layout.addWidget(self.btn_open_file)

        self.btn_scan_folder = QPushButton("Scan Folder")
        self.btn_scan_folder.setStyleSheet(
            """
            QPushButton {
                background-color: #37474F;
                color: white;
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #455A64; }
            """
        )
        self.btn_scan_folder.clicked.connect(self.scan_folder_requested.emit)
        top_title_layout.addWidget(self.btn_scan_folder)

        self.btn_new_study_list = QPushButton("+ Study List")
        self.btn_new_study_list.setStyleSheet(
            """
            QPushButton {
                background-color: #388E3C;
                color: white;
                border-radius: 5px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #2E7D32; }
            """
        )
        self.btn_new_study_list.clicked.connect(self._on_create_study_list)
        top_title_layout.addWidget(self.btn_new_study_list)

        h_layout.addLayout(top_title_layout)

        # Quick Stats & Search Bar
        stats_search_layout = QHBoxLayout()
        self.lbl_stats = QLabel("Catalog: 0 Books • 0 Study Lists")
        self.lbl_stats.setStyleSheet("color: #90A4AE; font-size: 11px;")
        stats_search_layout.addWidget(self.lbl_stats)

        stats_search_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter Home window...")
        self.search_input.setFixedWidth(220)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet(
            "QLineEdit { background: #121212; color: #eee; border: 1px solid #333; border-radius: 4px; padding: 4px 8px; }"
        )
        self.search_input.textChanged.connect(self._filter_cards)
        stats_search_layout.addWidget(self.search_input)

        h_layout.addLayout(stats_search_layout)
        main_layout.addWidget(header_frame)

        # 2. Main Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(16)

        # --- SECTION 0: Windows 11 Focus Session Dashboard ---
        self.focus_dashboard = FocusDashboardWidget(self.db_manager, self)
        self.scroll_layout.addWidget(self.focus_dashboard)

        # --- SECTION 1 (TOP): Study Lists & Collections ---
        study_hdr_layout = QHBoxLayout()
        lbl_study_title = QLabel("📚 Study Lists & Collections")
        lbl_study_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        lbl_study_title.setStyleSheet("color: #E0E0E0;")
        study_hdr_layout.addWidget(lbl_study_title)

        study_hdr_layout.addSpacing(15)

        self.btn_add_files_home = QPushButton("+ Add File(s)")
        self.btn_add_files_home.setStyleSheet(
            """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 4px;
                padding: 5px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #1e88e5; }
            """
        )
        self.btn_add_files_home.clicked.connect(self._on_add_files_to_home_study_list)
        study_hdr_layout.addWidget(self.btn_add_files_home)

        study_hdr_layout.addStretch()
        self.scroll_layout.addLayout(study_hdr_layout)

        # Profile Cards / Badges Container for Study Lists
        self.study_pills_container = QWidget()
        self.study_pills_layout = QHBoxLayout(self.study_pills_container)
        self.study_pills_layout.setContentsMargins(0, 0, 0, 0)
        self.study_pills_layout.setSpacing(10)
        self.study_pills_layout.setAlignment(Qt.AlignLeft)
        self.scroll_layout.addWidget(self.study_pills_container)

        # Study List Documents Grid
        self.study_container = QWidget()
        self.study_grid = QGridLayout(self.study_container)
        self.study_grid.setContentsMargins(0, 0, 0, 0)
        self.study_grid.setSpacing(10)
        self.scroll_layout.addWidget(self.study_container)

        # --- SECTION 2 (BOTTOM): Recently Opened Files ---
        recent_hdr_layout = QHBoxLayout()
        lbl_recent_title = QLabel("📖 Recently Opened Files")
        lbl_recent_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        lbl_recent_title.setStyleSheet("color: #E0E0E0;")
        recent_hdr_layout.addWidget(lbl_recent_title)
        recent_hdr_layout.addStretch()
        self.scroll_layout.addLayout(recent_hdr_layout)

        self.recent_container = QWidget()
        self.recent_grid = QGridLayout(self.recent_container)
        self.recent_grid.setContentsMargins(0, 0, 0, 0)
        self.recent_grid.setSpacing(10)
        self.scroll_layout.addWidget(self.recent_container)

        self.scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        self.all_card_widgets: List[BookCardWidget] = []
        self.refresh_home()

    def refresh_home(self):
        """Refreshes Study Lists on top, Recently Opened Files below, and stats."""
        if hasattr(self, 'focus_dashboard'):
            self.focus_dashboard.refresh_focus_dashboard()
        self.all_card_widgets.clear()

        self._clear_layout(self.study_pills_layout)
        self._clear_grid(self.study_grid)
        self._clear_grid(self.recent_grid)

        recent_docs = self.db_manager.get_recent_documents(limit=50)
        study_lists = self.db_manager.get_study_lists()

        total_docs = len(recent_docs)
        in_prog = sum(1 for d in recent_docs if d.get("current_page", 0) > 0)
        total_lists = len(study_lists)
        self.lbl_stats.setText(
            f"Catalog: {total_docs} Books ({in_prog} In Progress) • {total_lists} Study Lists"
        )

        # 1. Populate Section 1 (TOP): Study Lists Profile Cards & Documents
        if not study_lists:
            lbl_empty_s = QLabel("No Study Lists created yet. Click '+ Study List' to organize your reading.")
            lbl_empty_s.setStyleSheet("color: #777777; font-style: italic; font-size: 11px;")
            self.study_grid.addWidget(lbl_empty_s, 0, 0)
            self.selected_study_list_id = None
        else:
            if not self.selected_study_list_id or not any(l["id"] == self.selected_study_list_id for l in study_lists):
                self.selected_study_list_id = study_lists[0]["id"]

            for sl in study_lists:
                sl_id = sl["id"]
                sl_docs = self.db_manager.get_study_list_documents(sl_id)
                sl["doc_count"] = len(sl_docs)
                is_sel = (sl_id == self.selected_study_list_id)

                card = StudyListProfileCard(sl, is_selected=is_sel, parent=self.study_pills_container)
                card.clicked.connect(self._on_study_list_profile_clicked)
                self.study_pills_layout.addWidget(card)

            self._populate_study_list_documents(self.selected_study_list_id)

        # 2. Populate Section 2 (BOTTOM): Recently Opened Files
        if not recent_docs:
            lbl_empty = QLabel("No recently opened files found. Click '+ Open File' to start reading!")
            lbl_empty.setStyleSheet("color: #777777; font-style: italic; font-size: 11px;")
            self.recent_grid.addWidget(lbl_empty, 0, 0)
        else:
            col_max = 5
            for idx, doc in enumerate(recent_docs[:20]):
                card = BookCardWidget(doc, self.recent_container)
                card.open_requested.connect(self.open_document_requested.emit)
                card.add_to_study_requested.connect(self._prompt_add_to_study_list)
                card.remove_requested.connect(self._on_remove_document)
                row, col = divmod(idx, col_max)
                self.recent_grid.addWidget(card, row, col)
                self.all_card_widgets.append(card)

        if self.search_input.text():
            self._filter_cards(self.search_input.text())

    def _populate_study_list_documents(self, study_list_id: Optional[int]):
        self._clear_grid(self.study_grid)
        if not study_list_id:
            return

        docs = self.db_manager.get_study_list_documents(study_list_id)
        if not docs:
            lbl_empty = QLabel("This Study List is empty. Click '+ Add File(s)' above to add documents here.")
            lbl_empty.setStyleSheet("color: #777777; font-style: italic; font-size: 11px;")
            self.study_grid.addWidget(lbl_empty, 0, 0)
            return

        col_max = 5
        for idx, doc in enumerate(docs):
            card = BookCardWidget(doc, self.study_container)
            card.open_requested.connect(self.open_document_requested.emit)
            card.add_to_study_requested.connect(self._prompt_add_to_study_list)
            card.remove_requested.connect(self._on_remove_document)
            row, col = divmod(idx, col_max)
            self.study_grid.addWidget(card, row, col)
            self.all_card_widgets.append(card)

    def _on_study_list_profile_clicked(self, sl_id: int):
        self.selected_study_list_id = sl_id
        self.refresh_home()

    def _clear_grid(self, grid: QGridLayout):
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _filter_cards(self, query: str):
        query = query.lower().strip()
        for card in self.all_card_widgets:
            title = card.doc_data.get("title", "").lower()
            path = card.doc_data.get("file_path", "").lower()
            match = not query or (query in title or query in path)
            card.setVisible(match)

    @Slot()
    def _on_create_study_list(self):
        name, ok = QInputDialog.getText(self, "Create Study List", "Study List Name:")
        if ok and name.strip():
            desc, _ = QInputDialog.getText(self, "Description", "Description (optional):")
            new_id = self.db_manager.create_study_list(name.strip(), desc.strip() if desc else "")
            self.selected_study_list_id = new_id
            self.refresh_home()

    @Slot(int)
    def _prompt_add_to_study_list(self, doc_id: int):
        lists = self.db_manager.get_study_lists()
        if not lists:
            QMessageBox.information(
                self, "No Study Lists", "Please create a Study List first using '+ Study List'."
            )
            return

        names = [l["name"] for l in lists]
        chosen_name, ok = QInputDialog.getItem(
            self, "Add to Study List", "Select Study List:", names, 0, False
        )
        if ok and chosen_name:
            target_list = next((l for l in lists if l["name"] == chosen_name), None)
            if target_list:
                self.db_manager.add_document_to_study_list(target_list["id"], doc_id)
                self.selected_study_list_id = target_list["id"]
                self.refresh_home()
                QMessageBox.information(
                    self, "Success", f"Document added to '{chosen_name}' Study List!"
                )

    @Slot(int)
    def _on_remove_document(self, doc_id: int):
        reply = QMessageBox.question(
            self,
            "Remove Document",
            "Are you sure you want to remove this document from your library catalog?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db_manager.delete_document(doc_id)
            self.refresh_home()

    @Slot()
    def _on_add_files_to_home_study_list(self):
        if not self.selected_study_list_id:
            QMessageBox.warning(self, "No Study List", "Please create or select a Study List first.")
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
                        self.selected_study_list_id, doc_record["id"]
                    )
                    added_count += 1
                except Exception:
                    continue

        self.refresh_home()
        QMessageBox.information(
            self, "Added", f"Added {added_count} document(s) to active Study List!"
        )
