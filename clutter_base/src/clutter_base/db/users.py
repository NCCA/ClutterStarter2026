"""User management helpers using MongoDB native RBAC authentication.

Passwords are handled entirely by MongoDB's ``db.createUser()`` /
``db.updateUser()`` mechanism.  The ``users`` collection is a metadata/profile
store only (username + role).

App-level roles map to MongoDB built-in roles:
  - ``app_user``  -> ``readWrite``
  - ``app_admin`` -> ``dbOwner``
"""

from __future__ import annotations

import logging
from typing import Optional

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import OperationFailure

__all__ = [
    "create_app_user",
    "create_app_admin",
    "remove_app_user",
    "get_user_role",
    "get_user_id",
    "user_exists",
    "update_user_password",
    "migrate_existing_users",
]


def _get_users_collection(database: Database) -> Collection:
    """Return the ``users`` collection, ensuring a unique index on ``username``."""
    collection = database["users"]
    collection.create_index("username", unique=True)
    return collection


# ------------------------------------------------------------------
# User creation
# ------------------------------------------------------------------


def create_app_user(username: str, password: str, db: Database) -> bool:
    """Create a new App User (MongoDB RBAC user + ``users`` collection doc).

    The caller must be connected as App Admin or Root so that
    ``db.command("createUser", ...)`` succeeds.
    Assigns the ``readWrite`` MongoDB role.

    Returns ``True`` on success, ``False`` if the user already exists.
    """
    if not username or not password:
        raise ValueError("username and password must be non-empty strings")

    collection = _get_users_collection(db)
    if collection.find_one({"username": username}, {"_id": 1}):
        return False

    try:
        db.command(
            "createUser",
            username,
            pwd=password,
            roles=[{"role": "readWrite", "db": db.name}],
        )
    except OperationFailure as exc:
        logging.error("Failed to create MongoDB user '%s': %s", username, exc)
        return False

    collection.insert_one({"username": username, "role": "app_user"})
    return True


def create_app_admin(username: str, password: str, db: Database) -> bool:
    """Create a new App Admin (MongoDB RBAC user + ``users`` collection doc).

    The caller must be connected as App Admin or Root.
    Assigns the ``dbOwner`` MongoDB role.

    Returns ``True`` on success, ``False`` if the user already exists.
    """
    if not username or not password:
        raise ValueError("username and password must be non-empty strings")

    collection = _get_users_collection(db)
    if collection.find_one({"username": username}, {"_id": 1}):
        return False

    try:
        db.command(
            "createUser",
            username,
            pwd=password,
            roles=[{"role": "dbOwner", "db": db.name}],
        )
    except OperationFailure as exc:
        logging.error("Failed to create MongoDB admin '%s': %s", username, exc)
        return False

    collection.insert_one({"username": username, "role": "app_admin"})
    return True


# ------------------------------------------------------------------
# User removal
# ------------------------------------------------------------------


def remove_app_user(username: str, db: Database) -> bool:
    """Remove a user: drop the MongoDB RBAC user and the ``users`` document.

    Returns ``True`` when both operations succeed.
    """
    if not username:
        raise ValueError("username must be provided")

    collection = _get_users_collection(db)

    try:
        db.command("dropUser", username)
    except OperationFailure as exc:
        logging.error("Failed to drop MongoDB user '%s': %s", username, exc)
        return False

    result = collection.delete_one({"username": username})
    return bool(result.deleted_count)


# ------------------------------------------------------------------
# Queries
# ------------------------------------------------------------------


def user_exists(username: str, db: Database) -> bool:
    """Return ``True`` when a user document exists for *username*."""
    if not username:
        return False
    collection = _get_users_collection(db)
    return bool(collection.find_one({"username": username}, {"_id": 1}))


def get_user_id(username: str, db: Database) -> Optional[ObjectId]:
    """Return the ``ObjectId`` of the user document, or ``None``."""
    if not username:
        return None
    collection = _get_users_collection(db)
    user = collection.find_one({"username": username}, {"_id": 1})
    return user.get("_id") if user else None


def get_user_role(username: str, db: Database) -> Optional[str]:
    """Return the role string (``'app_admin'`` or ``'app_user'``) or ``None``."""
    if not username:
        return None
    collection = _get_users_collection(db)
    user = collection.find_one({"username": username}, {"role": 1})
    return user.get("role") if user else None


# ------------------------------------------------------------------
# Password management
# ------------------------------------------------------------------


def update_user_password(username: str, new_password: str, db: Database) -> bool:
    """Update the MongoDB RBAC password for *username*.

    The caller must be connected as App Admin or Root.
    Returns ``True`` on success.
    """
    if not username or not new_password:
        raise ValueError("username and new_password must be non-empty strings")

    try:
        db.command("updateUser", username, pwd=new_password)
        return True
    except OperationFailure as exc:
        logging.error("Failed to update password for '%s': %s", username, exc)
        return False


# ------------------------------------------------------------------
# Role management
# ------------------------------------------------------------------


def promote_user(username: str, db: Database) -> bool:
    """Promote an App User to App Admin.

    Updates both the MongoDB RBAC role (readWrite -> dbOwner) and the
    ``users`` collection document.
    """
    if not username:
        raise ValueError("username must be provided")

    collection = _get_users_collection(db)
    user = collection.find_one({"username": username})
    if not user or user.get("role") != "app_user":
        return False

    try:
        db.command(
            "grantRolesToUser",
            username,
            roles=[{"role": "dbOwner", "db": db.name}],
        )
        db.command(
            "revokeRolesFromUser",
            username,
            roles=[{"role": "readWrite", "db": db.name}],
        )
    except OperationFailure as exc:
        logging.error("Failed to promote user '%s': %s", username, exc)
        return False

    collection.update_one({"username": username}, {"$set": {"role": "app_admin"}})
    return True


def demote_user(username: str, db: Database) -> bool:
    """Demote an App Admin to App User.

    Updates both the MongoDB RBAC role (dbOwner -> readWrite) and the
    ``users`` collection document.
    """
    if not username:
        raise ValueError("username must be provided")

    collection = _get_users_collection(db)
    user = collection.find_one({"username": username})
    if not user or user.get("role") != "app_admin":
        return False

    try:
        db.command(
            "grantRolesToUser",
            username,
            roles=[{"role": "readWrite", "db": db.name}],
        )
        db.command(
            "revokeRolesFromUser",
            username,
            roles=[{"role": "dbOwner", "db": db.name}],
        )
    except OperationFailure as exc:
        logging.error("Failed to demote user '%s': %s", username, exc)
        return False

    collection.update_one({"username": username}, {"$set": {"role": "app_user"}})
    return True


# ------------------------------------------------------------------
# Migration
# ------------------------------------------------------------------


def migrate_existing_users(db: Database) -> int:
    """Set ``role: 'app_user'`` on any user documents missing a ``role`` field.

    Returns the number of documents updated.  This function is idempotent.
    """
    collection = _get_users_collection(db)
    result = collection.update_many(
        {"role": {"$exists": False}},
        {"$set": {"role": "app_user"}},
    )
    return result.modified_count
