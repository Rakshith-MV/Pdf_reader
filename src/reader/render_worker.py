from typing import List, Tuple, Dict, Any, Optional
from PySide6.QtCore import QRunnable, QObject, Signal, Slot
from PySide6.QtGui import QPixmap
from src.reader.document import DocumentReader


class PageRenderSignals(QObject):
    """Signals for background page rendering completed tasks."""
    render_complete = Signal(int, float, str, object, list)  # page_num, zoom, theme, pixmap, words


class PageRenderTask(QRunnable):
    """
    Background worker task rendering PDF page pixmap and extracting word lists off the Qt main UI thread.
    """

    def __init__(self, doc_reader: DocumentReader, page_num: int, zoom: float, theme: str = "day"):
        super().__init__()
        self.doc_reader = doc_reader
        self.page_num = page_num
        self.zoom = zoom
        self.theme = theme
        self.signals = PageRenderSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            pixmap = self.doc_reader.render_page(self.page_num, self.zoom, theme=self.theme)
            words = self.doc_reader.get_words(self.page_num)
            self.signals.render_complete.emit(self.page_num, self.zoom, self.theme, pixmap, words)
        except Exception:
            # Emit empty fallback pixmap and words if page rendering fails or is interrupted
            self.signals.render_complete.emit(self.page_num, self.zoom, self.theme, QPixmap(), [])
