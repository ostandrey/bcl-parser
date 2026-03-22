"""Shared Material Design 3 color palette and Qt stylesheet helpers."""

COLORS = {
    # Primary
    'primary':            '#6750A4',
    'primary_dark':       '#4F378B',
    'primary_container':  '#EADDFF',
    'primary_light':      '#EADDFF',   # alias used by date_picker
    'on_primary':         '#FFFFFF',
    # Secondary
    'secondary':          '#625B71',
    'secondary_container':'#E8DEF8',
    # Tertiary
    'tertiary':           '#7D5260',
    # Surface
    'surface':            '#FFFBFE',
    'surface_variant':    '#F3EFF7',
    'background':         '#FEF7FF',
    # On-surface
    'on_surface':         '#1C1B1F',
    'on_surface_dim':     '#6B6572',
    'on_surface_variant': '#49454F',
    # Outline
    'outline':            '#79747E',
    'outline_variant':    '#CAC4D0',
    # Semantic — error
    'error':              '#BA1A1A',
    'error_container':    '#F9DEDC',
    # Semantic — warning
    'warning':            '#B45309',
    'warning_container':  '#FEF3C7',
    'warning_border':     '#FCD34D',
    # Semantic — success
    'success':            '#166634',
    'success_container':  '#DCFCE7',
    'success_border':     '#86EFAC',
    # Misc
    'shadow':             'rgba(0,0,0,0.15)',
    'scrim':              'rgba(0,0,0,0.32)',
    'rose':               '#F4C2C2',   # date-range highlight
    'weekend':            '#B3261E',   # calendar weekend text
}

# ── Reusable Qt stylesheets ────────────────────────────────────────────────────

GLOBAL_STYLE = f"""
    QMainWindow, QDialog, QWidget {{
        background-color: {COLORS['background']};
        font-family: 'Segoe UI', 'Arial', sans-serif;
        font-size: 10pt;
        color: {COLORS['on_surface']};
    }}
"""

CARD_STYLE = f"""
    QFrame {{
        background-color: {COLORS['surface']};
        border: 1.5px solid {COLORS['outline_variant']};
        border-radius: 16px;
    }}
"""

FILLED_BTN_STYLE = f"""
    QPushButton {{
        background-color: {COLORS['primary']};
        color: {COLORS['on_primary']};
        border: none;
        border-radius: 26px;
        font-size: 12pt;
        font-weight: 600;
        letter-spacing: 0.3px;
    }}
    QPushButton:hover {{ background-color: {COLORS['primary_dark']}; }}
    QPushButton:pressed {{ background-color: #3B2A6E; }}
    QPushButton:disabled {{
        background-color: {COLORS['surface_variant']};
        color: {COLORS['on_surface_dim']};
    }}
"""

TONAL_BTN_STYLE = f"""
    QPushButton {{
        background-color: {COLORS['primary_container']};
        color: {COLORS['primary']};
        border: none;
        border-radius: 20px;
        padding: 10px 22px;
        font-weight: 600;
        font-size: 10pt;
    }}
    QPushButton:hover {{ background-color: #D8CAFF; }}
    QPushButton:pressed {{ background-color: #C4B0F5; }}
"""

TEXT_BTN_STYLE = f"""
    QPushButton {{
        background-color: transparent;
        color: {COLORS['on_surface_variant']};
        border: 1px solid {COLORS['outline_variant']};
        border-radius: 20px;
        padding: 10px 22px;
        font-weight: 500;
        font-size: 10pt;
    }}
    QPushButton:hover {{
        background-color: {COLORS['surface_variant']};
        border-color: {COLORS['outline']};
    }}
    QPushButton:pressed {{ background-color: #E8E0F0; }}
"""

DATE_CHIP_STYLE = f"""
    QPushButton {{
        background-color: {COLORS['surface']};
        color: {COLORS['on_surface']};
        border: 1.5px solid {COLORS['outline_variant']};
        border-radius: 12px;
        padding: 0 14px;
        font-size: 10.5pt;
        font-weight: 500;
        text-align: left;
    }}
    QPushButton:hover {{
        background-color: {COLORS['primary_container']};
        border-color: {COLORS['primary']};
        color: {COLORS['primary']};
    }}
    QPushButton:pressed {{ background-color: #D8CAFF; }}
"""

INPUT_STYLE = f"""
    QLineEdit {{
        padding: 8px 12px;
        border: 1.5px solid {COLORS['outline_variant']};
        border-radius: 8px;
        background-color: {COLORS['surface']};
        font-size: 10pt;
        color: {COLORS['on_surface']};
    }}
    QLineEdit:hover {{
        border-color: {COLORS['outline']};
    }}
    QLineEdit:focus {{
        border: 2px solid {COLORS['primary']};
    }}
    QLineEdit:disabled {{
        background-color: {COLORS['surface_variant']};
        color: {COLORS['on_surface_dim']};
    }}
"""

COMBO_STYLE = f"""
    QComboBox {{
        padding: 8px 12px;
        border: 1.5px solid {COLORS['outline_variant']};
        border-radius: 8px;
        background-color: {COLORS['surface']};
        font-size: 10pt;
        color: {COLORS['on_surface']};
        min-height: 20px;
    }}
    QComboBox:hover {{ border-color: {COLORS['outline']}; }}
    QComboBox:focus {{ border: 2px solid {COLORS['primary']}; }}
    QComboBox::drop-down {{
        border: none;
        width: 32px;
        background-color: transparent;
    }}
    QComboBox::drop-down:hover {{
        background-color: {COLORS['primary_container']};
        border-radius: 10px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLORS['surface']};
        border: 1px solid {COLORS['outline_variant']};
        border-radius: 6px;
        selection-background-color: {COLORS['primary_container']};
        selection-color: {COLORS['on_surface']};
        padding: 4px;
    }}
"""

GROUP_BOX_STYLE = f"""
    QGroupBox {{
        font-weight: 600;
        font-size: 11pt;
        color: {COLORS['on_surface']};
        border: 1.5px solid {COLORS['outline_variant']};
        border-radius: 10px;
        margin-top: 14px;
        background-color: {COLORS['surface']};
        padding-top: 4px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px;
        padding: 0 6px;
        background-color: {COLORS['surface']};
    }}
"""
