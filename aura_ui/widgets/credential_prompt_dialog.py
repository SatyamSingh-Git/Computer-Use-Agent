from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QCheckBox, QDialogButtonBox
)
from PyQt6.QtCore import pyqtSignal, Qt


class MasterPasswordDialog(QDialog):
    # Emits the master password if OK is clicked
    master_password_provided = pyqtSignal(str)

    def __init__(self, parent=None, setup_mode: bool = False):
        super().__init__(parent)
        self.setup_mode = setup_mode
        if self.setup_mode:
            self.setWindowTitle("Setup Master Password")
        else:
            self.setWindowTitle("Unlock Credential Store")

        self.setModal(True)  # Block other UI interaction
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        if self.setup_mode:
            info_label = QLabel(
                "This is the first time you're using Aura's credential store, "
                "or it needs to be re-initialized.\n"
                "Please create a strong master password. This password will be used to "
                "encrypt all your stored credentials. If you forget it, your stored "
                "credentials will be unrecoverable."
            )
            info_label.setWordWrap(True)
            layout.addWidget(info_label)

            self.password_label = QLabel("New Master Password:")
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

            self.confirm_password_label = QLabel("Confirm Master Password:")
            self.confirm_password_input = QLineEdit()
            self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)

            layout.addWidget(self.password_label)
            layout.addWidget(self.password_input)
            layout.addWidget(self.confirm_password_label)
            layout.addWidget(self.confirm_password_input)
        else:  # Unlock mode
            self.password_label = QLabel("Enter Master Password:")
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addWidget(self.password_label)
            layout.addWidget(self.password_input)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept_input)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.password_input.setFocus()

    def accept_input(self):
        password = self.password_input.text()
        if not password:
            QMessageBox.warning(self, "Input Error", "Master password cannot be empty.")
            return

        if self.setup_mode:
            confirm_password = self.confirm_password_input.text()
            if password != confirm_password:
                QMessageBox.warning(self, "Input Error", "Passwords do not match.")
                return
            if len(password) < 8:  # Basic strength check
                QMessageBox.warning(self, "Input Error", "Master password should be at least 8 characters long.")
                return

        self.master_password_provided.emit(password)
        self.accept()  # Closes the dialog with QDialog.Accepted status

    def get_password(self) -> str | None:
        # This method can be called after exec() if you want to retrieve the password
        # However, using the signal is generally cleaner for Qt.
        if self.result() == QDialog.DialogCode.Accepted:
            return self.password_input.text()
        return None


class CredentialEntryDialog(QDialog):
    # Emits service_name, username, password, should_save
    credential_details_provided = pyqtSignal(str, str, str, bool)

    def __init__(self, service_name_hint: str = "", username_hint: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Enter Credentials for '{service_name_hint or 'Service'}'")
        self.setModal(True)
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        self.service_label = QLabel("Service Name:")
        self.service_input = QLineEdit(service_name_hint)
        if service_name_hint:  # If provided, make it read-only or less prominent
            self.service_input.setReadOnly(True)
            # self.service_input.setStyleSheet("background-color: #eee;") # Visually indicate read-only

        self.username_label = QLabel("Username/Email:")
        self.username_input = QLineEdit(username_hint)

        self.password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.save_credential_checkbox = QCheckBox("Save these credentials securely for future use")
        self.save_credential_checkbox.setChecked(True)  # Default to save

        layout.addWidget(self.service_label)
        layout.addWidget(self.service_input)
        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)
        layout.addWidget(self.save_credential_checkbox)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept_input)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        if not username_hint:
            self.username_input.setFocus()
        else:
            self.password_input.setFocus()

    def accept_input(self):
        service_name = self.service_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()  # Password can have spaces

        if not service_name or not username or not password:
            QMessageBox.warning(self, "Input Error", "Service name, username, and password cannot be empty.")
            return

        should_save = self.save_credential_checkbox.isChecked()
        self.credential_details_provided.emit(service_name, username, password, should_save)
        self.accept()


# Example usage
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QPushButton

    app = QApplication(sys.argv)


    def test_master_password_dialog():
        # Test setup mode
        dialog_setup = MasterPasswordDialog(setup_mode=True)
        dialog_setup.master_password_provided.connect(lambda pwd: print(f"Setup Master Password: {pwd}"))
        if dialog_setup.exec() == QDialog.DialogCode.Accepted:
            print("Master password setup accepted.")
        else:
            print("Master password setup cancelled.")

        # Test unlock mode
        dialog_unlock = MasterPasswordDialog(setup_mode=False)
        dialog_unlock.master_password_provided.connect(lambda pwd: print(f"Unlock Master Password: {pwd}"))
        if dialog_unlock.exec() == QDialog.DialogCode.Accepted:
            print("Master password unlock accepted.")
        else:
            print("Master password unlock cancelled.")


    def test_credential_entry_dialog():
        dialog = CredentialEntryDialog(service_name_hint="MyTestService.com")
        dialog.credential_details_provided.connect(
            lambda service, user, pwd, save: print(
                f"Service: {service}, User: {user}, Pass: {'*' * len(pwd)}, Save: {save}")
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            print("Credential entry accepted.")
        else:
            print("Credential entry cancelled.")


    # Create a dummy main window to show dialogs
    main_win = QDialog()  # Using QDialog as a simple window
    btn_layout = QVBoxLayout(main_win)
    btn1 = QPushButton("Test Master Password Dialog")
    btn1.clicked.connect(test_master_password_dialog)
    btn2 = QPushButton("Test Credential Entry Dialog")
    btn2.clicked.connect(test_credential_entry_dialog)
    btn_layout.addWidget(btn1)
    btn_layout.addWidget(btn2)
    main_win.setWindowTitle("Dialog Test")
    main_win.show()

    sys.exit(app.exec())