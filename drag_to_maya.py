"""
drag_to_maya.py
---------------
Maya shelf installer script.

Drag and drop this file into a Maya viewport to automatically create (or update)
the ClutterBase shelf tab and its associated tool button.  When the button already
exists only its command payload is refreshed; otherwise a new button is created from
scratch.
"""

import importlib
import sys
from imp import reload
from pathlib import Path
from typing import Optional

import maya.cmds as cmds
import maya.mel as mel

SHELF_NAME: str = "ClutterBase"
SHELF_LABEL: str = "ClutterBase"

BUTTON_LABEL: str = "ClutterTools"
BUTTON_ICON: str = "commandButton.png"
BUTTON_ANNOTATION: str = "Run the main clutter base tools"
BUTTON_SOURCE: str = "installer_files/main_ui.py"


def reload_package(package_name: str, re_import: bool = True):
    """
    Purge all cached submodules for a package and optionally reimport.
    Safe to call repeatedly during development.

    Parameters
    ----------
    package_name:
        Name of the package whose modules should be cleared from cache.
    re_import:
        Whether to re-import the package once old modules are removed.
    """
    to_unload = sorted(
        [k for k in sys.modules if k == package_name or k.startswith(package_name + ".")],
        key=lambda x: x.count("."),
        reverse=True,
    )
    for key in to_unload:
        del sys.modules[key]
    if re_import:
        return importlib.import_module(package_name)
    return None


def _get_main_shelves_layout() -> str:
    """Return the name of Maya's top-level shelf tab layout.

    Uses the MEL global variable ``$gShelfTopLevel`` which always points to the
    main shelf container regardless of the current UI state.

    Returns
    -------
    str
        The name of the top-level ``tabLayout`` that holds all shelf tabs.
    """
    return mel.eval("$tmpVar=$gShelfTopLevel")


def _shelf_exists(shelves_layout: str, shelf_name: str) -> bool:
    """Check whether a named shelf tab already exists inside the given layout.

    Parameters
    ----------
    shelves_layout:
        The name of the top-level shelf ``tabLayout`` (usually obtained from
        :func:`_get_main_shelves_layout`).
    shelf_name:
        The internal name of the shelf tab to look for.

    Returns
    -------
    bool
        ``True`` if a child layout called *shelf_name* is present, ``False``
        otherwise.
    """
    existing: list[str] = cmds.tabLayout(shelves_layout, query=True, childArray=True) or []
    return shelf_name in existing


def _find_button(shelf_name: str, button_label: str) -> Optional[str]:
    """Search a shelf for a button with a specific label.

    Iterates over every child of *shelf_name* and returns the first
    ``shelfButton`` whose label matches *button_label*.

    Parameters
    ----------
    shelf_name:
        The name of the ``shelfLayout`` to search.
    button_label:
        The label text to match against each button.

    Returns
    -------
    Optional[str]
        The Maya control name of the matching button, or ``None`` if no button
        with *button_label* was found.
    """
    buttons: list[str] = cmds.shelfLayout(shelf_name, query=True, childArray=True) or []
    for btn in buttons:
        if cmds.objectTypeUI(btn) == "shelfButton":
            label: str = cmds.shelfButton(btn, query=True, label=True)
            if label == button_label:
                return btn
    return None


def _get_button_source(source_file: str) -> str:
    """Read and return the Python source that will be embedded in the shelf button.

    The path is resolved relative to the directory that contains this script,
    so the installer can be placed anywhere on disk as long as the
    ``installer_files`` sub-directory travels alongside it.

    Parameters
    ----------
    source_file:
        Relative path (from this script's directory) to the Python file whose
        contents should be used as the button command.

    Returns
    -------
    str
        The full text content of *source_file*.
    """
    parent: Path = Path(__file__).parent
    return (parent / Path(source_file)).read_text()


def setup_shelf() -> None:
    """Create or update the ClutterBase Maya shelf and its tool button.

    Execution flow
    --------------
    1. Retrieve the main shelf tab layout.
    2. Create the ``SHELF_NAME`` tab if it does not already exist.
    3. Look for an existing button labelled ``BUTTON_LABEL`` on that shelf.
    4. If the button exists, update its command payload with the latest source.
    5. If the button does not exist, create it with the configured icon,
       annotation, and command.
    """
    print(f"setting up shelf {SHELF_NAME}")
    shelves_layout: str = _get_main_shelves_layout()

    if _shelf_exists(shelves_layout, SHELF_NAME):
        print(f"Shelf {SHELF_NAME} exists")
    else:
        print(f"No shelf {SHELF_NAME} creating")
        cmds.setParent(shelves_layout)
        cmds.shelfLayout(SHELF_NAME, parent=shelves_layout)
        # Maya uses the layout name as the tab key, so set a human-readable label.
        cmds.tabLayout(shelves_layout, edit=True, tabLabel=(SHELF_NAME, SHELF_LABEL))

    existing_button: Optional[str] = _find_button(SHELF_NAME, BUTTON_LABEL)
    button_payload: str = _get_button_source(BUTTON_SOURCE)

    if existing_button:
        print(f"Button {BUTTON_LABEL} exists — updating command payload")
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


def onMayaDroppedPythonFile(*args: object, **kwargs: object) -> None:
    """Entry point called automatically by Maya when this file is dragged into a viewport.

    Clears any cached version of this module from ``sys.modules`` to guarantee
    that a fresh copy is always executed, then delegates to :func:`setup_shelf`.

    Parameters
    ----------
    *args:
        Positional arguments forwarded by Maya (not used).
    **kwargs:
        Keyword arguments forwarded by Maya (not used).

    Raises
    ------
    Exception
        Re-raises any exception that occurs while removing the module from the
        cache, preserving the original traceback.
    """
    try:
        sys.modules.pop("drag_to_maya", None)
    except Exception:
        raise

    print("installer dropped")
    setup_shelf()
    reload_package("clutter_base")
