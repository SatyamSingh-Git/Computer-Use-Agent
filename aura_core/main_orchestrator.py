import logging
import json
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QEventLoop, pyqtSlot

from aura_core.agents.nlu_agent import NLUAgent
from aura_core.agents.planning_agent import PlanningAgent
from aura_core.agents.action_agent import ActionAgent
from aura_core.agents.perception_agent import PerceptionAgent
from aura_core.services.credential_manager import CredentialManager

logger = logging.getLogger(__name__)


class MainOrchestrator(QObject):  # Inherits from QObject
    # --- DEFINE SIGNALS AT CLASS LEVEL ---
    update_status_signal = pyqtSignal(str, str)
    trigger_master_password_prompt_signal = pyqtSignal(bool)
    trigger_service_credential_prompt_signal = pyqtSignal(str, str)

    # --- END SIGNAL DEFINITIONS ---

    def __init__(self, nlu_agent: NLUAgent, planning_agent: PlanningAgent,
                 action_agent: ActionAgent, perception_agent: PerceptionAgent,
                 credential_manager: CredentialManager, main_window_ref: 'MainWindow'):
        super().__init__()  # Call QObject's __init__ FIRST

        self.nlu_agent = nlu_agent
        self.planning_agent = planning_agent
        self.action_agent = action_agent
        self.perception_agent = perception_agent
        self.credential_manager = credential_manager
        self.main_window = main_window_ref

        self.is_busy = False
        self.current_plan = []
        self.current_step_index = 0
        self.execution_context = {}

        self.step_execution_timer = QTimer(self)
        self.step_execution_timer.setSingleShot(True)
        self.step_execution_timer.timeout.connect(self._execute_next_plan_step)

        if self.main_window:
            # These signals are emitted BY MainWindow TO this Orchestrator
            self.main_window.master_password_response_signal.connect(self._on_master_password_received)
            self.main_window.service_credential_response_signal.connect(self._on_service_credential_received)
        else:
            logger.error("MainOrchestrator initialized without MainWindow reference! Credential dialogs will not work.")

        self._dialog_response_event_loop = None
        self._dialog_response_data = None

        logger.info(
            "MainOrchestrator initialized. Credential store readiness will be checked on demand or at startup by main.py.")

    # (Rest of the MainOrchestrator class methods: ensure_credential_store_is_ready,
    #  _request_*_from_ui, _on_*_received, get_*_input_for_action, handle_user_command,
    #  _validate_nlu_result, _validate_plan, _execute_next_plan_step,
    #  _finish_plan_execution, handle_stop_request - all remain the same as the last complete version)
    def ensure_credential_store_is_ready(self):
        logger.info("Orch: Ensuring cred store ready...")
        if not self.credential_manager.is_initialized():
            self.update_status_signal.emit("Cred store needs setup. Create master password.", "info")
            master_pwd = self._request_master_password_from_ui(setup_mode=True)
            if master_pwd and self.credential_manager.setup_master_password(master_pwd):
                self.update_status_signal.emit("Master pwd set. Store initialized.", "success")
            elif master_pwd:
                self.update_status_signal.emit("Failed to set up master pwd.", "error")
            else:
                self.update_status_signal.emit("Master pwd setup cancelled.", "warning")
        elif not self.credential_manager.is_unlocked:
            self.update_status_signal.emit("Cred store locked. Enter master pwd.", "info")
            master_pwd = self._request_master_password_from_ui(setup_mode=False)
            if master_pwd and self.credential_manager.unlock_store(master_pwd):
                self.update_status_signal.emit("Cred store unlocked.", "success")
            elif master_pwd:
                self.update_status_signal.emit("Failed to unlock (incorrect pwd?).", "error")
            else:
                self.update_status_signal.emit("Cred store unlock cancelled.", "warning")
        else:
            logger.info("Cred store already ready."); self.update_status_signal.emit("Cred store ready.", "info")

    def _request_master_password_from_ui(self, setup_mode: bool) -> str | None:
        if not self.main_window: logger.error("No MainWindow ref for master pwd dialog."); return None
        logger.debug(f"Orch: Req master pwd UI (setup={setup_mode})")
        self._dialog_response_data = None;
        loop = QEventLoop();
        self._dialog_response_event_loop = loop
        self.trigger_master_password_prompt_signal.emit(setup_mode);
        loop.exec()
        self._dialog_response_event_loop = None;
        response = self._dialog_response_data
        logger.debug(f"Orch: Master pwd dialog done. Resp: {'******' if response else 'None/Cancel'}")
        return response if isinstance(response, str) and response else None

    @pyqtSlot(str)
    def _on_master_password_received(self, password: str):
        logger.debug(f"Orch: Master pwd resp received: {'******' if password else 'Cancelled/Empty'}")
        self._dialog_response_data = password
        if self._dialog_response_event_loop and self._dialog_response_event_loop.isRunning(): self._dialog_response_event_loop.quit()

    def _request_service_credential_from_ui(self, s_name: str, u_hint: str = "") -> tuple[str, str, str, bool] | None:
        if not self.main_window: logger.error("No MainWindow ref for service cred dialog."); return None
        logger.debug(f"Orch: Req service creds UI for '{s_name}'")
        self._dialog_response_data = None;
        loop = QEventLoop();
        self._dialog_response_event_loop = loop
        self.trigger_service_credential_prompt_signal.emit(s_name, u_hint);
        loop.exec()
        self._dialog_response_event_loop = None;
        response = self._dialog_response_data
        logger.debug(f"Orch: Service cred dialog done. Resp data present: {response is not None}")
        return response if isinstance(response, tuple) and len(response) == 4 and response[0] else None

    @pyqtSlot(str, str, str, bool)
    def _on_service_credential_received(self, s: str, u: str, p: str, save: bool):
        logger.debug(f"Orch: Service cred resp received for '{s}'. Save: {save}")
        self._dialog_response_data = (s, u, p, save)
        if self._dialog_response_event_loop and self._dialog_response_event_loop.isRunning(): self._dialog_response_event_loop.quit()

    def get_master_password_input_for_action(self, setup_mode: bool) -> str | None:
        return self._request_master_password_from_ui(setup_mode)

    def get_service_credential_input_for_action(self, s_name: str, u_hint: str = "") -> tuple[
                                                                                            str, str, str, bool] | None:
        return self._request_service_credential_from_ui(s_name, u_hint)

    def handle_user_command(self, command_text: str):
        if self.is_busy: self.update_status_signal.emit("Aura busy. Wait.", "warning"); return
        self.is_busy = True;
        self.update_status_signal.emit(f"Processing: '{command_text}'...", "info")
        parsed_command = self.nlu_agent.parse_command(command_text, self.execution_context)
        self.current_plan = [];
        self.current_step_index = 0
        if not self._validate_nlu_result(parsed_command): self.is_busy = False; return
        intent = parsed_command.get("intent");
        nlu_entities = parsed_command.get("entities", {})
        if isinstance(nlu_entities, dict):
            logger.debug(f"Orch: Merging NLU entities. Old context keys: {list(self.execution_context.keys())}")
            self.execution_context.update(nlu_entities)
            logger.info(f"Orch: NLU entities merged. Exec_context keys: {list(self.execution_context.keys())}")
        app_hint = nlu_entities.get("application_hint") or nlu_entities.get("tool_hint") or nlu_entities.get(
            "application_name")
        if app_hint:
            if self.execution_context.get("last_opened_app_name") != app_hint:
                logger.info(f"Orch Context: last_app_name='{app_hint}'. Clearing old window title.")
                self.execution_context["last_opened_app_name"] = app_hint
                self.execution_context.pop("last_opened_window_title", None)
        self.update_status_signal.emit(f"NLU: {intent}, Entities: {json.dumps(nlu_entities)}", "debug")
        if intent == "unknown_command": self.update_status_signal.emit("Unknown command. Rephrase?",
                                                                       "info"); self.is_busy = False; return
        plan_to_execute = None
        if intent == "achieve_goal":
            goal_desc = nlu_entities.get("goal_description")
            if not goal_desc: self.update_status_signal.emit("NLU Error: Goal unclear.",
                                                             "error"); self.is_busy = False; return
            self.update_status_signal.emit(f"Planning for: '{goal_desc[:70]}...'...", "info")
            plan_to_execute = self.planning_agent.create_plan_for_goal(goal_desc, nlu_entities)
        else:  # Fallback for simpler intents if any are still directly used
            logger.warning(f"Orch: Handling non-'achieve_goal' intent '{intent}'. Basic planning.")
            plan_to_execute = self.planning_agent.create_plan(intent,
                                                              nlu_entities)  # Assumes create_plan exists in PlanningAgent
        if not self._validate_plan(plan_to_execute): self.is_busy = False; return
        self.current_plan = plan_to_execute
        self.update_status_signal.emit(f"Plan Generated ({len(self.current_plan)} steps). Executing...", "info")
        for i, step in enumerate(self.current_plan): self.update_status_signal.emit(
            f"  Step {i + 1}: {step.get('action_type')} - {json.dumps(step.get('parameters'))}", "debug")
        self._execute_next_plan_step()

    def _validate_nlu_result(self, parsed_command) -> bool:
        if not parsed_command or not isinstance(parsed_command, dict) or "intent" not in parsed_command: logger.error(
            "NLU: Invalid structure."); self.update_status_signal.emit("NLU Error: Structure.", "error"); return False
        intent = parsed_command.get("intent");
        entities = parsed_command.get("entities", {})
        if intent in ["nlu_error", "nlu_parsing_error"]: err = entities.get("error_message", "Unknown"); raw = str(
            entities.get("raw_response", ""))[:70]; logger.error(
            f"NLU Error: {err}. Raw: {raw}..."); self.update_status_signal.emit(f"NLU Error: {err}",
                                                                                "error"); return False
        if intent == "achieve_goal" and not entities.get("goal_description"): logger.error(
            "NLU: 'achieve_goal' no 'goal_description'."); self.update_status_signal.emit("NLU Error: Goal unclear.",
                                                                                          "error"); return False
        return True

    def _validate_plan(self, plan) -> bool:
        if not plan or not isinstance(plan, list) or not (
                plan and isinstance(plan[0], dict) and plan[0].get("action_type")): logger.error(
            f"Plan: Invalid structure. Plan: {str(plan)[:200]}"); self.update_status_signal.emit(
            "Planning Error: Structure.", "error"); return False
        if plan[0].get("action_type") == "error": err = plan[0].get("parameters", {}).get("message",
                                                                                          "Unknown"); raw = str(
            plan[0].get("parameters", {}).get("raw_response", ""))[:70]; logger.error(
            f"Plan Error: {err}. Raw: {raw}..."); self.update_status_signal.emit(f"Planning Error: {err}",
                                                                                 "error"); return False
        return True

    def _execute_next_plan_step(self):
        if self.current_step_index < len(self.current_plan):
            action_step = self.current_plan[self.current_step_index];
            action_type_log = action_step.get('action_type', 'UnknownAction')
            self.update_status_signal.emit(
                f"Executing Step {self.current_step_index + 1}/{len(self.current_plan)}: {action_type_log}", "info")
            success, result_data = self.action_agent.execute_action(action_step, self.execution_context,
                                                                    orchestrator_callback=self)
            if result_data and isinstance(result_data, dict):
                keys_to_clear = [k for k, v in result_data.items() if v is None and k in self.execution_context]
                for key_to_clear in keys_to_clear:
                    if key_to_clear in self.execution_context: del self.execution_context[key_to_clear]
                    if key_to_clear in result_data: del result_data[key_to_clear]
                self.execution_context.update(result_data)
                logger.debug(f"Orch: Exec_context updated. Keys: {list(self.execution_context.keys())}")
                if result_data.get("error"): self.update_status_signal.emit(f"Action Error: {result_data.get('error')}",
                                                                            "error")
            if success:
                self.current_step_index += 1; self.step_execution_timer.start(500)
            else:
                self.update_status_signal.emit(
                    f"Error at step {self.current_step_index + 1} ('{action_type_log}'). Halting.",
                    "error"); self._finish_plan_execution(completed=False)
        else:
            self._finish_plan_execution(completed=True)

    def _finish_plan_execution(self, completed: bool):
        status = "Plan completed." if completed else "Plan finished (halted/failed).";
        level = "success" if completed else "warning"
        self.update_status_signal.emit(status, level);
        logger.info(status)
        self.is_busy = False;
        self.current_plan = [];
        self.current_step_index = 0

    def handle_stop_request(self):
        logger.info("Orch: STOP request.");
        if self.step_execution_timer.isActive(): self.step_execution_timer.stop(); logger.info("Step timer stopped.")
        if self.is_busy or self.current_plan:
            self.update_status_signal.emit("STOP: Halting plan...", "warning"); self._finish_plan_execution(
                completed=False)
        else:
            self.update_status_signal.emit("No active plan to stop.", "info")