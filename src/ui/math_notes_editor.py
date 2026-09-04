import os
import re
from typing import Optional
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QUrl
from PySide6.QtGui import QFont, QTextDocument, QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QTextBrowser,
    QPushButton,
    QLabel,
    QSplitter,
    QFileDialog,
    QMessageBox,
)
from src.database.db_manager import DatabaseManager

HTML_MATH_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body {{
        background-color: #1e1e1e;
        color: #d4d4d4;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        padding: 12px;
        line-height: 1.6;
    }}
    h1, h2, h3 {{ color: #4FC3F7; border-bottom: 1px solid #333; padding-bottom: 4px; }}
    code {{ background-color: #2d2d2d; color: #FFB74D; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
    pre {{ background-color: #2d2d2d; padding: 10px; border-radius: 4px; overflow-x: auto; }}
    blockquote {{ border-left: 4px solid #2196F3; margin-left: 0; padding-left: 12px; color: #aaa; }}
    a {{ color: #4FC3F7; font-weight: bold; text-decoration: underline; }}
    a:hover {{ color: #81D4FA; }}
    .math-inline {{ color: #81C784; font-family: "Courier New", monospace; font-style: italic; font-weight: bold; }}
    .math-display {{ background: #263238; color: #A5D6A7; padding: 8px; border-radius: 4px; text-align: center; margin: 10px 0; font-family: "Courier New", monospace; font-weight: bold; }}
</style>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"
    onload="renderMathInElement(document.body, {{delimiters: [{{left: '$$', right: '$$', display: true}}, {{left: '$', right: '$', display: false}}]}});">
</script>
</head>
<body>
{content}
</body>
</html>
"""


class MathNotesEditor(QWidget):
    """Running Markdown Notes editor with live math formula preview and interactive bookmark links."""

    jump_to_page_requested = Signal(int)

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_study_list_id: Optional[int] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header Bar
        hdr_layout = QHBoxLayout()
        lbl_title = QLabel("Running Notes (Markdown & LaTeX Math)")
        lbl_title.setStyleSheet("font-weight: bold; color: #2196F3;")
        hdr_layout.addWidget(lbl_title)

        hdr_layout.addStretch()

        self.btn_export = QPushButton("Export .md")
        self.btn_export.setStyleSheet(
            "QPushButton { background: #424242; color: white; border-radius: 3px; padding: 4px 8px; } "
            "QPushButton:hover { background: #616161; }"
        )
        self.btn_export.clicked.connect(self._export_markdown)
        hdr_layout.addWidget(self.btn_export)

        layout.addLayout(hdr_layout)

        # Splitter: Left Editor, Right Live Preview
        self.splitter = QSplitter(Qt.Horizontal, self)

        # Left Text Editor
        self.editor = QTextEdit(self.splitter)
        self.editor.setPlaceholderText(
            "# Study Notes\n\nWrite running notes in Markdown with LaTeX math formulas:\n\nInline math: $\\hat{x}^* N^\\alpha \\hat{x} \\ge |X| + |Y|$\n\nDisplay equation:\n$$\\rho = -X - Y - Z < 2(|X| + |Y|) + \\nu_1$$\n"
        )
        self.editor.setStyleSheet(
            "QTextEdit { background-color: #1a1a1a; color: #f0f0f0; border: 1px solid #333; font-family: 'Consolas', monospace; font-size: 13px; }"
        )
        self.editor.textChanged.connect(self._on_text_changed)
        self.splitter.addWidget(self.editor)

        # Right Preview Browser
        self.preview = QTextBrowser(self.splitter)
        self.preview.setOpenExternalLinks(False)
        self.preview.anchorClicked.connect(self._on_anchor_clicked)
        self.preview.setStyleSheet(
            "QTextBrowser { background-color: #1e1e1e; color: #ddd; border: 1px solid #333; }"
        )
        self.splitter.addWidget(self.preview)

        self.splitter.setSizes([350, 350])
        layout.addWidget(self.splitter)

        # Auto-save timer
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._save_notes)

    def insert_bookmark_link(self, page_num: int, label: str):
        """Appends a markdown bookmark link [🔖 Label (p. N)](page:N) into the editor."""
        page_1based = page_num + 1
        link_md = f"\n[🔖 {label} (p. {page_1based})](page:{page_1based})\n"
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(link_md)
        self.editor.setTextCursor(cursor)
        self._on_text_changed()

    def load_study_list_notes(self, study_list_id: int):
        self.current_study_list_id = study_list_id
        md_text = self.db_manager.get_study_list_notes(study_list_id)
        self.editor.blockSignals(True)
        self.editor.setPlainText(md_text)
        self.editor.blockSignals(False)
        self._update_preview()

    @Slot(QUrl)
    def _on_anchor_clicked(self, url: QUrl):
        href = url.toString()
        # Parse page:N or #page-N
        page_match = re.search(r"(?:page:|#page-)(\d+)", href, re.IGNORECASE)
        if page_match:
            page_1based = int(page_match.group(1))
            page_0based = max(0, page_1based - 1)
            self.jump_to_page_requested.emit(page_0based)

    @Slot()
    def _on_text_changed(self):
        self._update_preview()
        if self.current_study_list_id:
            self.save_timer.start(500)

    def _save_notes(self):
        if self.current_study_list_id:
            self.db_manager.update_study_list_notes(
                self.current_study_list_id, self.editor.toPlainText()
            )

    def _update_preview(self):
        md = self.editor.toPlainText()

        # Convert basic markdown formatting to HTML
        doc = QTextDocument()
        doc.setMarkdown(md)
        html_body = doc.toHtml()

        # Format display math block syntax $$ ... $$
        html_body = re.sub(
            r"\$\$(.*?)\$\$",
            r'<div class="math-display">$$\1$$</div>',
            html_body,
            flags=re.DOTALL,
        )

        # Format inline math syntax $ ... $
        html_body = re.sub(
            r"\$(.*?)\$",
            r'<span class="math-inline">$\1$</span>',
            html_body,
        )

        full_html = HTML_MATH_TEMPLATE.format(content=html_body)
        self.preview.setHtml(full_html)

    def _export_markdown(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Running Notes", "study_notes.md", "Markdown Files (*.md)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            QMessageBox.information(self, "Export Successful", f"Notes exported to:\n{file_path}")
