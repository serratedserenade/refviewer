from pathlib import Path

from PyQt6.QtWidgets import QTreeView, QAbstractItemView, QMenu
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtCore import Qt, QDir, pyqtSignal

from config import STYLES, FAVOURITE_ICONS


class FolderTree(QTreeView):
    """A directory-only filesystem tree for picking the folder to scan.

    Emits `folder_selected` on a single click, which is the whole point: it
    replaces a trip through the Browse dialog. Holds no reference to the window,
    so scanning is entirely the caller's business.
    """

    folder_selected = pyqtSignal(str)
    add_favourite_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.fs_model = QFileSystemModel()
        # Directories only; files would just be noise since a scan is recursive
        # anyway. Hidden entries are excluded by the default filter.
        self.fs_model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.Drives | QDir.Filter.NoDotAndDotDot
        )
        # Enables the model's file watcher, so folders created or removed while
        # the app is open show up without a restart.
        self.fs_model.setRootPath(QDir.rootPath())

        self.setModel(self.fs_model)
        # No root index is set, so the view starts at the model's own root: "/"
        # on Linux and macOS, the drive list on Windows.

        # The size/type/date columns are dead weight in a sidebar this narrow.
        for column in range(1, self.fs_model.columnCount()):
            self.hideColumn(column)
        self.setHeaderHidden(True)

        self.setStyleSheet(STYLES["tree"])
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)

        # `clicked` rather than a selection signal, so programmatically
        # revealing a folder never scans it a second time. It also covers only
        # left clicks, so raising the context menu never triggers a scan.
        self.clicked.connect(self._on_clicked)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self.expand_to(str(Path.home()), select=False)

    def _on_clicked(self, index):
        path = self.fs_model.filePath(index)
        if path:
            self.folder_selected.emit(path)

    def _show_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return

        path = self.fs_model.filePath(index)
        if not path:
            return

        menu = QMenu(self)
        menu.setStyleSheet(STYLES["menu"])
        add_action = menu.addAction(f"{FAVOURITE_ICONS['add']}  Add to Favourites")

        if menu.exec(self.viewport().mapToGlobal(pos)) is add_action:
            self.add_favourite_requested.emit(path)

    def expand_to(self, path: str, select: bool = True):
        """Reveals `path` in the tree, expanding every folder above it.

        Used to keep the tree in step with folders chosen elsewhere — the
        Browse dialog, or the folder restored at startup.
        """
        if not path:
            return

        index = self.fs_model.index(path)
        if not index.isValid():
            return

        # Collected upwards, then expanded downwards, because a parent has to be
        # populated before its child can be expanded.
        ancestors = []
        walker = index.parent()
        while walker.isValid():
            ancestors.append(walker)
            walker = walker.parent()

        for ancestor in reversed(ancestors):
            self.expand(ancestor)

        if select:
            self.setCurrentIndex(index)
        self.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)
