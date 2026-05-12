# Complete Maya PySide6 Best Practices Discussion

# Original Developer Guide

## Introduction

This document outlines recommended practices for using PySide6 in Autodesk Maya for production-quality tools and UI development. It focuses on:

- Window lifetimes and ownership
- Dockable tools
- Proper cleanup and destruction
- Maya integration patterns
- Dialog and tool design decisions
- Common pitfalls ("gotchas")
- Production architecture recommendations

This guide assumes:

- Maya 2025+
- Python 3
- PySide6
- `shiboken6`

For older Maya versions using PySide2, minor API differences exist.

---

# Why Use PySide6 in Maya?

PySide6 provides direct access to the Qt framework used internally by Maya.

Advantages over `maya.cmds` UI:

- Object-oriented architecture
- Signal/slot system
- Dockable windows
- Model/View widgets
- Better styling and layouts
- Reusable widgets
- Easier maintenance
- Standalone compatibility
- Better performance for complex UIs

Qt is the standard for professional DCC tooling.

---

# Core Principles

## 1. Always Parent Windows to Maya

One of the most important rules.

If a Qt widget is not parented to a Maya widget, Python garbage collection may destroy it unexpectedly.

Autodesk explicitly recommends parenting custom widgets to Maya's main window.

---

## 2. Use Unique `objectName()` Values

Always set a unique object name.

Maya internally uses object names for:

- Workspace controls
- Docking
- UI restoration
- Lookup through `MQtUtil`

```python
self.setObjectName("myUniqueToolWindow")
```

Failure to do this can result in:

- Duplicate windows
- Docking issues
- Inability to restore state
- Ghost workspace controls

---

## 3. Prefer Persistent Tools Over Recreating Windows

Avoid repeatedly creating and destroying windows.

A common pattern:

```python
if window_instance is None:
    window_instance = MyWindow()

window_instance.show()
window_instance.raise_()
```

This avoids:

- Duplicate callbacks
- Memory leaks
- Ghost dock controls
- Lost state

---

# Accessing the Maya Main Window

This helper is used constantly.

```python
from maya import OpenMayaUI as omui
from shiboken6 import wrapInstance
from PySide6 import QtWidgets


def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)
```

---

# Choosing the Correct Base Class

Choosing the correct Qt widget type is important.

| Type | Use Case |
|---|---|
| `QDialog` | Tool dialogs |
| `QMainWindow` | Large applications |
| `QWidget` | Generic embedded widgets |
| `QDockWidget` | Rarely needed directly in Maya |
| `QToolBar` | Toolbar-style floating tools |

---

# Recommended Window Types

## Tool Windows

Most Maya tools should use:

```python
QDialog
```

Reasons:

- Proper window behavior
- Supports modal workflows
- Better integration with Maya
- Works cleanly with docking mixins

Recommended for:

- Exporters
- Asset managers
- Utility tools
- Scene validators
- Pipeline tools

---

## Large Applications

Use `QMainWindow` for:

- Multi-panel applications
- Applications with menus/toolbars
- Complex editors
- Large asset browsers

Avoid using `QMainWindow` for simple tools.

---

# Basic Tool Window Example

```python
from PySide6 import QtWidgets
from maya import OpenMayaUI as omui
from shiboken6 import wrapInstance


def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


class MyTool(QtWidgets.QDialog):

    WINDOW_NAME = "MyToolWindow"

    def __init__(self, parent=maya_main_window()):
        super().__init__(parent)

        self.setObjectName(self.WINDOW_NAME)
        self.setWindowTitle("My Tool")
        self.resize(400, 200)

        layout = QtWidgets.QVBoxLayout(self)

        button = QtWidgets.QPushButton("Run")
        layout.addWidget(button)
```

---

# Dockable Windows

Maya provides:

```python
maya.app.general.mayaMixin.MayaQWidgetDockableMixin
```

This is the standard solution for dockable tools.

---

# Basic Dockable Window

```python
from PySide6 import QtWidgets
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin


class MyDockableTool(
    MayaQWidgetDockableMixin,
    QtWidgets.QDialog
):

    TOOL_NAME = "MyDockableTool"

    def __init__(self, parent=maya_main_window()):
        super().__init__(parent)

        self.setObjectName(self.TOOL_NAME)
        self.setWindowTitle("Dockable Tool")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Hello Maya"))
```

Show it:

```python
tool = MyDockableTool()

tool.show(
    dockable=True,
    floating=True,
    area="right"
)
```

---

# IMPORTANT: Mixin Order Matters

The mixin MUST come first.

### Correct

```python
class MyTool(MayaQWidgetDockableMixin, QtWidgets.QDialog):
```

### Wrong

```python
class MyTool(QtWidgets.QDialog, MayaQWidgetDockableMixin):
```

---

# Window Lifetime Management

This is one of the biggest sources of Maya UI bugs.

---

# Understanding Qt Ownership

Qt uses parent-child ownership.

When a parent widget is destroyed:

- All children are destroyed automatically

In Maya:

- Parent to Maya main window
- Avoid orphaned widgets

---

# Safe Window Cleanup Pattern

```python
from maya import cmds

WINDOW_NAME = "MyToolWindow"


def delete_window():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)


class MyWindow(QtWidgets.QDialog):

    def __init__(self, parent=maya_main_window()):
        delete_window()

        super().__init__(parent)

        self.setObjectName(WINDOW_NAME)
```

---

# Using `WA_DeleteOnClose`

Recommended for temporary windows.

```python
self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
```

This ensures:

- Memory cleanup
- Signal cleanup
- Proper Qt destruction

---

# Modal vs Non-Modal Windows

Most Maya tools should be non-modal.

Modal dialogs block Maya interaction and should only be used for:

- confirmations
- setup prompts
- warnings

---

# Threading Best Practices

## Rule: UI Only in Main Thread

Never update widgets from worker threads.

Bad:

```python
label.setText("Done")
```

Good:

```python
signal.emit("Done")
```

then update the UI in a slot.

---

# UI Architecture Best Practices

## Separate UI From Logic

Avoid embedding Maya logic directly in widgets.

Bad:

```python
button.clicked.connect(
    lambda: cmds.polyCube()
)
```

Better:

```python
button.clicked.connect(self.create_cube)
```

Best:

```python
button.clicked.connect(controller.create_cube)
```

---

# Maya-Specific Gotchas

## `long()` No Longer Exists

Old examples use:

```python
long(ptr)
```

Python 3 requires:

```python
int(ptr)
```

---

## Docked Windows Behave Differently

Docked widgets:

- may not receive normal close events
- may persist in workspace layouts
- can restore unexpectedly

Always test both floating and docked states.

---

## Maya Shutdown Crashes

During Maya exit:

- Qt widgets may already be destroyed
- callbacks may still fire

Defensive programming is essential.

Example:

```python
try:
    widget.close()
except RuntimeError:
    pass
```

---

# Production Template

```python
from PySide6 import QtWidgets
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from maya import OpenMayaUI as omui
from shiboken6 import wrapInstance


WINDOW_INSTANCE = None


def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


class MyTool(
    MayaQWidgetDockableMixin,
    QtWidgets.QDialog
):

    OBJECT_NAME = "MyProductionTool"

    def __init__(self, parent=maya_main_window()):
        super().__init__(parent)

        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("Production Tool")

        self.build_ui()
        self.create_connections()

    def build_ui(self):

        self.button = QtWidgets.QPushButton("Run")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.button)

    def create_connections(self):

        self.button.clicked.connect(self.run)

    def run(self):

        print("Running")

    def dockCloseEventTriggered(self):

        print("Dock closed")

    def closeEvent(self, event):

        super().closeEvent(event)


def show():

    global WINDOW_INSTANCE

    try:
        WINDOW_INSTANCE.close()
        WINDOW_INSTANCE.deleteLater()
    except:
        pass

    WINDOW_INSTANCE = MyTool()

    WINDOW_INSTANCE.show(
        dockable=True,
        floating=True,
        area="right"
    )
```

---

# Additional Discussion


## Do I need `MQtUtil.addWidgetToMayaLayout()`?

Usually: **no**, not for normal PySide6 Maya tools.

Most PySide6 tools in Maya should simply:

- parent to the Maya main window
- use `MayaQWidgetDockableMixin`
- call `.show(dockable=True)`

Example:

```python
tool = MyTool(parent=maya_main_window())
tool.show(dockable=True)
```

That is enough for the vast majority of production tools.

---

# When `MQtUtil.addWidgetToMayaLayout()` *is* needed

You only typically need:

```python
MQtUtil.addWidgetToMayaLayout()
```

when you are:

1. Embedding a Qt widget into an existing Maya layout
2. Restoring a workspace control manually
3. Integrating custom Qt widgets deeply into Maya UI commands
4. Writing C++ Qt plugins
5. Using `workspaceControl` with a custom `uiScript`

This is primarily an advanced integration API.

---

# Typical Modern PySide6 Tool

You do **not** need `addWidgetToMayaLayout()` here:

```python
class MyTool(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    pass

tool = MyTool()
tool.show(dockable=True)
```

Maya handles the docking internally.

---

# The Main Exception: Workspace Restoration

You *do* need it when restoring a docked workspace control using `uiScript`.

Example:

```python
def restore(restore=False):

    global WINDOW

    if WINDOW is None:
        WINDOW = MyTool()

    if restore:
        parent = omui.MQtUtil.getCurrentParent()
        widget = omui.MQtUtil.findControl(WINDOW.objectName())

        omui.MQtUtil.addWidgetToMayaLayout(
            int(widget),
            int(parent)
        )
    else:
        WINDOW.show(
            dockable=True,
            uiScript="restore(True)"
        )
```

---

# Important Distinction

There are two docking systems people often confuse:

| System | Need `addWidgetToMayaLayout`? |
|---|---|
| `MayaQWidgetDockableMixin.show(dockable=True)` | Usually no |
| Manual `workspaceControl` restoration | Yes |

---

# Best Practice Recommendation

For most Maya pipeline tools:

## Recommended

```python
MayaQWidgetDockableMixin
```

with:

```python
show(dockable=True)
```

## Avoid Unless Necessary

```python
MQtUtil.addWidgetToMayaLayout()
```

because it adds:

- more lifecycle complexity
- workspace restoration edge cases
- harder cleanup
- tighter Maya UI coupling

---

# Production Recommendation

A good rule:

> If your tool works correctly without `addWidgetToMayaLayout()`, don't use it.

Most studios only use it for:

- advanced workspace restoration
- embedded editors
- custom panels
- viewport integrations
- legacy hybrid MEL/Qt systems

Not standard artist tools.

---

# Creating Multiple Dockable Widgets

In Maya, "dockable" really means "hosted inside a workspaceControl".

So when you create a second dockable widget from inside another dockable widget, you are not truly nesting dock widgets inside each other like standard Qt docking systems. Instead, you are creating another independent Maya `workspaceControl`.

---

# Recommended Architecture

You generally want:

```text
Main Dockable Tool
    ├── Internal Qt Widgets
    ├── Tabs
    ├── Splitters
    └── Optional Secondary Dockable Tools
```

NOT:

```text
Dock Widget
    └── Another Dock Widget
            └── Another Dock Widget
```

Nested Maya docking becomes fragile very quickly.

---

# The Correct Way

The parent tool launches another *independent* dockable tool.

Example:

```python
from PySide6 import QtWidgets
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin


class SecondaryTool(
    MayaQWidgetDockableMixin,
    QtWidgets.QDialog
):

    OBJECT_NAME = "SecondaryTool"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName(self.OBJECT_NAME)
        self.setWindowTitle("Secondary Tool")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Secondary Tool"))
```

Main tool:

```python
class MainTool(
    MayaQWidgetDockableMixin,
    QtWidgets.QDialog
):

    OBJECT_NAME = "MainTool"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName(self.OBJECT_NAME)

        layout = QtWidgets.QVBoxLayout(self)

        btn = QtWidgets.QPushButton("Open Secondary Tool")
        layout.addWidget(btn)

        btn.clicked.connect(self.show_secondary)

        self.secondary = None

    def show_secondary(self):

        if self.secondary is None:
            self.secondary = SecondaryTool()

        self.secondary.show(
            dockable=True,
            floating=False,
            area="right"
        )
```

---

# Important Lifetime Rule

This is critical:

```python
self.secondary = SecondaryTool()
```

Store the reference.

Otherwise the secondary tool may:

- disappear
- get garbage collected
- become unstable during docking

---

# Better Alternative: Use Internal Docking

In many cases, you should NOT create multiple Maya dock widgets.

Instead use Qt internally:

- `QSplitter`
- `QTabWidget`
- stacked widgets
- collapsible panels

Example:

```text
One Maya Dock
    ├── Asset Browser
    ├── Properties Panel
    ├── Outliner
    └── Preview Widget
```

This is significantly more stable.

---

# Why Nested Dockables Become Problematic

Each Maya dockable tool creates:

```text
workspaceControl
```

Internally.

This introduces:

- workspace serialization
- restore ordering
- uiScript restoration
- docking ownership
- tab management

Problems commonly include:

- orphaned tabs
- restore failures
- invisible widgets
- broken layouts
- duplicated controls
- stale workspace state

---

# Recommended Production Pattern

## BEST

Single dockable window:

```text
Studio Tool
    ├── Tabs
    ├── Panels
    ├── Splitters
    └── Embedded widgets
```

## ACCEPTABLE

A few independent dockable tools:

```text
Asset Browser
Shader Editor
Publish Tool
Scene Validator
```

## AVOID

Deeply interconnected nested dock systems.

---

# Parent/Child Docking

You can dock relative to another workspace control:

```python
tool.show(
    dockable=True,
    floating=False,
    area="right"
)
```

Or manually using:

```python
cmds.workspaceControl(
    second_workspace,
    e=True,
    dockToControl=[main_workspace, "right"]
)
```

This creates sibling dock panels, not true nested Qt docks.

---

# Window Lifetime and Closing

In Maya with PySide6, clicking the close button may either:

- hide the widget
- destroy the widget
- destroy the Maya `workspaceControl`
- leave stale references behind

depending on:

- whether the widget is docked
- whether `WA_DeleteOnClose` is set
- whether you're using `MayaQWidgetDockableMixin`
- whether Maya created a `workspaceControl`

---

# Default Qt Behaviour

Normally in Qt:

```python
window.close()
```

does **NOT** destroy the widget.

It usually:

- hides the widget
- sends a `closeEvent`

The Python object still exists.

So this works:

```python
window.show()
window.close()
window.show()
```

because the widget still exists.

---

# In Maya Dockable Windows

When using:

```python
MayaQWidgetDockableMixin
```

things become more complicated.

Closing the dock tab often destroys the underlying:

```text
workspaceControl
```

but your Python object may still exist.

This can leave you with:

- invalid Qt pointers
- stale Python references
- "Internal C++ object already deleted" errors

---

# The Most Important Rule

Never assume your stored window reference is still valid.

This is BAD:

```python
WINDOW.show()
```

because the underlying Qt object may already be deleted.

---

# Correct Production Pattern

Always recreate safely.

---

# Recommended Singleton Pattern

```python
from shiboken6 import isValid

WINDOW = None


def show_tool():

    global WINDOW

    if WINDOW is None or not isValid(WINDOW):

        WINDOW = MyTool()

    WINDOW.show(dockable=True)
    WINDOW.raise_()
```

This is the safest pattern in Maya.

---

# Why `isValid()` Matters

This checks whether the underlying C++ Qt object still exists.

Without it:

```python
RuntimeError:
Internal C++ object already deleted
```

is extremely common.

---

# Recommended Close Handling

You should explicitly clean references.

Example:

```python
WINDOW = None


class MyTool(
    MayaQWidgetDockableMixin,
    QtWidgets.QDialog
):

    def dockCloseEventTriggered(self):

        global WINDOW
        WINDOW = None

    def closeEvent(self, event):

        global WINDOW
        WINDOW = None

        super().closeEvent(event)
```

This ensures the next `show_tool()` creates a fresh widget.

---

# Should You Use `WA_DeleteOnClose`?

Usually:

## YES for temporary dialogs

```python
self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
```

Good for:

- popup dialogs
- transient tools
- utility windows

---

## MAYBE for dockable Maya tools

Dockable Maya widgets already interact with workspace controls.

`WA_DeleteOnClose` can sometimes complicate restoration.

Many studios avoid it for persistent dock tools and instead rely on:

- explicit cleanup
- singleton recreation
- `isValid()`

---

# Best Practice for Dockable Maya Tools

Recommended approach:

```text
Close Window
    ->
Destroy WorkspaceControl
    ->
Clear Python Reference
    ->
Recreate Freshly Next Time
```

This is the most stable production workflow.

---

# Full Recommended Example

```python
from PySide6 import QtWidgets
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from shiboken6 import isValid


WINDOW = None


class MyTool(
    MayaQWidgetDockableMixin,
    QtWidgets.QDialog
):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("MyTool")

    def dockCloseEventTriggered(self):

        global WINDOW
        WINDOW = None

    def closeEvent(self, event):

        global WINDOW
        WINDOW = None

        super().closeEvent(event)


def show_tool():

    global WINDOW

    if WINDOW is None or not isValid(WINDOW):

        WINDOW = MyTool()

    WINDOW.show(dockable=True)
```

---

# Recommended Mental Model

Think of Maya dockable widgets as:

```text
Python Object
    +
Qt Widget
    +
Maya WorkspaceControl
```

All three lifetimes can diverge.

That is why robust lifetime handling is essential in Maya UI programming.

