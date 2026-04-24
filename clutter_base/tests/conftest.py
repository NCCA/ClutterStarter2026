"""Shared pytest fixtures for ClutterBase integration tests.

These fixtures require a running MongoDB container (``task up``).

A session-scoped fixture bootstraps two test users:
  * ``test_admin`` — an App Admin
  * ``test_user``  — an App User

Individual test modules receive ``Connection`` objects already bound to one
of these identities.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from clutter_base.db.connection import _connect_as_root, connect_as_user, Connection
from clutter_base.db.users import (
    create_app_admin,
    create_app_user,
    get_user_id,
    remove_app_user,
)

# Unique suffix so parallel test runs don't collide
_SUFFIX = uuid4().hex[:8]
TEST_ADMIN_USER = f"test_admin_{_SUFFIX}"
TEST_ADMIN_PASS = "admin_pass_123"
TEST_USER_USER = f"test_user_{_SUFFIX}"
TEST_USER_PASS = "user_pass_123"


@pytest.fixture(scope="session")
def root_connection():
    """Connect as the MongoDB root user.  Used only for bootstrap."""
    client, db = _connect_as_root(server_selection_timeout_ms=5000)
    try:
        yield client, db
    finally:
        client.close()


@pytest.fixture(scope="session")
def bootstrap_test_users(root_connection):
    """Create the two test users (admin + user) before any tests run."""
    _, db = root_connection

    assert create_app_admin(TEST_ADMIN_USER, TEST_ADMIN_PASS, db), (
        f"Failed to create test admin {TEST_ADMIN_USER}"
    )
    assert create_app_user(TEST_USER_USER, TEST_USER_PASS, db), (
        f"Failed to create test user {TEST_USER_USER}"
    )

    yield

    # Teardown: remove test users
    remove_app_user(TEST_ADMIN_USER, db)
    remove_app_user(TEST_USER_USER, db)


@pytest.fixture(scope="session")
def admin_connection(bootstrap_test_users):
    """Yield a (client, db) pair authenticated as the test App Admin."""
    client, db = connect_as_user(
        TEST_ADMIN_USER, TEST_ADMIN_PASS, server_selection_timeout_ms=5000
    )
    try:
        yield client, db
    finally:
        client.close()


@pytest.fixture(scope="session")
def user_connection(bootstrap_test_users):
    """Yield a (client, db) pair authenticated as the test App User."""
    client, db = connect_as_user(
        TEST_USER_USER, TEST_USER_PASS, server_selection_timeout_ms=5000
    )
    try:
        yield client, db
    finally:
        client.close()


@pytest.fixture
def admin_conn(admin_connection) -> Connection:
    """Return a ``Connection`` object for the test admin."""
    _, db = admin_connection
    user_id = get_user_id(TEST_ADMIN_USER, db)
    assert user_id is not None
    return Connection(db, user_id, "app_admin")


@pytest.fixture
def user_conn(user_connection) -> Connection:
    """Return a ``Connection`` object for the test user."""
    _, db = user_connection
    user_id = get_user_id(TEST_USER_USER, db)
    assert user_id is not None
    return Connection(db, user_id, "app_user")
