from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtCore import Qt

class ScaledImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap_source = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(1, 1)

    def set_image(self, pixmap: QPixmap):
        self.pixmap_source = pixmap
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.pixmap_source or self.pixmap_source.isNull():
            return
            
        painter = QPainter(self)
        scaled_size = self.pixmap_source.size()
        scaled_size.scale(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        
        x = (self.width() - scaled_size.width()) // 2
        y = (self.height() - scaled_size.height()) // 2
        
        scaled_pixmap = self.pixmap_source.scaled(
            scaled_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(x, y, scaled_pixmap)