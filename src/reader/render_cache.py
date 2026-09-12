from typing import Optional, Tuple, List, Dict, Any
from PySide6.QtGui import QPixmap
from src.reader.byte_cache import ImageLRUCache, WordLRUCache


class RenderCache:
    """Backward compatibility wrapper delegating to ByteBudgetLRUCache."""

    def __init__(self, max_entries: int = 25):
        self.image_cache = ImageLRUCache(max_bytes=100 * 1024 * 1024)
        self.word_cache = WordLRUCache(max_entries=300)

    def get(self, page_number: int, zoom: float, theme: str = "day") -> Optional[Tuple[QPixmap, List[Any]]]:
        qimg = self.image_cache.get("doc", page_number, zoom, theme, dpr=1.0)
        if qimg is not None:
            words = self.word_cache.get("doc", page_number) or []
            return (QPixmap.fromImage(qimg), words)
        return None

    def put(self, page_number: int, zoom: float, theme: str, pixmap: QPixmap, words: List[Any]):
        if not pixmap.isNull():
            qimg = pixmap.toImage()
            self.image_cache.put("doc", page_number, zoom, theme, 1.0, qimg)
        if words:
            self.word_cache.put("doc", page_number, words)

    def get_words(self, page_number: int) -> Optional[List[Any]]:
        return self.word_cache.get("doc", page_number)

    def clear(self):
        self.image_cache.clear()
        self.word_cache.clear()
