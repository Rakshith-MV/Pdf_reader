import queue
import time
import threading
from typing import Optional, Dict, Tuple, Any, List
from PySide6.QtCore import QThread, Signal, Slot, QObject
from PySide6.QtGui import QImage
from src.reader.document import DocumentReader
from src.reader.byte_cache import ImageLRUCache, DisplayListLRUCache, WordLRUCache
from src.reader.performance_metrics import metrics


class RenderRequest:
    """Encapsulates a single background render or word extraction job."""

    TYPE_RENDER = 1
    TYPE_WORDS = 2

    def __init__(
        self,
        req_type: int,
        page_num: int,
        zoom: float,
        theme: str,
        dpr: float,
        generation_id: int,
        priority: int,
        seq: int,
        doc_id: Any = None,
        doc_reader: Optional[DocumentReader] = None,
    ):
        self.req_type = req_type
        self.page_num = page_num
        self.zoom = zoom
        self.theme = theme
        self.dpr = dpr
        self.generation_id = generation_id
        self.priority = priority
        self.seq = seq
        # Capture the document at enqueue time.  A worker can finish an old
        # request just after the UI switches PDFs; it must never render that
        # old page number against the newly selected document.
        self.doc_id = doc_id
        self.doc_reader = doc_reader

    def __lt__(self, other: "RenderRequest") -> bool:
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.seq < other.seq


class RenderCoordinator(QThread):
    """
    Dedicated single worker thread that exclusively owns PyMuPDF document operations.
    Processes render and text extraction jobs from a priority queue with generation ID validation.
    Returns QImage objects to the main thread via Qt Signals.
    """

    page_rendered = Signal(int, float, str, float, int, QImage)  # page_num, zoom, theme, dpr, gen_id, qimage
    words_extracted = Signal(int, int, list)                    # page_num, gen_id, words

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc_reader: Optional[DocumentReader] = None
        self.doc_id: Any = None
        self.current_generation_id: int = 0

        self.req_queue: queue.PriorityQueue[RenderRequest] = queue.PriorityQueue()
        self.seq_counter: int = 0
        self._running: bool = True
        # A viewport refresh can happen several times before its first render
        # finishes.  Track queued/in-flight keys so those refreshes do not
        # flood the single rendering worker with the same page.
        self._pending_requests = set()
        self._pending_lock = threading.Lock()

        # Byte-budgeted LRU Caches managed by this coordinator thread
        self.image_cache = ImageLRUCache(max_bytes=120 * 1024 * 1024)       # 120 MB
        self.displaylist_cache = DisplayListLRUCache(max_bytes=60 * 1024 * 1024) # 60 MB
        self.word_cache = WordLRUCache(max_entries=300)

    def set_document(self, reader: Optional[DocumentReader], doc_id: Any = None):
        """Sets active DocumentReader and resets generation counter & caches."""
        self.current_generation_id += 1
        self.clear_queue()

        self.doc_reader = reader
        self.doc_id = doc_id or (reader.file_path if reader else None)
        # Keep raster and text caches keyed by document path.  This makes a
        # Ctrl+Tab-style switch back to a recently opened PDF instantaneous.
        # DisplayLists are document-owned native objects, so they are kept
        # only for the active document.
        self.displaylist_cache.clear()

    def set_generation_id(self, gen_id: int):
        self.current_generation_id = gen_id
        self.clear_queue()

    def clear_queue(self):
        with self.req_queue.mutex:
            self.req_queue.queue.clear()
        with self._pending_lock:
            self._pending_requests.clear()
        metrics.render_queue_depth = 0

    def _request_key(self, req_type: int, page_num: int, zoom: float = 1.0,
                     theme: str = "day", dpr: float = 1.0, doc_id: Any = None) -> tuple:
        doc_id = self.doc_id if doc_id is None else doc_id
        if req_type == RenderRequest.TYPE_WORDS:
            return (req_type, doc_id, page_num)
        return (req_type, doc_id, page_num, round(zoom, 2), theme, round(dpr, 2))

    def _mark_pending(self, key: tuple) -> bool:
        with self._pending_lock:
            if key in self._pending_requests:
                return False
            self._pending_requests.add(key)
            return True

    def _finish_pending(self, req: RenderRequest):
        key = self._request_key(req.req_type, req.page_num, req.zoom, req.theme, req.dpr, req.doc_id)
        with self._pending_lock:
            self._pending_requests.discard(key)

    def request_page_render(
        self,
        page_num: int,
        zoom: float,
        theme: str,
        dpr: float,
        generation_id: int,
        priority: int = 1,
    ):
        """Schedules a page render task."""
        if generation_id != self.current_generation_id:
            return

        # Check if already in image cache
        cached_img = self.image_cache.get(self.doc_id, page_num, zoom, theme, dpr)
        if cached_img is not None:
            self.page_rendered.emit(page_num, zoom, theme, dpr, generation_id, cached_img)
            return

        if not self._mark_pending(self._request_key(RenderRequest.TYPE_RENDER, page_num, zoom, theme, dpr)):
            return

        self.seq_counter += 1
        req = RenderRequest(
            req_type=RenderRequest.TYPE_RENDER,
            page_num=page_num,
            zoom=zoom,
            theme=theme,
            dpr=dpr,
            generation_id=generation_id,
            priority=priority,
            seq=self.seq_counter,
            doc_id=self.doc_id,
            doc_reader=self.doc_reader,
        )
        self.req_queue.put(req)
        metrics.render_queue_depth = self.req_queue.qsize()

    def request_words_extraction(self, page_num: int, generation_id: int):
        """Schedules word extraction task."""
        if generation_id != self.current_generation_id:
            return

        cached_words = self.word_cache.get(self.doc_id, page_num)
        if cached_words is not None:
            self.words_extracted.emit(page_num, generation_id, cached_words)
            return

        if not self._mark_pending(self._request_key(RenderRequest.TYPE_WORDS, page_num)):
            return

        self.seq_counter += 1
        req = RenderRequest(
            req_type=RenderRequest.TYPE_WORDS,
            page_num=page_num,
            zoom=1.0,
            theme="day",
            dpr=1.0,
            generation_id=generation_id,
            priority=1,
            seq=self.seq_counter,
            doc_id=self.doc_id,
            doc_reader=self.doc_reader,
        )
        self.req_queue.put(req)
        metrics.render_queue_depth = self.req_queue.qsize()

    def run(self):
        """Worker thread main loop."""
        while self._running:
            try:
                req = self.req_queue.get(timeout=0.1)
            except queue.Empty:
                metrics.render_queue_depth = 0
                continue

            metrics.render_queue_depth = self.req_queue.qsize()

            # Stale request rejection
            if req.generation_id != self.current_generation_id or not self.doc_reader:
                self._finish_pending(req)
                self.req_queue.task_done()
                continue

            try:
                if req.req_type == RenderRequest.TYPE_RENDER:
                    self._process_render_request(req)
                elif req.req_type == RenderRequest.TYPE_WORDS:
                    self._process_words_request(req)
            finally:
                self._finish_pending(req)
                self.req_queue.task_done()

    def _process_render_request(self, req: RenderRequest):
        # 1. Try DisplayList Cache
        reader = req.doc_reader
        if reader is None:
            return
        dl = self.displaylist_cache.get(req.doc_id, req.page_num)
        if dl is None:
            dl = reader.get_displaylist(req.page_num)
            if dl is not None:
                self.displaylist_cache.put(req.doc_id, req.page_num, dl)

        if dl is not None:
            qimg = reader.render_page_image_from_displaylist(
                dl, zoom=req.zoom, theme=req.theme, dpr=req.dpr
            )
        else:
            qimg = reader.render_page_image(
                req.page_num, zoom=req.zoom, theme=req.theme, dpr=req.dpr
            )

        if not qimg.isNull():
            self.image_cache.put(req.doc_id, req.page_num, req.zoom, req.theme, req.dpr, qimg)
            if req.generation_id == self.current_generation_id:
                self.page_rendered.emit(
                    req.page_num, req.zoom, req.theme, req.dpr, req.generation_id, qimg
                )

    def _process_words_request(self, req: RenderRequest):
        reader = req.doc_reader
        if reader is None:
            return
        dl = self.displaylist_cache.get(req.doc_id, req.page_num)
        words = []
        if dl is not None:
            try:
                tp = dl.get_textpage()
                raw_words = tp.extractWORDS()
                words = [(w[0], w[1], w[2], w[3], w[4]) for w in raw_words]
            except Exception:
                words = reader.get_words(req.page_num)
        else:
            words = reader.get_words(req.page_num)

        self.word_cache.put(req.doc_id, req.page_num, words)
        if req.generation_id == self.current_generation_id:
            self.words_extracted.emit(req.page_num, req.generation_id, words)

    def stop(self):
        self._running = False
        self.clear_queue()
        self.wait()
