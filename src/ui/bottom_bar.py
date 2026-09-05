import os
import requests
import xml.etree.ElementTree as ET
from typing import List, Tuple
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QSpinBox,
    QFrame,
    QInputDialog,
    QMessageBox,
    QMenu,
)

class BottomBarWidget(QFrame):
    """Top toolbar for page navigation, zoom adjustment, panel toggles, text search, Timer, VLC Music, and 3-line More menu."""

    prev_page_requested = Signal()
    next_page_requested = Signal()
    page_jump_requested = Signal(int)
    zoom_in_requested = Signal()
    zoom_out_requested = Signal()
    zoom_set_requested = Signal(float)
    fit_width_requested = Signal()
    fit_page_requested = Signal()

    search_requested = Signal(str)
    next_search_match_requested = Signal()
    prev_search_match_requested = Signal()

    toggle_left_panel_requested = Signal()
    toggle_right_panel_requested = Signal()
    home_requested = Signal()
    timer_button_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.total_pages: int = 0
        self.timer_seconds_left: int = 0
        self.timer_active: bool = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background-color: #1e1e1e; color: #E0E0E0; border-bottom: 1px solid #2d2d2d; } "
            "QPushButton { background-color: #2b2b2b; border: 1px solid #3c3c3c; border-radius: 3px; padding: 3px 6px; font-size: 11px; color: #eee; } "
            "QPushButton:hover { background-color: #3d3d3d; border-color: #2196F3; } "
            "QLineEdit, QSpinBox { background-color: #121212; border: 1px solid #3c3c3c; color: #fff; padding: 2px 4px; border-radius: 3px; font-size: 11px; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        # --- Section 1: Navigation & Left Panel ---
        self.btn_home = QPushButton("🏠")
        self.btn_home.setToolTip("Go to Home Dashboard (F2)")
        self.btn_home.setFixedWidth(28)
        self.btn_home.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold;")
        self.btn_home.clicked.connect(self.home_requested.emit)
        layout.addWidget(self.btn_home)

        self.btn_toggle_left = QPushButton("☰ Lib")
        self.btn_toggle_left.setToolTip("Toggle Left Library & Study Lists (F9)")
        self.btn_toggle_left.setFixedWidth(46)
        self.btn_toggle_left.clicked.connect(self.toggle_left_panel_requested.emit)
        layout.addWidget(self.btn_toggle_left)

        self.btn_prev = QPushButton("◀")
        self.btn_prev.setToolTip("Previous Page (Left Arrow)")
        self.btn_prev.setFixedWidth(28)
        self.btn_prev.clicked.connect(self.prev_page_requested)
        layout.addWidget(self.btn_prev)

        lbl_p = QLabel("p.")
        lbl_p.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(lbl_p)

        self.spin_page = QSpinBox()
        self.spin_page.setRange(1, 1)
        self.spin_page.setFixedWidth(52)
        self.spin_page.setButtonSymbols(QSpinBox.NoButtons)
        self.spin_page.setAlignment(Qt.AlignCenter)
        self.spin_page.editingFinished.connect(self._on_spin_page_changed)
        layout.addWidget(self.spin_page)

        self.lbl_total_pages = QLabel("/ 0")
        self.lbl_total_pages.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self.lbl_total_pages)

        self.btn_next = QPushButton("▶")
        self.btn_next.setToolTip("Next Page (Right Arrow)")
        self.btn_next.setFixedWidth(28)
        self.btn_next.clicked.connect(self.next_page_requested)
        layout.addWidget(self.btn_next)

        layout.addSpacing(6)

        # --- Section 2: Zoom Controls ---
        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setFixedWidth(24)
        self.btn_zoom_out.clicked.connect(self.zoom_out_requested)
        layout.addWidget(self.btn_zoom_out)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(40)
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        self.lbl_zoom.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.lbl_zoom)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedWidth(24)
        self.btn_zoom_in.clicked.connect(self.zoom_in_requested)
        layout.addWidget(self.btn_zoom_in)

        self.btn_fit_width = QPushButton("Width")
        self.btn_fit_width.setToolTip("Fit Page to Width (Ctrl+1)")
        self.btn_fit_width.setFixedWidth(48)
        self.btn_fit_width.clicked.connect(self.fit_width_requested)
        layout.addWidget(self.btn_fit_width)

        self.btn_fit_page = QPushButton("Page")
        self.btn_fit_page.setToolTip("Fit Entire Page (Ctrl+2)")
        self.btn_fit_page.setFixedWidth(42)
        self.btn_fit_page.clicked.connect(self.fit_page_requested)
        layout.addWidget(self.btn_fit_page)

        layout.addSpacing(6)

        # --- Section 3: Study Timer & VLC Music Controls ---
        self.btn_timer = QPushButton("⏱️ Timer")
        self.btn_timer.setToolTip("Start or stop Study Timer / Pomodoro (e.g. 25 min)")
        self.btn_timer.setStyleSheet("QPushButton { background-color: #2e7d32; color: white; font-weight: bold; } QPushButton:hover { background-color: #388e3c; }")
        self.btn_timer.clicked.connect(self._toggle_study_timer)
        layout.addWidget(self.btn_timer)

        self.btn_vlc = QPushButton("🎵 VLC")
        self.btn_vlc.setToolTip("Toggle VLC Music Playback / Check Now Playing")
        self.btn_vlc.setStyleSheet("QPushButton { background-color: #d84315; color: white; font-weight: bold; } QPushButton:hover { background-color: #e64a19; }")
        self.btn_vlc.clicked.connect(self._toggle_vlc_music)
        layout.addWidget(self.btn_vlc)

        layout.addStretch()

        # --- Section 4: Search Bar & Right Panel Toggle ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setFixedWidth(130)
        self.search_input.returnPressed.connect(self._on_search_triggered)
        layout.addWidget(self.search_input)

        self.btn_search_prev = QPushButton("▲")
        self.btn_search_prev.setFixedWidth(24)
        self.btn_search_prev.clicked.connect(self.prev_search_match_requested)
        layout.addWidget(self.btn_search_prev)

        self.btn_search_next = QPushButton("▼")
        self.btn_search_next.setFixedWidth(24)
        self.btn_search_next.clicked.connect(self.next_search_match_requested)
        layout.addWidget(self.btn_search_next)

        self.lbl_search_count = QLabel("")
        self.lbl_search_count.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self.lbl_search_count)

        self.btn_toggle_right = QPushButton("Notes 📖")
        self.btn_toggle_right.setToolTip("Toggle Right Sidebar & Notes (F10)")
        self.btn_toggle_right.clicked.connect(self.toggle_right_panel_requested.emit)
        layout.addWidget(self.btn_toggle_right)

        # 3-line "More" hamburger menu button containing all top actions
        self.btn_more = QPushButton("☰ More")
        self.btn_more.setToolTip("More Options & Actions (Menu)")
        self.btn_more.setStyleSheet(
            "QPushButton { background-color: #37474F; color: white; font-weight: bold; padding: 3px 8px; border-radius: 3px; } "
            "QPushButton:hover { background-color: #455A64; }"
        )
        self.more_menu = QMenu(self)
        self.more_menu.setStyleSheet(
            "QMenu { background-color: #1e1e1e; color: #E0E0E0; border: 1px solid #333; } "
            "QMenu::item:selected { background-color: #2196F3; color: white; }"
        )
        self.btn_more.setMenu(self.more_menu)
        layout.addWidget(self.btn_more)

    def set_document_state(self, current_page: int, total_pages: int, zoom_level: float):
        self.total_pages = max(0, total_pages)
        if self.total_pages > 0:
            self.spin_page.setRange(1, self.total_pages)
            self.spin_page.setValue(current_page + 1)
            self.lbl_total_pages.setText(f"/ {self.total_pages}")
            self.spin_page.setEnabled(True)
            self.btn_prev.setEnabled(current_page > 0)
            self.btn_next.setEnabled(current_page < self.total_pages - 1)
        else:
            self.spin_page.setRange(1, 1)
            self.spin_page.setValue(1)
            self.lbl_total_pages.setText("/ 0")
            self.spin_page.setEnabled(False)
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)

        self.lbl_zoom.setText(f"{int(zoom_level * 100)}%")

    def set_search_results_status(self, current_match_idx: int, total_matches: int):
        if total_matches == 0:
            self.lbl_search_count.setText("0 matches")
        else:
            self.lbl_search_count.setText(f"{current_match_idx + 1}/{total_matches}")

    @Slot()
    def _on_spin_page_changed(self):
        page_val = self.spin_page.value() - 1
        self.page_jump_requested.emit(page_val)

    @Slot()
    def _on_search_triggered(self):
        query = self.search_input.text().strip()
        self.search_requested.emit(query)

    def _toggle_study_timer(self):
        self.timer_button_clicked.emit()

    def sync_timer_state(self, seconds_left: int, total_seconds: int, is_running: bool, is_paused: bool):
        """Synchronizes TopBar Timer button display with global Focus/Study Session timer."""
        self.timer_seconds_left = seconds_left
        self.timer_active = is_running
        if is_running:
            m, s = divmod(seconds_left, 60)
            if is_paused:
                self.btn_timer.setText(f"⏸️ {m:02d}:{s:02d}")
                self.btn_timer.setStyleSheet(
                    "QPushButton { background-color: #d84315; color: white; font-weight: bold; }"
                )
            else:
                self.btn_timer.setText(f"⏱️ {m:02d}:{s:02d}")
                self.btn_timer.setStyleSheet(
                    "QPushButton { background-color: #c62828; color: white; font-weight: bold; }"
                )
        else:
            self.btn_timer.setText("⏱️ Timer")
            self.btn_timer.setStyleSheet(
                "QPushButton { background-color: #2e7d32; color: white; font-weight: bold; } QPushButton:hover { background-color: #388e3c; }"
            )

    def _toggle_vlc_music(self):
        host = os.getenv("VLC_HOST", "localhost").strip() or "localhost"
        port = os.getenv("VLC_PORT", "8080").strip() or "8080"
        password = os.getenv("VLC_HTTP_PASSWORD", "").strip()

        url = f"http://{host}:{port}/requests/status.xml"
        try:
            resp = requests.get(url, params={"command": "pl_pause"}, auth=("", password), timeout=2)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                state_elem = root.find("state")
                state = state_elem.text.strip() if state_elem is not None and state_elem.text else "unknown"
                QMessageBox.information(self, "VLC Music", f"🎵 VLC Playback toggled: {state}")
            elif resp.status_code == 401:
                QMessageBox.warning(self, "VLC Auth Error", "VLC HTTP Authentication failed. Check VLC_HTTP_PASSWORD in .env.")
            else:
                QMessageBox.warning(self, "VLC Error", f"VLC returned status code {resp.status_code}.")
        except Exception:
            QMessageBox.warning(self, "VLC Unreachable", f"Could not connect to VLC at http://{host}:{port}.\nMake sure VLC is running with Web Interface enabled.")


TopBarWidget = BottomBarWidget
