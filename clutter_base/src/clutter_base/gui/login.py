"""A small PySide6 login widget using per-user MongoDB RBAC authentication.

Users are created by an App Admin via the ``clutter-admin`` CLI tool.
Self-registration has been removed.
"""

from __future__ import annotations

from typing import Optional, Tuple

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from clutter_base.db.connection import connect_as_user
from clutter_base.db.users import get_user_role


class LoginWidget(QWidget):
    """Widget that collects credentials and emits login success.

    On successful authentication the ``authenticated`` signal is emitted with
    ``(role, username)``.  The caller can retrieve the active MongoDB session
    via :attr:`session` (a ``(MongoClient, Database)`` tuple).
    """

    authenticated = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._session: Optional[Tuple[MongoClient, Database]] = None
        self._build_ui()

    # ------------------------------------------------------------------
    # Public accessor
    # ------------------------------------------------------------------

    @property
    def session(self) -> Optional[Tuple[MongoClient, Database]]:
        """Return the ``(client, db)`` pair from the last successful login."""
        return self._session

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        form = QFormLayout()

        self._username = QLineEdit()
        self._username.setPlaceholderText("Enter username")
        form.addRow("Username", self._username)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Enter password")
        form.addRow("Password", self._password)

        self._status = QLabel()
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        login_button = QPushButton("Login")
        login_button.clicked.connect(self._handle_login)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(login_button)
        layout.addWidget(self._status)

    # ------------------------------------------------------------------
    # Login handler
    # ------------------------------------------------------------------

    def _handle_login(self) -> None | tuple[str, str]:
        username = self._username.text().strip()
        password = self._password.text()

        if not username or not password:
            self._show_message("Both username and password are required.", QMessageBox.Icon.Warning)
            return

        try:
            client, db = connect_as_user(username, password)
        except (PyMongoError, ValueError):
            self._show_message("Invalid credentials.", QMessageBox.Icon.Warning)
            return

        role = get_user_role(username, db)
        print(role)
        if role is None:
            client.close()
            self._show_message(
                "Authenticated but no user profile found. Contact an admin.",
                QMessageBox.Icon.Warning,
            )
            return

        self._session = (client, db)
        self._set_status(f"Logged in as {role.replace('_', ' ').title()}.")
        self.authenticated.emit(role, username)
        return role, username, db

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        self._status.setText(message)

    def _show_message(
        self,
        message: str,
        icon: QMessageBox.Icon = QMessageBox.Icon.Information,
    ) -> None:
        QMessageBox(icon, "Login", message, QMessageBox.StandardButton.Ok, self).exec()


def main() -> None:
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    widget = LoginWidget()
    widget.authenticated.connect(lambda role, user: print(f"{role} '{user}' authenticated"))
    widget.show()
    app.exec()


if __name__ == "__main__":
    main()
