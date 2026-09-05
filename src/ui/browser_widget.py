from typing import Optional
from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QLabel,
    QToolButton,
    QFrame,
    QTabBar,
)

# Attempt to import PySide6 QtWebEngineWidgets
HAS_WEBENGINE = True
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None


class BrowserTab(QWidget):
    """Single Web Browser Tab containing a QWebEngineView or fallback label."""

    url_changed = Signal(str)
    title_changed = Signal(str)

    def __init__(self, parent=None, initial_url="https://www.google.com"):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        if HAS_WEBENGINE and QWebEngineView is not None:
            self.web_view = QWebEngineView(self)
            self.layout.addWidget(self.web_view)

            self.web_view.urlChanged.connect(lambda url: self.url_changed.emit(url.toString()))
            self.web_view.titleChanged.connect(lambda title: self.title_changed.emit(title))
            self.web_view.load(QUrl(initial_url))
        else:
            self.web_view = None
            fallback_label = QLabel(
                "⚠️ QtWebEngine is not available in your PySide6 installation.\n\n"
                "To enable the embedded web browser, please ensure PySide6 with WebEngine is installed:\n"
                "pip install PySide6",
                self
            )
            fallback_label.setAlignment(Qt.AlignCenter)
            fallback_label.setWordWrap(True)
            fallback_label.setStyleSheet("color: #ff9800; font-size: 13px; padding: 20px; background: #1e1e1e;")
            self.layout.addWidget(fallback_label)

    def navigate(self, input_text: str):
        if not self.web_view:
            return
        text = input_text.strip()
        if not text:
            return
        if text.startswith("http://") or text.startswith("https://") or text.startswith("file://"):
            url_str = text
        elif "." in text and " " not in text:
            url_str = "https://" + text
        else:
            url_str = f"https://www.google.com/search?q={QUrl.toPercentEncoding(text).data().decode('utf-8')}"
        self.web_view.load(QUrl(url_str))

    def back(self):
        if self.web_view:
            self.web_view.back()

    def forward(self):
        if self.web_view:
            self.web_view.forward()

    def reload(self):
        if self.web_view:
            self.web_view.reload()


class WebBrowserWidget(QWidget):
    """Collapsible side-by-side embedded Web Browser panel with multi-tab support."""

    toggle_panel_requested = Signal()

    def __init__(self, parent=None, initial_url: str = "https://www.google.com"):
        super().__init__(parent)
        self.initial_url = initial_url

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Bar
        self.header_bar = QWidget()
        self.header_bar.setStyleSheet(
            "QWidget { background-color: #1a1a1a; border-bottom: 1px solid #333; } "
            "QPushButton, QToolButton { background: transparent; border: none; color: #aaa; font-size: 13px; font-weight: bold; } "
            "QPushButton:hover, QToolButton:hover { color: #2196F3; background-color: #2b2b2b; border-radius: 3px; }"
        )
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(6, 4, 6, 4)
        header_layout.setSpacing(4)

        lbl_icon = QLabel("🌐")
        lbl_icon.setStyleSheet("font-size: 14px;")
        header_layout.addWidget(lbl_icon)

        lbl_title = QLabel("Web Browser")
        lbl_title.setStyleSheet("font-weight: bold; color: #eee; font-size: 12px;")
        header_layout.addWidget(lbl_title)

        header_layout.addStretch()

        self.btn_new_tab = QToolButton()
        self.btn_new_tab.setText("＋ Tab")
        self.btn_new_tab.setToolTip("Open New Tab")
        self.btn_new_tab.clicked.connect(lambda: self.add_new_tab())
        header_layout.addWidget(self.btn_new_tab)

        self.btn_collapse = QToolButton()
        self.btn_collapse.setText("✕")
        self.btn_collapse.setToolTip("Close Web Browser Panel (F11)")
        self.btn_collapse.clicked.connect(self.toggle_panel_requested.emit)
        header_layout.addWidget(self.btn_collapse)

        main_layout.addWidget(self.header_bar)

        # 2. Navigation Address Bar
        self.nav_bar = QWidget()
        self.nav_bar.setStyleSheet(
            "QWidget { background-color: #222; border-bottom: 1px solid #333; } "
            "QPushButton { background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 3px; color: #ddd; font-size: 11px; padding: 3px 6px; } "
            "QPushButton:hover { background-color: #3d3d3d; border-color: #2196F3; color: white; } "
            "QLineEdit { background-color: #121212; border: 1px solid #3c3c3c; color: #fff; padding: 3px 8px; border-radius: 3px; font-size: 11px; }"
        )
        nav_layout = QHBoxLayout(self.nav_bar)
        nav_layout.setContentsMargins(6, 4, 6, 4)
        nav_layout.setSpacing(4)

        self.btn_back = QPushButton("◀")
        self.btn_back.setToolTip("Back")
        self.btn_back.setFixedWidth(28)
        self.btn_back.clicked.connect(self._on_back_clicked)
        nav_layout.addWidget(self.btn_back)

        self.btn_forward = QPushButton("▶")
        self.btn_forward.setToolTip("Forward")
        self.btn_forward.setFixedWidth(28)
        self.btn_forward.clicked.connect(self._on_forward_clicked)
        nav_layout.addWidget(self.btn_forward)

        self.btn_reload = QPushButton("↻")
        self.btn_reload.setToolTip("Reload")
        self.btn_reload.setFixedWidth(28)
        self.btn_reload.clicked.connect(self._on_reload_clicked)
        nav_layout.addWidget(self.btn_reload)

        self.btn_home = QPushButton("🏠")
        self.btn_home.setToolTip("Google Home")
        self.btn_home.setFixedWidth(28)
        self.btn_home.clicked.connect(self._on_home_clicked)
        nav_layout.addWidget(self.btn_home)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search Google or type a URL...")
        self.url_bar.returnPressed.connect(self._on_url_submitted)
        nav_layout.addWidget(self.url_bar)

        main_layout.addWidget(self.nav_bar)

        # 3. Tab Widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.tab_widget.setStyleSheet(
            "QTabWidget::pane { border: none; background: #1e1e1e; } "
            "QTabBar::tab { background: #2a2a2a; color: #bbb; padding: 5px 10px; border-top-left-radius: 4px; border-top-right-radius: 4px; font-size: 11px; } "
            "QTabBar::tab:selected { background: #1e1e1e; color: #2196F3; font-weight: bold; border-bottom: 2px solid #2196F3; }"
        )
        main_layout.addWidget(self.tab_widget)

        # Create initial tab
        self.add_new_tab(url=self.initial_url, title="Google")

    def add_new_tab(self, url: str = "https://www.google.com", title: str = "New Tab") -> BrowserTab:
        tab = BrowserTab(self, initial_url=url)
        tab.url_changed.connect(lambda u, t=tab: self._on_tab_url_changed(t, u))
        tab.title_changed.connect(lambda ti, t=tab: self._on_tab_title_changed(t, ti))

        idx = self.tab_widget.addTab(tab, title)
        self.tab_widget.setCurrentIndex(idx)
        return tab

    def close_tab(self, index: int):
        if self.tab_widget.count() > 1:
            widget = self.tab_widget.widget(index)
            self.tab_widget.removeTab(index)
            if widget:
                widget.deleteLater()
        else:
            # If closing last tab, navigate to Google home
            current = self.current_tab()
            if current:
                current.navigate("https://www.google.com")

    def current_tab(self) -> Optional[BrowserTab]:
        widget = self.tab_widget.currentWidget()
        if isinstance(widget, BrowserTab):
            return widget
        return None

    def search_query(self, query: str):
        """Perform a web search for the given text string."""
        tab = self.current_tab()
        if not tab:
            tab = self.add_new_tab()
        tab.navigate(query)

    def _on_url_submitted(self):
        tab = self.current_tab()
        if tab:
            tab.navigate(self.url_bar.text())

    def _on_back_clicked(self):
        tab = self.current_tab()
        if tab:
            tab.back()

    def _on_forward_clicked(self):
        tab = self.current_tab()
        if tab:
            tab.forward()

    def _on_reload_clicked(self):
        tab = self.current_tab()
        if tab:
            tab.reload()

    def _on_home_clicked(self):
        tab = self.current_tab()
        if tab:
            tab.navigate("https://www.google.com")

    def _on_tab_changed(self, index: int):
        tab = self.current_tab()
        if tab and tab.web_view:
            self.url_bar.setText(tab.web_view.url().toString())

    def _on_tab_url_changed(self, tab: BrowserTab, url: str):
        if tab == self.current_tab():
            self.url_bar.setText(url)

    def _on_tab_title_changed(self, tab: BrowserTab, title: str):
        idx = self.tab_widget.indexOf(tab)
        if idx != -1:
            short_title = title[:16] + "..." if len(title) > 18 else title
            self.tab_widget.setTabText(idx, short_title or "Tab")
