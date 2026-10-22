# CLAUDE.md — Guidelines for RefViewer

RefViewer is a fast, local desktop image viewer and reference gallery tool built with **PyQt6** and **SQLite**, designed for artists and designers to organize, tag, annotate, and view reference images.

---

## 🛠️ Toolchain & Commands

The project uses `mise` for environment/tool version management and `uv` for package management.

### Common Development Tasks
- **Start application**: `mise run dev` (runs `uv run main.py`)
- **Start with hot-reload**: `mise run watch` (monitors files via `watchfiles` and restarts UI)
- **Install dependencies**: `uv sync`
- **Lint / check code**: `uv run ruff check .`

### Build Tasks
- **Build single-file executable**: `mise run build:one`
- **Build standard executable**: `mise run build`
- **Platform-specific builds**:
  - Linux: `mise run build:plat:linux`
  - macOS: `mise run build:plat:mac`
  - Windows: `mise run build:plat:win`
- **Clean build artifacts & cache**: `mise run clean`

---

## 📂 Architecture & Key Components

```
refviewer/
├── main.py                     # Entry point; sets up SQLite and boots QApplication
├── main_window.py              # Central coordinator (MainWindow), tabs, hotkeys, timers
├── config.py                   # Platform paths, UI limits, themes, and configuration
├── database.py                 # Thread-safe SQLite database manager (tags, favourites)
├── file_scanner.py             # Recursively scans folders for supported image extensions
├── RefViewer.spec              # PyInstaller build specification
├── mise.toml                   # Mise task runner & tool configuration
├── pyproject.toml              # Project dependencies (PyQt6, watchfiles, PyInstaller)
└── components/
    ├── drawing_canvas.py       # Transparent overlay widget for pen annotations & undo/redo
    ├── favourites.py           # Saved folder shortcuts widget (DB-backed, context menu)
    ├── file_tree.py            # QFileSystemModel directory tree browser tab
    ├── thumbnail_loader.py     # Background multi-threaded thumbnail loader & cacher
    └── image_viewer.py         # Canvas widget rendering the active image with EXIF rotation
```

---

## ⚙️ Core Technical Rules & Conventions

### 1. Database & Persistence
- SQLite database is stored in OS-native config directories (`config.py`):
  - **Linux**: `~/.config/refviewer/data.db`
  - **macOS**: `~/Library/Application Support/refviewer/data.db`
  - **Windows**: `%APPDATA%\refviewer\data.db`
- Thumbnail cache lives in native cache directories (`~/.cache/refviewer/thumbnails/` on Linux).
- Database operations must be thread-safe (uses `threading.Lock` within `database.py`).
- Tags and favourite folders persist across sessions; History and Pen Annotations are ephemeral and session-only.

### 2. Supported Image Formats
- Only scan and display formats explicitly defined in `file_scanner.py`:
  - `.png`, `.jpg`, `.jpeg`, `.webp`
  - *(TIFF, GIF, BMP, and ICO have been deliberately removed)*.

### 3. Caps & Limits
- **History List**: Capped at **100** items (in-memory, oldest evicted).
- **Pen Drawing Undo/Redo**: Capped at **500** stroke actions (`drawing_canvas.py`). Clearing drawings wipes the undo stack.
- **Splitter Ratios**: Files tab defaults to a **25 / 75** split between Favourites and Directory Tree.

### 4. Zoom, Pan & Deletion
- **Zoom & Pan**: `DrawableImageLabel` supports mouse wheel zoom (centered at cursor) and pan (Left drag when pen disabled, Middle drag, or Right drag). Double-click or `Ctrl+0` resets view to fit.
- **File Deletion**: `Delete` triggers image file deletion with a warning confirmation dialog. `Shift+Delete` deletes immediately without prompt. Both remove disk files, clean up SQLite tags via `database.remove_images()`, clean history and thumbnail cache, and advance to the next image. Ignored in text fields.

### 5. Tagging & Filtering Logic
- Tags support two distinct filtering modes:
  - **Click filter**: Clicking a tag filters for that single tag and clears multi-select checkboxes.
  - **Combined checkboxes**: Checking boxes enables combined filtering with radio buttons:
    - `AND`: Image must contain all checked tags.
    - `OR`: Image contains at least one checked tag.
- Multi-image bulk tagging: `+`/`-` buttons indicate a tag only if assigned to *all* selected images.

### 5. UI & Styling
- Pure dark theme with high-contrast text and tooltips.
- The thumbnail grid does not render text filepaths directly; full paths must be revealed via high-contrast dark `QToolTip` popups.
- Fullscreen focus mode (`F` key) hides both the sidebars and the pen annotation toolbar.

### 6. Code Style & Documentation Integrity
- Keep comments concise and descriptive of current functionality.
- Do not introduce session-specific or planning-specific comments into source files.
- Preserve type hints and PyQt signal-slot architecture patterns.
