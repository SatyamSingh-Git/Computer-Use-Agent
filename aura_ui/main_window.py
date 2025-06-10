import logging
import os
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QSplitter,
    QMenuBar, QMenu, QStatusBar, QDialog, QMessageBox, QPushButton, QApplication  # Added QDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QMetaObject, Q_ARG  # Added QMetaObject, Q_ARG
from PyQt6.QtGui import QAction, QIcon

# Import local widgets and services
from .widgets.command_input_bar import CommandInputBar
from .widgets.status_display import StatusDisplay
from .widgets.stop_button import StopButton
from .widgets.credential_prompt_dialog import MasterPasswordDialog, CredentialEntryDialog  # NEW IMPORT

# from .widgets.settings_dialog import SettingsDialog # Placeholder for future settings

# Import voice service from core (assuming it's set up correctly)
try:
    from aura_core.services.voice_service import VoiceService

    VOICE_SERVICE_AVAILABLE = True
except ImportError as e:
    VOICE_SERVICE_AVAILABLE = False
    # logger is not defined yet here, so print for critical import error
    print(f"CRITICAL: VoiceService could not be imported from aura_core.services.voice_service: {e}")
    # In a real app, you might have a fallback or disable voice features gracefully.

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    # --- Existing Signals ---
    process_command_signal = pyqtSignal(str)
    stop_action_signal = pyqtSignal()
    update_status_from_thread_signal = pyqtSignal(str, str)  # For VoiceService status updates

    # --- NEW Signals for Credential Dialog Interaction ---
    # Signals EMITTED BY Orchestrator (via main_window_ref) to trigger UI dialogs
    # These are connected to MainWindow's public prompt_for_* methods in main.py

    # Signals EMITTED BY MainWindow back TO Orchestrator with dialog results
    master_password_response_signal = pyqtSignal(str)  # Emits the entered master password or empty if cancelled
    service_credential_response_signal = pyqtSignal(str, str, str, bool)  # service, user, pass, save_flag

    # Internal signals used by QMetaObject.invokeMethod to call slots in the UI thread
    _internal_request_master_password_signal = pyqtSignal(bool)
    _internal_request_service_credential_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aura - AI Desktop Assistant")
        # A common size, adjust as needed for your content
        desktop = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(
            (desktop.width() - 900) // 2,
            (desktop.height() - 700) // 2,
            900, 700
        )
        self.setObjectName("MainWindow")

        self._create_menu_bar()
        self._create_status_bar()
        self._init_ui_layout()  # Renamed from _init_ui to avoid conflict if base class has it

        # Connect internal signals for dialog responses initiated by QMetaObject.invokeMethod
        self._internal_request_master_password_signal.connect(self._handle_request_master_password_slot)
        self._internal_request_service_credential_signal.connect(self._handle_request_service_credential_slot)

        # Initialize Voice Service
        self.voice_service = None
        self.voice_listening_active = False
        if VOICE_SERVICE_AVAILABLE:
            try:
                self.voice_service = VoiceService(
                    on_wake_word_detected_callback=self._on_wake_word_ui_update,
                    on_transcription_complete_callback=self._on_transcription_ui_update,
                    on_listening_status_callback=self._on_listening_status_ui_update
                )
                if hasattr(self.command_input_bar_widget, 'mic_button'):
                    self.command_input_bar_widget.mic_button.toggled.connect(self._toggle_voice_listening)
                    self.command_input_bar_widget.mic_button.setToolTip("Toggle Voice Input (Mic)")
                self._update_mic_button_icon(False)
                self.update_status("Voice service ready. Click Mic to activate or use wake word.", "info")
            except ValueError as e:
                logger.error(f"Failed to initialize VoiceService (ValueError): {e}")
                self.update_status(f"Voice Service Error: {e}. Check .env file and logs.", "error")
            except Exception as e:
                logger.error(f"Unexpected error initializing VoiceService: {e}", exc_info=True)
                self.update_status(f"Voice Service critical error: {e}. Check logs.", "error")
        else:
            self.update_status("Voice service module not available. Voice input disabled.", "warning")
            if hasattr(self, 'command_input_bar_widget') and hasattr(self.command_input_bar_widget, 'mic_button'):
                self.command_input_bar_widget.mic_button.setEnabled(False)
                self.command_input_bar_widget.mic_button.setToolTip("Voice service unavailable")

        # Connect the thread-safe signal for general status updates from other threads
        self.update_status_from_thread_signal.connect(self.update_status)

        logger.info("MainWindow initialized.")

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        settings_action = QAction(QIcon(), "&Settings", self)  # Placeholder for icon
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        exit_action = QAction(QIcon(), "&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction(QIcon(), "&About Aura", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)

    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

    def _init_ui_layout(self):
        central_widget = QWidget(self)
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Top bar (optional, e.g., for stop button or other global controls)
        top_bar_widget = QWidget()
        top_bar_layout = QHBoxLayout(top_bar_widget)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        # Add spacers to push stop button to the right
        top_bar_layout.addStretch(1)
        self.stop_button_widget = StopButton(self)
        self.stop_button_widget.stopped.connect(self._on_stop_button_pressed)
        top_bar_layout.addWidget(self.stop_button_widget)
        main_layout.addWidget(top_bar_widget)

        # Main content area using QSplitter
        splitter = QSplitter(Qt.Orientation.Vertical, self)

        self.status_display_widget = StatusDisplay(self)
        splitter.addWidget(self.status_display_widget)

        self.command_input_bar_widget = CommandInputBar(self)
        self.command_input_bar_widget.command_entered.connect(self._on_command_entered_from_input_bar)
        splitter.addWidget(self.command_input_bar_widget)

        # Set initial sizes for splitter sections (adjust as needed)
        # Give more space to status display initially
        splitter.setSizes([int(self.height() * 0.8), int(self.height() * 0.2)])
        splitter.setStretchFactor(0, 1)  # Status display can stretch
        splitter.setStretchFactor(1, 0)  # Command bar fixed height relative to its content

        main_layout.addWidget(splitter, 1)

        self.command_input_bar_widget.set_focus()

    def _on_command_entered_from_input_bar(self, command_text: str):
        logger.info(f"Command entered via UI text input: {command_text}")
        self.update_status(f"You: {command_text}", "info")
        self.process_command_signal.emit(command_text)

    def _on_stop_button_pressed(self):
        logger.warning("STOP button pressed by user.")
        self.update_status("STOP command received. Attempting to halt actions...", "warning")
        self.stop_action_signal.emit()

    @pyqtSlot(str, str)
    def update_status(self, message: str, message_type: str = "info"):
        self.status_display_widget.append_status(message, message_type)
        if message_type in ["info", "success", "debug"] and len(message) < 100:
            self.status_bar.showMessage(message, 5000)  # Show brief messages
        elif message_type in ["error", "warning"]:
            self.status_bar.showMessage(f"{message_type.upper()}: {message[:100]}...", 10000)  # Show errors longer

    @pyqtSlot(bool)
    def _toggle_voice_listening(self, checked: bool):
        if not self.voice_service or not VOICE_SERVICE_AVAILABLE:
            self.update_status("Voice service is not available.", "error")
            if hasattr(self.command_input_bar_widget, 'mic_button'):
                self.command_input_bar_widget.mic_button.setChecked(False)
            return

        if checked:
            logger.info("User toggled voice listening ON.")
            self.voice_service.start_listening()
            self.voice_listening_active = True
            # Status updates now come via _on_listening_status_ui_update
        else:
            logger.info("User toggled voice listening OFF.")
            self.voice_service.stop_listening()
            self.voice_listening_active = False
            self.update_status("Voice input deactivated.", "info")  # User action, direct update
        self._update_mic_button_icon(checked)

    def _update_mic_button_icon(self, is_listening: bool):
        if not hasattr(self.command_input_bar_widget, 'mic_button'): return

        button = self.command_input_bar_widget.mic_button
        icon_name = "microphone_on.svg" if is_listening else "microphone_off.svg"
        # Path construction assuming assets/ is at project root, and this file is in aura_ui/
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # up to aura_project/
        icon_path = os.path.join(project_root, "assets", "icons", icon_name)

        if os.path.exists(icon_path):
            button.setIcon(QIcon(icon_path))
        else:
            logger.warning(f"Mic icon not found: {icon_path}")
            button.setText("Mic" if not is_listening else "Listening")  # Fallback text
            button.setIcon(QIcon())

    def _on_wake_word_ui_update(self):
        self.update_status_from_thread_signal.emit("Wake word heard! Listening for your command...", "success")
        # Optionally, visually indicate wake word detected (e.g., brief mic button flash)

    def _on_transcription_ui_update(self, transcribed_text: str):
        self.update_status_from_thread_signal.emit(f"Aura heard: \"{transcribed_text}\"", "info")
        if transcribed_text:
            self.process_command_signal.emit(transcribed_text)  # Send to orchestrator

    def _on_listening_status_ui_update(self, status_message: str):
        msg_type = "debug"
        if "error" in status_message.lower():
            msg_type = "error"
        elif "listening for" in status_message.lower() and "error" not in status_message.lower():
            msg_type = "info"
        self.update_status_from_thread_signal.emit(status_message, msg_type)

    def _open_settings(self):
        self.update_status("Settings dialog not yet implemented.", "warning")
        # from .widgets.settings_dialog import SettingsDialog
        # settings_dialog = SettingsDialog(self)
        # settings_dialog.exec()

    def _show_about_dialog(self):
        QMessageBox.about(self, "About Aura",
                          "Aura - Your AI Desktop Assistant\nVersion 0.2.0 (Phase 7 Dev)\n"
                          "This application uses AI to assist with desktop tasks.")
        logger.info("About dialog shown.")

    # --- NEW SLOTS and METHODS for Credential Dialogs ---
    @pyqtSlot(bool)
    def _handle_request_master_password_slot(self, setup_mode: bool):
        """SLOT: Handles request from another thread to show master password dialog."""
        logger.debug(f"UI Thread: Received request for master password dialog (setup_mode={setup_mode})")
        dialog = MasterPasswordDialog(parent=self, setup_mode=setup_mode)

        # Disconnect previous connections if any to avoid multiple emissions (safer)
        try:
            dialog.master_password_provided.disconnect()
        except TypeError:
            pass  # No connections to disconnect

        dialog.master_password_provided.connect(
            lambda pwd: self.master_password_response_signal.emit(pwd)
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.master_password_response_signal.emit("")  # Emit empty for cancel

    @pyqtSlot(str, str)
    def _handle_request_service_credential_slot(self, service_name_hint: str, username_hint: str):
        """SLOT: Handles request to show service credential entry dialog."""
        logger.debug(f"UI Thread: Received request for service credential dialog for '{service_name_hint}'")
        dialog = CredentialEntryDialog(
            service_name_hint=service_name_hint,
            username_hint=username_hint,
            parent=self
        )

        try:
            dialog.credential_details_provided.disconnect()
        except TypeError:
            pass

        dialog.credential_details_provided.connect(
            lambda service, user, pwd, save: self.service_credential_response_signal.emit(service, user, pwd, save)
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.service_credential_response_signal.emit("", "", "", False)  # Emit empty/false for cancel

    # Public methods for Orchestrator to call (thread-safe via QMetaObject.invokeMethod)
    def prompt_for_master_password(self, setup_mode: bool = False):
        """Invokes the master password dialog. Called by Orchestrator."""
        logger.debug(f"MainWindow: Queuing master password prompt (setup_mode={setup_mode})")
        QMetaObject.invokeMethod(self, "_internal_request_master_password_signal", Qt.ConnectionType.QueuedConnection,
                                 Q_ARG(bool, setup_mode))

    def prompt_for_service_credential(self, service_name_hint: str = "", username_hint: str = ""):
        """Invokes the service credential dialog. Called by Orchestrator."""
        logger.debug(f"MainWindow: Queuing service credential prompt for '{service_name_hint}'")
        QMetaObject.invokeMethod(self, "_internal_request_service_credential_signal",
                                 Qt.ConnectionType.QueuedConnection,
                                 Q_ARG(str, service_name_hint),
                                 Q_ARG(str, username_hint))

    def closeEvent(self, event):
        logger.info("MainWindow closeEvent triggered.")
        if self.voice_service and VOICE_SERVICE_AVAILABLE:
            self.voice_service.stop_listening()  # Ensure graceful shutdown of the voice thread
            if hasattr(self.voice_service, 'cleanup'):  # If you added a cleanup method
                self.voice_service.cleanup()
        logger.info("Aura application is preparing to shut down.")
        event.accept()


# Example for standalone testing (optional, but good for UI development)
if __name__ == '__main__':
    import sys

    # Basic logging for standalone test
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s")

    # Mock VoiceService if not available or for simple UI testing
    if not VOICE_SERVICE_AVAILABLE:
        class MockVoiceService:
            def __init__(self, *args, **kwargs): logger.debug("MockVoiceService Initialized")

            def start_listening(self): logger.debug("MockVoiceService: start_listening called")

            def stop_listening(self): logger.debug("MockVoiceService: stop_listening called")

            def cleanup(self): logger.debug("MockVoiceService: cleanup called")


        VoiceService = MockVoiceService  # Override with mock
        VOICE_SERVICE_AVAILABLE = True  # Pretend it's available for the test

    app = QApplication(sys.argv)

    # Apply a theme for testing (ensure dark_theme.qss is accessible)
    try:
        theme_path = os.path.join(os.path.dirname(__file__), "themes", "dark_theme.qss")
        if os.path.exists(theme_path):
            with open(theme_path, "r") as f:
                app.setStyleSheet(f.read())
            logger.info("Test theme applied.")
        else:
            logger.warning(f"Test theme file not found: {theme_path}")
    except Exception as e:
        logger.error(f"Error applying test theme: {e}")

    window = MainWindow()


    # Test credential dialogs via direct call (for UI thread testing)
    # In real app, Orchestrator calls these via QMetaObject.invokeMethod
    def test_master_dialog_from_main():
        window._handle_request_master_password_slot(setup_mode=True)


    def test_service_dialog_from_main():
        window._handle_request_service_credential_slot("TestService.com", "testuser")


    window.master_password_response_signal.connect(lambda p: logger.info(f"TEST_MAIN: Master Pwd Response: '{p}'"))
    window.service_credential_response_signal.connect(lambda s, u, p, sv: logger.info(
        f"TEST_MAIN: Service Cred Response: S='{s}' U='{u}' PwdLen='{len(p)}' Save='{sv}'"))

    # Add test buttons to main window for dialogs (REMOVE FOR PRODUCTION)
    test_btn_master = QPushButton("Test Master Pwd Dialog (Setup)", window)
    test_btn_master.clicked.connect(lambda: window.prompt_for_master_password(True))  # Uses QMetaObject
    test_btn_master.move(10, window.height() - 80)
    test_btn_service = QPushButton("Test Service Cred Dialog", window)
    test_btn_service.clicked.connect(
        lambda: window.prompt_for_service_credential("Example.com", "user"))  # Uses QMetaObject
    test_btn_service.move(200, window.height() - 80)

    window.show()
    sys.exit(app.exec())