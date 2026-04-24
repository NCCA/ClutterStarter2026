#!/usr/bin/env -S uv run --script
"""Admin CLI tool for managing ClutterBase users.

Usage examples::

    clutter-admin create-user  --username jsmith --password temp123
    clutter-admin remove-user  --username jsmith
    clutter-admin list-users
    clutter-admin change-password --username jsmith --password newpass
    clutter-admin promote-user --username jsmith
    clutter-admin demote-user  --username jsmith

The caller must authenticate as an App Admin (or Root).
"""

from __future__ import annotations

import argparse
import getpass
import sys

from clutter_base.db.connection import connect_as_user
from clutter_base.db.users import (
    create_app_admin,
    create_app_user,
    demote_user,
    promote_user,
    remove_app_user,
    update_user_password,
)


def _get_admin_connection(args: argparse.Namespace):
    """Prompt for admin credentials and return the database handle."""
    admin_user = args.admin_user or input("Admin username: ")
    admin_pass = args.admin_pass or getpass.getpass("Admin password: ")
    try:
        client, db = connect_as_user(admin_user, admin_pass)
        return client, db
    except Exception as exc:
        print(f"Failed to connect as admin: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_create_user(args: argparse.Namespace) -> None:
    """Create a new App User."""
    client, db = _get_admin_connection(args)
    try:
        if create_app_user(args.username, args.password, db):
            print(f"App User '{args.username}' created.")
        else:
            print(f"User '{args.username}' already exists.", file=sys.stderr)
            sys.exit(1)
    finally:
        client.close()


def cmd_create_admin(args: argparse.Namespace) -> None:
    """Create a new App Admin."""
    client, db = _get_admin_connection(args)
    try:
        if create_app_admin(args.username, args.password, db):
            print(f"App Admin '{args.username}' created.")
        else:
            print(f"User '{args.username}' already exists.", file=sys.stderr)
            sys.exit(1)
    finally:
        client.close()


def cmd_remove_user(args: argparse.Namespace) -> None:
    """Remove a user (both MongoDB RBAC and users collection)."""
    client, db = _get_admin_connection(args)
    try:
        if remove_app_user(args.username, db):
            print(f"User '{args.username}' removed.")
        else:
            print(f"Failed to remove user '{args.username}'.", file=sys.stderr)
            sys.exit(1)
    finally:
        client.close()


def cmd_list_users(args: argparse.Namespace) -> None:
    """List all users in the users collection."""
    client, db = _get_admin_connection(args)
    try:
        users = db["users"].find({}, {"username": 1, "role": 1, "_id": 0})
        for user in users:
            print(f"  {user.get('username', '?'):20s}  {user.get('role', '?')}")
    finally:
        client.close()


def cmd_change_password(args: argparse.Namespace) -> None:
    """Change a user's MongoDB password."""
    client, db = _get_admin_connection(args)
    try:
        if update_user_password(args.username, args.password, db):
            print(f"Password updated for '{args.username}'.")
        else:
            print(
                f"Failed to update password for '{args.username}'.",
                file=sys.stderr,
            )
            sys.exit(1)
    finally:
        client.close()


def cmd_promote_user(args: argparse.Namespace) -> None:
    """Promote an App User to App Admin."""
    client, db = _get_admin_connection(args)
    try:
        if promote_user(args.username, db):
            print(f"User '{args.username}' promoted to App Admin.")
        else:
            print(
                f"Failed to promote '{args.username}'. User may not exist or is already an admin.",
                file=sys.stderr,
            )
            sys.exit(1)
    finally:
        client.close()


def cmd_demote_user(args: argparse.Namespace) -> None:
    """Demote an App Admin to App User."""
    client, db = _get_admin_connection(args)
    try:
        if demote_user(args.username, db):
            print(f"User '{args.username}' demoted to App User.")
        else:
            print(
                f"Failed to demote '{args.username}'. User may not exist or is already an app_user.",
                file=sys.stderr,
            )
            sys.exit(1)
    finally:
        client.close()


def main() -> None:
    """Entry point for the ``clutter-admin`` CLI."""
    parser = argparse.ArgumentParser(
        prog="clutter-admin",
        description="ClutterBase admin tool for user management",
    )

    # Global admin auth arguments
    parser.add_argument(
        "--admin-user",
        help="Admin username for authentication (prompted if omitted)",
    )
    parser.add_argument(
        "--admin-pass",
        help="Admin password for authentication (prompted if omitted)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-user
    p_create = subparsers.add_parser("create-user", help="Create a new App User")
    p_create.add_argument("--username", required=True, help="New user's username")
    p_create.add_argument("--password", required=True, help="New user's password")
    p_create.set_defaults(func=cmd_create_user)

    # create-admin
    p_cadmin = subparsers.add_parser("create-admin", help="Create a new App Admin")
    p_cadmin.add_argument("--username", required=True, help="New admin's username")
    p_cadmin.add_argument("--password", required=True, help="New admin's password")
    p_cadmin.set_defaults(func=cmd_create_admin)

    # remove-user
    p_remove = subparsers.add_parser("remove-user", help="Remove a user")
    p_remove.add_argument("--username", required=True, help="Username to remove")
    p_remove.set_defaults(func=cmd_remove_user)

    # list-users
    p_list = subparsers.add_parser("list-users", help="List all users")
    p_list.set_defaults(func=cmd_list_users)

    # change-password
    p_passwd = subparsers.add_parser("change-password", help="Change a user's password")
    p_passwd.add_argument("--username", required=True, help="Username")
    p_passwd.add_argument("--password", required=True, help="New password")
    p_passwd.set_defaults(func=cmd_change_password)

    # promote-user
    p_promote = subparsers.add_parser("promote-user", help="Promote App User to App Admin")
    p_promote.add_argument("--username", required=True, help="Username to promote")
    p_promote.set_defaults(func=cmd_promote_user)

    # demote-user
    p_demote = subparsers.add_parser("demote-user", help="Demote App Admin to App User")
    p_demote.add_argument("--username", required=True, help="Username to demote")
    p_demote.set_defaults(func=cmd_demote_user)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
