from dataclasses import dataclass, field
from typing import Optional

from bson import ObjectId

USERS_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["username", "role"],
        "properties": {
            "username": {"bsonType": "string"},
            "role": {"enum": ["app_admin", "app_user"]},
        },
    }
}

ASSET_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "file_type", "user_id"],
        "properties": {
            "name": {"bsonType": "string", "description": "Asset name"},
            "description": {"bsonType": "string", "description": "Asset description"},
            "keywords": {
                "bsonType": "array",
                "items": {"bsonType": "string"},
                "description": "Search keywords",
            },
            "user_id": {
                "bsonType": "objectId",
                "description": "Reference to users collection",
            },
            "file_type": {"enum": ["obj", "usd", "usda"]},
            "top_image": {"bsonType": "binData"},
            "persp_image": {"bsonType": "binData"},
            "side_image": {"bsonType": "binData"},
            "front_image": {"bsonType": "binData"},
            "mesh_file_id": {"bsonType": "objectId"},
        },
    }
}


@dataclass
class Asset:
    name: str = ""
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    user_id: Optional[str] = None
    file_type: Optional[str] = None
    top_image: Optional[bytes] = None
    persp_image: Optional[bytes] = None
    side_image: Optional[bytes] = None
    front_image: Optional[bytes] = None
    mesh_file_id: Optional[str] = None

    def to_dict(self) -> dict:
        data: dict = {
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
        }
        if self.user_id is not None:
            data["user_id"] = ObjectId(self.user_id)
        if self.file_type is not None:
            data["file_type"] = self.file_type
        if self.top_image is not None:
            data["top_image"] = self.top_image
        if self.persp_image is not None:
            data["persp_image"] = self.persp_image
        if self.side_image is not None:
            data["side_image"] = self.side_image
        if self.front_image is not None:
            data["front_image"] = self.front_image
        if self.mesh_file_id is not None:
            data["mesh_file_id"] = self.mesh_file_id
        return data
