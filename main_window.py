import os
import re
import random
import hashlib
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QFileDialog,
    QListWidgetItem,
    QFrame,
    QApplication,
    QProgressBar,
    QInputDialog,
    QMessageBox,
    QSplitter,
    QAbstractItemView,
    QAbstractSpinBox,
    QTabWidget,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
)
from PyQt6.QtGui import (
    QPixmap,
    QPainter,
    QIntValidator,
    QColor,
    QIcon,
    QPen,
    QKeySequence,
    QShortcut,
    QImage,
    QImageReader,
)
from PyQt6.QtCore import Qt, QTimer, QSize, QEvent

from config import (
    STYLES,
    CACHE_DIR,
    TAG_ICONS,
    TAG_BTN_SIZE,
    TAG_PARSE_REGEX,
    TAG_FILTER_MODES,
    TAG_FILTER_MODE_AND,
    TAG_FILTER_MODE_TOOLTIPS,
    DEFAULT_TAG_FILTER_MODE,
    APP_TIMER_DEFAULT,
    THUMBNAIL_SIZE,
    THUMBNAIL_GRID_SIZE,
    THUMBNAIL_GRID_SIZE_LABELLED,
    LIST_ROW_SIZE,
    PATH_FILTER_DEBOUNCE_MS,
    HISTORY_ICON_SIZE,
    HISTORY_GRID_SIZE,
    HISTORY_MAX_ITEMS,
)
from file_scanner import scan_directory
from components.image_viewer import CanvasLoader
from components.drawing_canvas import DrawableImageLabel, DrawingToolbar
from components.thumbnail_loader import ThumbnailLoader
import database


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RefViewer")
        self.setMinimumSize(1200, 600)

        # --- State ---
        self.active_image_path = None
        # Every image found by the last folder scan, regardless of filtering.
        self.scanned_files = []
        # Two mutually exclusive ways to filter by tag: clicking a single tag
        # row, or ticking any number of checkboxes. Whichever is used last wins,
        # so only one of these is ever non-empty.
        self.active_filter_tag = None
        self.checked_tags: set[str] = set()
        self.tag_filter_mode = DEFAULT_TAG_FILTER_MODE
        # Live checkbox widgets by tag name, rebuilt with the tag list. Lets the
        # boxes be cleared without destroying the rows mid-click.
        self._tag_checkboxes: dict[str, QCheckBox] = {}
        self.is_icon_view = True
        self.show_labels = False
        self.thumb_loader = None
        # Incremented per list rebuild so results from superseded thumbnail
        # loaders can be recognised and discarded.
        self.thumb_generation = 0
        self.time_left = 0
        self.timer_interval = 0
        self.left_sidebar: QTabWidget = None
        self.right_sidebar: QFrame = None

        self._canvas_loaders = []
        self._setup_shortcuts()

        # See eventFilter(): the annotation shortcuts have to be caught
        # application-wide to survive Qt's shortcut-override mechanism.
        QApplication.instance().installEventFilter(self)

        self.path_filter_timer = QTimer(self)
        self.path_filter_timer.setSingleShot(True)
        self.path_filter_timer.timeout.connect(self.update_file_list)

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self._build_ui()
        self._setup_timer()

        # Deferred so the window paints before the folder scan blocks.
        QTimer.singleShot(0, self._deferred_startup)

    def _deferred_startup(self):
        """Restores the last folder and tag list once the window is visible."""
        self.load_saved_folder()
        self.refresh_global_tags()

    # ========================== UI SETUP ==========================

    def _build_ui(self):
        """Assembles the three panels into a user-resizable splitter."""
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(4)

        self.left_sidebar = self._create_left_sidebar()
        self.center_canvas = self._create_center_canvas()
        self.right_sidebar = self._create_right_sidebar()

        self.splitter.addWidget(self.left_sidebar)
        self.splitter.addWidget(self.center_canvas)
        self.splitter.addWidget(self.right_sidebar)

        # Proportional rather than fixed, so the canvas absorbs window resizes.
        self.splitter.setStretchFactor(0, 1)  # Left sidebar
        self.splitter.setStretchFactor(1, 7)  # Center canvas
        self.splitter.setStretchFactor(2, 1)  # Right sidebar

        # Floors low enough that the stretch factors still govern normal sizing.
        self.left_sidebar.setMinimumWidth(200)
        self.center_canvas.setMinimumWidth(400)
        self.right_sidebar.setMinimumWidth(200)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.splitter)

    def _create_left_sidebar(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setStyleSheet(STYLES["tab_widget"])
        # Without this, the tab-bar strip past the last tab is painted by the
        # native style (often white) instead of the stylesheet background.
        tabs.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        tabs.addTab(self._create_images_tab(), "Images")
        tabs.addTab(self._create_history_tab(), "History")

        return tabs

    def _create_images_tab(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setStyleSheet(STYLES["sidebar"])

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Selected folder
        self.path_display = QLineEdit()
        self.path_display.setPlaceholderText("No folder selected")
        self.path_display.setReadOnly(True)
        self.path_display.setStyleSheet(STYLES["input"])
        layout.addWidget(self.path_display)

        # View controls
        buttons_row = QVBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(5)

        btn_browse = QPushButton("Browse")
        btn_browse.setStyleSheet(STYLES["button"])
        btn_browse.clicked.connect(self.select_folder)

        btn_toggle = QPushButton("Paths/Thumbnails")
        btn_toggle.setStyleSheet(STYLES["button"])
        btn_toggle.clicked.connect(self.toggle_view_mode)

        btn_toggle_text = QPushButton("Paths on Thumbnails")
        btn_toggle_text.setStyleSheet(STYLES["button"])
        btn_toggle_text.clicked.connect(self.toggle_text_mode)

        buttons_row.addWidget(btn_browse)
        buttons_row.addWidget(btn_toggle)
        buttons_row.addWidget(btn_toggle_text)
        layout.addLayout(buttons_row)

        # Image list
        self.file_list_widget = QListWidget()
        self.file_list_widget.setStyleSheet(STYLES["list"])
        self.file_list_widget.currentItemChanged.connect(self.on_file_item_changed)

        self.file_list_widget.setDragEnabled(False)
        self.file_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.file_list_widget.setAcceptDrops(False)

        self.file_list_widget.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )
        self.file_list_widget.itemSelectionChanged.connect(self.on_selection_changed)

        layout.addWidget(self.file_list_widget)

        # Path filter, debounced so each keystroke doesn't rebuild the list
        self.path_filter_input = QLineEdit()
        self.path_filter_input.setPlaceholderText("Filter by path/filename...")
        self.path_filter_input.setStyleSheet(STYLES["input"])
        self.path_filter_input.textChanged.connect(
            lambda: self.path_filter_timer.start(PATH_FILTER_DEBOUNCE_MS)
        )
        layout.addWidget(self.path_filter_input)

        # Thumbnail generation progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #34495e; border-radius: 4px; background-color: #1a252f; }
            QProgressBar::chunk { background-color: #2980b9; border-radius: 3px; }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        return sidebar

    def _create_history_tab(self) -> QFrame:
        """Builds the History tab: a thumbnail grid of images viewed this session.

        The list is in-memory only, so it starts empty on every launch, and is
        capped at HISTORY_MAX_ITEMS entries.
        """
        history_tab = QFrame()
        history_tab.setStyleSheet(STYLES["sidebar"])

        layout = QVBoxLayout(history_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.history_list_widget = QListWidget()
        self.history_list_widget.setStyleSheet(STYLES["list"])
        self.history_list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.history_list_widget.setIconSize(QSize(HISTORY_ICON_SIZE, HISTORY_ICON_SIZE))
        self.history_list_widget.setGridSize(QSize(HISTORY_GRID_SIZE, HISTORY_GRID_SIZE))
        self.history_list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.history_list_widget.setUniformItemSizes(True)
        self.history_list_widget.setSpacing(5)

        self.history_list_widget.setDragEnabled(False)
        self.history_list_widget.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.history_list_widget.setAcceptDrops(False)
        self.history_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        # Deliberately a separate handler from on_file_item_changed, so browsing
        # History never appends to History.
        self.history_list_widget.currentItemChanged.connect(self.on_history_item_changed)

        layout.addWidget(self.history_list_widget)

        btn_clear_history = QPushButton("Clear History")
        btn_clear_history.setStyleSheet(STYLES["button"])
        btn_clear_history.clicked.connect(self.clear_history)
        layout.addWidget(btn_clear_history)

        return history_tab

    def _create_center_canvas(self) -> QFrame:
        content_area = QFrame()
        content_area.setStyleSheet(STYLES["content"])

        layout = QVBoxLayout(content_area)
        layout.setContentsMargins(15, 15, 15, 15)

        self.timer_display = QLabel("")
        self.timer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_display.setStyleSheet(
            "color: red; font-size: 14px; background-color: #000000; font-weight: bold;"
        )
        self.timer_display.hide()
        layout.addWidget(self.timer_display)

        self.drawing_toolbar = DrawingToolbar()
        self.drawing_toolbar.draw_toggled.connect(self._on_draw_toggled)
        self.drawing_toolbar.color_changed.connect(self._on_pen_color_changed)
        self.drawing_toolbar.size_changed.connect(self._on_pen_size_changed)
        self.drawing_toolbar.clear_requested.connect(self._on_clear_annotations)
        self.drawing_toolbar.undo_requested.connect(self._on_undo_annotation)
        self.drawing_toolbar.redo_requested.connect(self._on_redo_annotation)
        layout.addWidget(self.drawing_toolbar)

        self.image_viewer = DrawableImageLabel()
        self.image_viewer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_viewer.setText("Select a folder to begin...")
        self.image_viewer.setStyleSheet(STYLES["placeholder"])
        self.image_viewer.set_pen_color(self.drawing_toolbar.pen_color)
        self.image_viewer.set_pen_width(self.drawing_toolbar.size_spin.value())
        layout.addWidget(self.image_viewer)

        self.current_image_path_label = QLabel("")
        self.current_image_path_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.current_image_path_label.setStyleSheet(STYLES["current_path_label"])
        self.current_image_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.current_image_path_label.setWordWrap(True)
        layout.addWidget(self.current_image_path_label)

        self.bubble_container = QFrame()
        self.bubble_container.setStyleSheet("background: transparent;")
        self.bubble_layout = QHBoxLayout(self.bubble_container)
        self.bubble_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.bubble_container)

        layout.setStretch(0, 0)
        layout.setStretch(1, 0)
        layout.setStretch(2, 1)
        layout.setStretch(3, 0)
        layout.setStretch(4, 0)

        return content_area

    def _create_right_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setStyleSheet(STYLES["right_sidebar"])
        sidebar.setFixedWidth(250)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)

        # Timer Row
        layout.addWidget(self._create_styled_label("Countdown Timer (Secs):"))
        timer_row = QHBoxLayout()
        self.timer_input = QLineEdit()
        self.timer_input.setValidator(QIntValidator(1, 99999, self))
        self.timer_input.setStyleSheet(STYLES["input"])

        if saved_timer := database.get_setting("timer_seconds"):
            self.timer_input.setText(saved_timer)

        btn_go = QPushButton("Go")
        btn_go.setStyleSheet(STYLES["button"])
        btn_go.clicked.connect(self.start_timer)

        btn_stop = QPushButton("Stop")
        btn_stop.setStyleSheet(STYLES["button"])
        btn_stop.clicked.connect(self.stop_timer)

        timer_row.addWidget(self.timer_input)
        timer_row.addWidget(btn_go)
        timer_row.addWidget(btn_stop)
        layout.addLayout(timer_row)

        layout.addSpacing(10)

        # Tag Entry Row
        layout.addWidget(self._create_styled_label("Add New Tag to Selected Image:"))
        tag_row = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Enter tag name...")
        self.tag_input.setStyleSheet(STYLES["input"])
        self.tag_input.returnPressed.connect(self.add_tag)

        btn_add_tag = QPushButton("Add")
        btn_add_tag.setStyleSheet(STYLES["button"])
        btn_add_tag.clicked.connect(self.add_tag)

        tag_row.addWidget(self.tag_input)
        tag_row.addWidget(btn_add_tag)
        layout.addLayout(tag_row)

        # Tag List
        layout.addWidget(
            self._create_styled_label(
                "All Database Tags\n(Click to Filter, Tick to Combine):"
            )
        )
        layout.addLayout(self._create_tag_filter_mode_row())

        self.tag_list_widget = QListWidget()
        self.tag_list_widget.setStyleSheet(STYLES["list"])
        self.tag_list_widget.itemClicked.connect(self.on_tag_item_clicked)

        layout.addWidget(self.tag_list_widget)

        return sidebar

    def _create_tag_filter_mode_row(self) -> QHBoxLayout:
        """Builds the AND/OR radio row governing how checked tags combine."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 4)
        row.setSpacing(8)

        label = QLabel("Match:")
        label.setStyleSheet(STYLES["tag_row_label"])
        row.addWidget(label)

        # Grouped so the radios are mutually exclusive and report as one signal.
        self.tag_filter_mode_group = QButtonGroup(self)
        for mode in TAG_FILTER_MODES:
            radio = QRadioButton(mode)
            radio.setStyleSheet(STYLES["radio"])
            radio.setToolTip(TAG_FILTER_MODE_TOOLTIPS[mode])
            radio.setChecked(mode == self.tag_filter_mode)
            radio.toggled.connect(
                lambda checked, m=mode: self._on_tag_filter_mode_changed(m, checked)
            )
            self.tag_filter_mode_group.addButton(radio)
            row.addWidget(radio)

        row.addStretch()
        return row

    def _on_tag_filter_mode_changed(self, mode: str, checked: bool):
        # toggled fires for the radio being cleared as well as the one being set.
        if not checked:
            return

        self.tag_filter_mode = mode
        # Only changes the result set once more than one tag is checked.
        if len(self.checked_tags) > 1:
            self.update_file_list()

    def _create_styled_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(STYLES["label"])
        return lbl

    def _setup_timer(self):
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_timer)

    # ========================== FOLDER MANAGEMENT ==========================

    def load_saved_folder(self):
        if past_path := database.get_setting("last_folder"):
            self.path_display.setText(past_path)
            self.perform_scan(past_path)

    def select_folder(self):
        if folder_path := QFileDialog.getExistingDirectory(
            self, "Select Image Directory"
        ):
            self.path_display.setText(folder_path)
            database.save_setting("last_folder", folder_path)
            self.perform_scan(folder_path)

    def perform_scan(self, path):
        self.file_list_widget.clear()
        self.clear_bubbles()
        self.current_image_path_label.setText("")
        self.image_viewer.reset_image()
        self.active_image_path = None
        self.active_filter_tag = None
        self.tag_list_widget.clearSelection()

        self.image_viewer.setStyleSheet(STYLES["placeholder"])
        self.image_viewer.setText("Scanning...")
        QApplication.processEvents()

        try:
            self.scanned_files = scan_directory(path)
            if self.scanned_files:
                self.image_viewer.setText(f"Found {len(self.scanned_files)} images.")
            else:
                self.image_viewer.setText("No images found.")
        except ValueError as e:
            self.image_viewer.setText(str(e))
            self.scanned_files = []

        self.update_file_list()

    def toggle_view_mode(self):
        self.is_icon_view = not self.is_icon_view
        self.update_file_list()

    def toggle_text_mode(self):
        """Show or hide the filepaths underneath the images."""
        self.show_labels = not self.show_labels
        self.update_file_list()

    def update_file_list(self):
        """Rebuilds the image list from the current folder, tag filter and search."""
        if self.thumb_loader and self.thumb_loader.isRunning():
            self.thumb_loader.stop()
            self.thumb_loader.wait()

        self.progress_bar.hide()
        self.progress_bar.setValue(0)

        self.file_list_widget.clear()

        # Cells grow taller when filepath labels sit beneath each thumbnail.
        if self.show_labels:
            grid_size = QSize(*THUMBNAIL_GRID_SIZE_LABELLED)
            icon_align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
        else:
            grid_size = QSize(THUMBNAIL_GRID_SIZE, THUMBNAIL_GRID_SIZE)
            icon_align = Qt.AlignmentFlag.AlignCenter

        if self.is_icon_view:
            self.file_list_widget.setViewMode(QListWidget.ViewMode.IconMode)
            self.file_list_widget.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
            self.file_list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
            self.file_list_widget.setGridSize(grid_size)
            self.file_list_widget.setSpacing(5)
            self.file_list_widget.setWordWrap(True)
            self.file_list_widget.setUniformItemSizes(True)
        else:
            self.file_list_widget.setViewMode(QListWidget.ViewMode.ListMode)
            self.file_list_widget.setGridSize(QSize())
            self.file_list_widget.setSpacing(0)
            self.file_list_widget.setWordWrap(False)
            self.file_list_widget.setUniformItemSizes(True)

        # A tag filter draws from the whole database, so it can return images
        # from outside the scanned folder; otherwise use the scan directly.
        filter_tags = self._active_filter_tags()
        if filter_tags:
            display_files = database.get_images_by_tags(
                filter_tags, match_all=self.tag_filter_mode == TAG_FILTER_MODE_AND
            )
        else:
            display_files = self.scanned_files

        # Tagged paths are absolute and may since have been moved or deleted.
        display_files = [f for f in display_files if os.path.isfile(f)]

        filter_text = self.path_filter_input.text().strip().lower()
        if filter_text:
            display_files = [f for f in display_files if filter_text in f.lower()]

        items_for_worker = []
        for row, file_path in enumerate(display_files):
            # Anything outside the current scan is highlighted in yellow.
            is_external = file_path not in self.scanned_files

            # List mode is text-only, so it always shows the path; icon mode
            # defers to the label toggle.
            if not self.is_icon_view or self.show_labels:
                display_text = file_path
            else:
                display_text = ""

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            # Always the full path, since icon mode usually shows no text and
            # list mode elides long paths.
            item.setToolTip(file_path)

            if self.is_icon_view:
                item.setSizeHint(grid_size)
                item.setTextAlignment(icon_align)
            else:
                item.setSizeHint(QSize(*LIST_ROW_SIZE))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )

            if not self.is_icon_view and is_external:
                item.setForeground(QColor("yellow"))

            self.file_list_widget.addItem(item)

            # Only icon mode needs thumbnails generated.
            if self.is_icon_view:
                items_for_worker.append((row, file_path, is_external))

        if self.is_icon_view and items_for_worker:
            self.loaded_thumbnail_count = 0
            self.progress_bar.setMaximum(len(items_for_worker))
            self.progress_bar.setValue(0)
            self.progress_bar.show()

            self.thumb_generation += 1
            current_gen = self.thumb_generation
            self.thumb_loader = ThumbnailLoader(items_for_worker, str(CACHE_DIR))
            self.thumb_loader.thumbnail_ready.connect(
                lambda row, fp, img, ext, gen=current_gen: self.on_thumbnail_ready(
                    row, fp, img, ext, gen
                )
            )

            self.thumb_loader.finished.connect(self._on_thumbnail_loading_finished)
            self.thumb_loader.start()
        else:
            self.progress_bar.hide()

    def _on_thumbnail_loading_finished(self):
        """Hides the progress bar, ignoring signals from superseded loaders."""
        if self.sender() is self.thumb_loader:
            self.progress_bar.hide()

    def on_thumbnail_ready(self, row, file_path, img, is_external, generation):
        if generation != self.thumb_generation:
            return  # A loader from a previous list build.

        self.loaded_thumbnail_count += 1
        self.progress_bar.setValue(self.loaded_thumbnail_count)

        # The row may have been reused or removed since the load was queued.
        item = self.file_list_widget.item(row)
        if not item or item.data(Qt.ItemDataRole.UserRole) != file_path:
            return

        pixmap = QPixmap.fromImage(img)
        if is_external:
            # Outline images that live outside the scanned folder.
            painter = QPainter(pixmap)
            pen = QPen(QColor("yellow"))
            pen.setWidth(6)
            painter.setPen(pen)
            painter.drawRect(0, 0, pixmap.width(), pixmap.height())
            painter.end()
            item.setForeground(QColor("yellow"))

        item.setIcon(QIcon(pixmap))

    def on_file_item_changed(self, current, previous):
        if not current:
            return

        path = current.data(Qt.ItemDataRole.UserRole)
        self._activate_image_path(path)
        self._add_to_history(path, current.icon())

    def on_history_item_changed(self, current, previous):
        """Displays a history entry without recording it as a new visit."""
        if not current:
            return

        path = current.data(Qt.ItemDataRole.UserRole)
        self._activate_image_path(path)

    def _activate_image_path(self, path):
        """Makes `path` the displayed image and starts decoding it.

        Shared by the Images and History lists.
        """
        self.active_image_path = path
        self.refresh_assigned_bubbles()

        # Supersede any in-flight decode; cancelled loaders drop their result.
        for loader in self._canvas_loaders:
            loader.cancel()

        self._canvas_loaders = [
            loader for loader in self._canvas_loaders if loader.isRunning()
        ]

        # Held in a list because a QThread that goes out of scope is destroyed
        # while still running.
        loader = CanvasLoader(self.active_image_path, parent=None)
        loader.image_ready.connect(self.on_canvas_image_ready)
        loader.finished.connect(lambda finished=loader: self._cleanup_loader(finished))
        loader.start()
        self._canvas_loaders.append(loader)

    def _cleanup_loader(self, loader):
        """Drops the reference to a finished loader so it can be collected."""
        if loader in self._canvas_loaders:
            self._canvas_loaders.remove(loader)

    # ========================== SESSION HISTORY ==========================
    # In-memory only: nothing here reaches the database or disk, so the History
    # tab starts empty on every launch.

    def _add_to_history(self, path, icon: QIcon):
        """Records `path` as the most recent view, trimming the oldest entries."""
        if not path:
            return

        # Repeatedly clicking one image shouldn't stack duplicate entries.
        top_item = self.history_list_widget.item(0)
        if top_item and top_item.data(Qt.ItemDataRole.UserRole) == path:
            return

        if icon.isNull():
            icon = self._make_thumbnail_icon(path)

        item = QListWidgetItem(icon, "")
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setToolTip(path)

        # Signals stay blocked so inserting and trimming never re-enters
        # on_history_item_changed and displays the wrong image.
        self.history_list_widget.blockSignals(True)
        # Newest first, so the oldest entries are the ones at the end.
        self.history_list_widget.insertItem(0, item)
        while self.history_list_widget.count() > HISTORY_MAX_ITEMS:
            self.history_list_widget.takeItem(self.history_list_widget.count() - 1)
        self.history_list_widget.blockSignals(False)

    def _make_thumbnail_icon(self, file_path) -> QIcon:
        """Builds a thumbnail for a history entry that has no icon yet.

        Needed because an image can be viewed before the Images list has
        finished generating its thumbnail. Shares ThumbnailLoader's on-disk
        cache, so the work is not repeated later.
        """
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            return QIcon()

        path_hash = hashlib.md5(f"{file_path}:{mtime}".encode("utf-8")).hexdigest()
        cache_path = os.path.join(CACHE_DIR, f"{path_hash}.png")

        img = QImage()
        if os.path.exists(cache_path):
            img.load(cache_path)
        else:
            reader = QImageReader(file_path)
            reader.setAutoTransform(True)
            reader.setAllocationLimit(0)
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(
                    size.scaled(
                        HISTORY_ICON_SIZE,
                        HISTORY_ICON_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatio,
                    )
                )
            img = reader.read()
            if not img.isNull():
                os.makedirs(CACHE_DIR, exist_ok=True)
                img.save(cache_path, "PNG")

        if img.isNull():
            return QIcon()
        return QIcon(QPixmap.fromImage(img))

    def clear_history(self):
        self.history_list_widget.clear()

    def on_canvas_image_ready(self, requested_path, img):
        # Discard results for an image the user has already navigated away from.
        if requested_path != self.active_image_path:
            return

        if img.isNull():
            self.image_viewer.setText("Failed to load image file.")
            self.image_viewer.setStyleSheet(STYLES["error"])
            self.image_viewer.reset_image()
            self.clear_bubbles()
        else:
            pixmap = QPixmap.fromImage(img)
            self.image_viewer.setStyleSheet("")
            self.image_viewer.set_image(pixmap)

    def get_selected_paths(self):
        """Returns a list of all currently selected image filepaths."""
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.file_list_widget.selectedItems()
        ]

    def on_selection_changed(self):
        """Recomputes tag assignment state, which depends on the whole selection."""
        self.refresh_global_tags()

    # ========================== ANNOTATIONS ==========================
    # Thin forwarding layer between the toolbar's signals and the canvas.
    # See components/drawing_canvas.py for the annotation model itself.

    def _on_draw_toggled(self, enabled):
        self.image_viewer.set_drawing_enabled(enabled)

    def _on_pen_color_changed(self, color):
        self.image_viewer.set_pen_color(color)

    def _on_pen_size_changed(self, size):
        self.image_viewer.set_pen_width(size)

    def _on_clear_annotations(self):
        self.image_viewer.clear_annotations()

    def _on_undo_annotation(self):
        self.image_viewer.undo_last_stroke()

    def _on_redo_annotation(self):
        self.image_viewer.redo_last_stroke()

    # ========================== TAG MANAGEMENT ==========================

    def add_tag(self):
        tag_text = self.tag_input.text().strip()
        selected_paths = self.get_selected_paths()

        if not tag_text or not selected_paths:
            self.tag_input.clear()
            return

        database.bulk_add_tag_to_images(selected_paths, tag_text)

        self.tag_input.clear()
        self.refresh_global_tags()
        self.refresh_assigned_bubbles()

    def action_rename_tag(self, old_name):
        """Prompts for a new tag name, then updates the database and UI."""
        new_name, ok = QInputDialog.getText(
            self, "Rename Tag", f"Rename '{old_name}' to:"
        )

        if ok and new_name.strip():
            clean_name = new_name.strip()
            database.rename_tag(old_name, clean_name)

            # Follow the rename, or the active filter would point at a dead tag.
            if self.active_filter_tag == old_name:
                self.active_filter_tag = clean_name

            # Discard rather than rename: the target may already be checked, and
            # renaming can merge two tags into one.
            if old_name in self.checked_tags:
                self.checked_tags.discard(old_name)
                self.checked_tags.add(clean_name)

            self.refresh_global_tags()
            self.refresh_assigned_bubbles()
            self.update_file_list()

    def action_delete_tag(self, tag_name):
        """Confirms, then deletes a tag from every image in the database."""
        reply = QMessageBox.question(
            self,
            "Delete Tag",
            f"Are you sure you want to permanently delete the tag '{tag_name}'?\nThis will remove it from all images.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            database.delete_tag(tag_name)

            # Drop the filter, or the list would keep showing a deleted tag.
            if self.active_filter_tag == tag_name:
                self.active_filter_tag = None
            self.checked_tags.discard(tag_name)

            self.refresh_global_tags()
            self.refresh_assigned_bubbles()
            self.update_file_list()

    def toggle_specific_tag(self, tag_name):
        """Adds the tag to the whole selection, or removes it if all already have it."""
        selected_paths = self.get_selected_paths()
        if not selected_paths:
            return

        shared_tags = database.get_shared_tags(selected_paths)

        if tag_name in shared_tags:
            database.bulk_remove_tag_from_images(selected_paths, tag_name)
        else:
            database.bulk_add_tag_to_images(selected_paths, tag_name)

        self.refresh_global_tags()
        self.refresh_assigned_bubbles()

        # Only matters while filtering, where the change can add or drop rows.
        if self.active_filter_tag:
            self.update_file_list()

    def on_tag_item_clicked(self, item):
        """Filters by the clicked tag alone, or clears the filter if re-clicked.

        A click always abandons the checkbox filter, so the two never combine.
        """
        tag_name = item.data(Qt.ItemDataRole.UserRole)

        self._clear_tag_checkboxes()

        if self.active_filter_tag == tag_name:
            self.active_filter_tag = None
            self.tag_list_widget.clearSelection()
        else:
            self.active_filter_tag = tag_name

        self.update_file_list()

    def _on_tag_check_toggled(self, tag_name: str, checked: bool):
        """Adds or drops a tag from the combined filter."""
        if checked:
            self.checked_tags.add(tag_name)
        else:
            self.checked_tags.discard(tag_name)

        # Ticking a box takes over from the single-tag click filter, so drop it
        # along with its highlight.
        if self.active_filter_tag is not None:
            self.active_filter_tag = None
            self.tag_list_widget.clearSelection()

        self.update_file_list()

    def _clear_tag_checkboxes(self):
        """Unticks every checkbox without rebuilding the rows.

        Called from the item-click handler, so the widgets have to survive: a
        rebuild here would delete the row being clicked mid-event.
        """
        if not self.checked_tags:
            return

        self.checked_tags.clear()
        for checkbox in self._tag_checkboxes.values():
            # Blocked so this doesn't re-enter _on_tag_check_toggled once per box.
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)

    def _active_filter_tags(self) -> list[str]:
        """Returns the tags currently filtering the list, in either mode."""
        if self.checked_tags:
            return sorted(self.checked_tags)
        if self.active_filter_tag:
            return [self.active_filter_tag]
        return []

    def _parse_tag_name(self, formatted_text: str) -> str:
        """Recovers the bare tag name from a display string like "portrait (5)"."""
        match = re.match(TAG_PARSE_REGEX, formatted_text)
        return match.group(1).strip() if match else formatted_text.strip()

    def _create_tag_button(
        self, icon_str: str, style_key: str, callback
    ) -> QPushButton:
        """Factory method to generate standardized tag management buttons."""
        btn = QPushButton(icon_str)
        btn.setFixedSize(TAG_BTN_SIZE, TAG_BTN_SIZE)
        btn.setStyleSheet(STYLES[style_key])
        btn.clicked.connect(callback)
        return btn

    def _build_tag_row_widget(
        self, tag_name: str, display_text: str, is_assigned: bool
    ) -> QWidget:
        """Builds the label-plus-buttons row shown for one tag in the sidebar."""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(5, 2, 5, 2)
        row_layout.setSpacing(5)

        # Unlike the label, the checkbox consumes its own clicks, so ticking a
        # box never reaches the item and never triggers the click filter.
        checkbox = QCheckBox()
        checkbox.setStyleSheet(STYLES["tag_checkbox"])
        checkbox.setToolTip(f"Include '{tag_name}' in the combined filter")
        checkbox.setChecked(tag_name in self.checked_tags)
        checkbox.toggled.connect(
            lambda checked, t=tag_name: self._on_tag_check_toggled(t, checked)
        )
        self._tag_checkboxes[tag_name] = checkbox

        # Transparent to mouse events so clicks fall through to the list item,
        # which is what drives tag filtering.
        lbl = QLabel(display_text)
        lbl.setStyleSheet(STYLES["tag_row_label"])
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        btn_rename = self._create_tag_button(
            TAG_ICONS["rename"],
            "tag_btn_action",
            lambda checked, t=tag_name: self.action_rename_tag(t),
        )

        btn_delete = self._create_tag_button(
            TAG_ICONS["delete"],
            "tag_btn_delete",
            lambda checked, t=tag_name: self.action_delete_tag(t),
        )

        # +/- reflects whether the entire selection already carries this tag.
        toggle_icon = TAG_ICONS["remove"] if is_assigned else TAG_ICONS["add"]
        toggle_style = "tag_btn_assigned" if is_assigned else "tag_btn_unassigned"
        btn_toggle = self._create_tag_button(
            toggle_icon,
            toggle_style,
            lambda checked, t=tag_name: self.toggle_specific_tag(t),
        )

        row_layout.addWidget(checkbox)
        row_layout.addWidget(lbl)
        row_layout.addStretch()
        row_layout.addWidget(btn_rename)
        row_layout.addWidget(btn_delete)
        row_layout.addWidget(btn_toggle)

        return row_widget

    def _restore_tag_list_selection(self):
        """Re-highlights the active filter tag after the list is rebuilt."""
        if not self.active_filter_tag:
            return

        for i in range(self.tag_list_widget.count()):
            list_item = self.tag_list_widget.item(i)
            if list_item.data(Qt.ItemDataRole.UserRole) == self.active_filter_tag:
                list_item.setSelected(True)
                break

    def refresh_global_tags(self):
        """Rebuilds the tag sidebar, preserving scroll position and filter highlight."""
        v_scrollbar = self.tag_list_widget.verticalScrollBar()
        scroll_pos = v_scrollbar.value() if v_scrollbar else 0
        self.tag_list_widget.clear()
        # clear() destroyed the old row widgets, so drop the stale references
        # before _build_tag_row_widget repopulates them.
        self._tag_checkboxes.clear()

        selected_paths = self.get_selected_paths()
        shared_tags = (
            database.get_shared_tags(selected_paths) if selected_paths else set()
        )

        for item_text in database.get_all_tags():
            tag_name = self._parse_tag_name(item_text)

            # Each row is an empty item carrying the tag name, with a custom
            # widget layered over it for the label and buttons.
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, tag_name)
            self.tag_list_widget.addItem(item)

            is_assigned = tag_name in shared_tags
            row_widget = self._build_tag_row_widget(tag_name, item_text, is_assigned)

            item.setSizeHint(row_widget.sizeHint())
            self.tag_list_widget.setItemWidget(item, row_widget)

        self._restore_tag_list_selection()

        if v_scrollbar:
            v_scrollbar.setValue(scroll_pos)

    def clear_bubbles(self):
        while self.bubble_layout.count():
            child = self.bubble_layout.takeAt(0)
            if child and child.widget():
                child.widget().deleteLater()

    def refresh_assigned_bubbles(self):
        self.clear_bubbles()
        self.current_image_path_label.setText(self.active_image_path or "")
        if not self.active_image_path:
            return

        for tag in database.get_image_tags(self.active_image_path):
            bubble = QLabel(tag)
            bubble.setStyleSheet(STYLES["bubble"])
            self.bubble_layout.addWidget(bubble)
        self.bubble_layout.addStretch()

    # ========================== TIMER LOGIC ==========================
    def pick_random_image(self):
        """Selects a random image, never the one already showing."""
        list_count = self.file_list_widget.count()
        if list_count <= 1:
            return

        current_row = self.file_list_widget.currentRow()
        candidates = [i for i in range(list_count) if i != current_row]
        self.file_list_widget.setCurrentRow(random.choice(candidates))

    def start_timer(self):
        if not (text := self.timer_input.text().strip()):
            return

        self.timer_interval = int(text)
        database.save_setting("timer_seconds", str(self.timer_interval))
        self.time_left = self.timer_interval

        self.timer_display.setText(str(self.time_left))
        self.timer_display.show()

        # Advance straight away rather than making the user wait one full cycle.
        self.pick_random_image()

        self.countdown_timer.start(1000)

    def stop_timer(self):
        self.countdown_timer.stop()
        self.time_left = self.timer_interval = 0
        self.timer_display.setText("0")
        self.timer_display.hide()

    def update_timer(self):
        # Multi-selection means the user is bulk-tagging, so don't yank the
        # selection out from under them.
        if len(self.file_list_widget.selectedItems()) > 1:
            self.timer_display.setText("Paused (Multi-Select)")
            return

        self.time_left -= 1
        if self.time_left > 0:
            self.timer_display.setText(str(self.time_left))
            return

        self.pick_random_image()

        self.time_left = self.timer_interval
        self.timer_display.setText(str(self.time_left))

    def toggle_timer(self):
        """Starts or stops the countdown, falling back to APP_TIMER_DEFAULT."""
        # Space is a legitimate character while typing, so ignore the shortcut.
        focused = QApplication.focusWidget()
        if isinstance(focused, QLineEdit):
            return

        if self.countdown_timer.isActive():
            self.stop_timer()
            return

        if not self.timer_input.text().strip():
            self.timer_input.setText(APP_TIMER_DEFAULT)
            database.save_setting("timer_seconds", APP_TIMER_DEFAULT)

        self.start_timer()

    def _setup_shortcuts(self):
        shortcut = QShortcut(QKeySequence("F"), self)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(self.toggle_ui_visibility)

        shortcut_timer = QShortcut(QKeySequence("Space"), self)
        shortcut_timer.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut_timer.activated.connect(self.toggle_timer)

        shortcut_random = QShortcut(QKeySequence("R"), self)
        shortcut_random.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut_random.activated.connect(self.pick_random_image)

        shortcut_draw = QShortcut(QKeySequence("Ctrl+D"), self)
        shortcut_draw.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut_draw.activated.connect(self._toggle_draw_shortcut)

    def _toggle_draw_shortcut(self):
        """Routes Ctrl+D through the toolbar button so its state stays in sync."""
        self.drawing_toolbar.draw_btn.toggle()

    # ------------------------------------------------------------------
    # Global Ctrl+Z / Ctrl+Shift+Z / Delete handling
    # ------------------------------------------------------------------
    # QLineEdit — including the one inside every QSpinBox — claims Ctrl+Z and
    # Delete for text editing through Qt's shortcut-override mechanism, which
    # swallows an equivalent QShortcut before it can fire. Filtering at the
    # application level catches the raw key press first, while still exempting
    # genuine text fields so their native editing keys keep working.
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            modifiers = event.modifiers()
            # A spinbox's internal QLineEdit doesn't count as a text field here.
            is_real_text_field = isinstance(obj, QLineEdit) and not isinstance(
                obj.parent(), QAbstractSpinBox
            )

            if not is_real_text_field:
                if event.key() == Qt.Key.Key_Z and modifiers & Qt.KeyboardModifier.ControlModifier:
                    if modifiers & Qt.KeyboardModifier.ShiftModifier:
                        self._on_redo_annotation()
                    else:
                        self._on_undo_annotation()
                    return True

                # Bare Delete only, so combinations stay available to Qt.
                no_extra_modifiers = not (
                    modifiers
                    & (
                        Qt.KeyboardModifier.ControlModifier
                        | Qt.KeyboardModifier.ShiftModifier
                        | Qt.KeyboardModifier.AltModifier
                    )
                )
                if event.key() == Qt.Key.Key_Delete and no_extra_modifiers:
                    self._on_clear_annotations()
                    return True

        return super().eventFilter(obj, event)

    def toggle_ui_visibility(self):
        """Hides or restores everything except the canvas, for a focus view."""
        # "F" is a legitimate character while typing, so ignore the shortcut.
        focused = QApplication.focusWidget()
        if isinstance(focused, QLineEdit):
            return
        should_hide = self.left_sidebar.isVisible() or self.right_sidebar.isVisible()

        self.left_sidebar.setVisible(not should_hide)
        self.right_sidebar.setVisible(not should_hide)
        self.bubble_container.setVisible(not should_hide)
        self.current_image_path_label.setVisible(not should_hide)
        self.drawing_toolbar.setVisible(not should_hide)

        # Hiding the focused widget would otherwise leave focus nowhere, and
        # the shortcut needed to restore the UI would stop working.
        if should_hide:
            self.setFocus()

    def closeEvent(self, event):
        """Stops every background thread before the window is destroyed."""
        self.countdown_timer.stop()

        if self.thumb_loader and self.thumb_loader.isRunning():
            self.thumb_loader.stop()
            self.thumb_loader.wait()

        # Cancel all of them first, then wait, so the waits overlap rather
        # than running back to back.
        for loader in self._canvas_loaders:
            loader.cancel()
        for loader in self._canvas_loaders:
            loader.wait(2000)

        self._canvas_loaders.clear()
        event.accept()