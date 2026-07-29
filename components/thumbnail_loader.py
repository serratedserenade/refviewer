import os
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QImageReader

from config import THUMBNAIL_SIZE


class ThumbnailLoader(QThread):
    """Generates and caches thumbnails for a batch of images off the UI thread.

    Runs a worker pool internally, so a single QThread fans one batch out across
    several cores while keeping the UI thread free.
    """

    # Sends: row_index, file_path, image_data, is_external
    thumbnail_ready = pyqtSignal(int, str, QImage, bool)

    def __init__(self, items_to_load, cache_dir):
        super().__init__()
        self.items_to_load = items_to_load
        self.cache_dir = cache_dir
        self.is_running = True

        os.makedirs(self.cache_dir, exist_ok=True)

    def process_image(self, row, file_path, is_ext):
        """Returns a cached thumbnail for `file_path`, generating one if needed."""
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            return row, file_path, QImage(), is_ext

        # Keying on mtime as well as path means editing a file invalidates its
        # cached thumbnail for free.
        hash_input = f"{file_path}:{mtime}".encode("utf-8")
        path_hash = hashlib.md5(hash_input).hexdigest()
        cache_path = os.path.join(self.cache_dir, f"{path_hash}.png")

        img = QImage()

        if os.path.exists(cache_path):
            img.load(cache_path)
        else:
            reader = QImageReader(file_path)
            reader.setAutoTransform(True)
            reader.setAllocationLimit(0)

            # Scaling during the read avoids ever decoding the full-size image.
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(
                    size.scaled(
                        THUMBNAIL_SIZE, THUMBNAIL_SIZE, Qt.AspectRatioMode.KeepAspectRatio
                    )
                )

            img = reader.read()

            if not img.isNull():
                # Re-checked here so the cache survives being deleted mid-run.
                os.makedirs(self.cache_dir, exist_ok=True)
                img.save(cache_path, "PNG")

        return row, file_path, img, is_ext

    def run(self):
        # Half the cores, so thumbnail generation never starves the UI thread.
        safe_workers = max(1, (os.cpu_count() or 2) // 2)

        with ThreadPoolExecutor(max_workers=safe_workers) as executor:
            futures = {
                executor.submit(self.process_image, row, fp, is_ext): (row, fp, is_ext)
                for row, fp, is_ext in self.items_to_load
            }

            for future in as_completed(futures):
                if not self.is_running:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                try:
                    row, file_path, img, is_ext = future.result()
                    if not img.isNull() and self.is_running:
                        self.thumbnail_ready.emit(row, file_path, img, is_ext)
                except Exception as e:
                    # One unreadable or corrupt file shouldn't abort the batch.
                    print(f"Thumbnail generator failed for a file: {e}")

    def stop(self):
        """Requests cancellation; in-flight futures are dropped, not awaited."""
        self.is_running = False
