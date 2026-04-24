#!/usr/bin/env -S uv run --script
#
"""Recursively add all mesh assets from a folder to the ClutterBase database.

The caller must supply their own MongoDB username and password.
"""

import argparse
from pathlib import Path

from bson import ObjectId

from clutter_base import SUPPORTED_IMAGE_EXTENSIONS, SUPPORTED_MESH_EXTENSIONS
from clutter_base.db import Asset, Connection, connect_as_user, get_user_id, user_exists
from clutter_base.db.users import get_user_role


def add_mesh(
    user_id: ObjectId,
    role: str,
    folder: Path,
    db: object,
) -> None:
    """Add a single mesh asset found in *folder*."""
    # Locate the mesh file
    mesh: str = ""
    file_type: str = ""
    name: str = folder.name
    for file in folder.glob("*"):
        if file.suffix.lower() in SUPPORTED_MESH_EXTENSIONS:
            mesh = str(file)
            file_type = file.suffix.lower()[1:]
            name = folder.name
            break

    if not mesh:
        return

    # Locate the image files
    top = None
    side = None
    front = None
    persp = None
    for file in folder.glob("*"):
        if file.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            if "top" in file.name.lower():
                top = str(file)
            elif "side" in file.name.lower():
                side = str(file)
            elif "front" in file.name.lower():
                front = str(file)
            elif "persp" in file.name.lower():
                persp = str(file)

    asset = Asset(
        name=name,
        file_type=file_type,
        description="inserted from add_folder",
        keywords=[name],
        top_image=top,  # type: ignore[arg-type]  # str paths resolved by add_asset
        side_image=side,  # type: ignore[arg-type]
        front_image=front,  # type: ignore[arg-type]
        persp_image=persp,  # type: ignore[arg-type]
        mesh_file_id=mesh,
    )
    with Connection(db, user_id, role) as conn:
        print(f"adding asset: {name}")
        conn.add_asset(asset)


def find_meshes(user_id: ObjectId, role: str, folder: Path, db: object) -> None:
    """Recursively find and add all mesh assets under *folder*."""
    for file in folder.rglob("*"):
        if file.suffix in SUPPORTED_MESH_EXTENSIONS:
            add_mesh(user_id, role, file.parent, db)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a folder of meshes to the clutter base."
    )
    parser.add_argument("--username", "-u", required=True, help="Your MongoDB username")
    parser.add_argument("--password", "-p", required=True, help="Your MongoDB password")
    parser.add_argument("folder", type=str, help="Path to the folder to add.")
    args = parser.parse_args()

    client, db = connect_as_user(args.username, args.password)
    try:
        if not user_exists(args.username, db):
            print(f"User {args.username} does not exist in the users collection")
            return
        user_id = get_user_id(args.username, db)
        if user_id is None:
            print(f"Could not resolve user_id for {args.username}")
            return
        role = get_user_role(args.username, db) or "app_user"
        find_meshes(user_id, role, Path(args.folder), db)
    finally:
        client.close()


if __name__ == "__main__":
    main()
