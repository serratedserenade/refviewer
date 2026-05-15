# RefViewer: Architecture & Implementation Guide

RefViewer is a desktop application built with **Python**, **PyQt6**, and **SQLite3**. It is designed for artists and designers who need to organize, tag, and rapidly browse large collections of reference images across their filesystem.

This document is a complete technical breakdown of every file, pattern, and design decision in the codebase. It assumes familiarity with Python but explains all Qt and database concepts from scratch.

---

## Table of Contents

1. [How PyQt6 Works (Crash Course)](#1-how-pyqt6-works-crash-course)
2. [`config.py` — Cross-Platform Paths & Global Styling](#2-configpy--cross-platform-paths--global-styling)
3. [`database.py` — SQLite3 Backend & Tag Schema](#3-databasepy--sqlite3-backend--tag-schema)
4. [`file_scanner.py` — Filesystem Walking](#4-file_scannerpy--filesystem-walking)
5. [`components/image_viewer.py` — Canvas Rendering & Background Loading](#5-componentsimage_viewerpy--canvas-rendering--background-loading)
6. [`components/thumbnail_loader.py` — Multithreaded Thumbnail Generation](#6-componentsthumbnail_loaderpy--multithreaded-thumbnail-generation)
7. [`main_window.py` — The Orchestrator](#7-main_windowpy--the-orchestrator)
8. [`main.py` — Application Entry Point](#8-mainpy--application-entry-point)
9. [Data Flow Diagrams](#9-data-flow-diagrams)
10. [Known Limitations & Edge Cases](#10-known-limitations--edge-cases)

---

## 1. How PyQt6 Works (Crash Course)

PyQt6 is a Python binding for the **Qt6** C++ GUI framework. Before diving into the code, here are the critical concepts used throughout this project:

### The Main Thread (aka the "UI Thread")
Qt applications run on a single **event loop**. This loop listens for user input (clicks, keypresses, window resizes) and repaints the screen. **Everything that touches a widget must happen on this thread.** If you run a slow operation here (like decoding a 50MB image), the entire window freezes until it finishes.

### Signals & Slots
Qt's communication system. A **Signal** is an event emitter (e.g., "button was clicked"). A **Slot** is a function that reacts to it. You connect them like wires:

```python
button.clicked.connect(self.do_something)  # clicked = Signal, do_something = Slot
```

Signals can carry data payloads. For example, `ThumbnailLoader` defines:

```python
thumbnail_ready = pyqtSignal(int, str, QImage, bool)
```

This means: "When I emit this signal, I will send an `int`, a `str`, a `QImage`, and a `bool` along with it." The receiving slot must accept those exact types.

### QThread
A wrapper around OS-level threads. You subclass `QThread`, override the `run()` method, and call `.start()`. The `run()` method executes on a **background thread**, but any signals it emits are safely delivered back to the main UI thread by Qt's event loop. This is how RefViewer decodes images without freezing.

### QSS (Qt Style Sheets)
Qt supports a CSS-like language called **QSS** for styling widgets. RefViewer stores all QSS strings in `config.py`'s `STYLES` dictionary so that `main_window.py` only contains logic, not visual formatting.

### QListWidget & Item Widgets
`QListWidget` is a scrollable list that holds `QListWidgetItem` entries. Each item can display:
- **Text** (`item.setText("hello")`)
- **Icons** (`item.setIcon(QIcon(pixmap))`)
- **Embedded Widgets** (`list.setItemWidget(item, custom_widget)`)

RefViewer uses all three modes depending on context.

### ItemDataRole.UserRole
Every `QListWidgetItem` has hidden data slots. `UserRole` is a general-purpose slot where you can store anything (a filepath, an ID, a tag name) invisibly behind the visible text. This is how RefViewer tracks which file or tag an item represents without parsing display strings.

---

## 2. `config.py` — Cross-Platform Paths & Global Styling

### Purpose
Centralizes two concerns: **where to store data on disk** and **how the UI looks**. No other file in the project makes OS-level path decisions or contains styling strings.

### Cross-Platform Path Resolution

```
_get_system_paths() → (config_dir: Path, cache_dir: Path)
```

Operating systems mandate specific directories for application data:

| OS      | Config Directory                          | Cache Directory                          |
|---------|-------------------------------------------|------------------------------------------|
| Windows | `%APPDATA%` → `C:\Users\X\AppData\Roaming` | `%LOCALAPPDATA%` → `C:\Users\X\AppData\Local` |
| macOS   | `~/Library/Application Support/`          | `~/Library/Caches/`                      |
| Linux   | `$XDG_CONFIG_HOME` → `~/.config/`        | `$XDG_CACHE_HOME` → `~/.cache/`         |

The function checks `sys.platform` and resolves the correct base paths, then appends `/refviewer/` to create the app-specific directories. Two global constants are exported:

- **`DB_PATH`**: Points to `<config_dir>/refviewer/data.db` (the SQLite database file).
- **`CACHE_DIR`**: Points to `<cache_dir>/refviewer/thumbnails/` (where generated thumbnail PNGs are stored).

### Global Stylesheet Dictionary

The `STYLES` dictionary maps human-readable keys to QSS strings:

```python
STYLES["sidebar"]  → "background-color: #2c3e50;"
STYLES["button"]   → "QPushButton { background-color: white; ... }"
STYLES["bubble"]   → "QLabel { background-color: #2980b9; border-radius: 10px; ... }"
```

Every widget in the project references styles via `widget.setStyleSheet(STYLES["key"])`. This means you can globally restyle the entire application by editing a single dictionary.

### Tag UI Constants

| Constant         | Value                  | Purpose                                                 |
|------------------|------------------------|---------------------------------------------------------|
| `TAG_ICONS`      | `{"rename": "✏️", ...}` | Unicode characters used as button labels                |
| `TAG_BTN_SIZE`   | `20`                   | Fixed pixel dimensions for tag action buttons           |
| `TAG_PARSE_REGEX`| `r"^(.*)\s\(\d+\)$"`  | Regex to strip `" (count)"` suffix from tag display text |

---

## 3. `database.py` — SQLite3 Backend & Tag Schema

### Purpose
Manages all persistent data: folder paths, image-tag associations, and user settings. SQLite is an embedded database engine — it runs inside your process and stores everything in a single `.db` file on disk. No server required.

### Schema Design

The database uses four tables in a **Many-to-Many** relational design:

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│   images     │       │   image_tags     │       │    tags      │
├──────────────┤       ├──────────────────┤       ├──────────────┤
│ id (PK)      │──┐    │ image_id (FK)    │    ┌──│ id (PK)      │
│ filepath     │  └───>│ tag_id   (FK)    │<───┘  │ name         │
└──────────────┘       └──────────────────┘       └──────────────┘

┌──────────────┐
│  settings    │
├──────────────┤
│ key (PK)     │
│ value        │
└──────────────┘
```

**Why Many-to-Many?** A single image can have multiple tags ("portrait", "lighting", "warm"). A single tag can apply to thousands of images. The `image_tags` junction table stores these links as `(image_id, tag_id)` pairs.

### Foreign Key Cascades

```python
conn.execute("PRAGMA foreign_keys = ON;")
```

This critical line activates SQLite's **referential integrity enforcement**. Combined with:

```sql
FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
```

...this means: if you delete a tag from the `tags` table, SQLite **automatically** deletes every row in `image_tags` that referenced it. Without this, you'd have orphaned junction rows pointing to deleted tags, corrupting query results over time.

### Connection Management

Every function calls `_get_connection()` independently and wraps operations in `with _get_connection() as conn:`. Python's `with` statement ensures that:
1. If the code succeeds, `conn.commit()` is called automatically.
2. If an exception is raised, `conn.rollback()` is called automatically.
3. The connection is closed when the block exits.

This prevents database corruption from partial writes.

### Key Operations

#### Adding a Tag to an Image (`add_tag_to_image`)
```
1. INSERT OR IGNORE the filepath into `images` (creates the row if it doesn't exist)
2. SELECT the image's ID
3. INSERT OR IGNORE the tag name into `tags` (creates the row if it doesn't exist)
4. SELECT the tag's ID
5. INSERT OR IGNORE the (image_id, tag_id) pair into `image_tags`
```
The `OR IGNORE` clauses make every step **idempotent** — calling it twice with the same data does nothing harmful.

#### Intelligent Tag Merging (`rename_tag`)
Renaming "Pencil" → "Traditional" is simple *unless* "Traditional" already exists. If it does, the function:
1. Finds the IDs for both the old and new tag.
2. Reassigns all `image_tags` rows from the old tag ID to the new tag ID (using `INSERT OR IGNORE` to silently drop duplicates).
3. Deletes the old tag's remaining `image_tags` entries and the old `tags` row itself.

This cleanly merges two tags without data loss.

#### Bulk Operations (`bulk_add_tag_to_images` / `bulk_remove_tag_from_images`)

SQLite imposes a hard limit of **999 bound parameters** per query. If you try to write:

```sql
SELECT id FROM images WHERE filepath IN (?, ?, ?, ... 5000 times ...)
```

...SQLite will throw an error. The bulk functions solve this by **chunking** the filepath list into slices of 900:

```python
chunk_size = 900
for i in range(0, len(filepaths), chunk_size):
    chunk = filepaths[i : i + chunk_size]
    placeholders = ", ".join("?" for _ in chunk)
    cursor.execute(f"SELECT id FROM images WHERE filepath IN ({placeholders})", chunk)
```

Additionally, `cursor.executemany()` batches thousands of `INSERT` statements into a single transaction, which is orders of magnitude faster than individual commits:

| Method                    | 5,000 images | Perceived Time |
|---------------------------|-------------|----------------|
| Individual `INSERT` loops | ~4-8 seconds | Visible freeze |
| `executemany` + chunking  | ~50-100ms    | Instant        |

#### Shared Tag Calculation (`get_shared_tags`)
When the user selects 50 images, the UI needs to know which tags are shared by **all** of them to correctly display the `+`/`−` toggle buttons. The function:

1. Queries all tags for all selected filepaths (chunked to respect the 900-parameter limit).
2. Builds a `dict[filepath → set[tag_name]]`.
3. Computes the **set intersection** across all entries: $\text{shared} = T_1 \cap T_2 \cap T_3 \cap \ldots \cap T_n$.
4. If any image has zero tags, the intersection collapses to $\emptyset$ immediately (short-circuit optimization).

---

## 4. `file_scanner.py` — Filesystem Walking

### Purpose
Recursively discovers all image files under a given directory path.

### How It Works
```python
for root, _, files in os.walk(clean_path):
    for file in files:
        if file.lower().endswith(IMAGE_EXTENSIONS):
            file_list.append(os.path.join(root, file))
```

`os.walk()` is a Python generator that traverses a directory tree depth-first. For each directory it enters, it yields:
- `root`: The current directory path
- `dirs`: Subdirectory names (unused here, hence `_`)
- `files`: Filenames in the current directory

The function filters for files ending in standard image extensions (`.png`, `.jpg`, `.jpeg`, `.bmp`, `.gif`, `.webp`, `.tiff`, `.ico`) and returns absolute paths.

### Input Sanitization
```python
clean_path = path.strip().strip('"').strip("'")
```
Users may paste paths with trailing whitespace or surrounding quotes from their file manager. This strips those before validation.

---

## 5. `components/image_viewer.py` — Canvas Rendering & Background Loading

This file contains two classes that work together to display the main "canvas" image in the center of the application.

### `ScaledImageLabel` (QLabel Subclass)

#### Problem It Solves
A standard `QLabel` with a `QPixmap` has a critical limitation: the image is rendered at its **native resolution** and does not resize when the window is resized. If you load a 4000×3000 image into a 800×600 label, it overflows. If you pre-scale it, it looks blurry when the window is enlarged.

#### How It Solves It
`ScaledImageLabel` overrides Qt's `paintEvent()` — the method Qt calls every time the widget needs to be redrawn (on resize, on repaint, on window focus changes, etc.).

```python
def paintEvent(self, event):
    super().paintEvent(event)                          # 1. Paint the base label (placeholder text, etc.)
    if not self.pixmap_source or self.pixmap_source.isNull():
        return                                         # 2. No image loaded — nothing to paint

    painter = QPainter(self)                           # 3. Create a painter targeting this widget's surface
    scaled_size = self.pixmap_source.size()
    scaled_size.scale(self.size(), KeepAspectRatio)    # 4. Calculate the largest size that fits the widget
                                                       #    while preserving the original aspect ratio

    x = (self.width() - scaled_size.width()) // 2     # 5. Center horizontally
    y = (self.height() - scaled_size.height()) // 2   # 6. Center vertically

    scaled_pixmap = self.pixmap_source.scaled(         # 7. Scale the raw pixmap using bilinear filtering
        scaled_size, KeepAspectRatio, SmoothTransformation
    )
    painter.drawPixmap(x, y, scaled_pixmap)            # 8. Blit the scaled image to the widget surface
```

The key insight: **the original full-resolution pixmap is stored permanently** in `self.pixmap_source`. Every time the window is resized, `paintEvent` recalculates the scaling from scratch using the original. This means:
- Enlarging the window reveals more detail (up to native resolution).
- Shrinking the window doesn't lose data.
- The image is always centered and never stretches or distorts.

#### Size Policy
```python
self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
self.setMinimumSize(1, 1)
```
`Expanding` tells Qt's layout engine: "Give me as much space as possible." `setMinimumSize(1, 1)` prevents Qt from collapsing the widget to zero pixels when the window is very small.

### `CanvasLoader` (QThread Subclass)

#### Problem It Solves
Decoding a high-resolution image (e.g., a 8192×8192 PSD export or a 50MB TIFF scan) can take **hundreds of milliseconds to several seconds**. If this runs on the main thread, the UI freezes completely — no scrolling, no clicking, no response to the OS window manager.

#### How It Solves It
`CanvasLoader` pushes the entire decode operation to a background thread:

```
Main Thread                          Background Thread (CanvasLoader)
────────────                         ──────────────────────────────────
User clicks image item
  → Spawns CanvasLoader(path)
  → Calls .start()
  → UI remains responsive              → QImageReader opens file
  → User can scroll, click, etc.       → Reads EXIF orientation metadata
                                        → Decodes pixel data into QImage
                                        → Emits image_ready(path, QImage)
  → Signal arrives on main thread  ←──┘
  → on_canvas_image_ready() fires
  → Converts QImage → QPixmap
  → Calls image_viewer.set_image()
  → paintEvent renders it
```

#### EXIF Auto-Transform
```python
reader.setAutoTransform(True)
```
Photos from phones and cameras store orientation metadata in EXIF headers (e.g., "this image was taken with the phone rotated 90° clockwise"). Without `setAutoTransform`, the image loads sideways. This single line tells Qt to read the EXIF tag and rotate the pixel buffer automatically before returning it.

#### Allocation Limit Bypass
```python
reader.setAllocationLimit(0)
```
Qt 6 introduced a safety mechanism that **aborts image decoding** if the estimated memory requirement exceeds 256MB. For an 8K×8K RGBA image, the raw pixel buffer alone is:

$$\text{Memory} = 8192 \times 8192 \times 4 \text{ bytes} = 256 \text{ MB}$$

This hits the limit exactly, causing legitimate art files to fail to load. Setting the limit to `0` disables the check entirely. **Trade-off:** A maliciously crafted image (a "decompression bomb") could allocate arbitrary amounts of RAM.

#### Race Condition Prevention
In `main_window.py`, when the signal arrives:
```python
def on_canvas_image_ready(self, requested_path, img):
    if requested_path != self.active_image_path:
        return  # User already clicked a different image — discard this result
```

If the user rapidly clicks 5 images, 5 `CanvasLoader` threads will be running simultaneously. The first 4 will emit results for stale paths. By comparing `requested_path` against the current `active_image_path`, the application silently drops outdated results, ensuring only the most recently clicked image is displayed.

---

## 6. `components/thumbnail_loader.py` — Multithreaded Thumbnail Generation

### Purpose
Generates 100×100 pixel thumbnail previews for every image in the file list, using a persistent disk cache and parallel processing across multiple CPU cores.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    ThumbnailLoader (QThread)             │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │           ThreadPoolExecutor (N workers)          │  │
│  │                                                   │  │
│  │  Worker 1: process_image(row=0, "photo1.jpg")     │  │
│  │  Worker 2: process_image(row=1, "photo2.png")     │  │
│  │  Worker 3: process_image(row=2, "sketch.tiff")    │  │
│  │  ...                                              │  │
│  └───────────────────────────────────────────────────┘  │
│                          │                              │
│              ┌───────────┼───────────┐                  │
│              ▼           ▼           ▼                  │
│     thumbnail_ready  thumbnail_ready  thumbnail_ready   │
│         signal           signal          signal         │
└─────────┬───────────────┬──────────────┬────────────────┘
          │               │              │
          ▼               ▼              ▼
    Main UI Thread: on_thumbnail_ready() updates QListWidgetItem icons
```

### Why Two Layers of Threading?
`ThumbnailLoader` is itself a `QThread`, and inside it, it spawns a `ThreadPoolExecutor`. This is because:

1. **`QThread`** allows the loader to emit Qt signals back to the main thread safely. Raw Python threads cannot interact with Qt widgets.
2. **`ThreadPoolExecutor`** enables *parallel* image decoding across multiple CPU cores. A single `QThread` would decode images sequentially, which is too slow for folders with thousands of files.

### Worker Count Calculation
```python
safe_workers = max(1, (os.cpu_count() or 2) // 2)
```

| System CPU Cores | `os.cpu_count()` | Workers Spawned |
|-----------------|-------------------|-----------------|
| 2               | 2                 | 1               |
| 4               | 4                 | 2               |
| 8               | 8                 | 4               |
| 16              | 16                | 8               |
| Unknown/None    | fallback 2        | 1               |

Using half the available cores ensures the application doesn't starve the OS, the desktop environment, or other running programs (like Spotify or Discord) of CPU time.

### Thumbnail Caching Strategy

Each image file's **absolute path** is hashed to produce a unique cache filename:

```python
path_hash = hashlib.md5(file_path.encode("utf-8")).hexdigest()
cache_path = os.path.join(self.cache_dir, f"{path_hash}.png")
```

Example: `/home/user/art/sketch.png` → `a3f2b8c1d4e5...png`

**On subsequent runs**, the loader checks if the cached PNG exists. If it does, it loads the tiny cached file instead of re-decoding the original (which may be 20-50MB). This turns a multi-second decode into a sub-millisecond disk read.

**Known limitation:** The hash is based solely on the file path. If the user modifies the image content without renaming it, the stale cached thumbnail will be served. Incorporating the file's modification time (`os.path.getmtime()`) into the hash would fix this.

### Thumbnail Generation Pipeline (per image)

```
1. Hash the filepath → check if cache PNG exists
   ├── YES → Load cached PNG → emit signal → done
   └── NO  → Continue to step 2

2. Open QImageReader on the original file
3. Enable EXIF auto-rotation
4. Disable allocation limits (for massive source files)
5. Read the original image dimensions
6. Calculate scaled dimensions that fit within 100×100 while preserving aspect ratio
7. Tell the reader to decode at the scaled size directly (memory optimization —
   the full-resolution image is never held in RAM)
8. Decode the scaled QImage
9. Save the result to the cache directory as PNG
10. Emit thumbnail_ready signal with the QImage payload
```

### Scaled Reading Optimization (Step 6-7)
```python
size = reader.size()
if size.isValid():
    reader.setScaledSize(size.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio))
```

This is a critical performance optimization. Instead of:
- Decoding 8192×8192 pixels into RAM (~256MB)
- Then scaling down to 100×100 pixels

...the reader is instructed to decode **directly at the target size**. The JPEG and PNG decoders can skip decoding detail that would be thrown away, reducing both CPU time and memory usage dramatically.

### Graceful Shutdown
```python
def stop(self):
    self.is_running = False
```

When the user changes folders or toggles the view mode, `main_window.py` calls `self.thumb_loader.stop()` and `self.thumb_loader.wait()`. The `run()` loop checks `self.is_running` after each future completes and calls `executor.shutdown(wait=False, cancel_futures=True)` to abandon remaining work immediately. Without this, switching folders rapidly would queue up thousands of stale thumbnail jobs.

---

## 7. `main_window.py` — The Orchestrator

This is the largest file in the project. It constructs the entire GUI, wires up all signals and slots, and manages application state.

### Window Layout (Three-Panel Design)

```
┌──────────────────────────────────────────────────────────────────────┐
│                           MainWindow                                 │
│ ┌────────────────┐ ┌──────────────────────────┐ ┌──────────────────┐ │
│ │  Left Sidebar  │ │     Center Canvas        │ │  Right Sidebar   │ │
│ │  (300px fixed) │ │     (stretches)          │ │  (250px fixed)   │ │
│ │                │ │                          │ │                  │ │
│ │ Path Display   │ │  Timer Display (hidden)  │ │ Timer Controls   │ │
│ │ Browse Button  │ │                          │ │                  │ │
│ │ View Toggles   │ │  ┌──────────────────┐   │ │ Tag Input        │ │
│ │                │ │  │                  │   │ │ [Add] Button     │ │
│ │ ┌────────────┐ │ │  │  ScaledImage     │   │ │                  │ │
│ │ │            │ │ │  │  Label           │   │ │ ┌──────────────┐ │ │
│ │ │  File List │ │ │  │  (paintEvent     │   │ │ │  Tag List    │ │ │
│ │ │  Widget    │ │ │  │   rendering)     │   │ │ │  (custom     │ │ │
│ │ │            │ │ │  │                  │   │ │ │   row        │ │ │
│ │ │            │ │ │  └──────────────────┘   │ │ │   widgets)   │ │ │
│ │ └────────────┘ │ │                          │ │ │              │ │ │
│ │                │ │  [tag1] [tag2] [tag3]    │ │ └──────────────┘ │ │
│ │ Filter Input   │ │  (bubble container)      │ │                  │ │
│ │ Progress Bar   │ │                          │ │                  │ │
│ └────────────────┘ └──────────────────────────┘ └──────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### State Variables

| Variable              | Type             | Purpose                                                        |
|-----------------------|------------------|----------------------------------------------------------------|
| `active_image_path`   | `str \| None`    | Filepath of the currently displayed image                      |
| `scanned_files`       | `list[str]`      | All image paths found in the selected folder                   |
| `active_filter_tag`   | `str \| None`    | If set, the file list shows only images with this tag          |
| `is_icon_view`        | `bool`           | `True` = thumbnail grid, `False` = text path list             |
| `show_labels`         | `bool`           | Whether to display filepath text under thumbnails              |
| `thumb_loader`        | `ThumbnailLoader` | Reference to the running thumbnail thread (for cancellation)  |
| `time_left`           | `int`            | Seconds remaining on the countdown timer                       |
| `timer_interval`      | `int`            | Total seconds per cycle (saved to database)                    |

### The File List: Two Rendering Modes

#### Icon Mode (Thumbnail Grid)
```python
self.file_list_widget.setViewMode(QListWidget.ViewMode.IconMode)
self.file_list_widget.setIconSize(QSize(100, 100))
self.file_list_widget.setUniformItemSizes(True)  # ← Critical for performance
```

**`setUniformItemSizes(True)`** is the single most important performance optimization in the entire UI. Without it, Qt calls `sizeHint()` on every single item during every scroll frame to compute dynamic layout positioning. With 10,000 items, this creates catastrophic lag. Setting uniform sizes tells Qt: "Every item is the same size — calculate the layout geometry once and reuse it." This reduces scroll rendering from $O(N)$ to $O(1)$.

Grid sizes change dynamically based on `show_labels`:
- **Labels on:** `120×180` pixels per cell (extra vertical space for text)
- **Labels off:** `110×110` pixels per cell (tight square grid)

#### List Mode (Text Paths)
```python
self.file_list_widget.setViewMode(QListWidget.ViewMode.ListMode)
```
Each item displays its full filepath as text. Items from outside the current folder (visible during tag filtering) are colored **yellow** via `item.setForeground(QColor("yellow"))`.

### Tag Filtering Mechanism

When the user **clicks a tag** in the right sidebar:

```
on_tag_item_clicked(item)
  → Reads tag_name from item.data(UserRole)
  → Sets self.active_filter_tag = tag_name
  → Calls update_file_list()
      → Checks: is active_filter_tag set?
         ├── YES → display_files = database.get_images_by_tag(tag_name)
         │         (returns ALL images with this tag, across ALL folders)
         └── NO  → display_files = self.scanned_files
                    (returns only images in the currently browsed folder)
      → Applies path text filter on top
      → Rebuilds the QListWidget items
```

Images returned by the tag filter that are **not in the currently scanned folder** are considered "external" and are visually marked:
- In **List Mode**: yellow text color
- In **Icon Mode**: a yellow border is painted around the thumbnail:
  ```python
  painter = QPainter(pixmap)
  pen = QPen(QColor("yellow"))
  pen.setWidth(6)
  painter.setPen(pen)
  painter.drawRect(0, 0, pixmap.width(), pixmap.height())
  ```

### Debounced Path Filter

```python
self.path_filter_timer = QTimer(self)
self.path_filter_timer.setSingleShot(True)
self.path_filter_timer.timeout.connect(self.update_file_list)

self.path_filter_input.textChanged.connect(lambda: self.path_filter_timer.start(300))
```

Every keystroke in the filter input **restarts** a 300ms timer. The list only updates when the user **stops typing** for 300ms. Without this debouncing:

| Typing "landscape" | Without Debounce           | With Debounce              |
|--------------------|----------------------------|----------------------------|
| "l"                | Full rebuild + thread spawn | Timer starts (300ms)       |
| "la"               | Full rebuild + thread spawn | Timer restarts (300ms)     |
| "lan"              | Full rebuild + thread spawn | Timer restarts (300ms)     |
| ...9 keystrokes    | 9 full rebuilds             | 0 rebuilds                 |
| (user stops)       | —                           | 1 rebuild after 300ms      |

### Multi-Selection Tag Management

RefViewer supports `Shift+Click` and `Ctrl+Click` to select multiple images. The tag toggle buttons (`+`/`−`) in the right sidebar reflect the **intersection** of tags across all selected images:

- Tag appears on **all** selected images → shows `−` (red, remove mode)
- Tag is missing from **any** selected image → shows `+` (green, add mode)

The toggle action calls the appropriate bulk function:
```python
if tag_name in shared_tags:
    database.bulk_remove_tag_from_images(selected_paths, tag_name)
else:
    database.bulk_add_tag_to_images(selected_paths, tag_name)
```

### Tag Row Widget Factory

Each tag in the right sidebar is not a simple text item — it's a full custom widget with interactive buttons:

```
┌─────────────────────────────────────────────────────┐
│  portrait (5)          [✏️] [🗑️] [+]               │
│  ↑ label               ↑     ↑    ↑                │
│  (tag name + count)  rename delete toggle           │
└─────────────────────────────────────────────────────┘
```

The `_build_tag_row_widget()` factory method constructs this layout programmatically for each tag, using `_create_tag_button()` to stamp out consistently sized and styled buttons. This **Factory Pattern** prevents massive code duplication — without it, every tag would require ~30 lines of explicit Qt widget instantiation.

### Assigned Tag Bubbles

Below the main canvas, colored "bubble" labels show which tags are assigned to the currently active image:

```python
for tag in database.get_image_tags(self.active_image_path):
    bubble = QLabel(tag)
    bubble.setStyleSheet(STYLES["bubble"])  # Blue rounded pill shape
    self.bubble_layout.addWidget(bubble)
```

These are rebuilt from scratch every time the active image changes (`refresh_assigned_bubbles()`). Old bubbles are cleaned up by iterating the layout and calling `deleteLater()` on each widget to prevent memory leaks.

### Speed Drawing Timer

The timer system enables timed art practice sessions:

```
start_timer()
  → Reads seconds from input field
  → Saves value to database (persists across sessions)
  → Sets time_left = interval
  → Picks a random image immediately
  → Starts QTimer firing every 1000ms

update_timer() [called every second]
  → If multi-select is active: display "Paused" and skip
  → Decrement time_left
  → If time_left > 0: update display, return
  → If time_left == 0: reset to interval, pick new random image

pick_random_image()
  → Gets list count
  → Generates random index ≠ current index (avoids showing same image twice)
  → Sets the new row as current, triggering on_file_item_changed
```

The timer auto-pauses during multi-selection to prevent the random picker from overriding the user's deliberate selection.

---

## 8. `main.py` — Application Entry Point

```python
if __name__ == "__main__":
    database.init_database()       # 1. Ensure SQLite tables exist
    app = QApplication(sys.argv)   # 2. Create the Qt application instance
    window = MainWindow()          # 3. Construct the entire GUI
    window.show()                  # 4. Make the window visible
    sys.exit(app.exec())           # 5. Enter the event loop (blocks until window closes)
```

`app.exec()` starts Qt's event loop — this is a **blocking call** that processes all user input, timer events, and signal deliveries until the window is closed. `sys.exit()` ensures the process returns the correct exit code to the OS.

---

## 9. Data Flow Diagrams

### Image Selection Flow
```
User clicks thumbnail in file list
       │
       ▼
on_file_item_changed()
       │
       ├──→ self.active_image_path = filepath
       ├──→ refresh_assigned_bubbles()  →  database.get_image_tags()  →  render bubbles
       ├──→ Kill previous CanvasLoader if still running
       └──→ Spawn new CanvasLoader(filepath)
                    │
                    ▼  [Background Thread]
              QImageReader.read()
                    │
                    ▼
              image_ready signal
                    │
                    ▼  [Main Thread]
            on_canvas_image_ready()
                    │
                    ├── Path mismatch? → discard (race condition guard)
                    └── Path matches  → QPixmap.fromImage() → image_viewer.set_image() → paintEvent()
```

### Folder Change Flow
```
User clicks "Browse" → selects folder
       │
       ▼
select_folder()
       │
       ├──→ database.save_setting("last_folder", path)
       └──→ perform_scan(path)
                │
                ├──→ Clear all UI state
                ├──→ file_scanner.scan_directory()  →  os.walk()  →  self.scanned_files
                └──→ update_file_list()
                         │
                         ├──→ Stop running ThumbnailLoader
                         ├──→ Clear QListWidget
                         ├──→ Create QListWidgetItems for each file
                         └──→ Spawn new ThumbnailLoader
                                  │
                                  ▼  [Background Threads]
                              process_image() × N workers
                                  │
                                  ▼
                              thumbnail_ready signals
                                  │
                                  ▼  [Main Thread]
                              on_thumbnail_ready()  →  set icon on QListWidgetItem
```

---

## 10. Known Limitations & Edge Cases

| Issue | Description | Potential Fix |
|-------|-------------|---------------|
| **Stale thumbnail cache** | Editing an image without renaming it serves the old cached thumbnail | Include `os.path.getmtime()` in the cache hash |
| **Allocation limit disabled** | `setAllocationLimit(0)` removes Qt's memory safety check for image decoding | Set to a high but finite value (e.g., 1024 MB) |
| **Tag name collision with count format** | A tag named `"Character (2)"` would be misinterpreted by `TAG_PARSE_REGEX` | Store raw tag names in `UserRole` instead of parsing display strings (partially done) |
| **No database migrations** | Adding new columns to the schema requires manual intervention | Implement a version table and migration scripts |
| **Thread termination** | `canvas_loader.terminate()` is used for rapid clicks, which forcefully kills the thread and can leak resources | Use a cooperative cancellation flag like `ThumbnailLoader.stop()` |
| **Single-connection pattern** | Each function opens its own SQLite connection; under extreme concurrent access this could cause `database is locked` errors | Use a connection pool or a single long-lived connection with a mutex |

---

## Project Structure (Complete)

```
refviewer/
├── components/
│   ├── __init__.py              # Package marker (empty)
│   ├── image_viewer.py          # ScaledImageLabel + CanvasLoader
│   └── thumbnail_loader.py      # ThumbnailLoader (QThread + ThreadPoolExecutor)
├── config.py                    # OS paths, QSS styles, UI constants
├── database.py                  # SQLite3 schema, CRUD, bulk operations
├── file_scanner.py              # Recursive directory image discovery
├── main_window.py               # Complete GUI construction and event routing
├── main.py                      # Application entry point
└── mise.toml                    # Task runner configuration (dev, run, etc.)
```
