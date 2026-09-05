from collections import OrderedDict
from typing import Optional, Tuple, List, Dict, Any
from PySide6.QtGui import QPixmap
from src.reader.document import DocumentReader

class RenderCache:
    """LRU render cache for PyMuPDF rendered pages and word lists with theme support."""

    def __init__(self, max_entries: int = 25):
        self.max_entries = max_entries
        self.cache: OrderedDict[Tuple[int, float, str], Tuple[QPixmap, List[Any]]] = OrderedDict()
        self.words_cache: Dict[int, List[Any]] = {}

    def get(self, page_number: int, zoom: float, theme: str = "day") -> Optional[Tuple[QPixmap, List[Any]]]:
        key = (page_number, round(zoom, 2), theme)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, page_number: int, zoom: float, theme: str, pixmap: QPixmap, words: List[Any]):
        key = (page_number, round(zoom, 2), theme)
        if key in self.cache:
            self.cache.move_to_end(key)
            self.cache[key] = (pixmap, words)
        else:
            if len(self.cache) >= self.max_entries:
                self.cache.popitem(last=False)
            self.cache[key] = (pixmap, words)

        if words:
            self.words_cache[page_number] = words

    def get_words(self, page_number: int) -> Optional[List[Any]]:
        return self.words_cache.get(page_number)

    def clear(self):
        self.cache.clear()
        self.words_cache.clear()
