from __future__ import annotations

from pathlib import Path
from typing import Optional

from bson import ObjectId
from pymongo.database import Database
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from clutter_base import SUPPORTED_IMAGE_EXTENSIONS, SUPPORTED_MESH_EXTENSIONS
from clutter_base.db import Asset, Connection
from clutter_base.gui.ui_loader import load_ui

MODULE_DIR = Path(__file__).resolve().parent
UI_FILE = MODULE_DIR / "AddDialog.ui"
COMBO_INDEX = {
    ".obj": 0,
    "fbx": 1,
    ".usd": 2,
    ".usda": 2,
    "usdc": 2,
    "usdz": 2,
}

IMAGE_ROLES = ["front_image", "side_image", "top_image", "persp_image"]

# Maximum thumbnail dimension (width or height) for grid display
THUMBNAIL_SIZE = 128


class ImageCard(QWidget):
    """A card widget showing a single image with a role combo box and a delete button.

    The image button is clickable to allow replacing the image via a file dialog.
    Image bytes are stored in :attr:`image_data` for later DB insertion.
    """

    def __init__(self, image_path: Optional[Path], parent_dialog: "AddMeshWidget") -> None:
        super().__init__(parent_dialog)
        self._parent_dialog = parent_dialog
        self._image_path: Optional[Path] = image_path
        self.image_data: Optional[bytes] = None

        self._build_ui()
        if image_path is not None:
            self._load_image(image_path)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct child widgets and layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Clickable image button
        self.image_button = QPushButton()
        self.image_button.setFixedSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        self.image_button.setToolTip("Click to select image")
        self.image_button.setText("Click to add")
        self.image_button.clicked.connect(self._on_image_clicked)
        layout.addWidget(self.image_button, alignment=Qt.AlignCenter)

        # Role selector
        self.role_combo = QComboBox()
        for role in IMAGE_ROLES:
            self.role_combo.addItem(role)
        self.role_combo.currentTextChanged.connect(self._on_role_changed)
        layout.addWidget(self.role_combo)

        # Delete button
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(delete_btn)

    # ------------------------------------------------------------------
    # Image loading
    # ------------------------------------------------------------------

    def _load_image(self, path: Path) -> None:
        """Read *path*, cache bytes in :attr:`image_data` and update the icon."""
        image_data = path.read_bytes()
        pixmap = QPixmap()
        if pixmap.loadFromData(image_data):
            self.image_data = image_data
            self._image_path = path
            self.image_button.setText("")
            scaled = pixmap.scaled(
                THUMBNAIL_SIZE,
                THUMBNAIL_SIZE,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.image_button.setIcon(scaled)
            self.image_button.setIconSize(scaled.size())
        else:
            self.image_button.setText("?")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_image_clicked(self) -> None:
        """Open a file dialog so the user can replace this image."""
        ext_filter = "Images (" + " ".join(f"*{e}" for e in SUPPORTED_IMAGE_EXTENSIONS) + ")"
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Image", "", ext_filter)
        if file_name:
            self._load_image(Path(file_name))

    def _on_role_changed(self, role: str) -> None:
        """Delegate role-uniqueness enforcement to the parent dialog."""
        self._parent_dialog._enforce_unique_role(self, role)

    def _on_delete_clicked(self) -> None:
        """Ask the parent dialog to remove this card."""
        self._parent_dialog._remove_image_card(self)

    # ------------------------------------------------------------------
    # Role property
    # ------------------------------------------------------------------

    @property
    def role(self) -> str:
        """Currently selected role string."""
        return self.role_combo.currentText()

    @role.setter
    def role(self, value: str) -> None:
        idx = self.role_combo.findText(value)
        if idx >= 0:
            # Block signal to avoid re-entrance during enforcement
            self.role_combo.blockSignals(True)
            self.role_combo.setCurrentIndex(idx)
            self.role_combo.blockSignals(False)


class AddMeshWidget(QDialog):
    """Dialog that collects mesh metadata and reference images for DB insertion.

    Receives an already-authenticated database session and user identity
    from the login flow.
    """

    def __init__(
        self,
        user: str,
        db: Database,
        user_id: ObjectId,
        role: str,
        location: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        load_ui(UI_FILE, self)
        self.cancel.clicked.connect(self.reject)
        self.insert.clicked.connect(self.insert_into_db)
        self.location = location
        self.setWindowTitle("Add Mesh")
        self._image_cards: list[ImageCard] = []
        self.user = user
        self._db = db
        self._user_id = user_id
        self._role = role
        if location != "":
            self._load_location(location)
        else:
            self._create_default_image_cards()

    def accept(self) -> None:
        super().accept()

    @Slot()
    def insert_into_db(self) -> None:
        """Insert the current item into the database.

        Images are stored inline in the document (as bytes).  The mesh is stored
        in GridFS and referenced via ``mesh_file_id``, matching the format used
        by ``addToDB.py``.

        The ``user_id`` is automatically set by the ``Connection`` to the
        authenticated user's id.
        """
        blobs = self.get_image_blobs()
        asset = Asset(
            name=self.item_name.text(),
            file_type=self.mesh_type.currentText(),
            description=self.description.toPlainText(),
            top_image=blobs["top_image"],
            side_image=blobs["side_image"],
            front_image=blobs["front_image"],
            persp_image=blobs["persp_image"],
            mesh_file_id=self.mesh_name.text(),
            keywords=self.keywords.text().split(","),
        )
        with Connection(self._db, self._user_id, self._role) as conn:
            conn.add_asset(asset)

        self.accept()

    # ------------------------------------------------------------------
    # Location / mesh loading
    # ------------------------------------------------------------------

    def _load_location(self, location: str) -> None:
        """Scan *location* directory for a mesh file and supported images."""
        path = Path(location)

        # Locate the mesh file
        for file in path.glob("*"):
            if file.suffix.lower() in SUPPORTED_MESH_EXTENSIONS:
                self.location = str(file)
                self.mesh_name.setText(str(file))
                self.item_name.setText(file.name[:-4])
                self.mesh_type.setCurrentIndex(COMBO_INDEX[file.suffix.lower()])
                break

        # Collect and display all image files, sorted for determinism
        image_files = sorted(f for f in path.glob("*") if f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS)
        for img_file in image_files:
            self._add_image_card(img_file)

        # Guess roles from filename keywords
        self._auto_assign_roles()

    def _create_default_image_cards(self) -> None:
        """Create one empty :class:`ImageCard` per role when no folder is supplied."""
        for role in IMAGE_ROLES:
            card = ImageCard(None, self)
            card.role = role
            self._image_cards.append(card)
        self._rebuild_grid()

    # ------------------------------------------------------------------
    # Image grid management
    # ------------------------------------------------------------------

    def _add_image_card(self, image_path: Optional[Path] = None) -> None:
        """Create an :class:`ImageCard` and insert it into the grid."""
        card = ImageCard(image_path, self)
        self._image_cards.append(card)
        self._rebuild_grid()

    def _remove_image_card(self, card: ImageCard) -> None:
        """Remove *card* from the internal list and destroy the widget."""
        if card in self._image_cards:
            self._image_cards.remove(card)
        self._rebuild_grid()
        card.deleteLater()

    def _rebuild_grid(self) -> None:
        """Re-populate the ``image_group_box`` grid layout with current cards."""
        layout: QGridLayout = self.gridLayout_2  # type: ignore[assignment]

        # Detach all widgets without deleting them
        while layout.count():
            item = layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)  # type: ignore[call-overload]

        columns = max(1, min(4, len(self._image_cards)))
        for idx, card in enumerate(self._image_cards):
            row, col = divmod(idx, columns)
            layout.addWidget(card, row, col)

    # ------------------------------------------------------------------
    # Role enforcement
    # ------------------------------------------------------------------

    def _enforce_unique_role(self, changed_card: ImageCard, new_role: str) -> None:
        """If another card already holds *new_role*, move it to a free role."""
        for card in self._image_cards:
            if card is changed_card:
                continue
            if card.role == new_role:
                used = {c.role for c in self._image_cards if c is not changed_card}
                free_roles = [r for r in IMAGE_ROLES if r not in used]
                if free_roles:
                    card.role = free_roles[0]
                break

    def _auto_assign_roles(self) -> None:
        """Assign roles based on filename keywords (front/side/top/persp)."""
        keyword_map = {
            "front": "front_image",
            "side": "side_image",
            "top": "top_image",
            "persp": "persp_image",
        }
        assigned: set[str] = set()
        for card in self._image_cards:
            if card._image_path is None:
                continue
            stem = card._image_path.stem.lower()
            for keyword, role in keyword_map.items():
                if keyword in stem and role not in assigned:
                    card.role = role
                    assigned.add(role)
                    break

    # ------------------------------------------------------------------
    # Public accessor for DB insertion
    # ------------------------------------------------------------------

    def get_image_blobs(self) -> dict[str, Optional[bytes]]:
        """Return a mapping of role name to image bytes (``None`` when unset).

        Example::

            {
                "front_image": b"...",
                "side_image":  b"...",
                "top_image":   None,
                "persp_image": b"...",
            }
        """
        result: dict[str, Optional[bytes]] = {role: None for role in IMAGE_ROLES}
        for card in self._image_cards:
            result[card.role] = card.image_data
        return result


def main() -> None:
    from PySide6.QtWidgets import QApplication

    from clutter_base.db.connection import connect_as_user
    from clutter_base.db.users import get_user_id, get_user_role

    app = QApplication([])
    # For standalone testing, prompt or hardcode credentials
    client, db = connect_as_user("clutter_admin", "clutter_pass")
    user_id = get_user_id("clutter_admin", db)
    role = get_user_role("clutter_admin", db) or "dbOwner"
    print(f"user_id={user_id}, role={role}")
    assert user_id is not None
    widget = AddMeshWidget(
        "clutter_admin",
        db,
        user_id,
        role,
        "/home/jmacey/Desktop/25-26/ClutterStarter/ExportedMeshes/SaltShakerShakerPepper_1",
    )
    widget.show()
    app.exec()


if __name__ == "__main__":
    main()
