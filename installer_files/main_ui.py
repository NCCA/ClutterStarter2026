import maya.api.OpenMaya as OpenMaya
import maya.api.OpenMayaUI as OpenMayaUI
import maya.cmds as cmds
import maya.OpenMayaUI as omui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Slot
from shiboken6 import wrapInstance

from clutter_base.gui import GridViewWidget, LoginWidget

TOOL_NAME = "ClutterBaseTools"
WINDOW_INSTANCE = None


def get_main_window():
    """This returns the maya main window for parenting"""
    window = omui.MQtUtil.mainWindow()
    return wrapInstance(int(window), QtWidgets.QDialog)


def delete_workspace_control(control: str):
    if cmds.workspaceControl(control, query=True, exists=True):
        cmds.workspaceControl(control, edit=True, close=True)
        cmds.deleteUI(control, control=True)


class _GridViewShim(GridViewWidget):
    """Prevents GridViewWidget.__init__ being called a second time
    by MayaQWidgetDockableMixin's cooperative super() chain."""

    def __init__(self, *args, **kwargs):
        if not getattr(self, "_grid_initialised", False):
            super().__init__(*args, **kwargs)


class MayaGridView(MayaQWidgetDockableMixin, _GridViewShim):
    def __init__(self, user: str, client, db, parent=get_main_window()):
        # GridViewWidget FIRST — the underlying QWidget C++ object must exist
        # before the mixin calls setAttribute / setObjectName etc.
        GridViewWidget.__init__(self, user, client, db, parent)
        self._grid_initialised = True  # arm the shim guard
        MayaQWidgetDockableMixin.__init__(self, parent=parent)


class ClutterDialog(QtWidgets.QDialog):
    def __init__(self, parent=get_main_window()):
        delete_workspace_control(TOOL_NAME + "WorkspaceControl")
        super().__init__(parent)
        self.setWindowTitle("Clutter Base Tools")
        self.resize(400, 200)
        self.grid_layout = QtWidgets.QGridLayout(self)
        self.login_button = QtWidgets.QPushButton("Login", self)
        self.login_button.clicked.connect(self.user_login)
        self.grid_layout.addWidget(self.login_button)
        self.show_grid = QtWidgets.QPushButton("Show Grid", self)
        self.show_grid.setEnabled(False)
        self.show_grid.clicked.connect(self.show_grid_view)
        self.grid_layout.addWidget(self.show_grid)
        self.grid_view_widget = None
        self.setObjectName(TOOL_NAME)

    @Slot(str, str)
    def auth_user(self, role, user):
        print(role, user)
        self.role = role
        self.user = user
        # grab the client and session from widget
        self.session = self.login_widget.session
        print(self.session)
        self.login_widget.close()
        self.show_grid.setEnabled(True)

    @Slot(int)
    def _update_grid_visible(self, value):
        delete_workspace_control("MayaGridViewWorkspaceControl")
        self.grid_view_widget = None

    def dockCloseEventTriggered(self):
        delete_workspace_control("MayaGridViewWorkspaceControl")
        self.grid_view_widget = None

    @Slot()
    def show_grid_view(self):
        if not self.grid_view_widget:
            self.grid_view_widget = MayaGridView(self.user, self.session[0], self.session[1], parent=get_main_window())
            # Override the UUID name with a fixed one before show()
            self.grid_view_widget.setObjectName("MayaGridView")
            self.grid_view_widget.show(dockable=True)
            self.grid_view_widget.raise_()
            self.grid_view_widget.activateWindow()
            # self.grid_view_widget.finished.connect(self._update_grid_visible)

    def user_login(self):
        self.login_widget = LoginWidget(self.parent())
        self.login_widget.authenticated.connect(self.auth_user)
        self.login_widget.show()


def show_tool():
    global WINDOW_INSTANCE

    try:
        WINDOW_INSTANCE.close()
        WINDOW_INSTANCE.deleteLater()

    except Exception:
        pass
    WINDOW_INSTANCE = ClutterDialog()
    WINDOW_INSTANCE.show()


show_tool()
# clutter_dialog = ClutterDialog()
# clutter_dialog.show(dockable=True)
