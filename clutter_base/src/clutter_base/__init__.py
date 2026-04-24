from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("clutter-base")  # pragma: no cover
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
__author__ = "Jon Macey jmacey@bournemouth.ac.uk"
__license__ = "MIT"


SUPPORTED_MESH_EXTENSIONS = [".obj", ".usd", ".usda", "usdc", "usdz", "fbx"]
SUPPORTED_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".tif"]


def main() -> None:
    print(f"clutter-base version {__version__}")
