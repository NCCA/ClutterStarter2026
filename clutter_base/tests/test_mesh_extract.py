import gridfs
import pytest
from bson import ObjectId
from clutter_base.db.schema import Asset


def test_extract_obj_mesh(admin_conn, tmp_path):
    mesh_dir = tmp_path / "mesh"
    mesh_dir.mkdir()
    obj_path = mesh_dir / "example.obj"
    obj_path.write_text("# this is an obj test")
    mtl_path = mesh_dir / "example.mtl"
    mtl_path.write_text("# this is a mtl file")
    asset = Asset(
        name="Extracted obj",
        description="a test obj file",
        keywords=["obj", "extract"],
        file_type="obj",
        mesh_file_id=str(obj_path),
    )
    mesh_id = admin_conn.add_asset(asset)
    assert mesh_id
    try:
        destination = tmp_path / "extracted"
        result_path = admin_conn.extract_mesh_files(mesh_id, str(destination))
        assert result_path == destination / mesh_id
        assert (result_path / obj_path.name).is_file()
        assert (result_path / mtl_path.name).is_file()
    finally:
        doc = admin_conn.db["assets"].find_one({"_id": ObjectId(mesh_id)})
        if doc:
            mesh_file_id = doc.get("mesh_file_id")
            if mesh_file_id:
                gridfs.GridFS(admin_conn.db).delete(mesh_file_id)
        admin_conn.db["assets"].delete_one({"_id": ObjectId(mesh_id)})
