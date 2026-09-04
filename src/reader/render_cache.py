from collections import OrderedDict
from typing import Optional, Tuple
from PySide6.QtGui import QPixmap
from src.reader.document import DocumentReader

class RenderCache:
    """LRU render cache for PyMuPDF rendered pages with theme support."""

    def __init__(self, max_entries: int = 15):
        self.max_entries = max_entries
        self.cache: OrderedDict[Tuple[int, float, str], QPixmap] = OrderedDict()

    def get(self, page_number: int, zoom: float, theme: str = "day") -> Optional[QPixmap]:
        key = (page_number, round(zoom, 2), theme)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, page_number: int, zoom: float, theme: str, pixmap: QPixmap):
        key = (page_number, round(zoom, 2), theme)
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.max_entries:
                self.cache.popitem(last=False)
            self.cache[key] = pixmap

    def prefetch_surrounding(self, doc_reader: DocumentReader, current_page: int, zoom: float, theme: str = "day"):
        """Prefetches pages current_page - 1 and current_page + 1."""
        for p in (current_page - 1, current_page + 1):
            if 0 <= p < doc_reader.total_pages:
                key = (p, round(zoom, 2), theme)
                if key not in self.cache:
                    pixmap = doc_reader.render_page(p, zoom, theme=theme)
                    self.put(p, zoom, theme, pixmap)

    def clear(self):
        self.cache.clear()
