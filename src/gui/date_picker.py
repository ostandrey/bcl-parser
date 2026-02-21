"""
Custom Material Design Date Range Picker — single calendar, range selection.
Click 1 → sets start date
Click 2 → sets end date (if >= start, else resets start)
"""

import calendar
from datetime import date, datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QWidget, QGridLayout, QFrame, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QRect
from PyQt6.QtGui import QAction, QPainter, QColor, QPen, QBrush

# ── Palette ────────────────────────────────────────────────────────────────────
C = {
    "primary":         "#6750A4",
    "primary_light":   "#EADDFF",
    "primary_dark":    "#4F378B",
    "rose":            "#F4C2C2",
    "on_primary":      "#FFFFFF",
    "surface":         "#FDFBFD",
    "surface_variant": "#F3EFF7",
    "on_surface":      "#1C1B1F",
    "on_surface_dim":  "#79747E",
    "outline":         "#CAC4D0",
    "weekend":         "#B3261E",
}

MONTHS_UA = [
    "Січень", "Лютий", "Березень", "Квітень",
    "Травень", "Червень", "Липень", "Серпень",
    "Вересень", "Жовтень", "Листопад", "Грудень"
]
DAYS_UA = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]

# Fixed cell size — key to preventing wide tiles
CELL_W = 40   # container width
CELL_H = 40   # container height
BTN_W  = 32   # actual button width (smaller than cell → perfect circle)
BTN_H  = 32   # actual button height

RANGE_BAR_H = 20   # height of the rose-colored range bar strip


# ── RangeCell — draws the range highlight bar behind the day button ────────────
class RangeCell(QWidget):
    """
    Transparent container that paints a rose-colored bar for range highlighting.
    mode:
      "none"   — no highlight
      "mid"    — full-width rose bar
      "start"  — rose bar from center to right edge
      "end"    — rose bar from left edge to center
      "single" — no bar (just the purple circle)
    """
    def __init__(self, mode: str = "none", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def paintEvent(self, event):
        if self.mode in ("none", "single"):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        bar_y = (h - RANGE_BAR_H) // 2
        rose  = QColor(C["rose"])

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(rose))

        if self.mode == "mid":
            painter.drawRect(QRect(0, bar_y, w, RANGE_BAR_H))
        elif self.mode == "start":
            # left half = rounded cap, right half = flat
            r = RANGE_BAR_H // 2
            painter.drawRoundedRect(QRect(w // 2 - r, bar_y, w // 2 + r, RANGE_BAR_H), r, r)
            # fill right half flat
            painter.drawRect(QRect(w // 2, bar_y, w // 2, RANGE_BAR_H))
        elif self.mode == "end":
            r = RANGE_BAR_H // 2
            painter.drawRoundedRect(QRect(0, bar_y, w // 2 + r, RANGE_BAR_H), r, r)
            painter.drawRect(QRect(0, bar_y, w // 2, RANGE_BAR_H))

        painter.end()


# ── Calendar Panel ─────────────────────────────────────────────────────────────
class CalendarPanel(QWidget):
    dateClicked = pyqtSignal(date)

    def __init__(self, initial: date = None, max_year: int = None, parent=None):
        super().__init__(parent)
        self._current    = initial or date.today()
        self._max_year   = max_year or date.today().year
        self._range_start: date | None = None
        self._range_end:   date | None = None

        # 7 cols × CELL_W + margins
        panel_w = 7 * CELL_W + 8 + 8  # left+right margin = 16
        self.setFixedWidth(panel_w)
        self._build_ui()
        self._render()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        self._header = QWidget()
        self._header.setFixedHeight(48)
        self._header.setStyleSheet(f"""
            background-color: {C['primary']};
            border-radius: 12px 12px 0 0;
        """)
        h_lay = QHBoxLayout(self._header)
        h_lay.setContentsMargins(8, 0, 8, 0)

        self._btn_prev = self._nav_btn("◀")
        self._btn_prev.clicked.connect(self._prev_month)
        h_lay.addWidget(self._btn_prev)
        h_lay.addStretch()

        self._btn_month = self._header_label_btn()
        self._btn_month.clicked.connect(self._show_month_menu)
        h_lay.addWidget(self._btn_month)

        self._btn_year = self._header_label_btn()
        self._btn_year.clicked.connect(self._show_year_menu)
        h_lay.addWidget(self._btn_year)

        h_lay.addStretch()
        self._btn_next = self._nav_btn("▶")
        self._btn_next.clicked.connect(self._next_month)
        h_lay.addWidget(self._btn_next)

        root.addWidget(self._header)

        # ── Day-of-week row ──────────────────────────────────────────────────
        dow = QWidget()
        dow.setStyleSheet(f"background: {C['surface_variant']};")
        dow_lay = QGridLayout(dow)
        dow_lay.setContentsMargins(8, 4, 8, 4)
        dow_lay.setSpacing(0)
        for i, name in enumerate(DAYS_UA):
            lbl = QLabel(name)
            lbl.setFixedWidth(CELL_W)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = C["weekend"] if i >= 5 else C["on_surface_dim"]
            lbl.setStyleSheet(f"color:{color}; font-size:9pt; font-weight:600;")
            dow_lay.addWidget(lbl, 0, i)
        root.addWidget(dow)

        # ── Day grid ─────────────────────────────────────────────────────────
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet(f"background:{C['surface']};")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(8, 4, 8, 4)
        self._grid.setSpacing(0)
        # Lock column widths
        for col in range(7):
            self._grid.setColumnMinimumWidth(col, CELL_W)
            self._grid.setColumnStretch(col, 0)
        root.addWidget(self._grid_widget)

        self.setStyleSheet(f"""
            CalendarPanel {{
                border: 1px solid {C['outline']};
                border-radius: 12px;
                background: {C['surface']};
            }}
        """)

    def _nav_btn(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(32, 32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                color:{C['on_primary']}; background:transparent;
                border:none; font-size:12pt; font-weight:bold;
                border-radius:16px;
            }}
            QPushButton:hover {{ background:rgba(255,255,255,0.2); }}
            QPushButton:pressed {{ background:rgba(255,255,255,0.35); }}
        """)
        return btn

    def _header_label_btn(self) -> QPushButton:
        btn = QPushButton()
        btn.setFlat(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                color:{C['on_primary']}; font-size:12pt; font-weight:600;
                background:transparent; border:none; padding:2px 6px;
            }}
            QPushButton:hover {{
                background:rgba(255,255,255,0.15); border-radius:6px;
            }}
        """)
        return btn
    
    def clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
                else:
                    self.clear_layout(item.layout())

    def _render(self):
        self.clear_layout(self._grid)
    
        year = self._current.year
        month = self._current.month
        self._btn_month.setText(MONTHS_UA[month - 1])
        self._btn_year.setText(str(year))
        cal = calendar.monthcalendar(year, month)
        cal = [week for week in cal if any(d != 0 for d in week)]
        for row, week in enumerate(cal):
            for col, day_num in enumerate(week):
                if day_num == 0:
                    spacer = QWidget()
                    spacer.setFixedSize(CELL_W, CELL_W)
                    self._grid.addWidget(spacer, row, col)
                    continue

                # ── инициализируем переменные для каждого дня ──
                curr_date = date(year, month, day_num)
                is_start  = (curr_date == self._range_start)
                is_end    = (curr_date == self._range_end)
                mode      = "none"

                if self._range_start and self._range_end:
                    if is_start:
                        mode = "start"
                    elif is_end:
                        mode = "end"
                    elif self._range_start < curr_date < self._range_end:
                        mode = "mid"
                elif is_start or is_end:
                    mode = "single"

                cell = RangeCell(mode)
                cell.setFixedSize(CELL_W, CELL_H)

                btn = QPushButton(str(day_num))
                btn.setFixedSize(BTN_W, BTN_H)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)

                today = date.today()
                btn.setStyleSheet(self._day_style(curr_date, col, today))
                btn.clicked.connect(lambda checked, d=curr_date: self.dateClicked.emit(d))

                lay = QHBoxLayout(cell)
                lay.setContentsMargins(0, 0, 0, 0)
                lay.setSpacing(0)
                lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lay.addWidget(btn)

                self._grid.addWidget(cell, row, col)
            
    def _day_style(self, d: date, col: int, today: date) -> str:
        is_start   = d == self._range_start
        is_end     = d == self._range_end
        in_range   = (bool(self._range_start and self._range_end) and
                      self._range_start < d < self._range_end)
        # Don't show today highlight when it's part of the range
        is_today   = d == today and not in_range and not is_start and not is_end
        is_weekend = col >= 5
        r = BTN_W // 2  # perfect circle radius

        base = f"""
                min-width:{BTN_W}px; max-width:{BTN_W}px;
                min-height:{BTN_H}px; max-height:{BTN_H}px;
                border-radius:{r}px; font-size:10pt;
                padding:0px; qproperty-alignment:AlignCenter;
        """
        if is_start or is_end:
            return f"""
                QPushButton {{
                    background:{C['primary']}; color:{C['on_primary']};
                    border:none; font-weight:700;
                    {base}
                }}
                QPushButton:hover {{ background:{C['primary_dark']}; }}
            """
        if is_today:
            text_color = C["weekend"] if is_weekend else C["primary"]
            return f"""
                QPushButton {{
                    background:{C['primary_light']}; color:{text_color};
                    border:2px solid {C['primary']}; font-weight:600;
                    {base}
                }}
            """
        text_color = C["weekend"] if is_weekend else C["on_surface"]
        return f"""
            QPushButton {{
                background:transparent; color:{text_color};
                border:none;
                {base}
            }}
            QPushButton:hover {{
                background:{C['primary_light']}; color:{C['primary']};
            }}
        """

    # ── Navigation ─────────────────────────────────────────────────────────────
    def _prev_month(self):
        y, m = self._current.year, self._current.month
        m -= 1
        if m == 0:
            m, y = 12, y - 1
        self._current = self._current.replace(year=y, month=m, day=1)
        self._render()

    def _next_month(self):
        y, m = self._current.year, self._current.month
        m += 1
        if m == 13:
            m, y = 1, y + 1
        if y > self._max_year:
            return
        self._current = self._current.replace(year=y, month=m, day=1)
        self._render()

    # ── Dropdowns ──────────────────────────────────────────────────────────────
    def _menu_style(self) -> str:
        return f"""
            QMenu {{
                background:{C['surface']}; border:1px solid {C['outline']};
                border-radius:8px; padding:4px;
            }}
            QMenu::item {{
                padding:6px 20px; border-radius:6px; color:{C['on_surface']};
            }}
            QMenu::item:selected {{
                background:{C['primary_light']}; color:{C['primary']};
            }}
        """

    def _show_month_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(self._menu_style())
        for i, name in enumerate(MONTHS_UA):
            action = QAction(name, self)
            if i + 1 == self._current.month:
                action.setCheckable(True); action.setChecked(True)
            action.triggered.connect(lambda _, m=i+1: self._set_month(m))
            menu.addAction(action)
        menu.exec(self._btn_month.mapToGlobal(QPoint(0, self._btn_month.height())))

    def _show_year_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(self._menu_style())
        for y in range(self._max_year, self._max_year - 10, -1):
            action = QAction(str(y), self)
            if y == self._current.year:
                action.setCheckable(True); action.setChecked(True)
            action.triggered.connect(lambda _, yr=y: self._set_year(yr))
            menu.addAction(action)
        menu.exec(self._btn_year.mapToGlobal(QPoint(0, self._btn_year.height())))

    def _set_month(self, month: int):
        self._current = self._current.replace(month=month, day=1)
        self._render()

    def _set_year(self, year: int):
        self._current = self._current.replace(year=year, day=1)
        self._render()

    def set_range(self, start: date | None, end: date | None):
        self._range_start = start
        self._range_end   = end
        self._render()


# ── Range Dialog ───────────────────────────────────────────────────────────────
class MaterialDateRangeDialog(QDialog):
    """
    Single-calendar range picker.
    Click 1 → start date
    Click 2 → end date (if < start, resets and sets new start)
    """

    def __init__(self, parent=None, start_date: str = "", end_date: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Select Date Range")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._range_start: date | None = None
        self._range_end:   date | None = None
        self._awaiting_end = False          # True after first click
        self._max_year = date.today().year

        init_start = self._parse(start_date) or date.today()
        init_end   = self._parse(end_date)   or date.today()

        self.result_start = None
        self.result_end   = None

        self._build_ui(init_start, init_end)

        # Pre-fill range if both dates provided
        if start_date and end_date:
            self._range_start  = init_start
            self._range_end    = init_end
            self._awaiting_end = False
            self._cal.set_range(init_start, init_end)
            self._update_labels()

    def _parse(self, s: str) -> date | None:
        try:
            return datetime.strptime(s, "%d.%m.%Y").date()
        except Exception:
            return None

    def _build_ui(self, init_start: date, init_end: date):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(f"""
            QFrame#card {{
                background:{C['surface']};
                border-radius:20px;
                border:1px solid {C['outline']};
            }}
        """)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(20, 16, 20, 16)
        card_lay.setSpacing(10)
        outer.addWidget(card)

        # Title
        title = QLabel("Select Date Range")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            color:{C['on_surface']}; font-size:15pt;
            font-weight:700; padding-bottom:4px;
        """)
        card_lay.addWidget(title)

        # From / To labels row
        lbl_row = QHBoxLayout()
        lbl_row.setSpacing(12)

        self._lbl_from = QLabel("From: —")
        self._lbl_to   = QLabel("To: —")
        for lbl in (self._lbl_from, self._lbl_to):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"""
                background:{C['primary_light']}; color:{C['primary']};
                font-size:10pt; font-weight:600;
                border-radius:8px; padding:5px 14px;
            """)
            lbl_row.addWidget(lbl)
        card_lay.addLayout(lbl_row)

        # Hint
        self._hint = QLabel("← Click a start date")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(f"color:{C['on_surface_dim']}; font-size:9pt;")
        card_lay.addWidget(self._hint)

        # Single calendar
        self._cal = CalendarPanel(init_start, self._max_year)
        self._cal.dateClicked.connect(self._on_date_clicked)
        card_lay.addWidget(self._cal, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{C['outline']};")
        card_lay.addWidget(line)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(120, 40)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{C['primary']};
                border:2px solid {C['primary']}; border-radius:20px;
                font-size:11pt; font-weight:500;
            }}
            QPushButton:hover {{ background:{C['primary_light']}; }}
            QPushButton:pressed {{ background:#D1C4E9; }}
        """)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(12)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedSize(120, 40)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self._on_ok)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C['primary']}; color:{C['on_primary']};
                border:none; border-radius:20px;
                font-size:11pt; font-weight:700;
            }}
            QPushButton:hover {{ background:{C['primary_dark']}; }}
            QPushButton:pressed {{ background:#3B2A6E; }}
        """)
        btn_row.addWidget(ok_btn)
        btn_row.addStretch()
        card_lay.addLayout(btn_row)

    # ── Click logic ────────────────────────────────────────────────────────────
    def _on_date_clicked(self, d: date):
        if not self._awaiting_end:
            # First click → set start, wait for end
            self._range_start  = d
            self._range_end    = None
            self._awaiting_end = True
            self._cal.set_range(d, None)
        else:
            # Second click
            if d < self._range_start:
                # Clicked before start → reset, treat as new start
                self._range_start  = d
                self._range_end    = None
                self._awaiting_end = True
                self._cal.set_range(d, None)
            elif d == self._range_start:
                # Same day → single-day range
                self._range_end    = d
                self._awaiting_end = False
                self._cal.set_range(d, d)
            else:
                # Valid end date
                self._range_end    = d
                self._awaiting_end = False
                self._cal.set_range(self._range_start, d)

        self._update_labels()

    def _update_labels(self):
        fmt = "%d.%m.%Y"
        from_txt = self._range_start.strftime(fmt) if self._range_start else "—"
        to_txt   = self._range_end.strftime(fmt)   if self._range_end   else "—"
        self._lbl_from.setText(f"From: {from_txt}")
        self._lbl_to.setText(f"To: {to_txt}")

        if self._awaiting_end:
            self._hint.setText("→ Now click an end date")
        elif self._range_end:
            self._hint.setText("✓ Range selected")
        else:
            self._hint.setText("← Click a start date")

    def _on_ok(self):
        self.result_start = self._range_start
        self.result_end   = self._range_end
        self.accept()

    @staticmethod
    def get_range(parent=None, start_date: str = "", end_date: str = ""):
        dlg = MaterialDateRangeDialog(parent, start_date, end_date)
        if dlg.exec():
            fmt = "%d.%m.%Y"
            s = dlg.result_start.strftime(fmt) if dlg.result_start else ""
            e = dlg.result_end.strftime(fmt)   if dlg.result_end   else ""
            return s, e
        return None, None


# ── Single date dialog (backward compat) ──────────────────────────────────────
class MaterialDateDialog(QDialog):
    def __init__(self, parent=None, initial_date: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Select Date")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._max_year = date.today().year
        init = self._parse(initial_date) or date.today()
        self.result_date = None

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(f"""
            QFrame#card {{
                background:{C['surface']}; border-radius:20px;
                border:1px solid {C['outline']};
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        title = QLabel("Select Date")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{C['on_surface']}; font-size:14pt; font-weight:700;")
        lay.addWidget(title)

        self._panel = CalendarPanel(init, self._max_year)
        self._panel.dateClicked.connect(self._on_click)
        lay.addWidget(self._panel)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        cancel.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{C['primary']};
                border:2px solid {C['primary']}; border-radius:20px;
                padding:7px 24px; font-weight:500;
            }}
            QPushButton:hover {{ background:{C['primary_light']}; }}
        """)
        btn_row.addWidget(cancel)
        btn_row.addSpacing(8)

        ok = QPushButton("OK")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.clicked.connect(self._on_ok)
        ok.setStyleSheet(f"""
            QPushButton {{
                background:{C['primary']}; color:white;
                border:none; border-radius:20px;
                padding:7px 32px; font-weight:600;
            }}
            QPushButton:hover {{ background:{C['primary_dark']}; }}
        """)
        btn_row.addWidget(ok)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._selected = init

    def _parse(self, s: str) -> date | None:
        try:
            return datetime.strptime(s, "%d.%m.%Y").date()
        except Exception:
            return None

    def _on_click(self, d: date):
        self._selected = d
        self._panel.set_range(d, d)

    def _on_ok(self):
        self.result_date = self._selected
        self.accept()

    @staticmethod
    def get_date(parent=None, initial_date: str = "") -> str | None:
        dlg = MaterialDateDialog(parent, initial_date)
        if dlg.exec():
            return dlg.result_date.strftime("%d.%m.%Y") if dlg.result_date else None
        return None