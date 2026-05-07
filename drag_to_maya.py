import importlib
import sys
from pathlib import Path

import maya.cmds as cmds
import maya.mel as mel

SHELF_NAME = "ClutterBase"
SHELF_LABEL = "ClutterBase"

BUTTON_LABEL = "ClutterTools"
BUTTON_ICON = "commandButton.png"
BUTTON_ANNOTATION = "Run the main clutter base tools"
BUTTON_SOURCE = "installer_files/main_ui.py"
"""
See if the shelf exists, if not create one. Then see if button exists or not. If exists we will just update
button code, else create button first then add code.
"""


def reload_package(package_name, reimport=True):
    """
    Purge all cached submodules for a package and optionally reimport.
    Safe to call repeatedly during development.
    """
    # Collect all related module keys
    to_unload = sorted(
        [k for k in sys.modules if k == package_name or k.startswith(package_name + ".")],
        key=lambda x: x.count("."),  # deepest submodules first
        reverse=True,
    )

    for key in to_unload:
        del sys.modules[key]

    if reimport:
        return importlib.import_module(package_name)


def _get_main_shelves_layout():
    """return the top-level maya shelf"""
    return mel.eval("$tmpVar=$gShelfTopLevel")


def _shelf_exists(shelves_layout: str, shelf_name: str) -> bool:
    existing = cmds.tabLayout(shelves_layout, query=True, childArray=True) or []
    return shelf_name in existing


def _find_button(shelf_name: str, button_label: str):
    buttons = cmds.shelfLayout(shelf_name, query=True, childArray=True) or []
    for btn in buttons:
        if cmds.objectTypeUI(btn) == "shelfButton":
            label = cmds.shelfButton(btn, query=True, label=True)
            if label == button_label:
                return btn
    return None


def _get_button_source(source_file: str):
    parent = Path(__file__).parent
    return (parent / Path(source_file)).read_text()


def setup_shelf():
    print(f"setting up shelf {SHELF_NAME}")
    shelves_layout = _get_main_shelves_layout()
    # see if this exists
    if _shelf_exists(shelves_layout, SHELF_NAME):
        print(f"Shelf {SHELF_NAME} exists")
    else:
        print(f"No shelf {SHELF_NAME} creating")
        # create new shelf tab
        cmds.setParent(shelves_layout)
        cmds.shelfLayout(SHELF_NAME, parent=shelves_layout)
        # set visible tab label (maya uses the layout name as the tab key)
        cmds.tabLayout(shelves_layout, edit=True, tabLabel=(SHELF_NAME, SHELF_LABEL))

    existing_button = _find_button(SHELF_NAME, BUTTON_LABEL)
    button_payload = _get_button_source(BUTTON_SOURCE)
    if existing_button:
        print(f"Button {BUTTON_LABEL} exists")
        cmds.shelfButton(existing_button, edit=True, command=button_payload)
    else:
        print(f"Creating new button {BUTTON_LABEL}")
        cmds.setParent(SHELF_NAME)
        cmds.shelfButton(
            label=BUTTON_LABEL,
            annotation=BUTTON_ANNOTATION,
            image1=BUTTON_ICON,
            command=button_payload,
            sourceType="python",
            parent=SHELF_NAME,
        )


def onMayaDroppedPythonFile(*args, **kwargs):
    try:
        sys.modules.pop("drag_to_maya", None)
    except:
        raise
    print("installer dropped")
    setup_shelf()
    reload_package("clutter_base")
