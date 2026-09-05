import math
from typing import Dict, Any, List, Optional
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QRectF
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QFrame,
    QScrollArea,
    QRadioButton,
    QButtonGroup,
    QInputDialog,
    QMessageBox,
)
from src.database.db_manager import DatabaseManager


class DailyProgressRing(QWidget):
    """Custom painted circular progress ring widget showing daily focus goal completion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.completed_mins: int = 0
        self.goal_mins: int = 480  # Default 8 hours (480 mins)
        self.setFixedSize(170, 170)

    def set_stats(self, completed_mins: int, goal_mins: int = 480):
        self.completed_mins = max(0, completed_mins)
        self.goal_mins = max(1, goal_mins)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(12, 12, self.width() - 24, self.height() - 24)
        pen_bg = QPen(QColor(50, 50, 50), 14, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen_bg)
        painter.drawEllipse(rect)

        pct = min(1.0, self.completed_mins / float(self.goal_mins))
        angle_span = int(-360 * pct * 16)

        pen_fg = QPen(QColor(224, 86, 56), 14, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen_fg)
        painter.drawArc(rect, 90 * 16, angle_span)

        # Center Text Display
        painter.setPen(QColor(180, 180, 180))
        font_sub = QFont("Segoe UI", 9)
        painter.setFont(font_sub)
        painter.drawText(0, 42, self.width(), 20, Qt.AlignCenter, "Daily goal")

        painter.setPen(QColor(255, 255, 255))
        font_num = QFont("Segoe UI", 24, QFont.Bold)
        painter.setFont(font_num)
        goal_val = self.goal_mins // 60 if self.goal_mins >= 60 else self.goal_mins
        unit_str = "hours" if self.goal_mins >= 60 else "mins"
        painter.drawText(0, 66, self.width(), 36, Qt.AlignCenter, str(goal_val))

        painter.setPen(QColor(180, 180, 180))
        font_unit = QFont("Segoe UI", 9)
        painter.setFont(font_unit)
        painter.drawText(0, 106, self.width(), 20, Qt.AlignCenter, unit_str)
        painter.end()


class FocusDashboardWidget(QWidget):
    """
    Windows 11 Focus Session Dashboard Widget:
    Card 1: Focus Session Setup & Timer ("Get ready to focus")
    Card 2: Daily Progress Ring & Stats ("Daily progress")
    Card 3: Study Lists Task Selector ("Study Lists" replacing "Tasks")
    """

    session_started = Signal(int)  # duration_minutes
    session_completed = Signal(int, int)  # duration_minutes, study_list_id
    timer_tick_signal = Signal(int, int, bool, bool)  # seconds_left, total_seconds, is_running, is_paused

    DURATIONS = [5, 10, 15, 20, 25, 30, 45, 60, 90, 120]

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.selected_study_list_id: Optional[int] = None
        self.current_duration_idx: int = 4  # Default 25 mins

        # Timer state
        self.is_running: bool = False
        self.is_paused: bool = False
        self.seconds_left: int = 0
        self.total_session_seconds: int = 0
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._on_tick)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(14)

        # -----------------------------------------------------------------
        # CARD 1: Focus Session Setup & Timer ("Get ready to focus")
        # -----------------------------------------------------------------
        self.card_timer = QFrame()
        self.card_timer.setStyleSheet(
            """
            QFrame {
                background-color: #232323;
                border: 1px solid #333333;
                border-radius: 12px;
            }
            """
        )
        c1_layout = QVBoxLayout(self.card_timer)
        c1_layout.setContentsMargins(18, 16, 18, 16)
        c1_layout.setSpacing(10)

        # Header Title
        lbl_c1_title = QLabel("Get ready to focus")
        lbl_c1_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        lbl_c1_title.setStyleSheet("color: #FFFFFF;")
        c1_layout.addWidget(lbl_c1_title)

        lbl_c1_sub = QLabel(
            "We'll turn off notifications and app alerts during each session. For longer sessions, we'll add a short break so you can recharge."
        )
        lbl_c1_sub.setWordWrap(True)
        lbl_c1_sub.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        c1_layout.addWidget(lbl_c1_sub)

        c1_layout.addSpacing(4)

        # Duration Picker Box (or Live Timer display)
        self.time_box_frame = QFrame()
        self.time_box_frame.setStyleSheet(
            "QFrame { background-color: #191919; border: 1px solid #3a3a3a; border-radius: 8px; }"
        )
        tb_layout = QHBoxLayout(self.time_box_frame)
        tb_layout.setContentsMargins(16, 10, 16, 10)

        # Left Display: Minutes Number & Label
        lbl_box = QVBoxLayout()
        lbl_box.setSpacing(0)
        self.lbl_time_display = QLabel("25")
        self.lbl_time_display.setFont(QFont("Segoe UI", 28, QFont.Bold))
        self.lbl_time_display.setStyleSheet("color: #FFFFFF; border: none; background: transparent;")
        self.lbl_time_display.setAlignment(Qt.AlignCenter)
        lbl_box.addWidget(self.lbl_time_display)

        self.lbl_time_unit = QLabel("mins")
        self.lbl_time_unit.setFont(QFont("Segoe UI", 9))
        self.lbl_time_unit.setStyleSheet("color: #AAAAAA; border: none; background: transparent;")
        self.lbl_time_unit.setAlignment(Qt.AlignCenter)
        lbl_box.addWidget(self.lbl_time_unit)

        tb_layout.addLayout(lbl_box)
        tb_layout.addStretch()

        # Right Display: Up / Down Stepper Buttons
        self.stepper_box = QWidget()
        step_layout = QVBoxLayout(self.stepper_box)
        step_layout.setContentsMargins(0, 0, 0, 0)
        step_layout.setSpacing(2)

        self.btn_time_up = QPushButton("▲")
        self.btn_time_up.setFixedSize(28, 22)
        self.btn_time_up.setStyleSheet(
            "QPushButton { background: #2c2c2c; border: 1px solid #444; color: white; border-radius: 4px; } QPushButton:hover { background: #3d3d3d; }"
        )
        self.btn_time_up.clicked.connect(self._step_time_up)
        step_layout.addWidget(self.btn_time_up)

        self.btn_time_down = QPushButton("▼")
        self.btn_time_down.setFixedSize(28, 22)
        self.btn_time_down.setStyleSheet(
            "QPushButton { background: #2c2c2c; border: 1px solid #444; color: white; border-radius: 4px; } QPushButton:hover { background: #3d3d3d; }"
        )
        self.btn_time_down.clicked.connect(self._step_time_down)
        step_layout.addWidget(self.btn_time_down)

        tb_layout.addWidget(self.stepper_box)
        c1_layout.addWidget(self.time_box_frame)

        # Break Info & Skip Checkbox
        self.lbl_break_info = QLabel("You'll have no breaks")
        self.lbl_break_info.setAlignment(Qt.AlignCenter)
        self.lbl_break_info.setStyleSheet("color: #CCCCCC; font-size: 11px;")
        c1_layout.addWidget(self.lbl_break_info)

        self.chk_skip_breaks = QCheckBox("Skip breaks")
        self.chk_skip_breaks.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        self.chk_skip_breaks.toggled.connect(self._update_break_info)
        c1_layout.addWidget(self.chk_skip_breaks, alignment=Qt.AlignCenter)

        c1_layout.addSpacing(6)

        # Action Start / Pause / Stop Button
        self.btn_start = QPushButton("▶  Start focus session")
        self.btn_start.setFixedHeight(38)
        self.btn_start.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setStyleSheet(
            """
            QPushButton {
                background-color: #e05638;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #f06444;
            }
            """
        )
        self.btn_start.clicked.connect(self._on_start_clicked)
        c1_layout.addWidget(self.btn_start)

        main_layout.addWidget(self.card_timer, stretch=1)

        # -----------------------------------------------------------------
        # CARD 2: Daily Progress Ring & Stats ("Daily progress")
        # -----------------------------------------------------------------
        self.card_progress = QFrame()
        self.card_progress.setStyleSheet(
            """
            QFrame {
                background-color: #232323;
                border: 1px solid #333333;
                border-radius: 12px;
            }
            """
        )
        c2_layout = QVBoxLayout(self.card_progress)
        c2_layout.setContentsMargins(18, 16, 18, 16)
        c2_layout.setSpacing(8)

        # Header Title with Edit Goal icon
        hdr_c2 = QHBoxLayout()
        lbl_c2_title = QLabel("Daily progress")
        lbl_c2_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        lbl_c2_title.setStyleSheet("color: #FFFFFF;")
        hdr_c2.addWidget(lbl_c2_title)

        hdr_c2.addStretch()

        btn_edit_goal = QPushButton("✏️")
        btn_edit_goal.setToolTip("Change Daily Goal")
        btn_edit_goal.setFixedSize(24, 24)
        btn_edit_goal.setStyleSheet("background: transparent; border: none; color: #AAA;")
        btn_edit_goal.clicked.connect(self._prompt_change_goal)
        hdr_c2.addWidget(btn_edit_goal)
        c2_layout.addLayout(hdr_c2)

        # Center Content: Side Stats + Ring
        ring_stats_layout = QHBoxLayout()

        # Left Stats: Yesterday
        stat_left = QVBoxLayout()
        stat_left.setAlignment(Qt.AlignCenter)
        lbl_y_head = QLabel("Yesterday")
        lbl_y_head.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        self.lbl_y_val = QLabel("0")
        self.lbl_y_val.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.lbl_y_val.setStyleSheet("color: #FFFFFF;")
        lbl_y_unit = QLabel("minutes")
        lbl_y_unit.setStyleSheet("color: #AAAAAA; font-size: 10px;")
        stat_left.addWidget(lbl_y_head, alignment=Qt.AlignCenter)
        stat_left.addWidget(self.lbl_y_val, alignment=Qt.AlignCenter)
        stat_left.addWidget(lbl_y_unit, alignment=Qt.AlignCenter)
        ring_stats_layout.addLayout(stat_left)

        # Ring
        self.ring_widget = DailyProgressRing()
        ring_stats_layout.addWidget(self.ring_widget, alignment=Qt.AlignCenter)

        # Right Stats: Streak
        stat_right = QVBoxLayout()
        stat_right.setAlignment(Qt.AlignCenter)
        lbl_s_head = QLabel("Streak")
        lbl_s_head.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        self.lbl_s_val = QLabel("0")
        self.lbl_s_val.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.lbl_s_val.setStyleSheet("color: #FFFFFF;")
        lbl_s_unit = QLabel("days")
        lbl_s_unit.setStyleSheet("color: #AAAAAA; font-size: 10px;")
        stat_right.addWidget(lbl_s_head, alignment=Qt.AlignCenter)
        stat_right.addWidget(self.lbl_s_val, alignment=Qt.AlignCenter)
        stat_right.addWidget(lbl_s_unit, alignment=Qt.AlignCenter)
        ring_stats_layout.addLayout(stat_right)

        c2_layout.addLayout(ring_stats_layout)

        self.lbl_completed_text = QLabel("Completed: 0 minutes")
        self.lbl_completed_text.setAlignment(Qt.AlignCenter)
        self.lbl_completed_text.setStyleSheet("color: #CCCCCC; font-size: 11px;")
        c2_layout.addWidget(self.lbl_completed_text)

        main_layout.addWidget(self.card_progress, stretch=1)

        # -----------------------------------------------------------------
        # CARD 3: Study Lists Selector ("Study Lists" replacing "Tasks")
        # -----------------------------------------------------------------
        self.card_tasks = QFrame()
        self.card_tasks.setStyleSheet(
            """
            QFrame {
                background-color: #232323;
                border: 1px solid #333333;
                border-radius: 12px;
            }
            """
        )
        c3_layout = QVBoxLayout(self.card_tasks)
        c3_layout.setContentsMargins(18, 16, 18, 16)
        c3_layout.setSpacing(8)

        # Header Title with Add Study List button
        hdr_c3 = QHBoxLayout()
        lbl_c3_title = QLabel("✔ Study Lists")
        lbl_c3_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        lbl_c3_title.setStyleSheet("color: #FFFFFF;")
        hdr_c3.addWidget(lbl_c3_title)

        hdr_c3.addStretch()

        btn_add_task = QPushButton("+")
        btn_add_task.setToolTip("Create New Study List")
        btn_add_task.setFixedSize(24, 24)
        btn_add_task.setStyleSheet(
            "QPushButton { background: #2c2c2c; border: 1px solid #444; color: white; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #3d3d3d; }"
        )
        btn_add_task.clicked.connect(self._prompt_add_study_list)
        hdr_c3.addWidget(btn_add_task)
        c3_layout.addLayout(hdr_c3)

        lbl_c3_sub = QLabel("Select a study list for your session")
        lbl_c3_sub.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        c3_layout.addWidget(lbl_c3_sub)

        # Scrollable list of Study Lists with Radio buttons
        scroll_sl = QScrollArea()
        scroll_sl.setWidgetResizable(True)
        scroll_sl.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.sl_content = QWidget()
        self.sl_layout = QVBoxLayout(self.sl_content)
        self.sl_layout.setContentsMargins(0, 4, 0, 4)
        self.sl_layout.setSpacing(6)

        scroll_sl.setWidget(self.sl_content)
        c3_layout.addWidget(scroll_sl)

        main_layout.addWidget(self.card_tasks, stretch=1)

        self.refresh_focus_dashboard()

    def refresh_focus_dashboard(self):
        """Refreshes daily stats, progress ring, and study list task selection."""
        stats = self.db_manager.get_focus_stats()
        today_mins = stats.get("today_minutes", 0)
        yest_mins = stats.get("yesterday_minutes", 0)
        streak = stats.get("streak_days", 0)
        sl_mins_map = stats.get("study_list_minutes", {})

        self.lbl_y_val.setText(str(yest_mins))
        self.lbl_s_val.setText(str(streak))
        self.lbl_completed_text.setText(f"Completed: {today_mins} minutes")
        self.ring_widget.set_stats(today_mins, goal_mins=480)

        # Populate Study Lists Task Selector
        self._clear_layout(self.sl_layout)
        study_lists = self.db_manager.get_study_lists()

        if not study_lists:
            lbl_no_sl = QLabel("No Study Lists found. Click '+' above to add one.")
            lbl_no_sl.setStyleSheet("color: #777777; font-style: italic; font-size: 11px;")
            self.sl_layout.addWidget(lbl_no_sl)
        else:
            if not self.selected_study_list_id or not any(l["id"] == self.selected_study_list_id for l in study_lists):
                self.selected_study_list_id = study_lists[0]["id"]

            self.bg_group = QButtonGroup(self)
            for sl in study_lists:
                sl_id = sl["id"]
                sl_name = sl["name"]
                logged = sl_mins_map.get(sl_id, 0)

                frame = QFrame()
                is_sel = (sl_id == self.selected_study_list_id)
                bg_col = "#2d3748" if is_sel else "#1c1c1c"
                border_col = "#2196F3" if is_sel else "#333333"

                frame.setStyleSheet(
                    f"QFrame {{ background-color: {bg_col}; border: 1px solid {border_col}; border-radius: 6px; }}"
                )
                f_layout = QHBoxLayout(frame)
                f_layout.setContentsMargins(8, 6, 8, 6)

                radio = QRadioButton(sl_name)
                radio.setChecked(is_sel)
                radio.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 11px;")
                radio.toggled.connect(lambda checked, s_id=sl_id: self._on_sl_selected(checked, s_id))
                self.bg_group.addButton(radio)
                f_layout.addWidget(radio)

                f_layout.addStretch()

                if logged > 0:
                    lbl_log = QLabel(f"⏱ {logged}m")
                    lbl_log.setStyleSheet("color: #888888; font-size: 10px;")
                    f_layout.addWidget(lbl_log)

                self.sl_layout.addWidget(frame)

    def _step_time_up(self):
        if self.is_running:
            return
        if self.current_duration_idx < len(self.DURATIONS) - 1:
            self.current_duration_idx += 1
            self._update_duration_display()

    def _step_time_down(self):
        if self.is_running:
            return
        if self.current_duration_idx > 0:
            self.current_duration_idx -= 1
            self._update_duration_display()

    def _update_duration_display(self):
        mins = self.DURATIONS[self.current_duration_idx]
        self.lbl_time_display.setText(str(mins))
        self._update_break_info()

    def _update_break_info(self):
        if self.is_running:
            return
        mins = self.DURATIONS[self.current_duration_idx]
        if self.chk_skip_breaks.isChecked():
            self.lbl_break_info.setText("You'll have no breaks (skipped)")
        elif mins < 30:
            self.lbl_break_info.setText("You'll have no breaks")
        elif mins < 60:
            self.lbl_break_info.setText("1 break (5 mins)")
        elif mins < 90:
            self.lbl_break_info.setText("2 breaks (5 mins each)")
        else:
            self.lbl_break_info.setText("3 breaks (10 mins each)")

    def _on_sl_selected(self, checked: bool, sl_id: int):
        if checked:
            self.selected_study_list_id = sl_id
            self.refresh_focus_dashboard()

    def _on_start_clicked(self):
        if not self.is_running:
            # Start focus session
            mins = self.DURATIONS[self.current_duration_idx]
            self.total_session_seconds = mins * 60
            self.seconds_left = self.total_session_seconds
            self.is_running = True
            self.is_paused = False
            self.timer.start()

            self.btn_time_up.setEnabled(False)
            self.btn_time_down.setEnabled(False)
            self.chk_skip_breaks.setEnabled(False)

            self.btn_start.setText("⏸  Pause focus session")
            self.btn_start.setStyleSheet(
                "QPushButton { background-color: #d84315; color: white; border: none; border-radius: 6px; }"
            )
            self.session_started.emit(mins)
            self.timer_tick_signal.emit(self.seconds_left, self.total_session_seconds, True, False)
        elif not self.is_paused:
            # Pause session
            self.is_paused = True
            self.timer.stop()
            self.btn_start.setText("▶  Resume focus session")
            self.btn_start.setStyleSheet(
                "QPushButton { background-color: #2e7d32; color: white; border: none; border-radius: 6px; }"
            )
            self.timer_tick_signal.emit(self.seconds_left, self.total_session_seconds, True, True)
        else:
            # Resume session
            self.is_paused = False
            self.timer.start()
            self.btn_start.setText("⏸  Pause focus session")
            self.btn_start.setStyleSheet(
                "QPushButton { background-color: #d84315; color: white; border: none; border-radius: 6px; }"
            )
            self.timer_tick_signal.emit(self.seconds_left, self.total_session_seconds, True, False)

    def _on_tick(self):
        if self.seconds_left > 0:
            self.seconds_left -= 1
            m, s = divmod(self.seconds_left, 60)
            self.lbl_time_display.setText(f"{m:02d}:{s:02d}")
            self.timer_tick_signal.emit(self.seconds_left, self.total_session_seconds, True, False)
        else:
            self.timer.stop()
            self.is_running = False
            self.is_paused = False

            mins = max(1, self.total_session_seconds // 60)
            self.db_manager.log_focus_session(self.selected_study_list_id, mins)

            self.btn_time_up.setEnabled(True)
            self.btn_time_down.setEnabled(True)
            self.chk_skip_breaks.setEnabled(True)
            self.btn_start.setText("▶  Start focus session")
            self.btn_start.setStyleSheet(
                "QPushButton { background-color: #e05638; color: white; border: none; border-radius: 6px; }"
            )

            self._update_duration_display()
            self.refresh_focus_dashboard()
            self.timer_tick_signal.emit(0, 0, False, False)

            QMessageBox.information(
                self,
                "Focus Session Complete!",
                f"🎉 Great job! You completed a {mins}-minute focus session.",
            )
            self.session_completed.emit(mins, self.selected_study_list_id)

    def handle_topbar_timer_click(self, default_mins: int = 25):
        """Called when user clicks ⏱️ Timer button on top bar."""
        if self.is_running:
            # Toggle pause / resume or prompt stop
            if not self.is_paused:
                self._on_start_clicked()  # Pause
            else:
                self._on_start_clicked()  # Resume
        else:
            mins, ok = QInputDialog.getInt(self, "Study Timer", "Set Study Timer (minutes):", default_mins, 1, 180)
            if ok and mins > 0:
                self.start_custom_timer(mins)

    def start_custom_timer(self, mins: int):
        if self.is_running:
            self.timer.stop()

        self.total_session_seconds = mins * 60
        self.seconds_left = self.total_session_seconds
        self.is_running = True
        self.is_paused = False
        self.timer.start()

        self.btn_time_up.setEnabled(False)
        self.btn_time_down.setEnabled(False)
        self.chk_skip_breaks.setEnabled(False)
        self.lbl_time_display.setText(f"{mins:02d}:00")

        self.btn_start.setText("⏸  Pause focus session")
        self.btn_start.setStyleSheet(
            "QPushButton { background-color: #d84315; color: white; border: none; border-radius: 6px; }"
        )
        self.session_started.emit(mins)
        self.timer_tick_signal.emit(self.seconds_left, self.total_session_seconds, True, False)

    def _prompt_add_study_list(self):
        name, ok = QInputDialog.getText(self, "Create Study List", "Study List Name:")
        if ok and name.strip():
            new_id = self.db_manager.create_study_list(name.strip())
            self.selected_study_list_id = new_id
            self.refresh_focus_dashboard()

    def _prompt_change_goal(self):
        val, ok = QInputDialog.getInt(self, "Daily Goal", "Daily Focus Goal (minutes):", 480, 15, 1440)
        if ok and val > 0:
            stats = self.db_manager.get_focus_stats()
            self.ring_widget.set_stats(stats.get("today_minutes", 0), goal_mins=val)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
