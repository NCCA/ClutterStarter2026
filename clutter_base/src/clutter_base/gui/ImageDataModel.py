from typing import Any, Optional, Union

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget


class ImageDataModel(QAbstractTableModel):
    """
    A custom data model for handling image data stored in a MongoDB database.
    This model detects columns containing image data and renders them as QPixmap objects.
    """

    def __init__(self, database, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the ImageDataModel.

        :param parent: The parent widget, if any.
        """
        super().__init__(parent)
        self._data: list[dict[str, Any]] = []
        self._headers: list[str] = []
        self._image_columns: set[int] = set()
        self._db = database

    def setQuery(self, filter_doc: Optional[dict[str, Any]] = None) -> None:
        """
        Execute a MongoDB query and populate the model with results.

        :param filter_doc: The MongoDB filter document (default: {}).
        """
        self.beginResetModel()
        if filter_doc is None:
            filter_doc = {}
        collection = self._db["assets"]
        exclude = {"mesh_file_id": 0, "user_id": 0, "_id": 0}
        self._data = list(collection.find(filter_doc, exclude))

        if self._data:
            self._headers = list(self._data[0].keys())
        else:
            self._headers = []
        self._detect_image_columns()
        self.endResetModel()

    def _detect_image_columns(self) -> None:
        """
        Detect columns in the model that contain image data.
        """
        self._image_columns = set()
        if not self._data:
            return
        for col_idx, col_name in enumerate(self._headers):
            value = self._data[0].get(col_name)
            if isinstance(value, bytes):
                pixmap = QPixmap()
                if pixmap.loadFromData(value):
                    self._image_columns.add(col_idx)

    def _is_text_column(self, column: int) -> bool:
        """Return True if the column is text based and editable."""

        if column in self._image_columns:
            return False
        if not (0 <= column < len(self._headers)):
            return False
        column_name = self._headers[column]
        if not self._data:
            return False
        sample_value = self._data[0].get(column_name)
        return isinstance(sample_value, str) or sample_value is None

    def rowCount(
        self,
        parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex(),
    ) -> int:
        """
        Return the number of rows in the model.

        :param parent: The parent index.
        :return: The number of rows.
        """
        if parent.isValid():
            return 0
        return len(self._data)

    def columnCount(
        self,
        parent: Union[QModelIndex, QPersistentModelIndex] = QModelIndex(),
    ) -> int:
        """
        Return the number of columns in the model.

        :param parent: The parent index.
        :return: The number of columns.
        """
        if parent.isValid():
            return 0
        return len(self._headers)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        """
        Return the header data for the given section.

        :param section: The section index.
        :param orientation: The orientation (horizontal/vertical).
        :param role: The role for which data is requested.
        :return: The header data.
        """
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    def data(
        self,
        index: Union[QModelIndex, QPersistentModelIndex],
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        """
        Retrieve data from the model, rendering image columns as QPixmap objects.

        :param index: The index of the data to retrieve.
        :param role: The role for which data is requested.
        :return: The data at the specified index and role.
        """
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if not (0 <= row < len(self._data) and 0 <= col < len(self._headers)):
            return None

        col_name = self._headers[col]
        value = self._data[row].get(col_name)

        if role == Qt.ItemDataRole.DecorationRole and col in self._image_columns:
            if isinstance(value, bytes):
                pixmap = QPixmap()
                if pixmap.loadFromData(value):
                    return pixmap
            return None

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col in self._image_columns:
                return None
            if isinstance(value, bytes):
                return f"<blob {len(value)} bytes>"
            if isinstance(value, list):
                return ", ".join(str(item) for item in value)
            return str(value) if value is not None else ""

        return None

    def flags(self, index: Union[QModelIndex, QPersistentModelIndex]):
        """Return item flags, enabling editing for text columns."""

        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        if self._is_text_column(index.column()):
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(
        self,
        index: Union[QModelIndex, QPersistentModelIndex],
        value: Any,
        role: int = int(Qt.ItemDataRole.EditRole),
    ) -> bool:
        """Allow updating editable fields directly from the view."""

        if not index.isValid():
            return False
        if role != Qt.ItemDataRole.EditRole:
            return False

        row = index.row()
        col = index.column()
        if not self._is_text_column(col):
            return False

        column_name = self._headers[col]
        asset_id = self._data[row].get("id")
        if asset_id is None:
            return False

        new_value = str(value) if value is not None else ""
        stored_value = self._data[row].get(column_name)
        if stored_value is None:
            current_value = ""
        elif isinstance(stored_value, str):
            current_value = stored_value
        else:
            current_value = str(stored_value)
        if current_value == new_value:
            return True

        try:
            execute_update(asset_id, {column_name: new_value})
            self._data[row][column_name] = new_value
            self.dataChanged.emit(
                index,
                index,
                [Qt.ItemDataRole.DisplayRole],
            )
            return True
        except Exception as exc:
            print(
                f"Failed to update column {column_name} for row {row}: {exc}",
            )
            return False

    def get_data_at_index(self, row: int, name: str) -> Any:
        """
        Retrieve data from a specific row and column name.

        :param row: The row index.
        :param name: The column name.
        :return: The data at the specified row and column.
        """
        if 0 <= row < len(self._data):
            return self._data[row].get(name)
        return None
