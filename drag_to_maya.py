import importlib
import sys
import textwrap
from pathlib import Path
from typing import Optional

import maya.cmds as cmds
import maya.mel as mel

SHELF_NAME = "ClutterBase"
SHELF_LABEL = "ClutterBase"
MODULE_NAME: str = "ClutterBase2026"
BUTTON_LABEL = "ClutterTools"
BUTTON_ANNOTATION = "Run the main clutter base tools"
BUTTON_SOURCE = "installer_files/main_ui.py"


# Deferred so __file__ is always resolved at call time, not import time
def _button_icon_path() -> Path:
    return Path(__file__).parent / "icons" / "ClutterBase.png"


def reload_package(package_name: str, reimport: bool = True) -> Optional[object]:
    """
    Purge all cached submodules for a package and optionally reimport.
    Unloads deepest submodules first to avoid KeyError on parent removal.
    Safe to call repeatedly during development.
    """
    to_unload = sorted(
        [k for k in sys.modules if k == package_name or k.startswith(package_name + ".")],
        key=lambda x: x.count("."),
        reverse=True,  # deepest submodules first
    )
    for key in to_unload:
        del sys.modules[key]

    if reimport:
        return importlib.import_module(package_name)
    return None


def _get_main_shelves_layout() -> str:
    """Return the top-level Maya shelf layout name."""
    return mel.eval("$tmpVar=$gShelfTopLevel")


def _shelf_exists(shelves_layout: str, shelf_name: str) -> bool:
    """Return True if a shelf tab with shelf_name exists."""
    existing = cmds.tabLayout(shelves_layout, query=True, childArray=True) or []
    return shelf_name in existing


def _find_button(shelf_name: str, button_label: str) -> Optional[str]:
    """Return the button widget name if a matching shelfButton exists, else None."""
    buttons = cmds.shelfLayout(shelf_name, query=True, childArray=True) or []
    for btn in buttons:
        if cmds.objectTypeUI(btn) == "shelfButton":
            if cmds.shelfButton(btn, query=True, label=True) == button_label:
                return btn
    return None


def _get_button_source(source_file: str) -> str:
    """Read and return the Python source that will be embedded in the shelf button."""
    path = Path(__file__).parent / source_file
    if not path.exists():
        raise FileNotFoundError(f"Button source not found: {path}")
    return path.read_text(encoding="utf-8")


def setup_shelf() -> None:
    """
    Ensure the ClutterBase shelf and its button exist.
    If the shelf is missing it is created; if the button already exists its
    command payload is updated rather than duplicated.
    """
    print(f"Setting up shelf '{SHELF_NAME}'")
    shelves_layout = _get_main_shelves_layout()

    if _shelf_exists(shelves_layout, SHELF_NAME):
        print(f"  Shelf '{SHELF_NAME}' already exists.")
    else:
        print(f"  Shelf '{SHELF_NAME}' not found — creating.")
        cmds.setParent(shelves_layout)
        cmds.shelfLayout(SHELF_NAME, parent=shelves_layout)
        cmds.tabLayout(shelves_layout, edit=True, tabLabel=(SHELF_NAME, SHELF_LABEL))

    button_payload = _get_button_source(BUTTON_SOURCE)
    existing_button = _find_button(SHELF_NAME, BUTTON_LABEL)

    if existing_button:
        print(f"  Button '{BUTTON_LABEL}' exists — updating command.")
        cmds.shelfButton(existing_button, edit=True, command=button_payload)
    else:
        print(f"  Button '{BUTTON_LABEL}' not found — creating.")
        cmds.setParent(SHELF_NAME)
        cmds.shelfButton(
            label=BUTTON_LABEL,
            annotation=BUTTON_ANNOTATION,
            image1=str(_button_icon_path()),
            command=button_payload,
            sourceType="python",
            parent=SHELF_NAME,
        )


def install_module() -> None:
    """
    Write a .mod file into Maya's user modules directory and load the module.
    Uses textwrap.dedent so the file contains no leading whitespace that would
    confuse Maya's module parser.
    """
    print("Installing module...")
    user_dir = Path(cmds.internalVar(userAppDir=True))
    modules_dir = user_dir / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)

    mod_file_path = modules_dir / f"{MODULE_NAME}.mod"
    mod_content = textwrap.dedent(f"""\
        + {MODULE_NAME} 1.0 {Path(__file__).parent}
        MAYA_PLUG_IN_PATH +:= plug-ins
        MAYA_SCRIPT_PATH +:= plug-ins/AETemplates
        XBMLANGPATH +:= icons
        PYTHONPATH +:= clutter_base/src
        icons: icons
    """)

    mod_file_path.write_text(mod_content, encoding="utf-8")
    print(f"  Module file written to: {mod_file_path}")

    cmds.loadModule(scan=True)
    cmds.loadModule(load=MODULE_NAME)
    print("  Module loaded.")


def onMayaDroppedPythonFile(*args, **kwargs) -> None:  # noqa: N802
    """Entry point called automatically when this file is drag-dropped into Maya."""
    print("Installer dropped.")

    # Remove any stale reference to this installer script itself
    sys.modules.pop("drag_to_maya", None)

    try:
        setup_shelf()
    except Exception as exc:
        cmds.error(f"ClutterBase: shelf setup failed — {exc}")
        return

    try:
        install_module()
    except Exception as exc:
        cmds.error(f"ClutterBase: module install failed — {exc}")
        return

    reload_package("clutter_base")
    print("ClutterBase installation complete.")
