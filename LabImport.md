# ClutterStarter2026 - Maya Import Branch Changes Lab Guide

This is a manual walkthrough of the changes needed to implement Maya mesh loading functionality. These changes are already in the `maya_import` branch, and this guide will help you demonstrate them step-by-step to your students.

---

## Overview of Changes

Three files have been modified to add the ability to double-click on assets in the grid view and load them directly into Maya. Here's what we're adding:

1. **Store MongoDB IDs separately** in the data model
2. **Wire up a double-click handler** in the grid view
3. **Create mesh loading functions** that extract and import into Maya
4. **Improve error handling and documentation** in the installer script

---

## File 1: `clutter_base/src/clutter_base/gui/ImageDataModel.py`

### Change 1.1: Add ID storage (Line 21)

**What we're doing:** Store the MongoDB `_id` separately so we can retrieve assets without displaying the ID to users.

**Current code (lines 19-21):**
```python
        super().__init__(parent)
        self._data: list[dict[str, Any]] = []
        self._headers: list[str] = []
```

**Add this line after `self._data`:**
```python
        self._ids: list[Any] = []
```

**Why:** We need to keep track of the MongoDB `_id` for each asset so we can fetch it later when the user double-clicks.

---

### Change 1.2: Modify the `setQuery` method (Lines 34-41)

**What we're doing:** Exclude the `_id` from the MongoDB query projection, extract it separately, then store it in our `_ids` list.

**Current code (lines 34-40):**
```python
        collection = self._db["assets"]
        exclude = {"mesh_file_id": 0, "user_id": 0, "_id": 0}
        self._data = list(collection.find(filter_doc, exclude))

        if self._data:
            self._headers = list(self._data[0].keys())
        else:
            self._headers = []
```

**Replace with:**
```python
        collection = self._db["assets"]
        exclude = {"mesh_file_id": 0, "user_id": 0}
        results = list(collection.find(filter_doc, exclude))
        # Separate _id from display data; store as str for easy use
        self._ids: list[Any] = [str(doc.pop("_id")) for doc in results]
        self._data = results

        if self._data:
            self._headers = list(self._data[0].keys())
        else:
            self._headers = []
```

**Why:** Now we're:
- Removing `"_id": 0` from the projection so the `_id` is included in results
- Using a list comprehension to pop `_id` from each document and convert it to a string
- Storing these IDs in `self._ids` for later retrieval
- Removing the IDs from the display data so they don't show up in the table

---

### Change 1.3: Add UserRole handler in `data()` method (Lines 155-158)

**What we're doing:** Add a new case in the `data()` method to return the `_id` when requested via the `UserRole`.

**Locate the line that says:**
```python
            return None
```
(This should be around line 151, after the DecorationRole check)

**After that line, add (before the `DisplayRole` check):**
```python
        if role == Qt.ItemDataRole.UserRole:
            if 0 <= row < len(self._ids):
                return self._ids[row]
            return None

```

**Why:** This makes the `_id` available to other parts of the application that need it (like our new mesh loader), without displaying it in the table.

---

## File 2: `clutter_base/src/clutter_base/gui/grid_view.py`

### Change 2.1: Add imports (Lines 1-14)

**What we're doing:** Add four new imports needed for the mesh loading functionality.

**Current imports (lines 1-3):**
```python
from pathlib import Path
from typing import Dict, Optional

from bson import ObjectId
```

**Add these lines to your imports section:**
```python
from bson import ObjectId
from pymongo import MongoClient
from pymongo.database import Database
from PySide6.QtCore import QModelIndex, Qt, Slot
```

**Then make sure these imports exist:**
```python
from clutter_base.db.connection import Connection
from clutter_base.gui.ImageDataModel import ImageDataModel
```

**Summary of new imports:**
- `ObjectId` from bson - for MongoDB ID handling
- `QModelIndex, Qt, Slot` from PySide6.QtCore - for signal handling
- `Connection` from clutter_base.db.connection - for mesh extraction

---

### Change 2.2: Wire up double-click signal (Line 50)

**What we're doing:** Connect the double-click event on the table to our new `load_mesh` function.

**Current code (lines 49-50):**
```python
        self.database_view: QTableView = QTableView(self.database_gb)
        self.database_view.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
```

**Add this line after `setEditTriggers`:**
```python
        self.database_view.doubleClicked.connect(self.load_mesh)
```

**Why:** This connects the table's double-click signal to our mesh loader, so users can double-click any asset to load it.

---

### Change 2.3: Add two new methods (Lines 56-89)

**What we're doing:** Add the `_load_to_maya()` helper and the main `load_mesh()` function.

**Add these two methods after the `update_view()` method and before `_connect_signals()`:**

```python
    def _load_to_maya(self, output_path: str, file_type: str) -> None:
        import maya.cmds as cmds

        print(f"_load_to_maya: loading {output_path} ({file_type})")
        cmds.file(output_path, i=True, type=file_type, groupReference=True, groupName="clutter_base")

    @Slot(QModelIndex)
    def load_mesh(self, index: QModelIndex) -> None:
        import tempfile

        mesh_id = self.data_model.data(index, Qt.ItemDataRole.UserRole)
        if not mesh_id:
            print("load_mesh: no mesh_id for selected item")
            return

        # Get mesh name and file_type from the data model
        row = index.row()
        mesh_name = self.data_model.get_data_at_index(row, "name")
        file_type = self.data_model.get_data_at_index(row, "file_type")

        print(f"load_mesh: extracting mesh {mesh_id} ({mesh_name}, {file_type})")
        conn = Connection(self._db, ObjectId(), "app_user")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = conn.extract_mesh_files(mesh_id, temp_dir)
            print(f"load_mesh: extracted to {output_path}")
            self._load_to_maya(f"{output_path}/{mesh_name}.{file_type}", file_type)
```

**What these methods do:**

- **`_load_to_maya()`**: A helper that uses Maya's file import command to load the mesh as a group reference
- **`load_mesh()`**: The main handler that:
  1. Gets the MongoDB `_id` from the clicked row (via `UserRole`)
  2. Retrieves the mesh name and file type from the data model
  3. Creates a `Connection` object to access the database
  4. Uses a temporary directory to extract mesh files from MongoDB
  5. Calls `_load_to_maya()` to import into Maya

---

## File 3: `drag_to_maya.py`

This file has extensive improvements for error handling, type hints, and documentation. Here are the key changes:

### Change 3.1: Update module name and imports (Lines 1-15)

**What we're doing:** Add module name constant, add type hints, and add textwrap import.

**Current code (lines 1-4):**
```python
import importlib
import sys
from pathlib import Path

import maya.cmds as cmds
```

**Replace with:**
```python
import importlib
import sys
import textwrap
from pathlib import Path
from typing import Optional

import maya.cmds as cmds
import maya.mel as mel
```

**New addition (after `SHELF_LABEL`):**
```python
MODULE_NAME: str = "ClutterBase2026"
```

---

### Change 3.2: Add icon path function (Lines 17-20)

**What we're doing:** Replace the static `BUTTON_ICON` with a dynamic function that resolves the path at call time.

**Remove this line:**
```python
BUTTON_ICON = "commandButton.png"
```

**Add this function instead:**
```python
# Deferred so __file__ is always resolved at call time, not import time
def _button_icon_path() -> Path:
    return Path(__file__).parent / "icons" / "ClutterBase.png"
```

**Why:** This ensures the path is resolved when the function is called, not when the module is imported.

---

### Change 3.3: Add type hints and improve `reload_package()` (Lines 23-37)

**What we're doing:** Add type hints to the function and improve documentation.

**Current code:**
```python
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
```

**Replace with:**
```python
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
```

---

### Change 3.4: Add docstrings and type hints to helper functions (Lines 40-68)

**What we're doing:** Add comprehensive docstrings and return type hints to all helper functions.

**Update each function:**

```python
def _get_main_shelves_layout() -> str:
    """Return the top-level Maya shelf layout name."""
    return mel.eval("$tmpVar=$gShelfTopLevel")
```

```python
def _shelf_exists(shelves_layout: str, shelf_name: str) -> bool:
    """Return True if a shelf tab with shelf_name exists."""
    existing = cmds.tabLayout(shelves_layout, query=True, childArray=True) or []
    return shelf_name in existing
```

```python
def _find_button(shelf_name: str, button_label: str) -> Optional[str]:
    """Return the button widget name if a matching shelfButton exists, else None."""
    buttons = cmds.shelfLayout(shelf_name, query=True, childArray=True) or []
    for btn in buttons:
        if cmds.objectTypeUI(btn) == "shelfButton":
            if cmds.shelfButton(btn, query=True, label=True) == button_label:
                return btn
    return None
```

```python
def _get_button_source(source_file: str) -> str:
    """Read and return the Python source that will be embedded in the shelf button."""
    path = Path(__file__).parent / source_file
    if not path.exists():
        raise FileNotFoundError(f"Button source not found: {path}")
    return path.read_text(encoding="utf-8")
```

---

### Change 3.5: Improve `setup_shelf()` function (Lines 69-107)

**What we're doing:** Add better docstring, clearer print messages, use the new icon path function, and reorganize logic.

**Replace the entire `setup_shelf()` function with:**

```python
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
```

**Key changes:**
- Better docstring explaining the function's purpose
- Clearer, more informative print messages with indentation
- Use `_button_icon_path()` instead of static `BUTTON_ICON`
- Reorganized to get button payload before checking existence

---

### Change 3.6: Add new `install_module()` function (Lines 109-133)

**What we're doing:** Add a new function to install the Maya module file.

**Add this entire new function after `setup_shelf()`:**

```python
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
```

**Why:** This ensures the ClutterBase package is properly registered with Maya's module system, making imports reliable.

---

### Change 3.7: Improve `onMayaDroppedPythonFile()` function (Lines 135-157)

**What we're doing:** Add better error handling, clearer output, and call the new `install_module()` function.

**Replace the entire function with:**

```python
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
```

**Key improvements:**
- Add `noqa: N802` comment (naming convention exception for Maya's callback)
- Clearer docstring
- Separate `setup_shelf()` and `install_module()` into independent try-except blocks
- Each has its own error message with context
- Better final success message

---

## Summary for Students

Here's what we've accomplished:

**ImageDataModel.py:**
- Store MongoDB `_id` values separately from display data
- Make `_id` available via `UserRole` for retrieval without showing it in the table

**grid_view.py:**
- Wire up double-click handler on the grid view table
- Create `load_mesh()` handler that retrieves asset metadata
- Create `_load_to_maya()` helper to import meshes into Maya
- Connect these together to enable double-click-to-load workflow

**drag_to_maya.py:**
- Add type hints for better code clarity
- Create `_button_icon_path()` to resolve icon path dynamically
- Add `install_module()` to properly register the package with Maya
- Improve error handling with separate try-except blocks
- Add comprehensive docstrings and clearer output messages

The result: Users can now double-click any asset in the grid view and it will be automatically extracted from MongoDB and loaded into Maya!
