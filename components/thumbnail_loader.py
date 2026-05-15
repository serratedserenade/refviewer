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

    def process_image(self, row, file_path, is_ext):
        path_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
        cache_path = os.path.join(self.cache_dir, f"{path_hash}.png")
        img = QImage()

        if os.path.exists(cache_path):
            img.load(cache_path)
        else:
            reader = QImageReader(file_path)
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(size.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio))
            img = reader.read()
            
            if not img.isNull():
                img.save(cache_path, "PNG")

        return row, file_path, img, is_ext

    def run(self):
        with ThreadPoolExecutor() as executor:
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
                except Exception:
                    pass

    def stop(self):
        self.is_running = False