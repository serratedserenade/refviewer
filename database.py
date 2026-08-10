import json
import sqlite3
import threading

from config import DB_DIR, DB_PATH

# SQLite allows roughly 999 bound parameters per statement, so any query built
# from a variable-length list of filepaths is issued in chunks of this size.
SQL_PARAM_CHUNK = 900

# sqlite3 connections cannot be shared across threads, and the thumbnail and
# canvas workers both read from the database, so each thread gets its own.
_local = threading.local()


def _get_connection():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH))
        _local.conn.execute("PRAGMA foreign_keys = ON;")
        # WAL lets background threads read while the UI thread writes.
        _local.conn.execute("PRAGMA journal_mode = WAL;")
    return _local.conn

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

        # Indexes covering the lookup paths used by the queries below.
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_filepath ON images(filepath);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_tags_image ON image_tags(image_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_image_tags_tag ON image_tags(tag_id);")

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


# Favourite folders live in the settings table as a single JSON value rather
# than in their own table: it is a short, ordered, single-user list, and JSON
# keeps each name paired with its path without needing a schema migration.
FAVOURITES_KEY = "favourite_folders"


def get_favourite_folders() -> list[dict]:
    """Returns the saved folder shortcuts as {"name", "path"} dicts, in order."""
    raw = get_setting(FAVOURITES_KEY)
    if not raw:
        return []

    try:
        stored = json.loads(raw)
    except json.JSONDecodeError:
        # A value corrupted by a partial write or hand-editing shouldn't stop
        # the app from starting; an empty list just means no shortcuts.
        return []

    if not isinstance(stored, list):
        return []

    return [
        {"name": str(entry["name"]), "path": str(entry["path"])}
        for entry in stored
        if isinstance(entry, dict) and entry.get("name") and entry.get("path")
    ]


def save_favourite_folders(favourites: list[dict]):
    """Replaces the stored shortcuts with `favourites`, order included."""
    save_setting(FAVOURITES_KEY, json.dumps(favourites))


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
    """Deletes a tag globally. Foreign key cascades unassign it from every image."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM tags WHERE name = ?", (tag_name,))
        conn.commit()


def rename_tag(old_name: str, new_name: str):
    """Renames a tag, merging into the target if that name is already taken.

    Merging rather than failing keeps the UNIQUE constraint on tags.name from
    rejecting a rename onto an existing tag.
    """
    with _get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM tags WHERE name = ?", (new_name,))
        existing = cursor.fetchone()

        if existing:
            new_id = existing[0]
            cursor.execute("SELECT id FROM tags WHERE name = ?", (old_name,))
            old_id_row = cursor.fetchone()

            if old_id_row:
                old_id = old_id_row[0]
                # Move every assignment over, then drop the old tag. IGNORE
                # covers images that already carry both tags.
                cursor.execute(
                    "INSERT OR IGNORE INTO image_tags (image_id, tag_id) SELECT image_id, ? FROM image_tags WHERE tag_id = ?",
                    (new_id, old_id),
                )
                cursor.execute("DELETE FROM image_tags WHERE tag_id = ?", (old_id,))
                cursor.execute("DELETE FROM tags WHERE id = ?", (old_id,))
        else:
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
    """Returns every tag formatted as "name (count)" for display."""
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
        # Clean up orphaned image rows with no remaining tags
        conn.execute("""
            DELETE FROM images WHERE id NOT IN (
                SELECT DISTINCT image_id FROM image_tags
            )
        """)

def get_images_by_tags(tag_names: list[str], match_all: bool) -> list[str]:
    """Returns filepaths tagged with all of `tag_names`, or any of them.

    `match_all` selects between AND and OR semantics. No chunking here: the
    parameter count is bounded by how many tags the user can check, which stays
    far below SQL_PARAM_CHUNK.
    """
    if not tag_names:
        return []

    with _get_connection() as conn:
        placeholders = ", ".join("?" for _ in tag_names)
        # GROUP BY collapses the one-row-per-tag join back to one row per image,
        # which also deduplicates the OR case.
        query = f"""
            SELECT images.filepath FROM images
            JOIN image_tags ON images.id = image_tags.image_id
            JOIN tags ON tags.id = image_tags.tag_id
            WHERE tags.name IN ({placeholders})
            GROUP BY images.id
        """
        params: list = list(tag_names)

        if match_all:
            # An image matched every tag only if it contributed a row for each.
            query += " HAVING COUNT(DISTINCT tags.name) = ?"
            params.append(len(tag_names))

        query += " ORDER BY images.filepath ASC"

        cursor = conn.execute(query, params)
        return [row[0] for row in cursor.fetchall()]


def get_shared_tags(filepaths: list[str]) -> set[str]:
    """Returns only the tags assigned to *every* one of the given filepaths.

    This drives the +/- toggle state in the tag sidebar during multi-selection:
    a tag reads as assigned only when the whole selection carries it.
    """
    if not filepaths:
        return set()
    with _get_connection() as conn:
        file_to_tags = {fp: set() for fp in filepaths}

        for i in range(0, len(filepaths), SQL_PARAM_CHUNK):
            chunk = filepaths[i : i + SQL_PARAM_CHUNK]
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
    """Assigns one tag to many images in a single transaction."""
    if not filepaths:
        return
    with _get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_id = cursor.fetchone()[0]

        # Images are only registered once they are tagged, so insert any that
        # aren't in the table yet before resolving their ids.
        cursor.executemany(
            "INSERT OR IGNORE INTO images (filepath) VALUES (?)",
            [(fp,) for fp in filepaths],
        )

        image_ids = []
        for i in range(0, len(filepaths), SQL_PARAM_CHUNK):
            chunk = filepaths[i : i + SQL_PARAM_CHUNK]
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
    """Unassigns one tag from many images in a single transaction."""
    if not filepaths:
        return
    with _get_connection() as conn:
        cursor = conn.cursor()
        for i in range(0, len(filepaths), SQL_PARAM_CHUNK):
            chunk = filepaths[i : i + SQL_PARAM_CHUNK]
            placeholders = ", ".join("?" for _ in chunk)
            cursor.execute(
                f"""
                DELETE FROM image_tags 
                WHERE tag_id = (SELECT id FROM tags WHERE name = ?)
                  AND image_id IN (SELECT id FROM images WHERE filepath IN ({placeholders}))
            """,
                [tag_name] + chunk,
            )
        
        # Clean up orphaned image rows with no remaining tags
        conn.execute("""
            DELETE FROM images WHERE id NOT IN (
                SELECT DISTINCT image_id FROM image_tags
            )
        """)
        conn.commit()
        
