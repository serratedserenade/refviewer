from PyQt6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QWidget,
    QHBoxLayout,
    QToolButton,
    QSpinBox,
    QSlider,
    QPushButton,
    QColorDialog,
)
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QPen, QColor
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal

from config import (
    STYLES,
    DRAWING_ICONS,
    MAX_ANNOTATION_STROKES,
    DEFAULT_PEN_COLOR,
    DEFAULT_PEN_ALPHA,
    DEFAULT_PEN_WIDTH,
    PEN_WIDTH_MIN,
    PEN_WIDTH_MAX,
    PEN_SIZE_SPINBOX_WIDTH,
    SIZE_SLIDER_WIDTH,
    COLOR_SWATCH_SIZE,
    PEN_OPACITY_PERCENT_MIN,
    PEN_OPACITY_PERCENT_MAX,
    OPACITY_SPINBOX_WIDTH,
    OPACITY_SLIDER_WIDTH,
    QUICK_PEN_COLORS,
    QUICK_COLOR_SWATCH_SIZE,
    QUICK_PEN_SIZES,
    QUICK_SIZE_BTN_WIDTH,
)


def _default_pen_color() -> QColor:
    color = QColor(DEFAULT_PEN_COLOR)
    color.setAlpha(DEFAULT_PEN_ALPHA)
    return color


class DrawableImageLabel(QLabel):
    """Displays a scaled image and supports non-destructive pen annotations.

    Strokes are stored as vectors in the *source image's* pixel space and
    repainted over the image each frame, so they stay locked to image features
    when the widget resizes. `pixmap_source` is never mutated and nothing is
    written back to the file on disk.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap_source: QPixmap | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(1, 1)
        # Clicking the canvas takes focus off the toolbar spinboxes, which
        # otherwise swallow the annotation shortcuts.
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self.drawing_enabled = False
        self.pen_color = _default_pen_color()
        self.pen_width = DEFAULT_PEN_WIDTH

        self.strokes: list[dict] = []
        self._current_stroke: dict | None = None
        self._redo_stack: list[dict] = []

        # Scale/offset of the letterboxed image as of the last paint, used to
        # convert mouse positions into image pixel coordinates.
        self._draw_scale = 1.0
        self._draw_offset = QPointF(0, 0)

        # Zoom and pan state
        self._zoom_factor: float = 1.0
        self._pan_offset: QPointF = QPointF(0, 0)
        self._is_panning: bool = False
        self._pan_start_pos: QPointF | None = None
        self._pan_button: Qt.MouseButton | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_image(self, pixmap: QPixmap):
        """Loads a new base image, discarding annotations and resetting zoom."""
        self.pixmap_source = pixmap
        self.clear_annotations()
        self.reset_view()

    def reset_image(self):
        """Clears the image, annotations, and zoom, e.g. after a failed load."""
        self.pixmap_source = None
        self.clear_annotations()
        self.reset_view()

    def reset_view(self):
        """Resets zoom and pan back to fit-to-window centering."""
        self._zoom_factor = 1.0
        self._pan_offset = QPointF(0, 0)
        self._is_panning = False
        self._pan_start_pos = None
        self._pan_button = None
        self._update_cursor()
        self.update()

    def zoom_at(self, cursor_pos: QPointF, factor: float):
        """Zooms by factor keeping the image point under cursor_pos stationary."""
        if not self.pixmap_source or self.pixmap_source.isNull():
            return
        img_w = self.pixmap_source.width()
        img_h = self.pixmap_source.height()
        if img_w <= 0 or img_h <= 0 or self.width() <= 0 or self.height() <= 0:
            return

        fit_scale = min(self.width() / img_w, self.height() / img_h)
        new_zoom = max(0.05, min(self._zoom_factor * factor, 50.0))
        if abs(new_zoom - self._zoom_factor) < 1e-6:
            return

        old_scale = fit_scale * self._zoom_factor
        new_scale = fit_scale * new_zoom

        old_cx = (self.width() - img_w * old_scale) / 2
        old_cy = (self.height() - img_h * old_scale) / 2
        old_offset = QPointF(old_cx + self._pan_offset.x(), old_cy + self._pan_offset.y())

        img_pt_x = (cursor_pos.x() - old_offset.x()) / old_scale
        img_pt_y = (cursor_pos.y() - old_offset.y()) / old_scale

        new_offset_x = cursor_pos.x() - img_pt_x * new_scale
        new_offset_y = cursor_pos.y() - img_pt_y * new_scale

        new_cx = (self.width() - img_w * new_scale) / 2
        new_cy = (self.height() - img_h * new_scale) / 2

        self._zoom_factor = new_zoom
        self._pan_offset = QPointF(new_offset_x - new_cx, new_offset_y - new_cy)
        self.update()

    def zoom_in(self):
        center = QPointF(self.width() / 2, self.height() / 2)
        self.zoom_at(center, 1.25)

    def zoom_out(self):
        center = QPointF(self.width() / 2, self.height() / 2)
        self.zoom_at(center, 0.8)

    def _update_cursor(self):
        if self._is_panning:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self.drawing_enabled:
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif self.pixmap_source and not self.pixmap_source.isNull():
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_drawing_enabled(self, enabled: bool):
        self.drawing_enabled = enabled
        self._update_cursor()

    def set_pen_color(self, color: QColor):
        self.pen_color = QColor(color)

    def set_pen_width(self, width: int):
        self.pen_width = width

    def clear_annotations(self):
        """Removes every stroke along with the whole undo/redo history.

        A clear is deliberately not itself undoable, so this is what both the
        Clear button and the Delete shortcut reset to.
        """
        self.strokes = []
        self._current_stroke = None
        self._redo_stack = []
        self.update()

    def undo_last_stroke(self):
        if self.strokes:
            self._redo_stack.append(self.strokes.pop())
            self._trim_history()
            self.update()

    def redo_last_stroke(self):
        if self._redo_stack:
            self.strokes.append(self._redo_stack.pop())
            self._trim_history()
            self.update()

    def has_annotations(self) -> bool:
        return bool(self.strokes)

    def _trim_history(self):
        """Enforces MAX_ANNOTATION_STROKES on both stacks, oldest dropped first.

        The stroke list doubles as the drawing itself, so trimming it also
        erases the oldest visible stroke — acceptable only because the cap is
        far beyond a plausible markup session and annotations are transient.
        """
        excess = len(self.strokes) - MAX_ANNOTATION_STROKES
        if excess > 0:
            del self.strokes[:excess]

        excess = len(self._redo_stack) - MAX_ANNOTATION_STROKES
        if excess > 0:
            del self._redo_stack[:excess]

    # ------------------------------------------------------------------
    # Coordinate mapping (widget space <-> native image pixel space)
    # ------------------------------------------------------------------
    def _widget_to_image_point(self, widget_pos) -> QPointF | None:
        if (
            not self.pixmap_source
            or self.pixmap_source.isNull()
            or self._draw_scale <= 0
        ):
            return None

        x = (widget_pos.x() - self._draw_offset.x()) / self._draw_scale
        y = (widget_pos.y() - self._draw_offset.y()) / self._draw_scale
        return QPointF(x, y)

    # ------------------------------------------------------------------
    # Mouse and Wheel events (drawing, zooming, panning)
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        # Pan triggers: MiddleButton, RightButton, or LeftButton when drawing is disabled
        can_pan = (
            event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton)
            or (event.button() == Qt.MouseButton.LeftButton and not self.drawing_enabled)
        )
        if can_pan and self.pixmap_source and not self.pixmap_source.isNull():
            self._is_panning = True
            self._pan_button = event.button()
            self._pan_start_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if self.drawing_enabled and event.button() == Qt.MouseButton.LeftButton:
            point = self._widget_to_image_point(event.position())
            if point is not None:
                self._current_stroke = {
                    "color": QColor(self.pen_color),
                    "width": self.pen_width,
                    "points": [point],
                }
                self.update()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning and self._pan_start_pos is not None:
            delta = event.position() - self._pan_start_pos
            self._pan_offset += delta
            self._pan_start_pos = event.position()
            self.update()
            return

        if self._current_stroke is not None:
            point = self._widget_to_image_point(event.position())
            if point is not None:
                self._current_stroke["points"].append(point)
                self.update()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_panning and event.button() == self._pan_button:
            self._is_panning = False
            self._pan_start_pos = None
            self._pan_button = None
            self._update_cursor()
            return

        if (
            self._current_stroke is not None
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.strokes.append(self._current_stroke)
            self._current_stroke = None
            # Drawing something new invalidates the redo history.
            self._redo_stack = []
            self._trim_history()
            self.update()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Double clicking resets zoom and pan to fit view
        if (
            event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton)
            and not (self.drawing_enabled and event.button() == Qt.MouseButton.LeftButton)
        ):
            self.reset_view()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        if not self.pixmap_source or self.pixmap_source.isNull():
            super().wheelEvent(event)
            return

        delta_y = event.angleDelta().y()
        if delta_y == 0:
            super().wheelEvent(event)
            return

        num_steps = (delta_y / 8) / 15
        factor = 1.15 ** num_steps
        self.zoom_at(event.position(), factor)
        event.accept()

    def keyPressEvent(self, event):
        # Ignore arrow keys so they propagate to MainWindow / eventFilter for library traversal
        if event.key() in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
        ):
            event.ignore()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.pixmap_source or self.pixmap_source.isNull():
            return

        img_w = self.pixmap_source.width()
        img_h = self.pixmap_source.height()
        if img_w <= 0 or img_h <= 0 or self.width() <= 0 or self.height() <= 0:
            return

        fit_scale = min(self.width() / img_w, self.height() / img_h)
        scale = fit_scale * self._zoom_factor
        self._draw_scale = scale

        cx = (self.width() - img_w * scale) / 2
        cy = (self.height() - img_h * scale) / 2
        self._draw_offset = QPointF(cx + self._pan_offset.x(), cy + self._pan_offset.y())

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        target_rect = QRectF(
            self._draw_offset.x(),
            self._draw_offset.y(),
            img_w * scale,
            img_h * scale,
        )
        source_rect = QRectF(0.0, 0.0, float(img_w), float(img_h))
        painter.drawPixmap(target_rect, self.pixmap_source, source_rect)

        # Committed strokes, plus the in-progress one so it's visible while drawn.
        strokes_to_paint = self.strokes + (
            [self._current_stroke] if self._current_stroke else []
        )
        for stroke in strokes_to_paint:
            self._paint_stroke(painter, stroke)

    def _paint_stroke(self, painter: QPainter, stroke: dict):
        points = stroke["points"]

        def to_widget(p: QPointF) -> QPointF:
            return QPointF(
                p.x() * self._draw_scale + self._draw_offset.x(),
                p.y() * self._draw_scale + self._draw_offset.y(),
            )

        # Scaling the width with the image keeps strokes proportional on resize.
        pen_width = max(1.0, stroke["width"] * self._draw_scale)

        if len(points) == 1:
            # A click with no drag still has to render as a visible dot.
            wp = to_widget(points[0])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(stroke["color"])
            radius = pen_width / 2
            painter.drawEllipse(wp, radius, radius)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            return

        pen = QPen(stroke["color"])
        pen.setWidthF(pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        path = QPainterPath()
        path.moveTo(to_widget(points[0]))
        for p in points[1:]:
            path.lineTo(to_widget(p))
        painter.drawPath(path)


class DrawingToolbar(QWidget):
    """Horizontal control bar for the pen tool, intended to sit above the canvas.

    Communicates only by emitting signals and holds no reference to the canvas,
    so it stays independent of `DrawableImageLabel`.
    """

    draw_toggled = pyqtSignal(bool)
    color_changed = pyqtSignal(QColor)
    size_changed = pyqtSignal(int)
    clear_requested = pyqtSignal()
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pen_color = _default_pen_color()
        # Every control other than draw_btn is hidden until the pen is enabled.
        self._drawing_only_controls: list[QWidget] = []
        # (base color, button) pairs. Base colors carry no alpha; the swatches
        # are repainted at the current opacity whenever it changes.
        self._quick_color_swatches: list[tuple[QColor, QPushButton]] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(6)

        self.draw_btn = QToolButton()
        self.draw_btn.setText(DRAWING_ICONS["draw_off"])
        self.draw_btn.setCheckable(True)
        self.draw_btn.setStyleSheet(STYLES["tool_toggle_btn"])
        self.draw_btn.toggled.connect(self._on_draw_toggled)
        layout.addWidget(self.draw_btn)

        size_label = QLabel("Size:")
        size_label.setStyleSheet(STYLES["tag_row_label"])
        layout.addWidget(size_label)
        self._drawing_only_controls.append(size_label)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(PEN_WIDTH_MIN, PEN_WIDTH_MAX)
        self.size_spin.setValue(DEFAULT_PEN_WIDTH)
        self.size_spin.setFixedWidth(PEN_SIZE_SPINBOX_WIDTH)
        self.size_spin.setStyleSheet(STYLES["spinbox"])
        layout.addWidget(self.size_spin)
        self._drawing_only_controls.append(self.size_spin)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(PEN_WIDTH_MIN, PEN_WIDTH_MAX)
        self.size_slider.setValue(DEFAULT_PEN_WIDTH)
        self.size_slider.setFixedWidth(SIZE_SLIDER_WIDTH)
        self.size_slider.setStyleSheet(STYLES["slider"])
        layout.addWidget(self.size_slider)
        self._drawing_only_controls.append(self.size_slider)

        # The spinbox and slider mirror each other; only the spinbox forwards
        # the value onward, so a change from either source emits exactly once.
        self.size_spin.valueChanged.connect(self.size_slider.setValue)
        self.size_slider.valueChanged.connect(self.size_spin.setValue)
        self.size_spin.valueChanged.connect(self.size_changed.emit)

        opacity_label = QLabel("Opacity:")
        opacity_label.setStyleSheet(STYLES["tag_row_label"])
        layout.addWidget(opacity_label)
        self._drawing_only_controls.append(opacity_label)

        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(PEN_OPACITY_PERCENT_MIN, PEN_OPACITY_PERCENT_MAX)
        self.opacity_spin.setSuffix("%")
        self.opacity_spin.setFixedWidth(OPACITY_SPINBOX_WIDTH)
        self.opacity_spin.setStyleSheet(STYLES["spinbox"])
        layout.addWidget(self.opacity_spin)
        self._drawing_only_controls.append(self.opacity_spin)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(PEN_OPACITY_PERCENT_MIN, PEN_OPACITY_PERCENT_MAX)
        self.opacity_slider.setFixedWidth(OPACITY_SLIDER_WIDTH)
        self.opacity_slider.setStyleSheet(STYLES["slider"])
        layout.addWidget(self.opacity_slider)
        self._drawing_only_controls.append(self.opacity_slider)

        self.opacity_spin.valueChanged.connect(self.opacity_slider.setValue)
        self.opacity_slider.valueChanged.connect(self.opacity_spin.setValue)
        self.opacity_spin.valueChanged.connect(self._on_opacity_percent_changed)

        self._set_opacity_percent(round(self.pen_color.alpha() / 255 * 100))

        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(COLOR_SWATCH_SIZE, COLOR_SWATCH_SIZE)
        self.color_btn.setToolTip("Pen color")
        self.color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()
        layout.addWidget(self.color_btn)
        self._drawing_only_controls.append(self.color_btn)

        self.undo_btn = QPushButton(DRAWING_ICONS["undo"])
        self.undo_btn.setToolTip("Undo last stroke (Ctrl+Z)")
        self.undo_btn.setStyleSheet(STYLES["button"])
        self.undo_btn.clicked.connect(self.undo_requested.emit)
        layout.addWidget(self.undo_btn)
        self._drawing_only_controls.append(self.undo_btn)

        self.redo_btn = QPushButton(DRAWING_ICONS["redo"])
        self.redo_btn.setToolTip("Redo last stroke (Ctrl+Shift+Z)")
        self.redo_btn.setStyleSheet(STYLES["button"])
        self.redo_btn.clicked.connect(self.redo_requested.emit)
        layout.addWidget(self.redo_btn)
        self._drawing_only_controls.append(self.redo_btn)

        self.clear_btn = QPushButton(DRAWING_ICONS["clear"])
        self.clear_btn.setToolTip("Clear all annotations")
        self.clear_btn.setStyleSheet(STYLES["button"])
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        layout.addWidget(self.clear_btn)
        self._drawing_only_controls.append(self.clear_btn)

        layout.addStretch()

        # -------------------- Right-aligned quick presets --------------------
        for size in QUICK_PEN_SIZES:
            size_btn = QPushButton(str(size))
            size_btn.setFixedWidth(QUICK_SIZE_BTN_WIDTH)
            size_btn.setToolTip(f"Pen size {size}")
            size_btn.setStyleSheet(STYLES["quick_size_btn"])
            # Routed through size_spin so the spinbox and slider follow along.
            size_btn.clicked.connect(
                lambda _checked=False, s=size: self.size_spin.setValue(s)
            )
            layout.addWidget(size_btn)
            self._drawing_only_controls.append(size_btn)

        for name, hex_color in QUICK_PEN_COLORS.items():
            base_color = QColor(hex_color)

            swatch_btn = QPushButton()
            swatch_btn.setFixedSize(QUICK_COLOR_SWATCH_SIZE, QUICK_COLOR_SWATCH_SIZE)
            swatch_btn.setToolTip(name)
            swatch_btn.clicked.connect(
                lambda _checked=False, c=base_color: self._select_quick_color(c)
            )
            layout.addWidget(swatch_btn)
            self._drawing_only_controls.append(swatch_btn)
            self._quick_color_swatches.append((base_color, swatch_btn))

        self._refresh_quick_color_swatches()
        self._set_controls_visible(False)

    def _set_controls_visible(self, visible: bool):
        for widget in self._drawing_only_controls:
            widget.setVisible(visible)

    def _select_quick_color(self, base_color: QColor):
        """Applies a preset color at whatever opacity is currently set."""
        color = QColor(base_color)
        color.setAlpha(round(self.opacity_spin.value() / 100 * 255))
        self.pen_color = color
        self._update_color_btn()
        self.color_changed.emit(self.pen_color)

    def _on_draw_toggled(self, checked: bool):
        self.draw_btn.setText(
            DRAWING_ICONS["draw_on"] if checked else DRAWING_ICONS["draw_off"]
        )
        self._set_controls_visible(checked)
        self.draw_toggled.emit(checked)

    def _pick_color(self):
        dialog = QColorDialog(self.pen_color, self)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        dialog.setStyleSheet(STYLES["color_dialog"])
        if dialog.exec() == QColorDialog.DialogCode.Accepted:
            color = dialog.selectedColor()
            if color.isValid():
                self.pen_color = color
                self._update_color_btn()
                self._set_opacity_percent(round(color.alpha() / 255 * 100))
                self.color_changed.emit(color)

    def _on_opacity_percent_changed(self, percent: int):
        """Converts the 0-100% control value into the 0-255 alpha QColor stores."""
        alpha = round(percent / 100 * 255)
        self.pen_color.setAlpha(alpha)
        self._update_color_btn()
        self._refresh_quick_color_swatches()
        self.color_changed.emit(self.pen_color)

    def _set_opacity_percent(self, percent: int):
        """Moves the opacity controls to `percent` without emitting.

        Signals are blocked because callers have already applied the alpha to
        pen_color themselves; letting the handler run would emit color_changed
        a second time.
        """
        self.opacity_spin.blockSignals(True)
        self.opacity_slider.blockSignals(True)
        self.opacity_spin.setValue(percent)
        self.opacity_slider.setValue(percent)
        self.opacity_spin.blockSignals(False)
        self.opacity_slider.blockSignals(False)
        self._refresh_quick_color_swatches()

    def _update_color_btn(self):
        c = self.pen_color
        rgba = f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alphaF():.3f})"
        self.color_btn.setStyleSheet(STYLES["color_swatch_btn"].format(color=rgba))

    def _refresh_quick_color_swatches(self):
        """Repaints the preset swatches so the palette previews current opacity."""
        alpha = round(self.opacity_spin.value() / 100 * 255)
        for base_color, swatch_btn in self._quick_color_swatches:
            c = QColor(base_color)
            c.setAlpha(alpha)
            rgba = f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alphaF():.3f})"
            swatch_btn.setStyleSheet(
                STYLES["quick_color_swatch"].replace("{color}", rgba)
            )
