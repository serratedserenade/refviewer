import os

from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMenu, QInputDialog
from PyQt6.QtCore import Qt, pyqtSignal

from config import STYLES, FAVOURITE_ICONS


class FavouritesList(QListWidget):
    """Saved folder shortcuts, shown above the directory tree.

    Each entry keeps a display name alongside its path, so renaming a favourite
    never changes the folder it points at. Storage is the caller's business:
    `favourites_changed` fires whenever the contents change.
    """

    folder_selected = pyqtSignal(str)
    favourites_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(STYLES["list"])
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)

        # Right-clicking does not emit `itemClicked`, so raising the menu can
        # never load a folder as a side effect.
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.itemClicked.connect(
            lambda item: self.folder_selected.emit(item.data(Qt.ItemDataRole.UserRole))
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_favourites(self, favourites: list[dict]):
        """Replaces the whole list, e.g. when restoring saved shortcuts."""
        self.clear()
        for entry in favourites:
            self._append(entry["name"], entry["path"])

    def favourites(self) -> list[dict]:
        """Returns the current shortcuts in display order, ready to persist."""
        return [
            {
                "name": self.item(row).text(),
                "path": self.item(row).data(Qt.ItemDataRole.UserRole),
            }
            for row in range(self.count())
        ]

    def add_folder(self, path: str) -> bool:
        """Saves `path` under its folder name; False if it is already saved."""
        if not path or self._row_for_path(path) is not None:
            return False

        self._append(self._default_name(path), path)
        self.favourites_changed.emit()
        return True

    def contains(self, path: str) -> bool:
        return self._row_for_path(path) is not None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _append(self, name: str, path: str):
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, path)
        # The row shows only the folder name, so as with the image grid the
        # tooltip is the only place the full path appears.
        item.setToolTip(path)
        self.addItem(item)

    def _row_for_path(self, path: str) -> int | None:
        for row in range(self.count()):
            if self.item(row).data(Qt.ItemDataRole.UserRole) == path:
                return row
        return None

    def _default_name(self, path: str) -> str:
        """Names a shortcut after its folder, falling back to the path itself.

        The fallback covers roots like "/", whose basename is empty.
        """
        return os.path.basename(path.rstrip(os.sep)) or path

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet(STYLES["menu"])
        rename_action = menu.addAction(f"{FAVOURITE_ICONS['rename']}  Rename")
        remove_action = menu.addAction(f"{FAVOURITE_ICONS['remove']}  Remove")

        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is rename_action:
            self._rename(item)
        elif chosen is remove_action:
            self._remove(item)

    def _rename(self, item: QListWidgetItem):
        new_name, ok = QInputDialog.getText(
            self, "Rename Favourite", "Name:", text=item.text()
        )
        if ok and new_name.strip():
            item.setText(new_name.strip())
            self.favourites_changed.emit()

    def _remove(self, item: QListWidgetItem):
        self.takeItem(self.row(item))
        self.favourites_changed.emit()
