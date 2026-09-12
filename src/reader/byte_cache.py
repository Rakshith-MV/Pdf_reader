from collections import OrderedDict
from typing import Dict, Tuple, Any, Optional, List
import sys
from PySide6.QtGui import QImage
from src.reader.performance_metrics import metrics


class ImageLRUCache:
    """Byte-budgeted LRU cache for rendered QImage page rasters."""

    def __init__(self, max_bytes: int = 100 * 1024 * 1024):  # 100 MB default
        self.max_bytes = max_bytes
        self.current_bytes = 0
        self.cache: OrderedDict[Tuple[Any, int, float, str, float], QImage] = OrderedDict()

    def make_key(self, doc_id: Any, page_num: int, zoom: float, theme: str, dpr: float) -> Tuple[Any, int, float, str, float]:
        return (doc_id, page_num, round(zoom, 2), theme, round(dpr, 2))

    def get(self, doc_id: Any, page_num: int, zoom: float, theme: str, dpr: float) -> Optional[QImage]:
        key = self.make_key(doc_id, page_num, zoom, theme, dpr)
        if key in self.cache:
            self.cache.move_to_end(key)
            metrics.record_cache_hit()
            return self.cache[key]
        metrics.record_cache_miss()
        return None

    def put(self, doc_id: Any, page_num: int, zoom: float, theme: str, dpr: float, qimage: QImage):
        if qimage.isNull():
            return
        key = self.make_key(doc_id, page_num, zoom, theme, dpr)
        size_bytes = qimage.sizeInBytes()

        if key in self.cache:
            old_img = self.cache.pop(key)
            self.current_bytes -= old_img.sizeInBytes()

        while self.current_bytes + size_bytes > self.max_bytes and self.cache:
            _, evicted_img = self.cache.popitem(last=False)
            self.current_bytes -= evicted_img.sizeInBytes()

        self.cache[key] = qimage
        self.current_bytes += size_bytes
        metrics.image_cache_memory_bytes = self.current_bytes

    def clear(self):
        self.cache.clear()
        self.current_bytes = 0
        metrics.image_cache_memory_bytes = 0


class DisplayListLRUCache:
    """Byte/Entry-budgeted LRU cache for parsed PyMuPDF DisplayList objects."""

    ESTIMATED_BYTES_PER_DL = 256 * 1024  # ~256 KB estimate per DisplayList

    def __init__(self, max_bytes: int = 50 * 1024 * 1024, max_entries: int = 100):  # 50 MB default
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self.current_bytes = 0
        self.cache: OrderedDict[Tuple[Any, int], Any] = OrderedDict()

    def get(self, doc_id: Any, page_num: int) -> Optional[Any]:
        key = (doc_id, page_num)
        if key in self.cache:
            self.cache.move_to_end(key)
            metrics.record_displaylist_hit()
            return self.cache[key]
        metrics.record_displaylist_miss()
        return None

    def put(self, doc_id: Any, page_num: int, display_list: Any):
        if display_list is None:
            return
        key = (doc_id, page_num)
        size_bytes = self.ESTIMATED_BYTES_PER_DL

        if key in self.cache:
            self.cache.pop(key)
            self.current_bytes -= size_bytes

        while (self.current_bytes + size_bytes > self.max_bytes or len(self.cache) >= self.max_entries) and self.cache:
            self.cache.popitem(last=False)
            self.current_bytes -= size_bytes

        self.cache[key] = display_list
        self.current_bytes += size_bytes
        metrics.displaylist_cache_memory_bytes = self.current_bytes

    def clear(self):
        self.cache.clear()
        self.current_bytes = 0
        metrics.displaylist_cache_memory_bytes = 0


class WordLRUCache:
    """LRU cache for extracted word bounding boxes."""

    def __init__(self, max_entries: int = 200):
        self.max_entries = max_entries
        self.cache: OrderedDict[Tuple[Any, int], List[Any]] = OrderedDict()
        self.current_bytes = 0

    def get(self, doc_id: Any, page_num: int) -> Optional[List[Any]]:
        key = (doc_id, page_num)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None

    def put(self, doc_id: Any, page_num: int, words: List[Any]):
        key = (doc_id, page_num)
        size_bytes = len(words) * 64  # rough estimate per word item

        if key in self.cache:
            old_words = self.cache.pop(key)
            self.current_bytes -= len(old_words) * 64

        while len(self.cache) >= self.max_entries and self.cache:
            _, evicted_words = self.cache.popitem(last=False)
            self.current_bytes -= len(evicted_words) * 64

        self.cache[key] = words
        self.current_bytes += size_bytes
        metrics.word_cache_memory_bytes = self.current_bytes

    def clear(self):
        self.cache.clear()
        self.current_bytes = 0
        metrics.word_cache_memory_bytes = 0
