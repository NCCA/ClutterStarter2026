"""Tests for ownership enforcement in the Connection class.

Validates that:
- App Users can only delete/update their own assets
- App Admins can delete/update any asset
- user_id is always set to the authenticated user on add
"""

from __future__ import annotations

import pytest
from bson import ObjectId

from clutter_base.db.connection import Connection
from clutter_base.db.schema import Asset


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _insert_asset(conn: Connection, name: str = "TestAsset") -> str:
    """Insert a minimal asset and return its string id."""
    asset = Asset(
        name=name,
        description="test",
        keywords=["test"],
        file_type="obj",
    )
    return conn.add_item("assets", asset)


# ------------------------------------------------------------------
# user_id stamping
# ------------------------------------------------------------------


def test_add_item_stamps_user_id(user_conn):
    """Adding an item automatically sets user_id to the authenticated user."""
    item_id = _insert_asset(user_conn)
    try:
        doc = user_conn.db["assets"].find_one({"_id": ObjectId(item_id)})
        assert doc is not None
        assert doc["user_id"] == user_conn.user_id
    finally:
        user_conn.delete_item("assets", item_id)


# ------------------------------------------------------------------
# Delete ownership
# ------------------------------------------------------------------


def test_user_can_delete_own_asset(user_conn):
    """App User can delete their own asset."""
    item_id = _insert_asset(user_conn)
    user_conn.delete_item("assets", item_id)
    assert user_conn.db["assets"].find_one({"_id": ObjectId(item_id)}) is None


def test_user_cannot_delete_other_users_asset(admin_conn, user_conn):
    """App User cannot delete an asset owned by another user."""
    # Admin creates an asset (owned by admin)
    item_id = _insert_asset(admin_conn, name="AdminAsset")
    try:
        with pytest.raises(PermissionError):
            user_conn.delete_item("assets", item_id)
    finally:
        # Clean up using admin
        admin_conn.delete_item("assets", item_id)


def test_admin_can_delete_any_asset(admin_conn, user_conn):
    """App Admin can delete another user's asset."""
    # User creates an asset
    item_id = _insert_asset(user_conn, name="UserAssetForAdmin")
    admin_conn.delete_item("assets", item_id)
    assert admin_conn.db["assets"].find_one({"_id": ObjectId(item_id)}) is None


# ------------------------------------------------------------------
# Update ownership
# ------------------------------------------------------------------


def test_user_can_update_own_asset(user_conn):
    """App User can update their own asset."""
    item_id = _insert_asset(user_conn)
    try:
        user_conn.update_item("assets", item_id, {"description": "updated"})
        doc = user_conn.db["assets"].find_one({"_id": ObjectId(item_id)})
        assert doc["description"] == "updated"
    finally:
        user_conn.delete_item("assets", item_id)


def test_user_cannot_update_other_users_asset(admin_conn, user_conn):
    """App User cannot update an asset owned by another user."""
    item_id = _insert_asset(admin_conn, name="AdminOnly")
    try:
        with pytest.raises(PermissionError):
            user_conn.update_item("assets", item_id, {"description": "hacked"})
    finally:
        admin_conn.delete_item("assets", item_id)


def test_admin_can_update_any_asset(admin_conn, user_conn):
    """App Admin can update another user's asset."""
    item_id = _insert_asset(user_conn, name="UserAssetForAdminUpdate")
    try:
        admin_conn.update_item("assets", item_id, {"description": "admin-updated"})
        doc = admin_conn.db["assets"].find_one({"_id": ObjectId(item_id)})
        assert doc["description"] == "admin-updated"
    finally:
        admin_conn.delete_item("assets", item_id)
