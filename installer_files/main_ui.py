import maya.api.OpenMaya as OpenMaya
import maya.api.OpenMayaUI as OpenMayaUI
import maya.cmds as cmds
import maya.OpenMayaUI as omui
from clutter_base.gui import LoginWidget
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Slot
from shiboken6 import wrapInstance

TOOL_NAME = "ClutterBaseTools"


def get_main_window():
    """This returns the maya main window for parenting"""
    window = omui.MQtUtil.mainWindow()
    return wrapInstance(int(window), QtWidgets.QDialog)


def delete_workspace_control(control: str):
    if cmds.workspaceControl(control, query=True, exists=True):
        cmds.workspaceControl(control, edit=True, close=True)
        cmds.deleteUI(control, control=True)


class ClutterDialog(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=get_main_window()):
        delete_workspace_control(TOOL_NAME + "WorkspaceControl")
        super().__init__(parent)
        self.setWindowTitle("Clutter Base Tools")
        self.resize(400, 200)
        self.grid_layout = QtWidgets.QGridLayout(self)
        self.login_button = QtWidgets.QPushButton("Login", self)
        self.login_button.clicked.connect(self.user_login)
        self.grid_layout.addWidget(self.login_button)

    @Slot(str, str)
    def auth_user(self, role, user):
        print(role, user)
        self.login_widget.close()

    def user_login(self):
        self.login_widget = LoginWidget(self.parent())
        self.login_widget.authenticated.connect(self.auth_user)
        self.login_widget.show()


clutter_dialog = ClutterDialog()
clutter_dialog.show(dockable=True)
