import sys
import os
from pathlib import Path

# ==============================================================================
# Cross-Platform Path Resolution
# ==============================================================================
def _get_system_paths() -> tuple[Path, Path]:
    """Returns (Config_Dir, Cache_Dir) natively formatted for Windows, Mac, or Linux."""
    home = Path.home()
    
    if sys.platform == "win32": # Windows
        config = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        cache = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    elif sys.platform == "darwin": # macOS
        config = home / "Library" / "Application Support"
        cache = home / "Library" / "Caches"
    else: # Linux / Unix
        config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        cache = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))
        
    app_config_dir = config / "refviewer"
    app_cache_dir = cache / "refviewer" / "thumbnails"
    
    return app_config_dir, app_cache_dir

DB_DIR, CACHE_DIR = _get_system_paths()
DB_PATH = DB_DIR / "data.db"


# ==============================================================================
# Global Stylesheet Dictionary
# ==============================================================================
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
}