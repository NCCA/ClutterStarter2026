from pathlib import Path
from typing import Dict, Optional

from pymongo import MongoClient
from pymongo.database import Database
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,  # noqa: F401
    QTableView,
    QWidget,
)

from clutter_base.gui.ImageDataModel import ImageDataModel
from clutter_base.gui.login import LoginWidget
from clutter_base.gui.ui_loader import load_ui

MODULE_DIR = Path(__file__).resolve().parent
UI_FILE = MODULE_DIR / "GridViewWidget.ui"

# Maximum thumbnail dimension (width or height) for grid display
THUMBNAIL_SIZE = 128


class GridViewWidget(QDialog):
    """Dialog that displays assets in a searchable grid view.

    Receives an already-authenticated ``(MongoClient, Database)`` session
    from the login flow rather than connecting internally.
    """

    def __init__(
        self,
        user: str,
        client: MongoClient,
        db: Database,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        load_ui(UI_FILE, self)
        self.setWindowTitle(f"Grid View - {user}")
        self._client = client
        self._db = db
        self.asset_collection = self._db["assets"]

        self.database_view: QTableView = QTableView(self.database_gb)
        self.database_view.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        self.database_gb_layout.addWidget(self.database_view)
        # auto-size select column to content
        self.database_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.data_model = ImageDataModel(self._db)
        self.update_view()
        self._connect_signals()

    def _connect_signals(self) -> None:
        self.search_location.currentIndexChanged.connect(self.update_query)
        self.search_text.textChanged.connect(self.update_query)
        self.case_sensitive.stateChanged.connect(self.update_query)
        self.mesh_type.currentIndexChanged.connect(self.update_query)

    def accept(self) -> None:
        super().accept()

    def update_query(self) -> None:
        location = self.search_location.currentText()
        text = self.search_text.text()
        mesh_type = self.mesh_type.currentText()

        query: dict = {}

        if text:
            regex_expr: dict = {"$regex": text}
            if not self.case_sensitive.isChecked():
                regex_expr["$options"] = "i"

            if location == "all":
                query["$or"] = [{field: regex_expr} for field in ("name", "description", "keywords")]
            else:
                query[location] = regex_expr

        if mesh_type != "all":
            if mesh_type == "usd":
                query["file_type"] = {"$regex": "^usd", "$options": "i"}
            else:
                query["file_type"] = mesh_type

        print(f"{query=}")
        self.update_view(query)

    def update_view(self, query_string: Dict = dict()) -> None:  # noqa: B006
        try:
            self.data_model.setQuery(query_string)
            self.database_view.setModel(self.data_model)
            self.database_view.resizeRowsToContents()
            self.database_view.resizeColumnsToContents()
        except RuntimeError as e:
            print(f"error running query {query_string}: {e}")


def main() -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    # Prevent the application from quitting when the login widget is closed
    # but before the grid view is shown.
    app.setQuitOnLastWindowClosed(False)

    login_widget = LoginWidget()
    # Mutable container keeps a strong Python reference to the grid dialog
    # so it is not garbage-collected when _on_authenticated returns.
    grid_holder: list[Optional[GridViewWidget]] = [None]

    def _on_authenticated(role: str, username: str) -> None:
        session = login_widget.session
        if session is None:
            return
        client, db = session
        grid = GridViewWidget(username, client, db)
        grid_holder[0] = grid
        login_widget.close()
        grid.show()
        # Now that a window is visible, restore normal quit behaviour.
        app.setQuitOnLastWindowClosed(True)

    login_widget.authenticated.connect(_on_authenticated)
    login_widget.show()
    app.exec()


if __name__ == "__main__":
    main()
