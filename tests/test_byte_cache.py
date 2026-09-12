import unittest
from PySide6.QtGui import QImage
from src.reader.byte_cache import ImageLRUCache, DisplayListLRUCache, WordLRUCache


class TestByteCache(unittest.TestCase):

    def test_image_lru_eviction(self):
        # 100x100 RGB888 image is approx 30,000 bytes
        img1 = QImage(100, 100, QImage.Format_RGB888)
        img2 = QImage(100, 100, QImage.Format_RGB888)
        img3 = QImage(100, 100, QImage.Format_RGB888)

        # Set max bytes to hold ~2 images (~65,000 bytes)
        cache = ImageLRUCache(max_bytes=65000)
        cache.put("doc1", 0, 1.0, "day", 1.0, img1)
        cache.put("doc1", 1, 1.0, "day", 1.0, img2)

        self.assertIsNotNone(cache.get("doc1", 0, 1.0, "day", 1.0))
        self.assertIsNotNone(cache.get("doc1", 1, 1.0, "day", 1.0))

        # Put img3 -> causes eviction of img0 (least recently used)
        cache.put("doc1", 2, 1.0, "day", 1.0, img3)

        self.assertIsNone(cache.get("doc1", 0, 1.0, "day", 1.0))
        self.assertIsNotNone(cache.get("doc1", 1, 1.0, "day", 1.0))
        self.assertIsNotNone(cache.get("doc1", 2, 1.0, "day", 1.0))

    def test_word_lru_cache(self):
        cache = WordLRUCache(max_entries=2)
        words = [(0.0, 0.0, 10.0, 10.0, "test")]
        cache.put("doc1", 0, words)
        cache.put("doc1", 1, words)
        cache.put("doc1", 2, words)

        self.assertIsNone(cache.get("doc1", 0))
        self.assertIsNotNone(cache.get("doc1", 1))
        self.assertIsNotNone(cache.get("doc1", 2))


if __name__ == "__main__":
    unittest.main()
