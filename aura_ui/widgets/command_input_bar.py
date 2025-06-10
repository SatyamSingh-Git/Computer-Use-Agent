import os
from PyQt6.QtWidgets import QLineEdit, QPushButton, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon


class CommandInputBar(QWidget):
    command_entered = pyqtSignal(str)

    # The mic_button's 'toggled' signal will be connected directly by MainWindow

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CommandInputBar")  # For QSS styling

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # Margins around the hbox
        layout.setSpacing(5)  # Spacing between widgets in the hbox

        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Type your command or say 'Hey Aura'...")
        self.input_field.returnPressed.connect(self._on_command_entered)
        self.input_field.setObjectName("CommandInputField")  # For QSS styling
        layout.addWidget(self.input_field, 1)  # Stretch factor 1 to take available space

        self.mic_button = QPushButton(self)
        self.mic_button.setObjectName("MicButton")  # For QSS styling
        self.mic_button.setCheckable(True)  # Essential: Makes it a toggle button
        self.mic_button.setFixedSize(35, 35)  # Consistent square size

        # Set a default icon. MainWindow can override this later if needed,
        # but it's good for the widget to be somewhat self-contained.
        # Path is relative to command_input_bar.py (in widgets/)
        # ../../assets/icons/microphone_off.svg
        default_mic_icon_path = os.path.join(
            os.path.dirname(__file__),  # current dir (widgets)
            "..",  # up to aura_ui/
            "..",  # up to aura_project/
            "assets", "icons", "microphone_off.svg"
        )
        if os.path.exists(default_mic_icon_path):
            self.mic_button.setIcon(QIcon(default_mic_icon_path))
            self.mic_button.setText("")  # Clear text if icon is set
        else:
            self.mic_button.setText("Mic")  # Fallback text if icon not found
            self.mic_button.setIcon(QIcon())  # Clear icon if not found

        self.mic_button.setToolTip("Toggle Voice Input")  # Default tooltip
        layout.addWidget(self.mic_button)

        # Optional Send button (uncomment if desired)
        # self.send_button = QPushButton("Send")
        # self.send_button.setObjectName("SendButton")
        # self.send_button.clicked.connect(self._on_command_entered)
        # layout.addWidget(self.send_button)

        self.setLayout(layout)

    def _on_command_entered(self):
        """Handles when the user presses Enter in the input field or clicks Send."""
        command_text = self.input_field.text().strip()
        if command_text:
            self.command_entered.emit(command_text)
            self.input_field.clear()

    def get_text(self) -> str:
        """Returns the current text in the input field."""
        return self.input_field.text()

    def set_text(self, text: str):
        """Sets the text in the input field."""
        self.input_field.setText(text)

    def set_focus(self):
        """Sets keyboard focus to the input field."""
        self.input_field.setFocus()

    def clear_input(self):
        """Clears the input field."""
        self.input_field.clear()


# Example of standalone execution for testing this widget (optional)
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)

    # Apply a basic style for testing
    app.setStyleSheet("""
        QWidget#CommandInputBar { background-color: #333; }
        QLineEdit#CommandInputField { background-color: #444; color: white; border: 1px solid #555; padding: 5px; }
        QPushButton#MicButton { background-color: #555; color: white; border: 1px solid #666; }
        QPushButton#MicButton:checked { background-color: #007ACC; }
    """)

    test_window = QMainWindow()
    test_widget = CommandInputBar(test_window)
    test_window.setCentralWidget(test_widget)


    def handle_command(cmd):
        print(f"Command Entered for test: {cmd}")
        test_widget.clear_input()  # Example usage of clear_input


    test_widget.command_entered.connect(handle_command)

    # Example of toggling the mic button programmatically (MainWindow would do this)
    # test_widget.mic_button.setChecked(True)

    test_window.setGeometry(300, 300, 400, 80)
    test_window.setWindowTitle("Test CommandInputBar")
    test_window.show()

    sys.exit(app.exec())