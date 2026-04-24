"""MongoDB connection helpers with per-user RBAC authentication."""

from __future__ import annotations

import io
import logging
import os
import zipfile
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote_plus

import gridfs
from bson import ObjectId
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import CollectionInvalid, PyMongoError

from .schema import ASSET_SCHEMA, Asset

_DEFAULT_DB = "clutter_base"


def connect_as_user(
    username: str,
    password: str,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    server_selection_timeout_ms: int = 5000,
) -> Tuple[MongoClient, Database]:
    """Connect to MongoDB using the caller's own credentials.

    If the ``MONGO_URI`` environment variable is set, it is used as-is with
    *username* and *password* substituted into the URI.  Otherwise the URI is
    constructed from *host*, *port* and the target database name.

    Parameters
    ----------
    username:
        MongoDB username (required — never read from env).
    password:
        MongoDB password (required — never read from env).
    host:
        Server hostname.  Falls back to ``DB_HOST`` env var, then ``127.0.0.1``.
    port:
        Server port.  Falls back to ``DB_PORT`` env var, then ``27017``.
    database:
        Target database name.  Falls back to ``MONGO_INITDB_DATABASE`` /
        ``DATABASE_NAME`` env vars, then ``clutter_base``.
    server_selection_timeout_ms:
        Milliseconds to wait before declaring the server unreachable.

    Returns
    -------
    tuple[MongoClient, Database]
        A connected client and the target database handle.

    Raises
    ------
    pymongo.errors.PyMongoError
        When the server cannot be reached or credentials are invalid.
    """
    if not username or not password:
        raise ValueError("username and password must be non-empty strings")

    target_db = (
        database
        or os.getenv("MONGO_INITDB_DATABASE")
        or os.getenv("DATABASE_NAME")
        or _DEFAULT_DB
    )

    mongo_uri = os.getenv("MONGO_URI")
    if mongo_uri:
        # Substitute credentials into the template URI.
        uri = mongo_uri.replace("<username>", quote_plus(username)).replace(
            "<password>", quote_plus(password)
        )
    else:
        host = host or os.getenv("DB_HOST") or "127.0.0.1"
        port = port or int(os.getenv("DB_PORT", "27017"))
        auth_db = os.getenv("MONGO_INITDB_DATABASE") or target_db
        uri = (
            f"mongodb://{quote_plus(username)}:{quote_plus(password)}"
            f"@{host}:{port}/{target_db}?authSource={auth_db}"
        )

    client: MongoClient = MongoClient(
        uri, serverSelectionTimeoutMS=server_selection_timeout_ms
    )
    client.admin.command("ping")
    return client, client[target_db]


def _connect_as_root(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    server_selection_timeout_ms: int = 5000,
) -> Tuple[MongoClient, Database]:
    """Connect as the MongoDB root user.  Internal use only.

    Credentials are read from ``MONGO_INITDB_ROOT_USERNAME`` /
    ``MONGO_INITDB_ROOT_PASSWORD`` environment variables.
    """
    root_user = os.getenv("MONGO_INITDB_ROOT_USERNAME")
    root_pass = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
    if not root_user or not root_pass:
        raise RuntimeError(
            "MONGO_INITDB_ROOT_USERNAME and MONGO_INITDB_ROOT_PASSWORD "
            "must be set for root connections"
        )

    host = host or os.getenv("DB_HOST") or "127.0.0.1"
    port = port or int(os.getenv("DB_PORT", "27017"))
    target_db = (
        database
        or os.getenv("MONGO_INITDB_DATABASE")
        or os.getenv("DATABASE_NAME")
        or _DEFAULT_DB
    )

    uri = (
        f"mongodb://{quote_plus(root_user)}:{quote_plus(root_pass)}"
        f"@{host}:{port}/{target_db}?authSource=admin"
    )
    client: MongoClient = MongoClient(
        uri, serverSelectionTimeoutMS=server_selection_timeout_ms
    )
    client.admin.command("ping")
    return client, client[target_db]


def create_asset_collection(db: Database) -> None:
    """Ensure the ``assets`` collection exists with schema validation."""
    try:
        db.create_collection("assets", validator=ASSET_SCHEMA, validationLevel="strict")
    except CollectionInvalid:
        pass  # already exists


class Connection:
    """Database session bound to an authenticated user.

    Enforces ownership rules: App Users may only delete/update their own
    assets, while App Admins may operate on any asset.

    Parameters
    ----------
    db:
        A pymongo ``Database`` handle (already authenticated).
    user_id:
        The ``_id`` of the authenticated user in the ``users`` collection.
    role:
        Either ``"app_admin"`` or ``"app_user"``.
    """

    def __init__(self, db: Database, user_id: ObjectId, role: str) -> None:
        self.db: Optional[Database] = db
        self.client: Optional[MongoClient] = db.client  # type: ignore[assignment]
        self.user_id: ObjectId = user_id
        self.role: str = role

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def _close(self) -> None:
        self.db = None
        self.client = None

    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self._close()

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------

    def add_item(self, collection: str, item: Asset) -> str:
        """Insert an item document, automatically stamping ``user_id``."""
        if self.db is None:
            raise RuntimeError("Connection not open")
        item.user_id = str(self.user_id)
        try:
            result = self.db[collection].insert_one(item.to_dict())
            return str(result.inserted_id)
        except PyMongoError as e:
            raise RuntimeError(f"Failed to add item: {e}")

    def _zip_mesh_file(self, mesh_path: Path) -> io.BytesIO:
        """Return an in-memory ZIP archive containing the mesh file.

        If *mesh_path* is an OBJ file and a companion MTL file exists in the
        same directory (same stem, ``.mtl`` suffix), both files are included in
        the archive.

        Parameters
        ----------
        mesh_path:
            Absolute or relative path to the mesh file to zip.

        Returns
        -------
        io.BytesIO
            Seeked-to-start in-memory ZIP buffer ready for reading.
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(mesh_path, arcname=mesh_path.name)

            if mesh_path.suffix.lower() == ".obj":
                mtl_path = mesh_path.with_suffix(".mtl")
                if mtl_path.is_file():
                    zf.write(mtl_path, arcname=mtl_path.name)
                    logging.info("Including companion MTL file: %s", mtl_path.name)
                else:
                    logging.warning(
                        "No companion MTL file found for %s", mesh_path.name
                    )

        buf.seek(0)
        return buf

    def add_asset(self, asset: Asset) -> str:
        """Insert an asset with images and a GridFS-stored mesh archive.

        The ``user_id`` is always set to the authenticated user's ``_id``,
        regardless of what the caller passes, preventing impersonation.
        """
        if self.db is None:
            raise RuntimeError("Connection not open")
        if not asset.mesh_file_id:
            raise ValueError("Asset mesh_file_id must be set before calling add_asset")

        # Force ownership to the authenticated user
        asset.user_id = str(self.user_id)

        try:
            fs = gridfs.GridFS(self.db)

            def resolve_image(value: object) -> object:
                return self.load_blob(value) if isinstance(value, str) else value

            asset.top_image = resolve_image(asset.top_image)  # type: ignore[assignment]
            asset.side_image = resolve_image(asset.side_image)  # type: ignore[assignment]
            asset.front_image = resolve_image(asset.front_image)  # type: ignore[assignment]
            asset.persp_image = resolve_image(asset.persp_image)  # type: ignore[assignment]
            asset_id = self.db["assets"].insert_one(asset.to_dict()).inserted_id

            # Zip the mesh file (and its companion MTL if OBJ) then store in GridFS
            mesh_path = Path(asset.mesh_file_id)
            zip_buf = self._zip_mesh_file(mesh_path)
            zip_filename = f"{asset_id}.zip"
            file_id = fs.put(
                zip_buf, filename=zip_filename, metadata={"mesh_id": asset_id}
            )

            self.db["assets"].update_one(
                {"_id": asset_id}, {"$set": {"mesh_file_id": file_id}}
            )
            logging.info("Item '%s' added successfully.", asset.name)
            return str(asset_id)

        except PyMongoError as e:
            raise RuntimeError(f"Failed to add asset: {e}")

    def load_blob(self, file_path: str) -> bytes:
        """Load a file as binary and return the raw bytes.

        Parameters
        ----------
        file_path:
            Path to the file to load.
        """
        if not file_path:
            logging.warning("File path is empty")
            return b""

        path = Path(file_path)
        if not path.is_file():
            logging.warning("File not found: %s", file_path)
            return b""

        return path.read_bytes()

    # ------------------------------------------------------------------
    # Ownership-aware delete / update
    # ------------------------------------------------------------------

    def _check_ownership(self, collection: str, item_id: str) -> None:
        """Raise ``PermissionError`` if the current user may not modify *item_id*."""
        if self.role == "app_admin":
            return  # admins can modify anything

        if self.db is None:
            raise RuntimeError("Connection not open")

        doc = self.db[collection].find_one({"_id": ObjectId(item_id)}, {"user_id": 1})
        if doc is None:
            raise RuntimeError(f"Item {item_id} not found in {collection}")

        if doc.get("user_id") != self.user_id:
            raise PermissionError(f"User {self.user_id} does not own item {item_id}")

    def delete_item(self, collection: str, item_id: str) -> None:
        """Delete an item.  App Users can only delete their own assets."""
        if self.db is None:
            raise RuntimeError("Connection not open")
        self._check_ownership(collection, item_id)
        try:
            self.db[collection].delete_one({"_id": ObjectId(item_id)})
        except PyMongoError as e:
            raise RuntimeError(f"Failed to delete item: {e}")

    def update_item(self, collection: str, item_id: str, updates: dict) -> None:
        """Update fields on an item.  App Users can only update their own assets."""
        if self.db is None:
            raise RuntimeError("Connection not open")
        self._check_ownership(collection, item_id)
        try:
            self.db[collection].update_one(
                {"_id": ObjectId(item_id)}, {"$set": updates}
            )
        except PyMongoError as e:
            raise RuntimeError(f"Failed to update item: {e}")
