from pathlib import Path

# Paths
CACHE_DIR: Path = Path.home() / ".cache" / "refviewer" / ".thumbnail_cache"
DB_DIR: Path = Path.home() / ".config" / "refviewer"
DB_PATH: Path = DB_DIR / "data.db"

# Global Stylesheet Dictionary
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