import os
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QImageReader


class ThumbnailLoader(QThread):
    # Sends: row_index, file_path, image_data, is_external
    thumbnail_ready = pyqtSignal(int, str, QImage, bool)

    def __init__(self, items_to_load, cache_dir):
        super().__init__()
        self.items_to_load = items_to_load
        self.cache_dir = cache_dir
        self.is_running = True

        # 1. Force the directory to exist the moment the thread initializes
        os.makedirs(self.cache_dir, exist_ok=True)

    def process_image(self, row, file_path, is_ext):
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            return row, file_path, QImage(), is_ext

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

            size = reader.size()
            if size.isValid():
                reader.setScaledSize(
                    size.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio)
                )

            img = reader.read()

            if not img.isNull():
                # 2. Force the directory to exist right before saving (in case you delete it mid-run)
                os.makedirs(self.cache_dir, exist_ok=True)
                img.save(cache_path, "PNG")

        return row, file_path, img, is_ext

    def run(self):
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
                    # 3. Actually print the error to the terminal so we can see what went wrong!
                    print(f"Thumbnail generator failed for a file: {e}")

    def stop(self):
        self.is_running = False
