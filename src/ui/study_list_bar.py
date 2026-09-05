import os
from typing import List, Dict, Any, Optional
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QWidget,
)


class StudyListBarWidget(QFrame):
    """Compact bottom navigation bar displaying PDF pills for all documents in the active Study List."""

    open_document_requested = Signal(str)
    next_pdf_requested = Signal()
    prev_pdf_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.documents: List[Dict[str, Any]] = []
        self.current_doc_id: Optional[int] = None
        self.study_list_name: str = ""

        self.setFixedHeight(32)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background-color: #1a1a1a; color: #E0E0E0; border-top: 1px solid #2d2d2d; } "
            "QPushButton { background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 3px; padding: 2px 6px; font-size: 11px; color: #ccc; } "
            "QPushButton:hover { background-color: #3d3d3d; border-color: #2196F3; color: white; }"
        )

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 2, 6, 2)
        main_layout.setSpacing(6)

        # Title Label
        self.lbl_title = QLabel("📚 Study List:")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #2196F3; font-size: 11px;")
        main_layout.addWidget(self.lbl_title)

        # Navigation Buttons
        self.btn_prev_pdf = QPushButton("◀ Prev")
        self.btn_prev_pdf.setToolTip("Previous PDF in Study List (Ctrl+Shift+Tab)")
        self.btn_prev_pdf.setFixedWidth(56)
        self.btn_prev_pdf.clicked.connect(self.prev_pdf_requested.emit)
        main_layout.addWidget(self.btn_prev_pdf)

        self.btn_next_pdf = QPushButton("Next ▶")
        self.btn_next_pdf.setToolTip("Next PDF in Study List (Ctrl+Tab)")
        self.btn_next_pdf.setFixedWidth(56)
        self.btn_next_pdf.clicked.connect(self.next_pdf_requested.emit)
        main_layout.addWidget(self.btn_next_pdf)

        # Scroll Area for PDF Pills
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.pills_container = QWidget()
        self.pills_layout = QHBoxLayout(self.pills_container)
        self.pills_layout.setContentsMargins(0, 0, 0, 0)
        self.pills_layout.setSpacing(4)
        self.pills_layout.setAlignment(Qt.AlignLeft)

        self.scroll_area.setWidget(self.pills_container)
        main_layout.addWidget(self.scroll_area)

    def set_study_list(
        self,
        study_list_name: str,
        documents: List[Dict[str, Any]],
        current_doc_id: Optional[int] = None,
    ):
        self.study_list_name = study_list_name
        self.documents = documents
        self.current_doc_id = current_doc_id

        if not documents:
            self.setVisible(False)
            return

        self.setVisible(True)
        self.lbl_title.setText(f"📚 {study_list_name}:")

        # Clear existing pill buttons
        while self.pills_layout.count():
            item = self.pills_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for doc in documents:
            title = doc.get("title") or os.path.basename(doc.get("file_path", "Document"))
            if len(title) > 24:
                title = title[:21] + "..."

            btn_pill = QPushButton(f"📄 {title}")
            file_path = doc.get("file_path")
            doc_id = doc.get("id")

            if doc_id == current_doc_id:
                btn_pill.setStyleSheet(
                    "QPushButton { background-color: #1976D2; color: white; font-weight: bold; border: 1px solid #42A5F5; border-radius: 3px; padding: 2px 8px; font-size: 11px; }"
                )
            else:
                btn_pill.setStyleSheet(
                    "QPushButton { background-color: #2b2b2b; color: #ccc; border: 1px solid #3c3c3c; border-radius: 3px; padding: 2px 8px; font-size: 11px; } "
                    "QPushButton:hover { background-color: #383838; color: white; border-color: #2196F3; }"
                )

            btn_pill.clicked.connect(lambda _, fp=file_path: self.open_document_requested.emit(fp))
            self.pills_layout.addWidget(btn_pill)
