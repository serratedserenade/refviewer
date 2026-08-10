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
# Tag UI
# ==============================================================================
TAG_ICONS = {"rename": "✏️", "delete": "🗑️", "add": "+", "remove": "−"}

TAG_BTN_SIZE = 20
# Matches the trailing image count in a formatted tag string, e.g. "portrait (12)".
TAG_PARSE_REGEX = r"^(.*)\s\(\d+\)$"

# How multiple checked tags combine when filtering the image list.
TAG_FILTER_MODE_AND = "AND"
TAG_FILTER_MODE_OR = "OR"
TAG_FILTER_MODES = (TAG_FILTER_MODE_AND, TAG_FILTER_MODE_OR)
DEFAULT_TAG_FILTER_MODE = TAG_FILTER_MODE_OR
TAG_FILTER_MODE_TOOLTIPS = {
    TAG_FILTER_MODE_AND: "Show only images carrying every checked tag",
    TAG_FILTER_MODE_OR: "Show images carrying at least one checked tag",
}

# ==============================================================================
# File List Thumbnails (Left Sidebar "Images" Tab)
# ==============================================================================
# THUMBNAIL_SIZE is both the icon size in the list and the size thumbnails are
# generated and cached at, so the two must stay in step.
THUMBNAIL_SIZE = 100
THUMBNAIL_GRID_SIZE = 110
# Delay before the path filter rebuilds the list, so typing doesn't rescan per key.
PATH_FILTER_DEBOUNCE_MS = 300

# ==============================================================================
# Folder Shortcuts (Left Sidebar "Files" Tab)
# ==============================================================================
FAVOURITE_ICONS = {"add": "★", "rename": "✏️", "remove": "🗑️"}
# How the Files tab splits between the favourites list and the tree below it,
# as a percentage of the available height. The splitter is user-draggable, so
# this only sets where it starts.
FAVOURITES_SPLIT_PERCENT = 25
FILE_TREE_SPLIT_PERCENT = 75

# ==============================================================================
# Session History (Left Sidebar "History" Tab)
# ==============================================================================
# The history list is in-memory only and is never persisted.
HISTORY_ICON_SIZE = 100
HISTORY_GRID_SIZE = 110
# Cap on retained entries; the oldest are dropped once the list exceeds this.
HISTORY_MAX_ITEMS = 100

# ==============================================================================
# Drawing / Annotation Tool Settings
# ==============================================================================
# Annotations are a transient overlay and are never persisted, so these are
# purely UI defaults and bounds.
DRAWING_ICONS = {
    "draw_off": "✏️ Draw",
    "draw_on": "✏️ Drawing",
    "undo": "↩️",
    "redo": "↪️",
    "clear": "🧹",
}

# Cap on retained annotation strokes. Because the stroke list *is* the drawing,
# this bounds both memory and how far back Undo can reach: once the cap is hit,
# the oldest stroke is dropped from the canvas along with its undo entry.
MAX_ANNOTATION_STROKES = 500

DEFAULT_PEN_COLOR = "#ff0000"
DEFAULT_PEN_ALPHA = 150  # 0-255; applied to DEFAULT_PEN_COLOR on startup
DEFAULT_PEN_WIDTH = 10
PEN_WIDTH_MIN = 1
PEN_WIDTH_MAX = 50

PEN_SIZE_SPINBOX_WIDTH = 55
SIZE_SLIDER_WIDTH = 80
COLOR_SWATCH_SIZE = 24

# Opacity is exposed to the user as 0-100%, translated internally to the
# 0-255 alpha range QColor uses.
PEN_OPACITY_PERCENT_MIN = 0
PEN_OPACITY_PERCENT_MAX = 100
OPACITY_SPINBOX_WIDTH = 55
OPACITY_SLIDER_WIDTH = 80

# Quick-access presets shown as swatches/buttons on the toolbar. These are base
# colors; their alpha is taken from the Opacity control at selection time.
QUICK_PEN_COLORS = {
    "Red": "#ff0000",
    "Blue": "#0000ff",
    "Yellow": "#ffff00",
    "Green": "#00ff00",
    "Magenta": "#ff00ff",
    "Orange": "#ff9900",
    "Cyan": "#00ddff",
}
QUICK_COLOR_SWATCH_SIZE = 20

QUICK_PEN_SIZES = [1, 2, 5, 10, 20]
QUICK_SIZE_BTN_WIDTH = 26

# ==============================================================================
# Global Stylesheet Dictionary
# ==============================================================================
# Qt propagates a widget's stylesheet down to the tooltips that widget shows, so
# a dark-backgrounded list hands its background to the tooltip while the text
# stays the default black — unreadable. Applied application-wide so every
# tooltip is pinned to the theme regardless of which widget raised it.
TOOLTIP_STYLE = """
    QToolTip { background-color: #1a252f; color: #ecf0f1; font-size: 11px;
               border: 1px solid #7f8c8d; border-radius: 3px; padding: 4px; }
"""

# Keys are referenced as STYLES["<key>"] throughout the UI. Entries containing
# a {color} placeholder are formatted with a live value at runtime.
STYLES = {
    "tooltip": TOOLTIP_STYLE,
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
    # The tooltip rule is repeated inside the styles of the widgets that raise
    # path tooltips: a widget's own stylesheet outranks the application-wide one,
    # so without it these two would still hand their background to the tooltip.
    "list": TOOLTIP_STYLE
    + """
        QListWidget { background-color: #1a252f; color: #ffffff; font-size: 11px;
                      border: 1px solid #34495e; border-radius: 4px; padding: 2px; }
        QListWidget::item:selected { background-color: #2980b9; }
    """,
    "tree": TOOLTIP_STYLE
    + """
        QTreeView { background-color: #1a252f; color: #ffffff; font-size: 11px;
                    border: 1px solid #34495e; border-radius: 4px; padding: 2px; }
        QTreeView::item { padding: 2px 0px; }
        QTreeView::item:hover { background-color: #34495e; }
        QTreeView::item:selected { background-color: #2980b9; }
    """,
    "bubble": """
        QLabel { background-color: #2980b9; color: #ecf0f1; font-size: 11px; font-weight: bold;
                 border-radius: 10px; padding: 4px 10px; margin-right: 5px; }
    """,
    "tag_row_label": "color: white; background: transparent; font-size: 11px;",
    "menu": """
        QMenu { background-color: #2c3e50; color: #ecf0f1; font-size: 11px;
                border: 1px solid #34495e; padding: 4px; }
        QMenu::item { padding: 4px 14px; border-radius: 3px; }
        QMenu::item:selected { background-color: #2980b9; }
    """,
    "tag_checkbox": """
        QCheckBox { background: transparent; spacing: 0px; }
        QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid #7f8c8d;
                               border-radius: 3px; background-color: #1a252f; }
        QCheckBox::indicator:hover { border-color: #ecf0f1; }
        QCheckBox::indicator:checked { background-color: #2980b9; border-color: #2980b9; }
    """,
    # The native indicator is dark-on-dark here, so both states are drawn
    # explicitly to keep the unchecked option visible.
    "radio": """
        QRadioButton { color: #ecf0f1; font-size: 11px; font-weight: bold;
                       background: transparent; spacing: 5px; }
        QRadioButton::indicator { width: 11px; height: 11px; border-radius: 6px;
                                  border: 1px solid #7f8c8d; background-color: #1a252f; }
        QRadioButton::indicator:hover { border-color: #ecf0f1; }
        QRadioButton::indicator:checked { background-color: #2980b9;
                                          border-color: #2980b9; }
    """,
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
