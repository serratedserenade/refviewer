# RefViewer: Architecture & Implementation Guide

RefViewer is a highly optimized desktop application built with Python and **PyQt6**. It connects a reactive frontend to an embedded **SQLite3** database and utilizes high-performance **Multithreading** for I/O and CPU-bound image processing. 

This guide breaks down exactly how the project is built, separated by its core files.

---

## 1. `config.py` (State & Styling)
This file acts as the configuration brain of the application. It handles Cross-Platform Pathing, Global CSS, and UI component definitions.

<details>
<summary><strong>Deep Dive: OS Paths & Style Dictionaries</strong></summary>

- **Natively Sandboxed Paths**: Operating systems have strict rules for application data. `config.py` uses `sys.platform` to check the OS environment dynamically:
  - **Windows (`win32`)**: Routes to `%APPDATA%` and `%LOCALAPPDATA%`.
  - **macOS (`darwin`)**: Routes to `~/Library/Application Support/` and `~/Library/Caches/`.
  - **Linux**: Respects the `XDG` base directory specification (`~/.config` and `~/.cache`).
- **Global Stylesheet Dictionary (`STYLES`)**: PyQt6 natively supports **QSS** (Qt Style Sheets). By keeping styling, button dimensions, and raw regular-expression strings in dictionaries (`TAG_ICONS`, `STYLES`), the UI components in `main_window.py` are purely logic-driven and clean.
</details>

---

## 2. `database.py` (The Backend)
SQLite is embedded directly into the application. It handles the Many-to-Many tagging schema and utilizes high-speed bulk transactions to process thousands of image changes simultaneously.

<details>
<summary><strong>Deep Dive: Schema, Merging, & Bulk Operations</strong></summary>

- **Foreign Key Cascades**: By passing `PRAGMA foreign_keys = ON;`, SQLite is configured to sever links in `image_tags` automatically whenever a generic tag is deleted.
- **Bulk Transactions**: Doing `INSERT` statements one-by-one for 5,000 files takes seconds. By utilizing `executemany` and chopping data into arrays of 900 (the SQLite variable limit), bulk-tagging highlighted images completes in $O(1)$ perceived time.
- **Intelligent Merging**: The `rename_tag` function doesn't just change text. If a user renames "Pencil" to "Traditional", and "Traditional" already exists, the database catches the collision. It assigns all "Pencil" image IDs to "Traditional", drops duplicates natively (`INSERT OR IGNORE`), and permanently drops the leftover tag.
</details>

---

## 3. Multithreading (`components/` & Canvas Loading)
Image decoding and scaling are highly CPU-intensive. If run on the main UI thread, the application freezes. We use PyQt's `QThread` to push calculations to the background.

<details>
<summary><strong>Deep Dive: Concurrency & Hardware Limits</strong></summary>

- **CanvasLoader (Asynchronous Painting)**: To prevent UI lag when clicking massive 8K canvases, `CanvasLoader` reads the bits from the disk in the background. It returns the raw `QImage` pointer to the UI only when it's structurally ready, providing a perfectly smooth, friction-free click experience. *(Note: We track the `active_image_path` to prevent race conditions if the user rapidly scrolls through 50 images).*
- **Preventing OS Choking**: Python's `ThreadPoolExecutor` maximizes parallel processing. Unchecked, thumbnail generation will consume 100% of a CPU, causing Discord or Spotify audio to glitch. We prevent this utilizing mathematical limits: $MaxWorkers = \text{Total CPU Cores} // 2$.
- **Bypassing Memory Limits**: Qt automatically aborts parsing images demanding > 256MB of RAM. Explicitly calling `setAllocationLimit(0)` removes this safety lock for large canvases.
</details>

---

## 4. `main_window.py` (The Orchestrator)
This file glues the UX, UI elements, and backend queues together using PyQt Slots and Signals. 

<details>
<summary><strong>Deep Dive: Virtualized Scrolling & Debouncing</strong></summary>

- **$O(1)$ Virtualized Scrolling**: A standard grid recalculates geometry sizes on every scroll frame (causing massive lag on >10,000 files). By pairing `setUniformItemSizes(True)` with explicit `item.setSizeHint()`, Qt locks the geometry in place and simply swaps the pixel buffers, making endless scrolling perfectly smooth.
- **Debounced SQL Filters**: The search bar triggers a `QTimer` waiting 300ms before filtering the list. This prevents the multithreading engine from starting/stopping needlessly on every individual keystroke.
- **Dynamic UX State Handling**: The timer auto-pauses when the user highlights multiple (`len > 1`) rows. When `Labels` are toggled off via the UI, the grid sizes dynamically shrink from `120x180` to `110x110` ensuring standard thumbnail squares remain perfectly centered without pushing the margins.
</details>

<details>
<summary><strong>Deep Dive: Modular UI Factories</strong></summary>

- Qt generates massive amounts of boilerplate code. The Tag UI utilizes a Factory Pattern (`_build_tag_row_widget`). 
- This loops through the database, spawns a `QWidget`, packs it with a standard label, rename (`✏️`), drop (`🗑️`), and math-evaluated toggle buttons (`+`/`-`), and embeds it recursively into the right sidebar list using `setItemWidget()`.
- The `+`/`-` assignment calculates intersect math: Only if a tag is shared among *every* selected canvas path will it display `−` (remove mode).
</details>