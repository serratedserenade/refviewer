import sqlite3
from config import DB_DIR, DB_PATH

def _get_connection():
    """Helper to return a connection with Foreign Keys enforced."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_database():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY AUTOINCREMENT, filepath TEXT UNIQUE)")
        cursor.execute("CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_tags (
                image_id INTEGER, tag_id INTEGER,
                PRIMARY KEY (image_id, tag_id),
                FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        """)
        conn.commit()

def save_setting(key: str, value: str):
    with _get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

def get_setting(key: str) -> str:
    with _get_connection() as conn:
        cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else ""

def add_tag_to_image(filepath: str, tag_name: str):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO images (filepath) VALUES (?)", (filepath,))
        cursor.execute("SELECT id FROM images WHERE filepath = ?", (filepath,))
        img_id = cursor.fetchone()[0]
        
        cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_id = cursor.fetchone()[0]
        
        cursor.execute("INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)", (img_id, tag_id))

def get_image_tags(filepath: str) -> list[str]:
    with _get_connection() as conn:
        cursor = conn.execute("""
            SELECT tags.name FROM tags
            JOIN image_tags ON tags.id = image_tags.tag_id
            JOIN images ON images.id = image_tags.image_id
            WHERE images.filepath = ?
            ORDER BY tags.name ASC
        """, (filepath,))
        return [row[0] for row in cursor.fetchall()]

def get_all_tags() -> list[str]:
    with _get_connection() as conn:
        cursor = conn.execute("""
            SELECT tags.name, COUNT(image_tags.image_id) 
            FROM tags
            LEFT JOIN image_tags ON tags.id = image_tags.tag_id
            GROUP BY tags.id
            ORDER BY tags.name ASC
        """)
        return [f"{row[0]} ({row[1]})" for row in cursor.fetchall()]

def remove_tag_from_image(filepath: str, tag_name: str):
    with _get_connection() as conn:
        conn.execute("""
            DELETE FROM image_tags 
            WHERE image_id = (SELECT id FROM images WHERE filepath = ?)
              AND tag_id = (SELECT id FROM tags WHERE name = ?)
        """, (filepath, tag_name))
        
def get_images_by_tag(tag_name: str) -> list[str]:
    with _get_connection() as conn:
        cursor = conn.execute("""
            SELECT images.filepath FROM images
            JOIN image_tags ON images.id = image_tags.image_id
            JOIN tags ON tags.id = image_tags.tag_id
            WHERE tags.name = ?
        """, (tag_name,))
        return [row[0] for row in cursor.fetchall()]