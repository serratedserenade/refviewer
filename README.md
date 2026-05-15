# ⚠️ MASSIVE WARNING ⚠️
**READ THIS BEFORE USING OR EXPECTING ANYTHING FROM THIS SOFTWARE:**

1. **This project is 100% vibe coded.** The architecture was manifested into existence.
2. **It is only tested on Linux on a single machine configuration.** It should theoretically work on Windows and macOS now due to cross-platform paths, but I make absolutely zero promises. 
3. **I will barely update this.** Do not expect active maintenance, feature requests, or bug fixes. Fork it if you want to change it.

---

# RefViewer

![alt text](2026-05-15_224203.png)

RefViewer is a fast (questionable, this is vibe coded after all), local desktop image viewer and reference gallery tool built with PyQt6 and SQLite. It is designed to help artists, designers, or anyone who needs to seamlessly organize, tag, and view reference images across their filesystem.

## Features

- **Global Tagging System:** Quickly add, remove, and manage tags using quick-toggle `+`/`-` buttons. Tags persist in an SQLite database and are linked to absolute file paths.
- **Cross-Folder Filtering:** Click a tag to instantly see all images associated with that tag, even if they live outside your currently selected folder (outlined in yellow).
- **Blazing Fast, Uncapped Rendering:** Multi-threaded background thumbnail generation. Image decoding allocation limits are completely disabled to support massive, high-res canvas files without crashing.
- **EXIF Aware:** Automatically reads EXIF metadata to ensure phone/camera photos aren't rotated sideways.
- **Speed Drawing Timer:** A configurable countdown timer that loops and randomly selects a *new* image when it hits zero—perfect for gesture drawing or art practice. 
- **Hot-Reloading:** Built-in `watchfiles` support for instant UI restarts on file save during development.

## Setup & Development (Using `uv` & `mise`)

This project uses modern Python tooling. You will need [uv](https://github.com/astral-sh/uv) and [mise](https://github.com/jdx/mise) installed on your system.

1. Clone or download this repository.
2. Install dependencies (creates `.venv` automatically):
   ```bash
   uv sync

    Use the built-in task runner to start the app:

    mise run dev

Available Tasks (mise.toml)

    mise run dev — Runs the application normally.
    mise run watch — Runs the app in Auto-Restart mode. Saving any .py file instantly reloads the app.
    mise run build — Compiles the app into a standalone cross-platform executable directory (using PyInstaller).
    mise run build:one — Compiles the app into a single standalone binary file.
    mise run clean — Wipes compiler cache, build artifacts, and virtual environments.

Where is my data saved?

RefViewer dynamically checks your Operating System and stores the SQLite database and Thumbnail Caches in secure, native app-data directories:

    Windows: C:\Users\<User>\AppData\Roaming\RefViewer\
    macOS: ~/Library/Application Support/RefViewer/
    Linux: ~/.config/RefViewer/

To clear out old sideways images or broken thumbnails, simply delete your OS thumbnails cache folder located in these directories.
Project Structure

refviewer/
 ┣ components/
 ┃ ┣ __init__.py
 ┃ ┣ image_viewer.py        # Central canvas rendering, handles EXIF & limits
 ┃ ┗ thumbnail_loader.py    # Multi-threaded concurrent cache generation
 ┣ config.py                # UI Styling and dynamic cross-platform paths
 ┣ database.py              # SQLite3 data management & tag schema
 ┣ file_scanner.py          # OS walking and file discovery
 ┣ main_window.py           # Core GUI layouts, signals, and routing
 ┣ main.py                  # Standard app entry point
 ┗ mise.toml                # Task runner commands (npm run style)

License

Do whatever you want with this codebase.