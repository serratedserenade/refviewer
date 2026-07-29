from PyQt6.QtGui import QImage, QImageReader
from PyQt6.QtCore import QThread, pyqtSignal


class CanvasLoader(QThread):
    """Decodes one full-resolution image off the UI thread.

    A loader is spawned per image selection. Because the user can click through
    images faster than large files decode, each loader can be cancelled: it
    still runs to completion but discards its result instead of emitting.
    """

    image_ready = pyqtSignal(str, QImage)

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._cancelled = False

    def cancel(self):
        """Signals this loader to discard its result once decoding finishes."""
        self._cancelled = True

    def run(self):
        reader = QImageReader(self.file_path)
        # Honour EXIF orientation so phone/camera photos aren't sideways.
        reader.setAutoTransform(True)
        # Lift Qt's default decode ceiling, which rejects very large canvases.
        reader.setAllocationLimit(0)
        img = reader.read()

        if not self._cancelled:
            self.image_ready.emit(self.file_path, img)
