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
- **Pen Annotations:** Draw directly on top of the currently viewed image with a configurable pen color and size — great for pointing out proportions, lighting notes, or gesture lines. Fully non-destructive: annotations are never saved to the image file or database, and are automatically cleared the moment you switch images or close the app. Supports Undo/Redo (`Ctrl+Z` / `Ctrl+Shift+Z`).
- **Filepath Display:** The full path of the currently viewed image is shown above the tag chips, and the text is selectable for easy copying.
- **Speed Drawing Timer:** A configurable countdown timer that loops and randomly selects a *new* image when it hits zero—perfect for gesture drawing or art practice. 
- **Hot-Reloading:** Built-in `watchfiles` support for instant UI restarts on file save during development.

## Shortcuts

* F to toggle sidebars
* Space to toggle timer start and stop. Defaults to 60 seconds if you haven't set a value yet.
* R to randomly select another image
* Ctrl+Z / Ctrl+Shift+Z to undo/redo pen annotations (ignored while typing in a text field)

## Setup & Development (Using `uv` & `mise`)

This project uses modern Python tooling. You will need [uv](https://github.com/astral-sh/uv) and [mise](https://github.com/jdx/mise) installed on your system.

1. Clone or download this repository.
2. Activate Mise in Your Shell

    You must hook mise into your shell so it can dynamically swap tool versions when you change directories. Add the appropriate line to your shell configuration file (e.g., ~/.zshrc, ~/.bashrc): 
    ```bash
    # For Zsh
    echo 'eval "$(mise activate zsh)"' >> ~/.zshrc

    # For Bash
    echo 'eval "$(mise activate bash)"' >> ~/.bashrc

    # Trust the local configuration file
    mise trust

    # Install Python, uv, and any other tools defined in mise.toml
    mise install
3. Create Your Virtual Environment Using uv

    Once mise has successfully provisioned Python and uv, use uv to instantly create a virtual environment and lock down your Python packages. 
        bash

        # Create a .venv virtual environment using the mise-managed Python version
        uv venv

        # Activate the virtual environment
        source .venv/bin/activate  # macOS/Linux
        .venv\Scripts\activate     # Windows
4. Install dependencies (creates `.venv` automatically):
   ```bash
    uv sync
Use the built-in task runner to start the app:

    mise run dev

Use the following to see what you can do

    mise tasks

### Where is my data saved?

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
    ┃ ┣ drawing_canvas.py      # Non-destructive pen annotation overlay & toolbar
    ┃ ┗ thumbnail_loader.py    # Multi-threaded concurrent cache generation
    ┣ config.py                # UI Styling and dynamic cross-platform paths
    ┣ database.py              # SQLite3 data management & tag schema
    ┣ file_scanner.py          # OS walking and file discovery
    ┣ main_window.py           # Core GUI layouts, signals, and routing
    ┣ main.py                  # Standard app entry point
    ┗ mise.toml                # Task runner commands (npm run style)

# License

Do whatever you want with this codebase.