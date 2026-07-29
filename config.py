import sys
import os
from pathlib import Path


# ==============================================================================
# Cross-Platform Path Resolution
# ==============================================================================
def _get_system_paths() -> tuple[Path, Path]:
    """Returns (Config_Dir, Cache_Dir) natively formatted for Windows, Mac, or Linux."""
    home = Path.home()

    if sys.platform == "win32":  # Windows
        config = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        cache = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    elif sys.platform == "darwin":  # macOS
        config = home / "Library" / "Application Support"
        cache = home / "Library" / "Caches"
    else:  # Linux / Unix
        config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        cache = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))

    app_config_dir = config / "refviewer"
    app_cache_dir = cache / "refviewer" / "thumbnails"

    return app_config_dir, app_cache_dir


DB_DIR, CACHE_DIR = _get_system_paths()
DB_PATH = DB_DIR / "data.db"

APP_TIMER_DEFAULT = "60"


# ==============================================================================
# Global Stylesheet Dictionary
# ==============================================================================
TAG_ICONS = {"rename": "✏️", "delete": "🗑️", "add": "+", "remove": "−"}

TAG_BTN_SIZE = 20
TAG_PARSE_REGEX = r"^(.*)\s\(\d+\)$"

# ==============================================================================
# Session History (Left Sidebar "History" Tab)
# ==============================================================================
# Purely in-memory / per-session (never written to disk or the database), so
# it's wiped every time the app restarts. These are just UI sizing knobs.
HISTORY_ICON_SIZE = 100
HISTORY_GRID_SIZE = 110

# ==============================================================================
# Drawing / Annotation Tool Settings
# ==============================================================================
# Annotations are a purely transient, in-session overlay (see components/drawing_canvas.py).
# They are never saved to disk or the database, so these are just UI defaults/bounds.
DRAWING_ICONS = {
    "draw_off": "✏️ Draw",
    "draw_on": "✏️ Drawing",
    "undo": "↩️",
    "redo": "↪️",
    "clear": "🧹",
}

DEFAULT_PEN_COLOR = "#ff0000"
DEFAULT_PEN_ALPHA = 150  # 0-255; applied to DEFAULT_PEN_COLOR on startup
DEFAULT_PEN_WIDTH = 10
PEN_WIDTH_MIN = 1
PEN_WIDTH_MAX = 50

PEN_SIZE_SPINBOX_WIDTH = 55
SIZE_SLIDER_WIDTH = 80
COLOR_SWATCH_SIZE = 24

# Opacity is exposed to the user as a 0-100% value, translated internally to
# the 0-255 alpha range QColor actually uses.
PEN_OPACITY_PERCENT_MIN = 0
PEN_OPACITY_PERCENT_MAX = 100
OPACITY_SPINBOX_WIDTH = 55
OPACITY_SLIDER_WIDTH = 80

# Quick-access presets shown as their own swatches/buttons on the toolbar.
QUICK_PEN_COLORS = {
    "Red": "#ff0000",
    "Blue": "#0000ff",
    "Yellow": "#ffff00",
    "Green": "#00ff00",
    "Magenta": "#ff00ff",
    "Orange": "#ff9900",
    "Cyan": "#00ddff",
}
QUICK_PEN_ALPHA = 150  # 0-255; applied to every QUICK_PEN_COLORS swatch
QUICK_COLOR_SWATCH_SIZE = 20

QUICK_PEN_SIZES = [1, 2, 5, 10, 20]
QUICK_SIZE_BTN_WIDTH = 26

STYLES = {
    "sidebar": "background-color: #2c3e50;",
    "right_sidebar": "background-color: #34495e;",
    "content": "background-color: #000000;",
    "placeholder": "color: #7f8c8d; font-size: 14px;",
    "error": "color: #e74c3c; font-size: 14px;",
    "label": "color: #ecf0f1; font-size: 12px; font-weight: bold;",
    "input": """
        QLineEdit { background-color: #1a252f; color: #ecf0f1; 
                    border: 1px solid #2c3e50; border-radius: 4px; padding: 4px; }
    """,
    "button": """
        QPushButton { background-color: white; color: #2c3e50; font-weight: bold;
                      border: 1px solid #bdc3c7; border-radius: 4px; padding: 4px 12px; }
        QPushButton:hover { background-color: #ecf0f1; }
        QPushButton:pressed { background-color: #dcdde1; }
    """,
    "list": """
        QListWidget { background-color: #1a252f; color: #ffffff; font-size: 11px;
                      border: 1px solid #34495e; border-radius: 4px; padding: 2px; }
        QListWidget::item:selected { background-color: #2980b9; } 
    """,
    "bubble": """
        QLabel { background-color: #2980b9; color: #ecf0f1; font-size: 11px; font-weight: bold;
                 border-radius: 10px; padding: 4px 10px; margin-right: 5px; }
    """,
    "tag_row_label": "color: white; background: transparent; font-size: 11px;",
    "tag_btn_action": """
        QPushButton { background: transparent; border: none; } 
        QPushButton:hover { background: #34495e; border-radius: 3px; }
    """,
    "tag_btn_delete": """
        QPushButton { background: transparent; border: none; } 
        QPushButton:hover { background: #e74c3c; border-radius: 3px; }
    """,
    "tag_btn_assigned": """
        QPushButton { background-color: #e74c3c; color: white; border-radius: 3px; font-weight: bold; } 
        QPushButton:hover { background-color: #c0392b; }
    """,
    "tag_btn_unassigned": """
        QPushButton { background-color: #27ae60; color: white; border-radius: 3px; font-weight: bold; } 
        QPushButton:hover { background-color: #2ecc71; }
    """,
    "current_path_label": "color: white; font-size: 12px; font-weight: bold; background: transparent;",
    "tool_toggle_btn": """
        QToolButton { background-color: #1a252f; color: #ecf0f1; font-weight: bold;
                      border: 1px solid #34495e; border-radius: 4px; padding: 4px 10px; }
        QToolButton:hover { background-color: #2c3e50; }
        QToolButton:checked { background-color: #2980b9; border-color: #2980b9; }
    """,
    "color_swatch_btn": "background-color: {color}; border: 1px solid #7f8c8d; border-radius: 3px;",
    "spinbox": """
        QSpinBox { background-color: #1a252f; color: #ecf0f1;
                   border: 1px solid #2c3e50; border-radius: 4px; padding: 2px 4px; }
        QSpinBox::up-button, QSpinBox::down-button { background-color: #2c3e50; border: none; width: 14px; }
        QSpinBox::up-arrow, QSpinBox::down-arrow { width: 8px; height: 8px; }
    """,
    "color_dialog": """
        QColorDialog { background-color: #2c3e50; }
        QColorDialog QLabel { color: #ecf0f1; background: transparent; }
        QColorDialog QLineEdit { background-color: #1a252f; color: #ecf0f1;
                                  border: 1px solid #34495e; border-radius: 3px; padding: 2px; }
        QColorDialog QSpinBox { background-color: #1a252f; color: #ecf0f1;
                                 border: 1px solid #34495e; border-radius: 3px; }
        QColorDialog QPushButton { background-color: white; color: #2c3e50; font-weight: bold;
                                    border: 1px solid #bdc3c7; border-radius: 4px; padding: 4px 12px; }
        QColorDialog QPushButton:hover { background-color: #ecf0f1; }
    """,
    "quick_color_swatch": """
        QPushButton { background-color: {color}; border: 1px solid #7f8c8d; border-radius: 3px; }
        QPushButton:hover { border: 1px solid #ecf0f1; }
    """,
    "quick_size_btn": """
        QPushButton { background-color: #1a252f; color: #ecf0f1; font-size: 10px;
                      border: 1px solid #34495e; border-radius: 4px; padding: 2px; }
        QPushButton:hover { background-color: #2c3e50; }
        QPushButton:pressed { background-color: #2980b9; }
    """,
    "slider": """
        QSlider::groove:horizontal { background-color: #1a252f; height: 4px; border-radius: 2px; }
        QSlider::handle:horizontal { background-color: #2980b9; width: 12px; margin: -5px 0; border-radius: 6px; }
        QSlider::handle:horizontal:hover { background-color: #3498db; }
    """,
    "tab_widget": """
        QTabWidget { background-color: #000000; }
        QTabWidget::pane { border: none; background-color: #2c3e50; top: -1px; }
        QTabWidget::tab-bar { background-color: #000000; }
        QTabBar { background-color: #000000; border: none; }
        QTabBar::tab { background-color: #1a252f; color: #ecf0f1; padding: 6px 14px;
                       border: 1px solid #34495e; border-bottom: none;
                       border-top-left-radius: 4px; border-top-right-radius: 4px; }
        QTabBar::tab:selected { background-color: #2980b9; color: white; }
        QTabBar::tab:!selected:hover { background-color: #34495e; }
    """,
}
