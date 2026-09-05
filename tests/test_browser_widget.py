import sys
import unittest
from PySide6.QtWidgets import QApplication
from src.ui.browser_widget import WebBrowserWidget, BrowserTab

app = QApplication.instance() or QApplication(sys.argv)

class TestWebBrowserWidget(unittest.TestCase):

    def setUp(self):
        self.browser = WebBrowserWidget()

    def tearDown(self):
        self.browser.close()

    def test_browser_initialization(self):
        self.assertIsNotNone(self.browser)
        self.assertEqual(self.browser.tab_widget.count(), 1)

    def test_add_new_tab(self):
        tab = self.browser.add_new_tab(url="https://www.wikipedia.org", title="Wikipedia")
        self.assertEqual(self.browser.tab_widget.count(), 2)
        self.assertIsInstance(tab, BrowserTab)

    def test_close_tab(self):
        self.browser.add_new_tab(url="https://www.google.com", title="Google")
        self.assertEqual(self.browser.tab_widget.count(), 2)
        self.browser.close_tab(0)
        self.assertEqual(self.browser.tab_widget.count(), 1)


if __name__ == "__main__":
    unittest.main()
