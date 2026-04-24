#!/usr/bin/env -S uv run --script
#
"""Add a single mesh asset to the ClutterBase database.

The caller must supply their own MongoDB username and password.
"""

import argparse

from clutter_base.db import Asset, Connection, connect_as_user, get_user_id, user_exists


def add_mesh(args: argparse.Namespace) -> None:
    client, db = connect_as_user(args.username, args.password)
    try:
        if not user_exists(args.username, db):
            print(f"User {args.username} does not exist in the users collection")
            return
        user_id = get_user_id(args.username, db)
        if user_id is None:
            print(f"Could not resolve user_id for {args.username}")
            return

        from clutter_base.db.users import get_user_role

        role = get_user_role(args.username, db) or "app_user"

        asset = Asset(
            name=args.name,
            file_type=args.type,
            description=args.description,
            top_image=args.top,
            side_image=args.side,
            front_image=args.front,
            persp_image=args.persp,
            mesh_file_id=args.mesh,
        )
        with Connection(db, user_id, role) as conn:
            conn.add_asset(asset)
    finally:
        client.close()


def main() -> None:
    parser_args = [
        ("--username", "-u", "Your MongoDB username", True, None),
        ("--password", "-p", "Your MongoDB password", True, None),
        ("--mesh", "-m", "Path to the mesh to load", True, None),
        ("--name", "-n", "Name of the asset in the database", True, None),
        ("--type", "-t", "Mesh type must be obj, usd or fbx", True, None),
        ("--description", "-d", "Description of the asset", False, ""),
        ("--top", "-T", "Top Image", False, None),
        ("--side", "-s", "Side Image", False, None),
        ("--front", "-f", "Front Image", False, None),
        ("--persp", "-i", "Perspective Image", False, None),
    ]
    parser = argparse.ArgumentParser(description="add mesh to database")
    for long_arg, short_arg, help_text, required, default in parser_args:
        parser.add_argument(
            long_arg, short_arg, help=help_text, required=required, default=default
        )
    args = parser.parse_args()
    add_mesh(args)


if __name__ == "__main__":
    main()
