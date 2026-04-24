"""Tests for the asset collection and Connection CRUD methods."""

from bson import ObjectId

from clutter_base.db.connection import create_asset_collection
from clutter_base.db.schema import Asset


def test_create_asset_collection(admin_connection):
    _, db = admin_connection
    create_asset_collection(db)


def test_add_item_via_admin(admin_conn):
    """Admin can add and delete an item."""
    asset = Asset(
        name="Test",
        description="This is the description",
        keywords=["do", "these", "show"],
        file_type="obj",
        user_id=str(ObjectId()),
    )
    inserted_id = admin_conn.add_item("assets", asset)
    assert inserted_id is not None

    # user_id should have been overridden to the admin's own id
    doc = admin_conn.db["assets"].find_one({"_id": ObjectId(inserted_id)})
    assert doc["user_id"] == admin_conn.user_id

    # Clean up
    admin_conn.delete_item("assets", inserted_id)
    result = admin_conn.db["assets"].find_one({"_id": ObjectId(inserted_id)})
    assert result is None


def test_add_item_via_user(user_conn):
    """App User can add an item and user_id is stamped correctly."""
    asset = Asset(
        name="UserAsset",
        description="User-created asset",
        keywords=["test"],
        file_type="obj",
    )
    inserted_id = user_conn.add_item("assets", asset)
    assert inserted_id is not None

    doc = user_conn.db["assets"].find_one({"_id": ObjectId(inserted_id)})
    assert doc["user_id"] == user_conn.user_id

    # Clean up
    user_conn.delete_item("assets", inserted_id)
