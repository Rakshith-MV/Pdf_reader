import json
import urllib.parse
from typing import List, Tuple, Optional, Dict, Any
from PySide6.QtCore import Qt, QRectF, Signal, Slot, QPoint, QRect, QTimer, QUrl, QEvent
from PySide6.QtGui import (
    QPainter,
    QPixmap,
    QColor,
    QPen,
    QBrush,
    QMouseEvent,
    QWheelEvent,
    QKeyEvent,
    QCursor,
    QFont,
    QShortcut,
    QKeySequence,
    QDesktopServices,
)
from PySide6.QtWidgets import (
    QScrollArea,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMenu,
    QInputDialog,
    QMessageBox,
    QApplication,
    QFrame,
    QLabel,
)
from src.reader.document import DocumentReader
from src.reader.render_cache import RenderCache

HIGHLIGHT_COLORS = [
    ("#FFF59D", "Yellow"),
    ("#A5D6A7", "Green"),
    ("#90CAF9", "Blue"),
    ("#F48FB1", "Pink"),
    ("#FFCC80", "Orange"),
]

class FloatingSelectionToolbar(QFrame):
    """Floating menu bar displayed near selected text for highlighting, underlining, copying, and Google search."""

    highlight_requested = Signal(str, str)
    comment_requested = Signal(str)
    copy_requested = Signal()
    search_google_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_color = "#FFF59D"
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background-color: #2b2b2b; color: white; border: 1px solid #555; border-radius: 6px; } "
            "QPushButton { background: #3c3c3c; border: none; border-radius: 3px; padding: 4px 8px; color: white; font-size: 11px; } "
            "QPushButton:hover { background: #505050; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        for hex_code, name in HIGHLIGHT_COLORS:
            btn_col = QPushButton()
            btn_col.setFixedSize(18, 18)
            btn_col.setToolTip(name)
            btn_col.setStyleSheet(
                f"background-color: {hex_code}; border: 1px solid #666; border-radius: 9px;"
            )
            btn_col.clicked.connect(lambda _, c=hex_code: self._set_color(c))
            layout.addWidget(btn_col)

        self.btn_hl = QPushButton("Highlight")
        self.btn_hl.clicked.connect(lambda: self.highlight_requested.emit(self.selected_color, "highlight"))
        layout.addWidget(self.btn_hl)

        self.btn_ul = QPushButton("Underline")
        self.btn_ul.clicked.connect(lambda: self.highlight_requested.emit(self.selected_color, "underline"))
        layout.addWidget(self.btn_ul)

        self.btn_note = QPushButton("+ Note")
        self.btn_note.clicked.connect(lambda: self.comment_requested.emit(self.selected_color))
        layout.addWidget(self.btn_note)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.clicked.connect(self.copy_requested.emit)
        layout.addWidget(self.btn_copy)

        self.btn_google = QPushButton("🔍 Search Google")
        self.btn_google.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; border-radius: 3px; padding: 4px 8px; } "
            "QPushButton:hover { background-color: #1e88e5; }"
        )
        self.btn_google.clicked.connect(self.search_google_requested.emit)
        layout.addWidget(self.btn_google)

    def _set_color(self, color_hex: str):
        self.selected_color = color_hex
        self.btn_hl.setStyleSheet(f"background-color: {color_hex}; color: black; font-weight: bold;")


class PageCanvas(QWidget):
    """Canvas widget painting Chrome-grade PDF page pixmap, highlights, underlines, and text selection."""

    region_selected = Signal(int, float, float, float, float)
    text_selected = Signal(int, str, list)
    clear_selection_signal = Signal()
    add_highlight_requested = Signal(int, list, str, str, str, str)

    def __init__(self, page_num: int = 0, parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self.pixmap: QPixmap = QPixmap()
        self.zoom: float = 1.0
        self.unscaled_size: Tuple[float, float] = (600.0, 800.0)

        self.words: List[Tuple[float, float, float, float, str]] = []
        self.search_boxes: List[Tuple[float, float, float, float]] = []
        self.notes: List[Dict[str, Any]] = []
        self.highlights: List[Dict[str, Any]] = []

        # Text Selection state
        self.is_selecting: bool = False
        self.select_start: QPoint = QPoint()
        self.select_current: QPoint = QPoint()
        self.selected_words: List[Tuple[float, float, float, float, str]] = []
        self.selected_rects: List[Tuple[float, float, float, float]] = []
        self.selected_text: str = ""

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("PageCanvas { background-color: white; border: 1px solid #1a1a1a; }")

    def clear_selection(self):
        self.selected_words = []
        self.selected_rects = []
        self.selected_text = ""
        self.update()

    def set_page_data(
        self,
        pixmap: QPixmap,
        zoom: float,
        unscaled_size: Tuple[float, float],
        words: List[Tuple[float, float, float, float, str]] = None,
        search_boxes: List[Tuple[float, float, float, float]] = None,
        notes: List[Dict[str, Any]] = None,
        highlights: List[Dict[str, Any]] = None,
    ):
        self.pixmap = pixmap
        self.zoom = zoom
        self.unscaled_size = unscaled_size
        self.words = words or []
        self.search_boxes = search_boxes or []
        self.notes = notes or []
        self.highlights = highlights or []

        w = int(unscaled_size[0] * zoom)
        h = int(unscaled_size[1] * zoom)
        self.setFixedSize(max(10, w), max(10, h))
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.clear_selection_signal.emit()
            self.is_selecting = True
            self.select_start = event.position().toPoint()
            self.select_current = event.position().toPoint()
            self.selected_words = []
            self.selected_rects = []
            self.selected_text = ""
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.is_selecting:
            self.select_current = event.position().toPoint()
            self._update_text_selection()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            self._update_text_selection()

            if self.selected_text.strip() and self.selected_rects:
                self.text_selected.emit(self.page_num, self.selected_text, self.selected_rects)
            else:
                rect = QRect(self.select_start, self.select_current).normalized()
                if rect.width() > 10 and rect.height() > 10 and self.zoom > 0:
                    ux, uy = rect.x() / self.zoom, rect.y() / self.zoom
                    uw, uh = rect.width() / self.zoom, rect.height() / self.zoom
                    self.region_selected.emit(self.page_num, ux, uy, uw, uh)

            self.update()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        event.ignore()

    def _get_word_index_at_pos(self, px: float, py: float) -> int:
        """Finds index of word in self.words closest in reading order to unscaled point (px, py)."""
        if not self.words:
            return -1

        # 1. Direct hit check
        for idx, (x0, y0, x1, y1, word) in enumerate(self.words):
            if x0 <= px <= x1 and y0 <= py <= y1:
                return idx

        # 2. Group words into horizontal lines
        lines = []
        for idx, (x0, y0, x1, y1, word) in enumerate(self.words):
            matched = False
            for line in lines:
                l_min_y, l_max_y, indices = line
                if not (y1 < l_min_y or y0 > l_max_y):
                    indices.append(idx)
                    line[0] = min(l_min_y, y0)
                    line[1] = max(l_max_y, y1)
                    matched = True
                    break
            if not matched:
                lines.append([y0, y1, [idx]])

        if not lines:
            return 0

        lines.sort(key=lambda l: l[0])

        # 3. Find target line
        if py < lines[0][0]:
            target_line = lines[0]
        elif py > lines[-1][1]:
            target_line = lines[-1]
        else:
            best_dist = float("inf")
            target_line = lines[0]
            for line in lines:
                l_min_y, l_max_y, _ = line
                if l_min_y <= py <= l_max_y:
                    target_line = line
                    break
                dist = min(abs(py - l_min_y), abs(py - l_max_y))
                if dist < best_dist:
                    best_dist = dist
                    target_line = line

        # 4. Find word on target line by x coordinate
        indices = target_line[2]
        indices.sort(key=lambda i: self.words[i][0])

        if px <= self.words[indices[0]][0]:
            return indices[0]
        if px >= self.words[indices[-1]][1]:
            return indices[-1]

        best_idx = indices[0]
        min_dx = float("inf")
        for i in indices:
            x0, _, x1, _, _ = self.words[i]
            if x0 <= px <= x1:
                return i
            mid_x = (x0 + x1) / 2.0
            dx = abs(px - mid_x)
            if dx < min_dx:
                min_dx = dx
                best_idx = i

        return best_idx

    def _update_text_selection(self):
        if not self.words or self.zoom <= 0:
            return

        start_px = self.select_start.x() / self.zoom
        start_py = self.select_start.y() / self.zoom
        curr_px = self.select_current.x() / self.zoom
        curr_py = self.select_current.y() / self.zoom

        start_idx = self._get_word_index_at_pos(start_px, start_py)
        end_idx = self._get_word_index_at_pos(curr_px, curr_py)

        if start_idx < 0 or end_idx < 0:
            self.selected_words = []
            self.selected_rects = []
            self.selected_text = ""
            return

        idx_a = min(start_idx, end_idx)
        idx_b = max(start_idx, end_idx)

        matched_words = self.words[idx_a : idx_b + 1]
        text_parts = [w[4] for w in matched_words]
        rects = [(w[0], w[1], w[2], w[3]) for w in matched_words]

        self.selected_words = matched_words
        self.selected_rects = rects
        self.selected_text = " ".join(text_parts)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 1. Paint PDF Page Pixmap
        if not self.pixmap.isNull():
            painter.drawPixmap(self.rect(), self.pixmap)
        else:
            painter.fillRect(self.rect(), QColor(250, 250, 250))

        # 2. Render Stored Highlights & Underlines
        for hl in self.highlights:
            color_hex = hl.get("color", "#FFF59D")
            style = hl.get("style", "highlight")
            rects = hl.get("rects", [])
            qcol = QColor(color_hex)

            if style == "highlight":
                qcol.setAlpha(130)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(qcol))
                for (rx0, ry0, rx1, ry1) in rects:
                    sx0, sy0 = rx0 * self.zoom, ry0 * self.zoom
                    sw, sh = (rx1 - rx0) * self.zoom, (ry1 - ry0) * self.zoom
                    painter.drawRoundedRect(QRectF(sx0, sy0, sw, sh), 2, 2)
            elif style == "underline":
                pen = QPen(qcol, max(2.0, 2.0 * self.zoom), Qt.SolidLine)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                for (rx0, ry0, rx1, ry1) in rects:
                    sx0, sy1 = rx0 * self.zoom, ry1 * self.zoom
                    sx1 = rx1 * self.zoom
                    painter.drawLine(int(sx0), int(sy1), int(sx1), int(sy1))

            if hl.get("comment_text") and rects:
                rx0, ry0, _, _ = rects[0]
                badge_x = int(rx0 * self.zoom)
                badge_y = int(ry0 * self.zoom - 4)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(33, 150, 243)))
                painter.drawEllipse(QPoint(badge_x, badge_y), 5, 5)

        # 3. Draw Search Highlights
        if self.search_boxes:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(255, 235, 59, 140)))
            for (x0, y0, x1, y1) in self.search_boxes:
                sx0, sy0 = x0 * self.zoom, y0 * self.zoom
                sw, sh = (x1 - x0) * self.zoom, (y1 - y0) * self.zoom
                painter.drawRect(QRectF(sx0, sy0, sw, sh))

        # 4. Draw Active Drag Selection Highlight
        if self.selected_rects:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(33, 150, 243, 100)))
            for (wx0, wy0, wx1, wy1) in self.selected_rects:
                sx0, sy0 = wx0 * self.zoom, wy0 * self.zoom
                sw, sh = (wx1 - wx0) * self.zoom, (wy1 - wy0) * self.zoom
                painter.drawRect(QRectF(sx0, sy0, sw, sh))


class PDFViewerWidget(QScrollArea):
    """
    Chrome-grade PDF viewer supporting Continuous Vertical Scroll, High-DPI sharpness,
    text selection toolbar, and Escape / click dismissal of text highlights.
    """

    page_changed = Signal(int)
    zoom_changed = Signal(float)
    add_highlight_signal = Signal(int, list, str, str, str, str)
    region_note_requested = Signal(int, float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc_reader: Optional[DocumentReader] = None
        self.render_cache = RenderCache()
        self.current_page: int = 0
        self.zoom_level: float = 1.0
        self.theme: str = "day"
        self.is_continuous_scroll: bool = True

        self.page_canvases: List[PageCanvas] = []
        self.search_boxes_by_page: Dict[int, List[Tuple[float, float, float, float]]] = {}
        self.notes_by_page: Dict[int, List[Dict[str, Any]]] = {}
        self.highlights_by_page: Dict[int, List[Dict[str, Any]]] = {}

        self.setAlignment(Qt.AlignCenter)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { background-color: #2b2b2b; border: none; }")

        # Vertical Scroll Container
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignCenter)
        self.container_layout.setContentsMargins(30, 20, 30, 20)
        self.container_layout.setSpacing(20)

        self.setWidget(self.container)

        # Track viewport scrolling
        self.verticalScrollBar().valueChanged.connect(self._on_scroll_position_changed)

        # Floating Text Selection Toolbar
        self.toolbar = FloatingSelectionToolbar(self.viewport())
        self.toolbar.hide()
        self.toolbar.highlight_requested.connect(self._apply_highlight)
        self.toolbar.comment_requested.connect(self._apply_highlight_with_comment)
        self.toolbar.copy_requested.connect(self._copy_selected_text)
        self.toolbar.search_google_requested.connect(self._search_google_for_selected_text)

        self.active_selection: Optional[Tuple[int, str, list]] = None

        # Shortcut: Pressing ESC clears highlight toolbar and selections
        QShortcut(QKeySequence("Escape"), self, self.clear_selection_and_toolbar)

    def clear_selection_and_toolbar(self):
        self.toolbar.hide()
        self.active_selection = None
        for c in self.page_canvases:
            c.clear_selection()

    def set_document(
        self,
        reader: DocumentReader,
        initial_page: int = 0,
        initial_zoom: float = 1.0,
        theme: str = "day",
    ):
        self.doc_reader = reader
        self.current_page = max(0, min(initial_page, reader.total_pages - 1)) if reader.total_pages > 0 else 0
        self.zoom_level = initial_zoom
        self.theme = theme
        self.render_cache.clear()
        self.clear_selection_and_toolbar()

        self._rebuild_page_canvases()
        self.update_view()

        QTimer.singleShot(50, lambda: self.set_page(self.current_page))

    def _rebuild_page_canvases(self):
        for c in self.page_canvases:
            self.container_layout.removeWidget(c)
            c.deleteLater()
        self.page_canvases.clear()

        if not self.doc_reader or self.doc_reader.total_pages == 0:
            return

        if self.is_continuous_scroll:
            for i in range(self.doc_reader.total_pages):
                canvas = PageCanvas(page_num=i, parent=self.container)
                canvas.region_selected.connect(self.region_note_requested.emit)
                canvas.text_selected.connect(self._on_text_selected)
                canvas.clear_selection_signal.connect(self.clear_selection_and_toolbar)
                self.container_layout.addWidget(canvas)
                self.page_canvases.append(canvas)
        else:
            canvas = PageCanvas(page_num=self.current_page, parent=self.container)
            canvas.region_selected.connect(self.region_note_requested.emit)
            canvas.text_selected.connect(self._on_text_selected)
            canvas.clear_selection_signal.connect(self.clear_selection_and_toolbar)
            self.container_layout.addWidget(canvas)
            self.page_canvases.append(canvas)

    def set_page(self, page_num: int):
        if not self.doc_reader or self.doc_reader.total_pages == 0:
            return
        target = max(0, min(page_num, self.doc_reader.total_pages - 1))

        if self.is_continuous_scroll and target < len(self.page_canvases):
            target_canvas = self.page_canvases[target]
            self.verticalScrollBar().setValue(target_canvas.y() - 10)
            self.current_page = target
            self.page_changed.emit(target)
            self.update_view()
        else:
            if target != self.current_page:
                self.current_page = target
                self.clear_selection_and_toolbar()
                self._rebuild_page_canvases()
                self.update_view()
                self.page_changed.emit(self.current_page)

    def set_theme(self, theme: str):
        if theme != self.theme:
            self.theme = theme
            self.update_view()

    def toggle_continuous_scroll(self, enabled: bool):
        if enabled != self.is_continuous_scroll:
            self.is_continuous_scroll = enabled
            self._rebuild_page_canvases()
            self.update_view()
            self.set_page(self.current_page)

    def set_zoom(self, zoom: float):
        zoom = max(0.2, min(5.0, zoom))
        if abs(zoom - self.zoom_level) > 0.01:
            self.zoom_level = zoom
            self.update_view()
            self.zoom_changed.emit(self.zoom_level)

    def fit_width(self):
        if not self.doc_reader or self.doc_reader.total_pages == 0:
            return
        pw, _ = self.doc_reader.get_page_size(self.current_page)
        viewport_w = self.viewport().width() - 80
        if pw > 0 and viewport_w > 0:
            self.set_zoom(viewport_w / pw)

    def fit_page(self):
        if not self.doc_reader or self.doc_reader.total_pages == 0:
            return
        pw, ph = self.doc_reader.get_page_size(self.current_page)
        vw = self.viewport().width() - 80
        vh = self.viewport().height() - 80
        if pw > 0 and ph > 0 and vw > 0 and vh > 0:
            self.set_zoom(min(vw / pw, vh / ph))

    def set_search_highlights(self, search_boxes_by_page: Dict[int, List[Tuple[float, float, float, float]]]):
        self.search_boxes_by_page = search_boxes_by_page
        self.update_view()

    def set_document_annotations(
        self, notes: List[Dict[str, Any]], highlights: List[Dict[str, Any]]
    ):
        self.notes_by_page = {}
        for n in notes:
            p = n["page_number"]
            self.notes_by_page.setdefault(p, []).append(n)

        self.highlights_by_page = {}
        for h in highlights:
            p = h["page_number"]
            self.highlights_by_page.setdefault(p, []).append(h)

        self.update_view()

    def update_view(self):
        if not self.doc_reader or not self.page_canvases:
            return

        viewport_rect = self.viewport().rect()
        scroll_y = self.verticalScrollBar().value()

        for canvas in self.page_canvases:
            p_num = canvas.page_num
            unscaled_size = self.doc_reader.get_page_size(p_num)

            canvas_y = canvas.y()
            canvas_h = int(unscaled_size[1] * self.zoom_level)

            is_near_viewport = (
                not self.is_continuous_scroll
                or (canvas_y + canvas_h >= scroll_y - 1000 and canvas_y <= scroll_y + viewport_rect.height() + 1000)
            )

            if is_near_viewport:
                pixmap = self.render_cache.get(p_num, self.zoom_level, self.theme)
                if pixmap is None:
                    pixmap = self.doc_reader.render_page(p_num, self.zoom_level, theme=self.theme)
                    self.render_cache.put(p_num, self.zoom_level, self.theme, pixmap)

                words = self.doc_reader.get_words(p_num)
                canvas.set_page_data(
                    pixmap=pixmap,
                    zoom=self.zoom_level,
                    unscaled_size=unscaled_size,
                    words=words,
                    search_boxes=self.search_boxes_by_page.get(p_num, []),
                    notes=self.notes_by_page.get(p_num, []),
                    highlights=self.highlights_by_page.get(p_num, []),
                )
            else:
                canvas.set_page_data(
                    pixmap=QPixmap(),
                    zoom=self.zoom_level,
                    unscaled_size=unscaled_size,
                )

    def _on_scroll_position_changed(self, value: int):
        if not self.is_continuous_scroll or not self.page_canvases:
            return

        viewport_center = value + self.viewport().height() // 2
        closest_page = 0
        min_dist = float("inf")

        for canvas in self.page_canvases:
            center = canvas.y() + canvas.height() // 2
            dist = abs(center - viewport_center)
            if dist < min_dist:
                min_dist = dist
                closest_page = canvas.page_num

        if closest_page != self.current_page:
            self.current_page = closest_page
            self.page_changed.emit(self.current_page)

        self.update_view()

    def mousePressEvent(self, event: QMouseEvent):
        self.clear_selection_and_toolbar()
        super().mousePressEvent(event)

    @Slot(int, str, list)
    def _on_text_selected(self, page_num: int, selected_text: str, rects: list):
        self.active_selection = (page_num, selected_text, rects)
        cursor_pos = self.viewport().mapFromGlobal(QCursor.pos())
        self.toolbar.move(max(10, cursor_pos.x() - 100), max(10, cursor_pos.y() - 50))
        self.toolbar.show()
        self.toolbar.raise_()

    @Slot(str, str)
    def _apply_highlight(self, color_hex: str, style: str):
        if self.active_selection:
            p_num, text, rects = self.active_selection
            self.add_highlight_signal.emit(p_num, rects, color_hex, style, text, "")
            self.clear_selection_and_toolbar()

    @Slot(str)
    def _apply_highlight_with_comment(self, color_hex: str):
        if self.active_selection:
            p_num, text, rects = self.active_selection
            comment, ok = QInputDialog.getMultiLineText(
                self, "Add Note to Highlight", f"Enter note for: '{text[:40]}...':"
            )
            if ok and comment.strip():
                self.add_highlight_signal.emit(p_num, rects, color_hex, "highlight", text, comment.strip())
            self.clear_selection_and_toolbar()

    @Slot()
    def _copy_selected_text(self):
        if self.active_selection:
            _, text, _ = self.active_selection
            QApplication.clipboard().setText(text)
            self.clear_selection_and_toolbar()

    @Slot()
    def _search_google_for_selected_text(self):
        if self.active_selection:
            _, text, _ = self.active_selection
            if text.strip():
                query = urllib.parse.quote(text.strip())
                search_url = f"https://www.google.com/search?q={query}"
                QDesktopServices.openUrl(QUrl(search_url))
            self.clear_selection_and_toolbar()

    def next_page(self):
        if self.doc_reader and self.current_page < self.doc_reader.total_pages - 1:
            self.set_page(self.current_page + 1)

    def prev_page(self):
        if self.doc_reader and self.current_page > 0:
            self.set_page(self.current_page - 1)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            angle = event.angleDelta().y()
            if angle > 0:
                self.set_zoom(self.zoom_level * 1.1)
            elif angle < 0:
                self.set_zoom(self.zoom_level / 1.1)
            event.accept()
        else:
            p_delta_y = event.pixelDelta().y()
            a_delta_y = event.angleDelta().y()
            p_delta_x = event.pixelDelta().x()
            a_delta_x = event.angleDelta().x()

            if p_delta_y != 0:
                dy = p_delta_y
            elif a_delta_y != 0:
                dy = int(a_delta_y * 1.2)
            else:
                dy = 0

            if p_delta_x != 0:
                dx = p_delta_x
            elif a_delta_x != 0:
                dx = int(a_delta_x * 1.2)
            else:
                dx = 0

            if dy != 0:
                vbar = self.verticalScrollBar()
                old_val = vbar.value()
                new_val = old_val - dy

                # Non-continuous mode page turning on scroll boundaries
                if not self.is_continuous_scroll:
                    if new_val < vbar.minimum() and self.current_page > 0:
                        self.prev_page()
                        event.accept()
                        return
                    elif new_val > vbar.maximum() and self.doc_reader and self.current_page < self.doc_reader.total_pages - 1:
                        self.next_page()
                        event.accept()
                        return

                vbar.setValue(new_val)
                event.accept()
            elif dx != 0:
                hbar = self.horizontalScrollBar()
                old_val = hbar.value()
                new_val = old_val - dx
                hbar.setValue(new_val)
                event.accept()
            else:
                event.ignore()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.clear_selection_and_toolbar()
            event.accept()
        elif event.key() in (Qt.Key_Right, Qt.Key_PageDown):
            self.next_page()
            event.accept()
        elif event.key() in (Qt.Key_Left, Qt.Key_PageUp):
            self.prev_page()
            event.accept()
        else:
            super().keyPressEvent(event)
