import time
from typing import Dict, Any

class PerformanceMetrics:
    """
    Lightweight instrumentation tracking rendering speed, cache hit rates,
    scroll handler latency, queue depth, and memory consumption.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.doc_open_time: float = 0.0
        self.time_to_first_page_ms: float = 0.0
        self.time_to_final_render_ms: float = 0.0
        self.first_page_rendered: bool = False

        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.displaylist_hits: int = 0
        self.displaylist_misses: int = 0

        self.render_queue_depth: int = 0
        self.scroll_handle_time_ms: float = 0.0
        self.scroll_event_count: int = 0

        self.image_cache_memory_bytes: int = 0
        self.displaylist_cache_memory_bytes: int = 0
        self.word_cache_memory_bytes: int = 0

        self.widget_count: int = 0

    def start_document_load(self):
        self.doc_open_time = time.perf_counter()
        self.first_page_rendered = False
        self.time_to_first_page_ms = 0.0
        self.time_to_final_render_ms = 0.0

    def mark_first_page_rendered(self):
        if not self.first_page_rendered and self.doc_open_time > 0:
            self.first_page_rendered = True
            self.time_to_first_page_ms = (time.perf_counter() - self.doc_open_time) * 1000.0

    def mark_final_render_complete(self):
        if self.doc_open_time > 0:
            self.time_to_final_render_ms = (time.perf_counter() - self.doc_open_time) * 1000.0

    def record_cache_hit(self):
        self.cache_hits += 1

    def record_cache_miss(self):
        self.cache_misses += 1

    def record_displaylist_hit(self):
        self.displaylist_hits += 1

    def record_displaylist_miss(self):
        self.displaylist_misses += 1

    def record_scroll_event(self, duration_ms: float):
        self.scroll_event_count += 1
        self.scroll_handle_time_ms += duration_ms

    @property
    def image_cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100.0) if total > 0 else 0.0

    @property
    def displaylist_hit_rate(self) -> float:
        total = self.displaylist_hits + self.displaylist_misses
        return (self.displaylist_hits / total * 100.0) if total > 0 else 0.0

    @property
    def avg_scroll_time_ms(self) -> float:
        return (self.scroll_handle_time_ms / self.scroll_event_count) if self.scroll_event_count > 0 else 0.0

    @property
    def total_cache_memory_bytes(self) -> int:
        return (
            self.image_cache_memory_bytes
            + self.displaylist_cache_memory_bytes
            + self.word_cache_memory_bytes
        )

    def get_summary(self) -> Dict[str, Any]:
        return {
            "time_to_first_page_ms": round(self.time_to_first_page_ms, 2),
            "time_to_final_render_ms": round(self.time_to_final_render_ms, 2),
            "image_cache_hit_rate_pct": round(self.image_cache_hit_rate, 2),
            "displaylist_hit_rate_pct": round(self.displaylist_hit_rate, 2),
            "render_queue_depth": self.render_queue_depth,
            "avg_scroll_time_ms": round(self.avg_scroll_time_ms, 3),
            "total_cache_memory_mb": round(self.total_cache_memory_bytes / (1024 * 1024), 2),
            "active_widget_count": self.widget_count,
        }


# Global singleton instance for performance instrumentation
metrics = PerformanceMetrics()
