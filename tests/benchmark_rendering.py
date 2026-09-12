import os
import sys
import time
import tempfile
import pymupdf as fitz
from PySide6.QtWidgets import QApplication
from src.reader.document import DocumentReader
from src.ui.viewer_widget import PDFViewerWidget
from src.reader.performance_metrics import metrics


def create_synthetic_text_pdf(path: str, num_pages: int = 5):
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=612, height=792)
        page.insert_text((50, 50), f"Sample Synthetic Document Page {i + 1}", fontsize=18)
        page.insert_text(
            (50, 100),
            f"This is synthetic page content generated for performance testing.\n"
            f"Line 1 of text content on page {i + 1}.\n"
            f"Line 2 of text content on page {i + 1}.\n"
            f"Line 3 of text content on page {i + 1}.\n" * 15,
            fontsize=11
        )
    doc.save(path)
    doc.close()


def create_synthetic_image_pdf(path: str, num_pages: int = 10):
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=612, height=792)
        pix = fitz.Pixmap(fitz.csRGB, fitz.Rect(0, 0, 400, 400), False)
        pix.clear_with(200 - (i * 10) % 200)
        img_bytes = pix.tobytes("png")
        page.insert_image(fitz.Rect(100, 100, 500, 500), stream=img_bytes)
        pix = None
    doc.save(path)
    doc.close()


def run_benchmark():
    app = QApplication.instance() or QApplication(sys.argv)
    temp_dir = tempfile.mkdtemp()

    path_small = os.path.join(temp_dir, "small_5p.pdf")
    path_large = os.path.join(temp_dir, "large_250p.pdf")
    path_image = os.path.join(temp_dir, "image_10p.pdf")

    print("Generating synthetic benchmark PDFs...")
    create_synthetic_text_pdf(path_small, num_pages=5)
    create_synthetic_text_pdf(path_large, num_pages=250)
    create_synthetic_image_pdf(path_image, num_pages=10)

    viewer = PDFViewerWidget()
    viewer.resize(1000, 800)
    viewer.show()

    results = {}

    # Test 1: 5-page small text PDF
    reader_small = DocumentReader(path_small)
    t0 = time.perf_counter()
    viewer.set_document(reader_small)
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()
    t1 = time.perf_counter()

    results["small_5p"] = {
        "load_time_ms": round((t1 - t0) * 1000.0, 2),
        "widget_count": len(viewer.active_canvases),
        "total_pages": 5,
    }

    # Test 2: 250-page large text PDF
    reader_large = DocumentReader(path_large)
    metrics.start_document_load()
    t0 = time.perf_counter()
    viewer.set_document(reader_large)
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()
    t1 = time.perf_counter()

    # Simulate scrolling
    vbar = viewer.verticalScrollBar()
    scroll_times = []
    for y in range(0, 10000, 500):
        ts0 = time.perf_counter()
        vbar.setValue(y)
        app.processEvents()
        scroll_times.append((time.perf_counter() - ts0) * 1000.0)

    results["large_250p"] = {
        "load_time_ms": round((t1 - t0) * 1000.0, 2),
        "widget_count": len(viewer.active_canvases),
        "total_pages": 250,
        "avg_scroll_frame_ms": round(sum(scroll_times) / len(scroll_times), 2),
    }

    # Test 3: Image-heavy PDF
    reader_image = DocumentReader(path_image)
    t0 = time.perf_counter()
    viewer.set_document(reader_image)
    app.processEvents()
    time.sleep(0.2)
    app.processEvents()
    t1 = time.perf_counter()

    results["image_10p"] = {
        "load_time_ms": round((t1 - t0) * 1000.0, 2),
        "widget_count": len(viewer.active_canvases),
        "total_pages": 10,
    }

    print("\n================ BENCHMARK RESULTS ================")
    print(f"1. Small PDF (5 pages):   Load time = {results['small_5p']['load_time_ms']} ms, Active Widgets = {results['small_5p']['widget_count']} (out of 5)")
    print(f"2. Large PDF (250 pages): Load time = {results['large_250p']['load_time_ms']} ms, Active Widgets = {results['large_250p']['widget_count']} (out of 250!)")
    print(f"                          Avg Scroll Frame = {results['large_250p']['avg_scroll_frame_ms']} ms")
    print(f"3. Image PDF (10 pages):  Load time = {results['image_10p']['load_time_ms']} ms, Active Widgets = {results['image_10p']['widget_count']} (out of 10)")
    print("===================================================\n")

    viewer.close()
    reader_small.close()
    reader_large.close()
    reader_image.close()

    try:
        os.remove(path_small)
        os.remove(path_large)
        os.remove(path_image)
        os.rmdir(temp_dir)
    except Exception:
        pass

    return results


if __name__ == "__main__":
    run_benchmark()
