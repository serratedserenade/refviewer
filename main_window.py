import sys
import re
import random
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
)
from PyQt6.QtGui import (
    QPixmap,
    QPainter,
    QIntValidator,
    QColor,
    QIcon,
    QPen,
    QImageReader,
)
from PyQt6.QtCore import Qt, QTimer, QSize

from config import STYLES, CACHE_DIR
from file_scanner import scan_directory
from components.image_viewer import ScaledImageLabel
from components.thumbnail_loader import ThumbnailLoader
import database


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RefViewer")
        self.resize(1200, 600)

        # State Variables
        self.active_image_path = None
        self.scanned_files = []
        self.active_filter_tag = None
        self.is_icon_view = True
        self.thumb_loader = None
        self.time_left = 0
        self.timer_interval = 0
        self.show_labels = False

        self.path_filter_timer = QTimer(self)
        self.path_filter_timer.setSingleShot(True)
        self.path_filter_timer.timeout.connect(self.update_file_list)

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self._build_ui()
        self._setup_timer()

        self.load_saved_folder()
        self.refresh_global_tags()

    # ========================== UI SETUP ==========================

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._create_left_sidebar())
        main_layout.addWidget(self._create_center_canvas())
        main_layout.addWidget(self._create_right_sidebar())

    def _create_left_sidebar(self):
        sidebar = QFrame()
        sidebar.setStyleSheet(STYLES["sidebar"])
        sidebar.setFixedWidth(300)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # ROW 1: Path Display (Full Width)
        self.path_display = QLineEdit()
        self.path_display.setPlaceholderText("No folder selected")
        self.path_display.setReadOnly(True)
        self.path_display.setStyleSheet(STYLES["input"])
        layout.addWidget(self.path_display)

        # ROW 2: Action Buttons
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

        # ROW 3: File Data List
        self.file_list_widget = QListWidget()
        self.file_list_widget.setStyleSheet(STYLES["list"])
        self.file_list_widget.currentItemChanged.connect(self.on_file_item_changed)

        layout.addWidget(self.file_list_widget)

        # ROW 4: Path Filter Input
        self.path_filter_input = QLineEdit()
        self.path_filter_input.setPlaceholderText("Filter by path/filename...")
        self.path_filter_input.setStyleSheet(STYLES["input"])
        # Use lambda to trigger the 300ms delay timer
        self.path_filter_input.textChanged.connect(
            lambda: self.path_filter_timer.start(300)
        )
        layout.addWidget(self.path_filter_input)

        # ROW 5: Thumbnail Loading Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)  # Slim and unobtrusive
        self.progress_bar.setTextVisible(False)  # Hide the percentage text
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #34495e; border-radius: 4px; background-color: #1a252f; }
            QProgressBar::chunk { background-color: #2980b9; border-radius: 3px; }
        """)
        self.progress_bar.hide()  # Hidden by default
        layout.addWidget(self.progress_bar)

        return sidebar

    def _create_center_canvas(self):
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

        self.image_viewer = ScaledImageLabel()
        self.image_viewer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_viewer.setText("Select a folder to begin...")
        self.image_viewer.setStyleSheet(STYLES["placeholder"])
        layout.addWidget(self.image_viewer)

        self.bubble_container = QFrame()
        self.bubble_container.setStyleSheet("background: transparent;")
        self.bubble_layout = QHBoxLayout(self.bubble_container)
        self.bubble_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.bubble_container)

        layout.setStretch(0, 0)
        layout.setStretch(1, 1)
        layout.setStretch(2, 0)

        return content_area

    def _create_right_sidebar(self):
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
                "All Database Tags\n(Click to Filter, Double-click to Assign):"
            )
        )
        self.tag_list_widget = QListWidget()
        self.tag_list_widget.setStyleSheet(STYLES["list"])
        self.tag_list_widget.itemClicked.connect(self.on_tag_filter_clicked)

        layout.addWidget(self.tag_list_widget)

        return sidebar

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
        if self.thumb_loader and self.thumb_loader.isRunning():
            self.thumb_loader.stop()
            self.thumb_loader.wait()

        self.file_list_widget.clear()

        # Define sizes and alignments dynamically based on the label toggle
        if self.show_labels:
            grid_size = QSize(120, 180)
            icon_align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
        else:
            grid_size = QSize(110, 110)
            icon_align = (
                Qt.AlignmentFlag.AlignCenter
            )  # Perfectly center the icon in the box

        # 1. Config List & Dynamic Grid Sizing
        if self.is_icon_view:
            self.file_list_widget.setViewMode(QListWidget.ViewMode.IconMode)
            self.file_list_widget.setIconSize(QSize(100, 100))
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

        # 2. Extract Base Files
        display_files = (
            database.get_images_by_tag(self.active_filter_tag)
            if self.active_filter_tag
            else self.scanned_files
        )

        # 3. Apply the Path/Text Filter
        filter_text = self.path_filter_input.text().strip().lower()
        if filter_text:
            display_files = [f for f in display_files if filter_text in f.lower()]

        # 4. Generate the UI Row Items
        items_for_worker = []
        for row, file_path in enumerate(display_files):
            is_external = file_path not in self.scanned_files

            # ALWAYS show text if in List Mode. Only obey the toggle if in Icon Mode.
            if not self.is_icon_view or self.show_labels:
                display_text = file_path
            else:
                display_text = ""

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, file_path)

            if self.is_icon_view:
                item.setSizeHint(grid_size)
                item.setTextAlignment(icon_align)
            else:
                item.setSizeHint(QSize(250, 24))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )

            if not self.is_icon_view and is_external:
                item.setForeground(QColor("yellow"))

            self.file_list_widget.addItem(item)

            if self.is_icon_view:
                items_for_worker.append((row, file_path, is_external))

        # 5. Multithreading the Icons
        if self.is_icon_view and items_for_worker:
            self.loaded_thumbnail_count = 0
            self.progress_bar.setMaximum(len(items_for_worker))
            self.progress_bar.setValue(0)
            self.progress_bar.show()

            self.thumb_loader = ThumbnailLoader(items_for_worker, str(CACHE_DIR))
            self.thumb_loader.thumbnail_ready.connect(self.on_thumbnail_ready)
            self.thumb_loader.finished.connect(self.progress_bar.hide)
            self.thumb_loader.start()
        else:
            self.progress_bar.hide()

    def on_thumbnail_ready(self, row, file_path, img, is_external):
        # Tick the progress bar forward purely for visual feedback
        self.loaded_thumbnail_count += 1
        self.progress_bar.setValue(self.loaded_thumbnail_count)

        item = self.file_list_widget.item(row)
        if not item or item.data(Qt.ItemDataRole.UserRole) != file_path:
            return

        pixmap = QPixmap.fromImage(img)
        if is_external:
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

        self.active_image_path = current.data(Qt.ItemDataRole.UserRole)

        # NEW: Use ImageReader to explicitly ignore EXIF rotation metadata
        reader = QImageReader(self.active_image_path)
        reader.setAutoTransform(True)
        reader.setAllocationLimit(0)
        img = reader.read()

        if img.isNull():
            self.image_viewer.setText("Failed to load image file.")
            self.image_viewer.setStyleSheet(STYLES["error"])
            self.clear_bubbles()
        else:
            pixmap = QPixmap.fromImage(img)
            self.image_viewer.setStyleSheet("")
            self.image_viewer.set_image(pixmap)
            self.refresh_assigned_bubbles()

            # Update the tag list UI so the +/- buttons sync to this new picture!
            self.refresh_global_tags()

    # ========================== TAG MANAGEMENT ==========================

    def add_tag(self):
        if (
            not (tag_text := self.tag_input.text().strip())
            or not self.active_image_path
        ):
            self.tag_input.clear()
            return

        database.add_tag_to_image(self.active_image_path, tag_text)
        self.tag_input.clear()
        self.refresh_global_tags()
        self.refresh_assigned_bubbles()

    def on_tag_filter_clicked(self, item):
        """Single click functionality: Filters the main file list toggleably"""
        # Because we use custom widgets, we extract the hidden string data instead of the visible text
        tag_name = item.data(Qt.ItemDataRole.UserRole)

        if self.active_filter_tag == tag_name:
            self.active_filter_tag = None
            self.tag_list_widget.clearSelection()
        else:
            self.active_filter_tag = tag_name

        self.update_file_list()

    def toggle_specific_tag(self, tag_name):
        """Triggered exclusively by the inline '+' or '-' UI buttons"""
        if not self.active_image_path:
            return

        if tag_name in database.get_image_tags(self.active_image_path):
            database.remove_tag_from_image(self.active_image_path, tag_name)
        else:
            database.add_tag_to_image(self.active_image_path, tag_name)

        self.refresh_global_tags()
        self.refresh_assigned_bubbles()
        self.update_file_list()

    def on_tag_item_clicked(self, item):
        if not self.active_image_path:
            return

        match = re.match(r"^(.*)\s\(\d+\)$", item.text())
        tag_name = match.group(1).strip() if match else item.text().strip()

        if tag_name in database.get_image_tags(self.active_image_path):
            database.remove_tag_from_image(self.active_image_path, tag_name)
        else:
            database.add_tag_to_image(self.active_image_path, tag_name)

        self.refresh_global_tags()
        self.refresh_assigned_bubbles()
        self.update_file_list()

    def refresh_global_tags(self):
        # Remember where the user scrolled so the list doesn't jump annoyingly
        v_scrollbar = self.tag_list_widget.verticalScrollBar()
        scroll_pos = v_scrollbar.value() if v_scrollbar else 0

        self.tag_list_widget.clear()

        # Capture exactly what tags are on the current image
        assigned_tags = (
            set(database.get_image_tags(self.active_image_path))
            if self.active_image_path
            else set()
        )

        for item_text in database.get_all_tags():
            match = re.match(r"^(.*)\s\(\d+\)$", item_text)
            tag_name = match.group(1).strip() if match else item_text.strip()

            # Create the master list item
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, tag_name)
            self.tag_list_widget.addItem(item)

            # Create the custom inline UI
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(5, 2, 5, 2)
            row_layout.setSpacing(5)

            # The invisible label (passes clicks through to the list filter natively)
            lbl = QLabel(item_text)
            lbl.setStyleSheet("color: white; background: transparent; font-size: 11px;")
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            # The dedicated Toggle button
            is_assigned = tag_name in assigned_tags
            btn = QPushButton("−" if is_assigned else "+")
            btn.setFixedSize(20, 20)

            # Make the button Red if assigned, Green if it can be added
            if is_assigned:
                btn.setStyleSheet(
                    "QPushButton { background-color: #e74c3c; color: white; border-radius: 3px; font-weight: bold; } QPushButton:hover { background-color: #c0392b; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background-color: #27ae60; color: white; border-radius: 3px; font-weight: bold; } QPushButton:hover { background-color: #2ecc71; }"
                )

            # Connect the button exclusively to the toggler (lambda freezes the exact tag name context)
            btn.clicked.connect(lambda checked, t=tag_name: self.toggle_specific_tag(t))

            row_layout.addWidget(lbl)
            row_layout.addStretch()
            row_layout.addWidget(btn)

            item.setSizeHint(row_widget.sizeHint())
            self.tag_list_widget.setItemWidget(item, row_widget)

        # Restore highlight visualization if a filter is active
        if self.active_filter_tag:
            for i in range(self.tag_list_widget.count()):
                list_item = self.tag_list_widget.item(i)
                if list_item.data(Qt.ItemDataRole.UserRole) == self.active_filter_tag:
                    list_item.setSelected(True)
                    break

        if v_scrollbar:
            v_scrollbar.setValue(scroll_pos)

    def clear_bubbles(self):
        while self.bubble_layout.count():
            child = self.bubble_layout.takeAt(0)
            if child and child.widget():
                child.widget().deleteLater()

    def refresh_assigned_bubbles(self):
        self.clear_bubbles()
        if not self.active_image_path:
            return

        for tag in database.get_image_tags(self.active_image_path):
            bubble = QLabel(tag)
            bubble.setStyleSheet(STYLES["bubble"])
            self.bubble_layout.addWidget(bubble)
        self.bubble_layout.addStretch()

    # ========================== TIMER LOGIC ==========================

    def start_timer(self):
        if not (text := self.timer_input.text().strip()):
            return

        self.timer_interval = int(text)
        database.save_setting("timer_seconds", str(self.timer_interval))
        self.time_left = self.timer_interval

        self.timer_display.setText(str(self.time_left))
        self.timer_display.show()
        self.countdown_timer.start(1000)

    def stop_timer(self):
        self.countdown_timer.stop()
        self.time_left = self.timer_interval = 0
        self.timer_display.setText("0")
        self.timer_display.hide()

    def update_timer(self):
        self.time_left -= 1
        if self.time_left > 0:
            self.timer_display.setText(str(self.time_left))
            return

        self.time_left = self.timer_interval
        self.timer_display.setText(str(self.time_left))

        if (list_count := self.file_list_widget.count()) > 1:
            current_row = self.file_list_widget.currentRow()
            rand_idx = current_row
            while rand_idx == current_row:
                rand_idx = random.randint(0, list_count - 1)
            self.file_list_widget.setCurrentRow(rand_idx)
