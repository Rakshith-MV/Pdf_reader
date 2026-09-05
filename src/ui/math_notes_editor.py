import os
import re
from typing import Optional
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QUrl, QEvent
from PySide6.QtGui import QFont, QTextDocument, QTextCursor, QKeyEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QStackedWidget,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

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
        padding: 16px;
        line-height: 1.6;
        user-select: text;
        cursor: default;
    }}
    h1, h2, h3 {{ color: #4FC3F7; border-bottom: 1px solid #333; padding-bottom: 4px; }}
    code {{ background-color: #2d2d2d; color: #FFB74D; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
    pre {{ background-color: #2d2d2d; padding: 10px; border-radius: 4px; overflow-x: auto; }}
    blockquote {{ border-left: 4px solid #2196F3; margin-left: 0; padding-left: 12px; color: #aaa; }}
    a {{ color: #4FC3F7; font-weight: bold; text-decoration: underline; }}
    a:hover {{ color: #81D4FA; }}
    .math-inline {{ font-size: 1.1em; color: #81C784; padding: 0 2px; }}
    .math-display {{ background: #263238; color: #A5D6A7; padding: 12px; border-radius: 6px; text-align: center; margin: 14px 0; font-size: 1.2em; overflow-x: auto; }}
    .katex-display {{ margin: 0.5em 0 !important; }}
</style>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"
    onload="renderMathInElement(document.body, {{delimiters: [{{left: '$$', right: '$$', display: true}}, {{left: '$', right: '$', display: false}}]}});">
</script>
<script>
    document.addEventListener('dblclick', function() {{
        window.location.href = 'action:edit';
    }});
</script>
</head>
<body>
{content}
</body>
</html>
"""


class MathWebPage(QWebEnginePage):
    """Custom QWebEnginePage intercepting page jump anchor links and double-click edit triggers."""

    jump_to_page_requested = Signal(int)
    double_clicked = Signal()

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        href = url.toString() if isinstance(url, QUrl) else str(url)
        if "action:edit" in href:
            self.double_clicked.emit()
            return False
        page_match = re.search(r"(?:page:|#page-)(\d+)", href, re.IGNORECASE)
        if page_match:
            page_1based = int(page_match.group(1))
            page_0based = max(0, page_1based - 1)
            self.jump_to_page_requested.emit(page_0based)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class MathTextEdit(QTextEdit):
    """QTextEdit subclass supporting Shift+Enter or Ctrl+Enter to trigger done/render signal."""

    done_editing_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and (
            event.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier)
        ):
            self.done_editing_requested.emit()
            return
        super().keyPressEvent(event)


class MathNotesEditor(QWidget):
    """Running Markdown Notes editor with Jupyter-style QWebEngineView KaTeX formula rendering."""

    jump_to_page_requested = Signal(int)

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_study_list_id: Optional[int] = None
        self._page_initialized: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header Bar
        hdr_layout = QHBoxLayout()
        self.lbl_title = QLabel("Running Notes (Markdown & LaTeX Math)")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #2196F3; font-size: 13px;")
        hdr_layout.addWidget(self.lbl_title)

        self.lbl_hint = QLabel("(Double-click rendered view to edit)")
        self.lbl_hint.setStyleSheet("color: #888; font-size: 11px; font-style: italic;")
        hdr_layout.addWidget(self.lbl_hint)

        hdr_layout.addStretch()

        self.btn_toggle_mode = QPushButton("✏️ Edit Notes")
        self.btn_toggle_mode.setStyleSheet(
            "QPushButton { background: #2196F3; color: white; border-radius: 3px; padding: 4px 10px; font-weight: bold; } "
            "QPushButton:hover { background: #1e88e5; }"
        )
        self.btn_toggle_mode.clicked.connect(self._toggle_mode)
        hdr_layout.addWidget(self.btn_toggle_mode)

        self.btn_export = QPushButton("Export .md")
        self.btn_export.setStyleSheet(
            "QPushButton { background: #424242; color: white; border-radius: 3px; padding: 4px 8px; } "
            "QPushButton:hover { background: #616161; }"
        )
        self.btn_export.clicked.connect(self._export_markdown)
        hdr_layout.addWidget(self.btn_export)

        layout.addLayout(hdr_layout)

        # Stacked Widget (Single Section Mode)
        self.stack = QStackedWidget(self)

        # View Index 0: Full-Width QWebEngineView KaTeX Renderer
        self.web_page = MathWebPage(self)
        self.web_page.jump_to_page_requested.connect(self.jump_to_page_requested.emit)
        self.web_page.double_clicked.connect(self.switch_to_edit_mode)

        self.preview = QWebEngineView(self.stack)
        self.preview.setPage(self.web_page)
        self.stack.addWidget(self.preview)

        # View Index 1: Full-Width Raw Markdown & LaTeX Text Editor
        self.editor = MathTextEdit(self.stack)
        self.editor.setPlaceholderText(
            "# Study Notes\n\nWrite running notes in Markdown with LaTeX math formulas:\n\nInline math: $\\hat{x}^* N^\\alpha \\hat{x} \\ge |X| + |Y|$\n\nDisplay equation:\n$$\\rho = -X - Y - Z < 2(|X| + |Y|) + \\nu_1$$\n"
        )
        self.editor.setStyleSheet(
            "QTextEdit { background-color: #1a1a1a; color: #f0f0f0; border: 1px solid #333; font-family: 'Consolas', monospace; font-size: 13px; border-radius: 4px; padding: 8px; }"
        )
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.done_editing_requested.connect(self.switch_to_preview_mode)
        self.stack.addWidget(self.editor)

        layout.addWidget(self.stack)

        # Auto-save timer
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._save_notes)

        # Start in rendered preview mode
        self.switch_to_preview_mode()

    def _toggle_mode(self):
        if self.stack.currentIndex() == 0:
            self.switch_to_edit_mode()
        else:
            self.switch_to_preview_mode()

    def switch_to_edit_mode(self):
        self.stack.setCurrentIndex(1)
        self.btn_toggle_mode.setText("✓ Done (Render Math)")
        self.btn_toggle_mode.setStyleSheet(
            "QPushButton { background: #4CAF50; color: white; border-radius: 3px; padding: 4px 10px; font-weight: bold; } "
            "QPushButton:hover { background: #43A047; }"
        )
        self.lbl_hint.setText("(Press Shift+Enter or click Done to render)")
        self.editor.setFocus()

    def switch_to_preview_mode(self):
        self._update_preview()
        self._save_notes()
        self.stack.setCurrentIndex(0)
        self.btn_toggle_mode.setText("✏️ Edit Notes")
        self.btn_toggle_mode.setStyleSheet(
            "QPushButton { background: #2196F3; color: white; border-radius: 3px; padding: 4px 10px; font-weight: bold; } "
            "QPushButton:hover { background: #1e88e5; }"
        )
        self.lbl_hint.setText("(Double-click rendered view to edit)")

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
        self.switch_to_preview_mode()

    @Slot(QUrl)
    def _on_anchor_clicked(self, url: QUrl):
        href = url.toString() if isinstance(url, QUrl) else str(url)
        page_match = re.search(r"(?:page:|#page-)(\d+)", href, re.IGNORECASE)
        if page_match:
            page_1based = int(page_match.group(1))
            page_0based = max(0, page_1based - 1)
            self.jump_to_page_requested.emit(page_0based)

    @Slot()
    def _on_text_changed(self):
        if self.current_study_list_id:
            self.save_timer.start(500)

    def _save_notes(self):
        if self.current_study_list_id:
            self.db_manager.update_study_list_notes(
                self.current_study_list_id, self.editor.toPlainText()
            )

    def _update_preview(self):
        md = self.editor.toPlainText()

        # Auto-correct common math symbols missing backslashes inside math delimiters (e.g., $sum_ -> $\sum_)
        def fix_math_commands(match):
            m_text = match.group(0)
            m_text = re.sub(
                r"(?<!\\)\b(sum|prod|int|lim|sin|cos|tan|log|ln|alpha|beta|gamma|delta|theta|lambda|mu|pi|sigma|phi|omega|Delta|Omega|Theta|Lambda|Sigma|infty|sqrt)\b",
                r"\\\1",
                m_text,
            )
            return m_text

        md = re.sub(r"\$\$[\s\S]*?\$\$|\$.*?\$", fix_math_commands, md)

        # Convert basic markdown formatting to HTML
        doc = QTextDocument()
        doc.setMarkdown(md)
        html_body = doc.toHtml()

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


