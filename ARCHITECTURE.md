# RefViewer: Architecture & Implementation Guide

RefViewer is a desktop application built exclusively with Python and **PyQt6**. It connects a reactive frontend to an embedded **SQLite3** database and utilizes high-performance **Multithreading** for I/O and CPU-bound image processing. 

This guide breaks down exactly how the project is built, separated by its core files.

---

## 1. `config.py` (State & Styling)
This file acts as the configuration brain of the application. It handles two major things: **Cross-Platform Pathing** and **Global CSS**.

### Natively Sandboxed Paths
Operating systems have strict rules on where apps should hiddenly store data. `config.py` uses `sys.platform` to check the OS environment dynamically:
- **Windows (`win32`)**: Routes to `%APPDATA%` and `%LOCALAPPDATA%`.
- **macOS (`darwin`)**: Routes to `~/Library/Application Support/` and `~/Library/Caches/`.
- **Linux**: Respects the `XDG` base directory specification (`~/.config` and `~/.cache`).

### Global Stylesheet Dictionary (`STYLES`)
PyQt6 natively supports **QSS** (Qt Style Sheets), which is nearly identical to CSS. By keeping all colors, borders, and margins in a global Python dictionary, we simulate a "Theme" file. When UI components are created in `main_window.py`, they simply call `.setStyleSheet(STYLES["button"])`, making the design instantly unified and easy to tweak.

---

## 2. `database.py` (The Backend)
SQLite is embedded directly into the application. We use the standard library `sqlite3`.

### Schema Design
The database utilizes a **Many-to-Many Relational Schema**:
1. `images`: Stores the absolute file path (Unique).
2. `tags`: Stores the text name of a tag (Unique).
3. `image_tags`: A junction table linking an `image_id` to a `tag_id`.

### Foreign Key Enforcement
By default, SQLite does *not* enforce Foreign Keys. We created a custom `_get_connection()` function to execute `PRAGMA foreign_keys = ON;` upon every connection. Because the junction table features `ON DELETE CASCADE`, removing a tag globally will safely and automatically sever the link in `image_tags` with zero orphaned data.

### Query Logic
To extract exactly what images possess a certain tag (used for our global filtering feature), we perform `JOIN` queries. We ask the database to match the user's string to the `tags` table, follow the ID to the `image_tags` table, and retrieve the corresponding paths from the `images` table.

---

## 3. `components/image_viewer.py` (Custom Canvas UI)
Standard PyQt `QLabel` widgets break the UI structure when you feed them massive images. To fix this, we created `ScaledImageLabel`.

### Overriding `paintEvent`
Instead of telling the label to resize to the image, we tell the label to *draw* the image onto whatever size the label currently is.
1. When the window resizes, it natively calls `paintEvent`.
2. The method mathematical calculates the scaled aspect ratio: $NewSize = OriginalSize \times (LabelSize / OriginalSize)$.
3. `QPainter` is used to literally paint the pixels into the center of the canvas dynamically.

---

## 4. `components/thumbnail_loader.py` (Multithreading core)
This is the most complex aspect of the backend. Image decoding and scaling are highly CPU-intensive. If run on the main UI thread, the application would freeze entirely for several seconds.

### The `QThread` and Signals
`ThumbnailLoader` inherits from `QThread`. Background threads are **not allowed** to interact with the UI directly (this causes instant crashes). Instead, PyQt uses an event-loop "Signal" (`pyqtSignal`). The background thread processes the data and "emits" a signal containing the row index and raw `QImage` data back to the Main Thread, which safely packages it into a UI `QIcon`.

### Preventing OS Choking (`ThreadPoolExecutor`)
The thread utilizes Python's concurrent futures to process images in parallel. To prevent the program from starving the host OS of resources (e.g., glitching Spotify/Discord audio), the worker limit is capped:
$MaxWorkers = \text{Total CPU Cores} / 2$
This ensures the thumbnail generator never uses more than 50% of the computer's compute threshold.

### Disk Caching & Limits
- **Hashing**: `hashlib.md5()` generates a unique string from the file path. E.g., `C:/image.png` becomes `2d4f...8a`. We check if `2d4f...8a.png` exists in the cache folder. If yes, it loads instantly.
- **Bypassing Memory Limits**: Qt auto-aborts parsing images larger than 256MB. We explicitly call `setAllocationLimit(0)` to disable this safety feature so large 8K canvases can load successfully.

---

## 5. `main_window.py` (The Orchestrator)
This file glues the UI components and backend data together.

### Layout Architecture
The UI is constructed using horizontal and vertical layouts (`QHBoxLayout`, `QVBoxLayout`).
- `_create_left_sidebar`: Contains the path inputs, view toggles, the main list widget, and the bottom `QProgressBar`.
- `_create_center_canvas`: Houses the timer label, the `ScaledImageLabel`, and a flex-box for bubble tags.
- `_create_right_sidebar`: Holds the `QTimer` setting inputs and the custom global tagging list.

### Advanced `QListWidget` Features
1. **IconMode vs ListMode**: The app natively supports toggling `self.file_list_widget` into a grid. By setting the `GridSize` and `ResizeMode.Adjust`, Qt natively reflows the thumbnails like a CSS flex-box.
2. **Custom Item Widgets**: In the right sidebar, standard list-text isn't enough. We use `setItemWidget()` to inject entirely custom nested layouts (a transparent label + a dynamic red/green push button) directly into the list rows.

### Asynchronous UI Updating
When the background generator emits a thumbnail, `on_thumbnail_ready` does three things:
1. Verifies the row index still points to the correct file path (in case the user swapped folders during load).
2. Ticks the `self.progress_bar` forward mathematically.
3. Paints a 6-pixel yellow border natively onto the icon if the database flags the file as an external cross-folder reference.

### The Timer Loop (`QTimer`)
We use `QTimer`, which executes on an asynchronous delay without blocking the UI.
When it hits $0$, it queries `self.file_list_widget.count()`. It uses Python's `random.randint` to pick a row index and guarantees it doesn't match the current iteration using a `while` loop. Calling `setCurrentRow()` natively triggers `on_file_item_changed`, entirely automating the image swap without writing duplicate load logic!