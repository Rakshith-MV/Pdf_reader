import os
import threading
from typing import List, Dict, Tuple, Optional, Any
import pymupdf as fitz  # PyMuPDF
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QColor, QPainter

COLOR_THEMES = {
    "day": {"bg": (255, 255, 255), "fg": (0, 0, 0)},
    "dark": {"bg": (20, 20, 20), "fg": (208, 208, 208)},
    "twilight": {"bg": (37, 37, 37), "fg": (160, 160, 160)},
    "sepia": {"bg": (251, 240, 217), "fg": (56, 43, 29)},
    "sepia_contrast": {"bg": (244, 226, 199), "fg": (42, 29, 18)},
}

class DocumentReader:
    """Wrapper around PyMuPDF fitz engine with High-DPI crisp rendering, text selection, and paper themes."""

    def __init__(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        self.file_path = file_path
        self._lock = threading.Lock()
        # Page geometry is immutable for the lifetime of a PDF.  Keeping it
        # here avoids walking the document again when a recently-opened file
        # is restored from the session cache.
        self._page_sizes: Dict[int, Tuple[float, float]] = {}
        with self._lock:
            self.doc: fitz.Document = fitz.open(file_path)
            self.total_pages = len(self.doc)

    @property
    def title(self) -> str:
        with self._lock:
            if self.doc:
                meta = self.doc.metadata
                if meta and meta.get("title"):
                    return meta["title"].strip()
        return os.path.basename(self.file_path)

    @property
    def author(self) -> str:
        with self._lock:
            if self.doc:
                meta = self.doc.metadata
                if meta and meta.get("author"):
                    return meta["author"].strip()
        return "Unknown Author"

    def get_toc(self) -> List[Tuple[int, str, int]]:
        """Returns Table of Contents as list of (level, title, page_number_1based)."""
        try:
            with self._lock:
                return self.doc.get_toc() if self.doc else []
        except Exception:
            return []

    def get_page_size(self, page_number: int) -> Tuple[float, float]:
        """Returns (width, height) of the page in points (0-indexed page_number)."""
        if 0 <= page_number < self.total_pages:
            with self._lock:
                cached_size = self._page_sizes.get(page_number)
                if cached_size is not None:
                    return cached_size
                if self.doc:
                    page = self.doc[page_number]
                    rect = page.rect
                    size = (rect.width, rect.height)
                    self._page_sizes[page_number] = size
                    return size
        return (600.0, 800.0)

    def get_displaylist(self, page_number: int) -> Optional[fitz.DisplayList]:
        """Creates and returns a PyMuPDF DisplayList for page_number."""
        if not (0 <= page_number < self.total_pages):
            return None
        with self._lock:
            if not self.doc:
                return None
            page = self.doc[page_number]
            return page.get_displaylist()

    def render_page_image_from_displaylist(
        self, display_list: fitz.DisplayList, zoom: float = 1.0, theme: str = "day", dpr: float = 1.0
    ) -> QImage:
        """Renders QImage directly from a cached DisplayList at requested zoom and devicePixelRatio."""
        if not display_list:
            return QImage()

        scale = zoom * dpr
        mat = fitz.Matrix(scale, scale)
        pix = display_list.get_pixmap(matrix=mat, alpha=False)

        qimg = QImage(
            pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888
        ).copy()

        if theme in COLOR_THEMES and theme != "day":
            qimg = self._apply_color_theme(qimg, theme)

        return qimg

    def render_page_image(
        self, page_number: int, zoom: float = 1.0, theme: str = "day", dpr: float = 1.0
    ) -> QImage:
        """
        Renders page_number (0-indexed) to QImage at requested zoom and devicePixelRatio.
        Returns QImage safely off the GUI thread.
        """
        if not (0 <= page_number < self.total_pages):
            return QImage()

        with self._lock:
            if not self.doc:
                return QImage()
            page = self.doc[page_number]
            scale = zoom * dpr
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            qimg = QImage(
                pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888
            ).copy()

        if theme in COLOR_THEMES and theme != "day":
            qimg = self._apply_color_theme(qimg, theme)

        return qimg

    def render_page(
        self, page_number: int, zoom: float = 1.0, theme: str = "day"
    ) -> QPixmap:
        """Legacy helper returning QPixmap (GUI thread only)."""
        qimg = self.render_page_image(page_number, zoom=zoom, theme=theme, dpr=1.0)
        return QPixmap.fromImage(qimg)

    def _apply_color_theme(self, qimg: QImage, theme: str) -> QImage:
        """Applies exact tinting & background color rendering matching ReadEra sepia, sepia contrast, and twilight."""
        bg_r, bg_g, bg_b = COLOR_THEMES[theme]["bg"]
        fg_r, fg_g, fg_b = COLOR_THEMES[theme]["fg"]

        result = QImage(qimg.size(), QImage.Format_RGB888)
        painter = QPainter(result)
        bg_qcolor = QColor(bg_r, bg_g, bg_b)
        painter.fillRect(result.rect(), bg_qcolor)

        if theme in ("dark", "twilight"):
            # Invert page pixels for dark/twilight reading
            inv = qimg.copy()
            inv.invertPixels(QImage.InvertRgb)
            painter.setCompositionMode(QPainter.CompositionMode_Screen)
            fg_qcolor = QColor(fg_r, fg_g, fg_b)
            painter.setBrush(fg_qcolor)
            painter.setPen(Qt.NoPen)
            painter.drawRect(result.rect())
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawImage(0, 0, inv)
        else:
            # Multiply blend mode for natural sepia & sepia contrast paper feel
            painter.setCompositionMode(QPainter.CompositionMode_Multiply)
            painter.drawImage(0, 0, qimg)
            if theme == "sepia_contrast":
                painter.setCompositionMode(QPainter.CompositionMode_Darken)
                painter.fillRect(result.rect(), QColor(fg_r, fg_g, fg_b, 40))

        painter.end()
        return result

    def render_cover(self, width: int = 160, height: int = 220) -> QPixmap:
        """Renders cover thumbnail (page 0) resized to fit bounding dimensions."""
        if self.total_pages == 0:
            return QPixmap()

        with self._lock:
            if not self.doc:
                return QPixmap()
            page = self.doc[0]
            rect = page.rect
            scale_x = width / rect.width if rect.width > 0 else 1.0
            scale_y = height / rect.height if rect.height > 0 else 1.0
            zoom = min(scale_x, scale_y) * 2.0

            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            qimg = QImage(
                pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888
            ).copy()
        pixmap = QPixmap.fromImage(qimg)
        return pixmap.scaled(
            width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

    def get_words(self, page_number: int) -> List[Tuple[float, float, float, float, str]]:
        """
        Returns word bounding boxes for text selection:
        [(x0, y0, x1, y1, word_text), ...] in page points.
        """
        if not (0 <= page_number < self.total_pages):
            return []
        with self._lock:
            if not self.doc:
                return []
            words = self.doc[page_number].get_text("words")
            return [(w[0], w[1], w[2], w[3], w[4]) for w in words]

    def search_page(self, page_number: int, query: str) -> List[Tuple[float, float, float, float]]:
        if not (0 <= page_number < self.total_pages) or not query.strip():
            return []

        page = self.doc[page_number]
        quads = page.search_for(query)
        res = []
        for r in quads:
            res.append((r.x0, r.y0, r.x1, r.y1))
        return res

    def search_all_pages(self, query: str) -> List[Dict[str, Any]]:
        results = []
        if not query.strip():
            return results

        for i in range(self.total_pages):
            boxes = self.search_page(i, query)
            if boxes:
                results.append({"page": i, "matches": len(boxes), "boxes": boxes})
        return results

    def extract_text(self, page_number: int) -> str:
        if 0 <= page_number < self.total_pages:
            return self.doc[page_number].get_text()
        return ""

    def close(self):
        if self.doc:
            self.doc.close()
            self.doc = None
