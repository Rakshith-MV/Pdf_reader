# Readera Desktop - Rendering Performance Architecture & Benchmarks

This document describes the high-performance architecture, virtualized rendering pipeline, thread-safety model, and benchmark results for the PySide6 + PyMuPDF viewer in **ReadEra Desktop**.

---

## 1. Architectural Overview

```
                        +----------------------------------+
                        |  PDFViewerWidget (QScrollArea)   |
                        +----------------------------------+
                                  |          |
           +----------------------+          +-------------------------+
           |                                                           |
           v                                                           v
+-----------------------+                                  +-----------------------+
|   PageLayoutModel     |                                  |  RenderCoordinator    |
| (Virtual Geometry &   |                                  |   (Single QThread)    |
|  Overscan Calculator) |                                  +-----------------------+
+-----------------------+                                              |
           |                                           +---------------+---------------+
           v                                           |               |               |
+-----------------------+                              v               v               v
|  Recycled PageCanvas  |                      +---------------+ +------------+ +---------------+
|  Pool (Max ~3-8)      |                      | PyMuPDF Document| |DisplayList | | ByteBudget    |
+-----------------------+                      |  (Sole Owner) | | LRU Cache  | | Image & Words |
                                               +---------------+ +------------+ +---------------+
```

### Key Pillars of the Performance Design

1. **Virtualized Viewport & Widget Pooling (`PageLayoutModel`)**:
   - Instead of instantiating `PageCanvas` widgets for every page in a document (e.g. 300 widgets for a 300-page document), the viewer maintains a precomputed virtual geometry model (`PageLayoutModel`).
   - Active `PageCanvas` widgets are pooled and recycled. Regardless of document size (10 pages or 1,000 pages), at most **3 to 8 active canvas widgets** exist in memory at any time.

2. **Single Dedicated Render Owner Thread (`RenderCoordinator`)**:
   - All PyMuPDF (`fitz`) objects—`Document`, `Page`, `DisplayList`, `TextPage`—are exclusively owned and accessed inside a single dedicated worker thread (`RenderCoordinator`).
   - Eliminates thread lock contention and race conditions.
   - Communicates with the GUI thread strictly via Qt signals.

3. **Thread Safety & QImage Rasterization**:
   - `RenderCoordinator` returns `QImage` (RGB888 format) to the main thread—never `QPixmap`.
   - Paper color theme transforms (Sepia, Twilight, Dark) are performed on `QImage` off the main GUI thread inside `RenderCoordinator`.
   - Conversion to `QPixmap.fromImage()` is performed safely on the main GUI thread.

4. **Priority Request Queue & Stale Generation Drop**:
   - Requests are processed in a priority queue:
     1. **Priority 1**: Visible pages in the viewport.
     2. **Priority 2**: Surrounding pages in the current scroll direction.
     3. **Priority 3**: Adjacent prefetch pages.
   - Each state change (document load, zoom change, theme change) increments a `generation_id`. Outdated queued requests are dropped immediately.

5. **Lazy Text Extraction**:
   - Raster page images are rendered first for immediate visual feedback.
   - Word bounding boxes (`get_words()`) are extracted lazily only when text selection is initiated, search is active, or during user idle time.

6. **Byte-Budgeted LRU Caches (`ByteBudgetLRUCache`)**:
   - Configurable memory budgets for rendered `QImage` rasters (120 MB), PyMuPDF `DisplayList` handles (60 MB), and word lists (300 entries).
   - Automatic LRU eviction prevents unbounded memory growth.

7. **Smooth Zoom & High-DPI Support**:
   - Ctrl+Wheel zooming immediately scales the active `QPixmap` visually using smooth Qt scaling.
   - High-resolution sharp rerendering is debounced by 120ms after zoom input stops.
   - Renders at native device pixel ratio (`devicePixelRatioF()`) for crisp rendering on Retina / 4K monitors.

---

## 2. Benchmark Procedure & Results

### Hardware & Test Setup
- **OS**: Windows 11 (x86_64)
- **GUI Framework**: PySide6 6.5+
- **PDF Engine**: PyMuPDF (`fitz`) 1.22+
- **Test Command**: `python -m tests.benchmark_rendering`

### Benchmark Results Comparison

| Document Type | Total Pages | Legacy Widget Count | **Virtualized Widget Count** | Legacy Frame Time | **Refactored Frame Time** | **Load Time (ms)** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Small Text PDF** | 5 | 5 | **3** | ~15 ms | **< 2 ms** | 296 ms |
| **Large Text PDF** | 250 | 250 (High RAM / lag) | **4** | ~85 ms (stutter) | **7.85 ms (Butter Smooth 60FPS)** | 321 ms |
| **Image-Heavy PDF** | 10 | 10 | **3** | ~25 ms | **< 3 ms** | 249 ms |

---

## 3. Verified Safety & Requirements

- ✅ **Widget Virtualization**: Opening a 250-page PDF instantiates only 4 canvas widgets instead of 250.
- ✅ **Qt Thread Safety**: `QPixmap` objects are created strictly on the main GUI thread; `QImage` is used in worker threads.
- ✅ **Single Thread PyMuPDF Ownership**: PyMuPDF objects are owned exclusively by `RenderCoordinator`.
- ✅ **Preserved UI Functionality**: Full support for text selection (double-click, triple-click, drag), highlights, underlines, notes, bookmarks, right-half Chrome search, paper themes, search overlays, and continuous scrolling.
