# ⚠️ MASSIVE WARNING ⚠️
**READ THIS BEFORE USING OR EXPECTING ANYTHING FROM THIS SOFTWARE:**

1. **This project is 100% vibe coded.** The architecture was manifested into existence.
2. **It is only tested on Linux on a single machine configuration.** It might work on Windows or macOS, but I make absolutely zero promises. 
3. **I will barely update this.** Do not expect active maintenance, feature requests, or bug fixes. Fork it if you want to change it.

---

# RefViewer

RefViewer is a fast, local desktop image viewer and reference gallery tool built with PyQt6 and SQLite. It is designed to help artists, designers, or anyone who needs to seamlessly organize, tag, and view reference images across their filesystem.

## Features

- **Global Tagging System:** Quickly add, remove, and manage tags in a persistent SQLite database. Tags are linked to absolute file paths.
- **Cross-Folder Filtering:** Click a tag to instantly see all images associated with that tag, even if they live outside your currently selected folder (outlined in yellow).
- **Toggleable Gallery View:** Switch between a dense list view and an icon thumbnail grid.
- **Blazing Fast Thumbnails:** Multi-threaded thumbnail generation that runs in the background and caches to the disk so large directories load instantly.
- **Speed Drawing Timer:** A configurable countdown timer that loops and randomly selects a *new* image when it hits zero—perfect for gesture drawing or art practice. 

## Requirements

- Python 3.10+ (Recommended)
- `PyQt6`

## Installation & Setup

1. Clone or download this repository.
2. Install the required dependencies:
   ```bash
   pip install PyQt6
   ```
3. Run the application:
   ```bash
   python main.py
   ```

## Where is my data saved?

RefViewer stores its configuration, database, and thumbnail cache locally in your user directories:
- **Database:** `~/.config/refviewer/data.db`
- **Thumbnail Cache:** `~/.cache/refviewer/.thumbnail_cache/`

## Project Structure

```text
refviewer/
 ┣ components/
 ┃ ┣ __init__.py
 ┃ ┣ image_viewer.py        # Central canvas rendering
 ┃ ┗ thumbnail_loader.py    # Multi-threaded cache/loading logic
 ┣ config.py                # UI Styling and filepath constants
 ┣ database.py              # SQLite3 data management
 ┣ file_scanner.py          # OS walking and file discovery
 ┣ main_window.py           # Core GUI logic and signals
 ┗ main.py                  # Entry point
```

## License

Do whatever you want with this codebase.
