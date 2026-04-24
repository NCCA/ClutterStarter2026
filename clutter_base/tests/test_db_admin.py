"""Tests for user management functions (create, remove, role, password)."""

from __future__ import annotations

from uuid import uuid4

import bson
import pytest

from clutter_base.db.users import (
    create_app_admin,
    create_app_user,
    get_user_id,
    get_user_role,
    remove_app_user,
    update_user_password,
)


# ------------------------------------------------------------------
# Basic connectivity
# ------------------------------------------------------------------


def test_admin_can_ping_database(admin_connection):
    client, db = admin_connection
    server_info = client.admin.command("ping")
    assert server_info.get("ok") == 1.0
    assert db.name


def test_admin_can_list_collections(admin_connection):
    _, db = admin_connection
    collections = db.list_collection_names()
    assert isinstance(collections, list)


# ------------------------------------------------------------------
# User CRUD — uses admin_connection to manage users
# ------------------------------------------------------------------


@pytest.fixture
def user_tracker(admin_connection):
    """Create users via admin and clean up after the test."""
    _, db = admin_connection
    tracked: list[str] = []

    def track(username: str) -> None:
        tracked.append(username)

    yield db, track

    for username in tracked:
        # Best-effort cleanup: remove RBAC user + users doc
        try:
            remove_app_user(username, db)
        except Exception:
            # Fall back to just removing the document
            db["users"].delete_many({"username": username})


def test_create_app_user(user_tracker):
    db, track = user_tracker
    username = f"test_create_user_{uuid4().hex[:8]}"
    track(username)
    assert create_app_user(username, "pass123", db)
    # Duplicate creation should return False
    assert not create_app_user(username, "pass123", db)


def test_create_app_admin(user_tracker):
    db, track = user_tracker
    username = f"test_create_admin_{uuid4().hex[:8]}"
    track(username)
    assert create_app_admin(username, "adminpass", db)
    assert get_user_role(username, db) == "app_admin"


def test_remove_app_user(user_tracker):
    db, track = user_tracker
    username = f"test_remove_{uuid4().hex[:8]}"
    track(username)
    assert create_app_user(username, "secret", db)
    assert remove_app_user(username, db)
    # Second removal should fail
    assert not remove_app_user(username, db)


def test_get_user_id(user_tracker):
    db, track = user_tracker
    username = f"test_get_id_{uuid4().hex[:8]}"
    track(username)
    assert create_app_user(username, "secret", db)
    user_id = get_user_id(username, db)
    assert isinstance(user_id, bson.ObjectId)
    assert db["users"].find_one({"_id": user_id})["username"] == username


def test_get_user_role(user_tracker):
    db, track = user_tracker
    username = f"test_role_{uuid4().hex[:8]}"
    track(username)
    assert create_app_user(username, "pass", db)
    assert get_user_role(username, db) == "app_user"


def test_update_user_password(user_tracker):
    """After updating the password, the user should be able to connect with the new one."""
    db, track = user_tracker
    username = f"test_update_pw_{uuid4().hex[:8]}"
    track(username)
    assert create_app_user(username, "first", db)
    assert update_user_password(username, "second", db)

    # Verify the new password works by connecting
    from clutter_base.db.connection import connect_as_user

    client, _ = connect_as_user(username, "second")
    client.close()
