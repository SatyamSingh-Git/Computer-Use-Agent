from PyQt6.QtWidgets import QPushButton, QWidget, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtGui import QIcon
import os

class StopButton(QWidget):
    stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StopButtonContainer")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.button = QPushButton("STOP", self)
        self.button.setObjectName("StopButton") # For styling
        self.button.setToolTip("Immediately stop Aura's current action (Ctrl+Shift+S)") # Placeholder for shortcut
        # You'll need to find/create an icon like 'stop.svg' or '.png'
        # and place it in aura_project/assets/icons/
        stop_icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icons", "stop_icon.svg") # Adjust path
        if os.path.exists(stop_icon_path):
            self.button.setIcon(QIcon(stop_icon_path))
            self.button.setIconSize(QSize(20, 20)) # Adjust size as needed
            self.button.setText("") # Show only icon if available
            self.button.setFixedSize(40, 40) # Make it a square or circle via QSS
        else:
            self.button.setText("STOP")

        self.button.clicked.connect(self.stopped.emit)
        layout.addWidget(self.button)

        self.setLayout(layout)