import sys
import logging

from aura_core.utils.logger_config import setup_logging

LOG_LEVEL_CONFIG = "INFO"
log_file_status_msg = setup_logging(log_level_str=LOG_LEVEL_CONFIG)

logger = logging.getLogger(__name__)
logger.info(f"Aura application starting. Logging status: {log_file_status_msg}")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from aura_ui.main_window import MainWindow
from aura_ui.themes.theme_manager import ThemeManager

from aura_core.services.gemini_service import GeminiService
from aura_core.services.os_interaction_service import OSInteractionService
from aura_core.services.credential_manager import CredentialManager
from aura_core.services.accessibility_service import AccessibilityService  # NEW IMPORT

from aura_core.agents.nlu_agent import NLUAgent
from aura_core.agents.planning_agent import PlanningAgent
from aura_core.agents.action_agent import ActionAgent
from aura_core.agents.perception_agent import PerceptionAgent

from aura_core.main_orchestrator import MainOrchestrator


def main():
    logger.info("Initializing QApplication...")
    app = QApplication(sys.argv)
    ThemeManager.apply_theme(app, "dark_theme.qss")
    main_window = MainWindow()

    orchestrator_instance = None
    initialization_successful = False
    try:
        gemini_service = GeminiService();
        logger.info("GeminiService initialized.")
        os_interaction_service = OSInteractionService();
        logger.info("OSInteractionService initialized.")
        credential_manager = CredentialManager();
        logger.info("CredentialManager initialized.")
        accessibility_service = AccessibilityService();
        logger.info("AccessibilityService initialized.")  # NEW

        perception_agent = PerceptionAgent(gemini_service, os_interaction_service);
        logger.info("PerceptionAgent initialized.")
        nlu_agent = NLUAgent(gemini_service);
        logger.info("NLUAgent initialized.")
        planning_agent = PlanningAgent(gemini_service);
        logger.info("PlanningAgent initialized.")

        action_agent = ActionAgent(  # MODIFIED: Pass accessibility_service
            os_interaction_service=os_interaction_service,
            perception_agent=perception_agent,
            credential_manager=credential_manager,
            gemini_service=gemini_service,
            accessibility_service=accessibility_service  # NEW
        );
        logger.info("ActionAgent initialized.")

        orchestrator_instance = MainOrchestrator(
            nlu_agent, planning_agent, action_agent, perception_agent,
            credential_manager, main_window
            # Note: Orchestrator doesn't directly need accessibility_service, ActionAgent uses it.
        );
        logger.info("MainOrchestrator initialized.")

        main_window.update_status("Core services initialized.", "info")
        initialization_successful = True

        main_window.process_command_signal.connect(orchestrator_instance.handle_user_command)
        main_window.stop_action_signal.connect(orchestrator_instance.handle_stop_request)
        orchestrator_instance.update_status_signal.connect(main_window.update_status)
        orchestrator_instance.trigger_master_password_prompt_signal.connect(main_window.prompt_for_master_password)
        orchestrator_instance.trigger_service_credential_prompt_signal.connect(
            main_window.prompt_for_service_credential)

    except Exception as e:
        logger.critical(f"CRITICAL ERROR during core component initialization: {e}", exc_info=True)
        if main_window:
            main_window.show(); main_window.update_status(f"Critical Setup Error: {e}. Check logs.", "error")
        else:
            print(f"CRITICAL: MainWindow could not be initialized. Error: {e}"); sys.exit(1)

    main_window.show();
    logger.info("Main window shown.")

    if initialization_successful and orchestrator_instance:
        logger.info("Scheduling credential store readiness check.")
        QTimer.singleShot(200, orchestrator_instance.ensure_credential_store_is_ready)
        main_window.update_status("Aura is ready. Checking credential store...", "info")
    elif main_window:
        main_window.update_status("Aura UI started, but core services have critical issues.", "warning")

    logger.info("Entering Qt application event loop.")
    exit_code = 0
    try:
        exit_code = app.exec()
    except SystemExit as se:
        exit_code = se.code if isinstance(se.code, int) else 0
    except KeyboardInterrupt:
        logger.info("Exited via Ctrl+C."); exit_code = 0
    except Exception as e:
        logger.critical(f"App crashed in exec(): {e}", exc_info=True); exit_code = 1
    finally:
        logger.info(f"Aura shutting down (exit code: {exit_code}).")
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        fatal_msg = f"FATAL ERROR in __main__: {e}";
        print(fatal_msg)
        if 'logger' in globals() and logger:
            logger.critical(fatal_msg, exc_info=True)
        else:
            import traceback; traceback.print_exc()
        sys.exit(1)