from PyQt6.QtWidgets import QTextEdit, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

class StatusDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusDisplay")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.status_text_area = QTextEdit(self)
        self.status_text_area.setReadOnly(True)
        self.status_text_area.setObjectName("StatusTextArea")
        self.status_text_area.setPlaceholderText("Aura's status will appear here...")
        layout.addWidget(self.status_text_area)

        self.setLayout(layout)

    def append_status(self, message: str, message_type: str = "info"):
        # Simple coloring based on message type (can be enhanced with HTML)
        color_map = {
            "info": "black",
            "success": "green",
            "error": "red",
            "warning": "orange",
            "debug": "grey"
        }
        color = color_map.get(message_type.lower(), "black")

        # Using HTML for basic color styling
        # More advanced styling could be done with QTextCharFormat
        self.status_text_area.append(f"<span style='color:{color};'>{message}</span>")
        self.status_text_area.ensureCursorVisible() # Scroll to the bottom

    def clear_status(self):
        self.status_text_area.clear()

    def set_status(self, message: str, message_type: str = "info"):
        self.clear_status()
        self.append_status(message, message_type)