from pathlib import Path
from typing import TypeVar, Union

from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QDialog, QLayout, QMainWindow, QVBoxLayout, QWidget

T = TypeVar("T", bound=QWidget)


def load_ui(ui_file_path: Union[str, Path], parent: T) -> QWidget:
    """Load a .ui file and set up the widget connections.

    Parameters :
        ui_file_path : Union[str, Path]
            Path to the .ui file to load.
        parent : T
            The parent widget to load the UI into.

    Returns :
        The loaded widget with all children accessible as attributes.
    """
    loader = QUiLoader()
    ui_file = QFile(ui_file_path)
    if not ui_file.open(QFile.ReadOnly):
        raise RuntimeError(f"Cannot open UI file: {ui_file_path}")

    loaded_ui = loader.load(ui_file, parent)
    ui_file.close()

    if loaded_ui is None:
        raise RuntimeError(f"Failed to load UI file: {ui_file_path}")

    for widget in loaded_ui.findChildren(QWidget):
        name = widget.objectName()
        if name:
            setattr(parent, name, widget)

    for layout in loaded_ui.findChildren(QLayout):
        name = layout.objectName()
        if name:
            setattr(parent, name, layout)

    if isinstance(parent, QDialog):
        if loaded_ui.layout():
            parent.setLayout(loaded_ui.layout())
        parent.setWindowTitle(loaded_ui.windowTitle())
        parent.resize(loaded_ui.size())
    elif isinstance(parent, QMainWindow):
        parent.setCentralWidget(loaded_ui)
    else:
        # Plain QWidget: embed loaded_ui via a zero-margin layout so its
        # contents fill the parent window.
        container = QVBoxLayout(parent)
        container.setContentsMargins(0, 0, 0, 0)
        container.addWidget(loaded_ui)
        parent.setWindowTitle(loaded_ui.windowTitle())
        parent.resize(loaded_ui.size())

    return loaded_ui
