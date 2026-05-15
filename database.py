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
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY AUTOINCREMENT, filepath TEXT UNIQUE)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)"
        )
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
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )


def get_setting(key: str) -> str:
    with _get_connection() as conn:
        cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else ""


def add_tag_to_image(filepath: str, tag_name: str):
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO images (filepath) VALUES (?)", (filepath,)
        )
        cursor.execute("SELECT id FROM images WHERE filepath = ?", (filepath,))
        img_id = cursor.fetchone()[0]

        cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
            (img_id, tag_id),
        )


def delete_tag(tag_name: str):
    """Permanently deletes a tag. (Foreign Key cascades will remove it from all images automatically)"""
    with _get_connection() as conn:
        conn.execute("DELETE FROM tags WHERE name = ?", (tag_name,))
        conn.commit()


def rename_tag(old_name: str, new_name: str):
    """Renames a tag. Intelligently merges data if the new name already exists."""
    with _get_connection() as conn:
        cursor = conn.cursor()

        # Check if the desired new name already exists
        cursor.execute("SELECT id FROM tags WHERE name = ?", (new_name,))
        existing = cursor.fetchone()

        if existing:
            # The new tag exists. We need to MERGE them.
            new_id = existing[0]
            cursor.execute("SELECT id FROM tags WHERE name = ?", (old_name,))
            old_id_row = cursor.fetchone()

            if old_id_row:
                old_id = old_id_row[0]
                # Re-assign all images holding the old tag to the new tag (IGNORE prevents duplicates)
                cursor.execute(
                    "INSERT OR IGNORE INTO image_tags (image_id, tag_id) SELECT image_id, ? FROM image_tags WHERE tag_id = ?",
                    (new_id, old_id),
                )
                # Delete the outdated link and the old tag itself
                cursor.execute("DELETE FROM image_tags WHERE tag_id = ?", (old_id,))
                cursor.execute("DELETE FROM tags WHERE id = ?", (old_id,))
        else:
            # It's a brand new word, just update the string globally
            cursor.execute(
                "UPDATE tags SET name = ? WHERE name = ?", (new_name, old_name)
            )

        conn.commit()


def get_image_tags(filepath: str) -> list[str]:
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT tags.name FROM tags
            JOIN image_tags ON tags.id = image_tags.tag_id
            JOIN images ON images.id = image_tags.image_id
            WHERE images.filepath = ?
            ORDER BY tags.name ASC
        """,
            (filepath,),
        )
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
        conn.execute(
            """
            DELETE FROM image_tags 
            WHERE image_id = (SELECT id FROM images WHERE filepath = ?)
              AND tag_id = (SELECT id FROM tags WHERE name = ?)
        """,
            (filepath, tag_name),
        )


def get_images_by_tag(tag_name: str) -> list[str]:
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT images.filepath FROM images
            JOIN image_tags ON images.id = image_tags.image_id
            JOIN tags ON tags.id = image_tags.tag_id
            WHERE tags.name = ?
        """,
            (tag_name,),
        )
        return [row[0] for row in cursor.fetchall()]


def get_shared_tags(filepaths: list[str]) -> set[str]:
    """Returns the intersection of tags shared across ALL given filepaths."""
    if not filepaths:
        return set()
    with _get_connection() as conn:
        chunk_size = 900  # SQLite limit for parameters is ~999
        file_to_tags = {fp: set() for fp in filepaths}

        for i in range(0, len(filepaths), chunk_size):
            chunk = filepaths[i : i + chunk_size]
            placeholders = ", ".join("?" for _ in chunk)
            cursor = conn.execute(
                f"""
                SELECT images.filepath, tags.name FROM tags
                JOIN image_tags ON tags.id = image_tags.tag_id
                JOIN images ON images.id = image_tags.image_id
                WHERE images.filepath IN ({placeholders})
            """,
                chunk,
            )
            for filepath, tag_name in cursor:
                file_to_tags[filepath].add(tag_name)

        # Intersection math
        shared = None
        for tags in file_to_tags.values():
            if shared is None:
                shared = tags
            else:
                shared = shared.intersection(tags)
            if not shared:
                break
        return shared or set()


def bulk_add_tag_to_images(filepaths: list[str], tag_name: str):
    """Instantly adds a tag to thousands of images in a single transaction."""
    if not filepaths:
        return
    with _get_connection() as conn:
        cursor = conn.cursor()

        # Ensure tag exists
        cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_id = cursor.fetchone()[0]

        # Bulk ensure images exist
        cursor.executemany(
            "INSERT OR IGNORE INTO images (filepath) VALUES (?)",
            [(fp,) for fp in filepaths],
        )

        chunk_size = 900
        image_ids = []
        for i in range(0, len(filepaths), chunk_size):
            chunk = filepaths[i : i + chunk_size]
            placeholders = ", ".join("?" for _ in chunk)
            res = cursor.execute(
                f"SELECT id FROM images WHERE filepath IN ({placeholders})", chunk
            ).fetchall()
            image_ids.extend([row[0] for row in res])

        cursor.executemany(
            "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
            [(img_id, tag_id) for img_id in image_ids],
        )
        conn.commit()


def bulk_remove_tag_from_images(filepaths: list[str], tag_name: str):
    """Instantly removes a tag from thousands of images."""
    if not filepaths:
        return
    with _get_connection() as conn:
        cursor = conn.cursor()
        chunk_size = 900
        for i in range(0, len(filepaths), chunk_size):
            chunk = filepaths[i : i + chunk_size]
            placeholders = ", ".join("?" for _ in chunk)
            cursor.execute(
                f"""
                DELETE FROM image_tags 
                WHERE tag_id = (SELECT id FROM tags WHERE name = ?)
                  AND image_id IN (SELECT id FROM images WHERE filepath IN ({placeholders}))
            """,
                [tag_name] + chunk,
            )
        conn.commit()
