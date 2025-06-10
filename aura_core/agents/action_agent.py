import logging
import time
import re

from aura_core.services.os_interaction_service import OSInteractionService
from aura_core.agents.perception_agent import PerceptionAgent
from aura_core.services.credential_manager import CredentialManager
from aura_core.services.gemini_service import GeminiService
from aura_core.services.accessibility_service import AccessibilityService

logger = logging.getLogger(__name__)


# Mock class for testing ActionAgent standalone
class MockGeminiServiceForTesting:  # Keep this for standalone test consistency
    def generate_text_response(self, prompt):
        logger.debug(f"MOCK GEMINI (text gen for ActionAgent test): Prompt - {prompt[:100]}...")
        if "leave application" in prompt.lower(): return "Subject: Leave Application - [Your Name]\n\nDear [Principal's Name],\nI am writing to request a leave of absence due to fever..."
        return "Mock generated text for ActionAgent."


class ActionAgent:
    def __init__(self, os_interaction_service: OSInteractionService,
                 perception_agent: PerceptionAgent = None,
                 credential_manager: CredentialManager = None,
                 gemini_service: GeminiService = None,
                 accessibility_service: AccessibilityService = None):
        # (Same __init__ as your last correct version, ensure all services are stored)
        self.os_interaction = os_interaction_service
        self.perception_agent = perception_agent
        self.credential_manager = credential_manager
        self.gemini_service = gemini_service
        self.accessibility_service = accessibility_service
        if not self.os_interaction: logger.critical("AA: OSInteractionService required."); raise ValueError(
            "OSInteractionService required.")
        if not self.credential_manager: logger.warning("AA: CredentialManager not provided.")
        if not self.perception_agent: logger.warning("AA: PerceptionAgent not provided for vision-based actions.")
        if not self.gemini_service and not isinstance(self.gemini_service, MockGeminiServiceForTesting): logger.warning(
            "AA: GeminiService not provided for content generation.")
        if not self.accessibility_service: logger.warning(
            "AA: AccessibilityService not provided for accessibility actions.")
        logger.info("ActionAgent initialized.")

    # (_ensure_creds_ready_for_action, _get_effective_target_title, _get_loggable_text, _resolve_context_variable as before)
    def _ensure_creds_ready_for_action(self, orchestrator_callback) -> bool:  # Same
        if not self.credential_manager: logger.error("AA: CredMan missing."); return False
        if not orchestrator_callback: logger.error("AA: Orch CB missing."); return False
        if not self.credential_manager.is_initialized():
            logger.info("AA: Cred store uninit. Requesting setup.")
            master_pwd = orchestrator_callback.get_master_password_input_for_action(setup_mode=True)
            if master_pwd and self.credential_manager.setup_master_password(master_pwd):
                logger.info("AA: Master pwd setup OK."); return True
            else:
                logger.error("AA: Master pwd setup FAILED/cancelled."); return False
        if not self.credential_manager.is_unlocked:
            logger.info("AA: Cred store locked. Requesting unlock.")
            master_pwd = orchestrator_callback.get_master_password_input_for_action(setup_mode=False)
            if master_pwd and self.credential_manager.unlock_store(master_pwd):
                logger.info("AA: Cred store unlocked OK."); return True
            else:
                logger.error("AA: Cred store unlock FAILED/cancelled."); return False
        return True

    def _get_effective_target_title(self, parameters: dict, current_context: dict) -> str | None:  # Same
        target_title_param = parameters.get("target_window_title");
        if target_title_param: return self._resolve_context_variable(target_title_param, current_context)
        return current_context.get("last_opened_window_title")

    def _get_loggable_text(self, text_template: str, resolved_text: str, current_context: dict) -> str:  # Same
        is_password_field = False
        if text_template and "{{" in text_template:
            template_vars = re.findall(r"\{\{\s*([\w_]+)\s*\}\}", text_template)
            for var_name in template_vars:
                if var_name.endswith("_password") and var_name in current_context:
                    if str(current_context.get(var_name)) == resolved_text: is_password_field = True; break
        return "*******" if is_password_field else (
            resolved_text[:25] + "..." if len(resolved_text) > 25 else resolved_text)

    def _resolve_context_variable(self, text_template: str, context: dict) -> str | None:
        if text_template is None:
            return None

        def replace_match(match):
            var_name = match.group(1).strip()
            return str(context.get(var_name, f"{{{{{var_name}}}}}"))

        try:
            resolved_text = text_template
            for _ in range(5):
                new_text = re.sub(r"\{\{\s*([\w_]+)\s*\}\}", replace_match, resolved_text)
                if new_text == resolved_text:
                    break
                resolved_text = new_text
            return resolved_text
        except Exception as e:
            logger.error(f"Error resolving context var in '{text_template}': {e}")
            return text_template

    def execute_action(self, action_details: dict, current_context: dict = None, orchestrator_callback=None) -> tuple[
        bool, dict | None]:
        action_type = action_details.get("action_type")
        parameters = action_details.get("parameters", {})
        if current_context is None: current_context = {}

        log_params = {k: (v if not (isinstance(v, str) and ('password' in k.lower())) else '********') for k, v in
                      parameters.items()}
        logger.info(
            f"AA Executing: '{action_type}' with params: {log_params}, context_keys: {list(current_context.keys())}")

        effective_target_title = self._get_effective_target_title(parameters, current_context)
        success = False
        action_result_data = None

        # Pre-action checks for required services
        # (These checks are good, keeping them as they were, just ensure no typos)
        if not self.os_interaction and action_type not in ["log_message", "get_info_from_screen",
                                                           "get_credentials_for_service", "wait",
                                                           "generate_text_content"]:
            return False, {"error": "OSInteractionService unavailable"}
        # For vision-based, perception_agent is key
        if not self.perception_agent and action_type in ["click_element_by_description",
                                                         "type_text_into_element_by_description"]:
            return False, {"error": f"PerceptionAgent (for vision) required for {action_type}"}
        # For accessibility-based, accessibility_service is key
        if not self.accessibility_service and action_type in ["click_element_by_accessibility",
                                                              "type_text_into_element_by_accessibility",
                                                              "get_element_text_by_accessibility"]:
            return False, {"error": f"AccessibilityService required for {action_type}"}
        if not self.gemini_service and action_type == "generate_text_content":
            return False, {"error": "GeminiService required for generate_text_content"}

        # --- ACTION HANDLERS ---
        if action_type == "click_element_by_accessibility":
            target_win_title = self._resolve_context_variable(parameters.get("target_window_title"),
                                                              current_context) or effective_target_title
            element_name = self._resolve_context_variable(parameters.get("element_name"), current_context)
            control_type = parameters.get("control_type");
            automation_id = parameters.get("automation_id")
            framework_id = parameters.get("framework_id");
            class_name_re = parameters.get("class_name_re")
            element_description_for_vision = element_name or parameters.get(
                "element_description") or "the described element"  # Fallback for vision

            if not target_win_title or not (element_name or automation_id or class_name_re):
                action_result_data = {
                    "error": "Missing target_window_title or element identifier for click_element_by_accessibility."}
            else:
                logger.info(
                    f"Attempting ACCESSIBILITY click: Name='{element_name}', Control='{control_type}', AutoID='{automation_id}' in Window='{target_win_title}'")
                window_spec = self.accessibility_service._get_window(window_title_hint=target_win_title)
                if window_spec:
                    element = self.accessibility_service.find_element(
                        window_spec, element_name=element_name, control_type=control_type,
                        automation_id=automation_id, framework_id=framework_id, class_name_re=class_name_re
                    )
                    if element and self.accessibility_service.click_element(element):
                        success = True
                        action_result_data = {
                            "info": f"Clicked element '{element_name or automation_id}' in '{target_win_title}' via accessibility."}
                    else:  # Accessibility click failed or element not found by accessibility
                        logger.warning(
                            f"Accessibility click failed for '{element_name or automation_id}'. Element found: {element is not None}. Falling back to VISION based click.")
                        action_result_data = {
                            "warning_accessibility_failed": f"Element '{element_name or automation_id}' (type: {control_type}) not found or click failed via accessibility in '{target_win_title}'.",
                            "info": "Attempting vision-based fallback..."}
                        # --- FALLBACK TO VISION ---
                        if not self.perception_agent:
                            action_result_data["error"] = (action_result_data.get("error",
                                                                                  "") + " PerceptionAgent unavailable for fallback.").strip()
                        else:
                            if effective_target_title and not self.os_interaction.activate_window(
                                    title_substring=effective_target_title):
                                action_result_data["error"] = (action_result_data.get("error",
                                                                                      "") + f" Could not activate window '{effective_target_title}' for vision fallback.").strip()
                            else:
                                logger.info(
                                    f"FALLBACK VISION click: Element='{element_description_for_vision}' in '{effective_target_title or 'screen'}'")
                                coords_info, ss_bounds = self.perception_agent.get_element_coordinates_via_vision(
                                    element_description_for_vision, effective_target_title)
                                if coords_info and coords_info.get("found") and coords_info.get("x_center") is not None:
                                    rel_x, rel_y = coords_info["x_center"], coords_info["y_center"];
                                    abs_x, abs_y = rel_x, rel_y
                                    if ss_bounds and ss_bounds[2] != -1: abs_x = ss_bounds[0] + rel_x; abs_y = \
                                    ss_bounds[1] + rel_y
                                    if self.os_interaction.click_at(abs_x, abs_y):
                                        success = True;
                                        action_result_data[
                                            "info"] = f"Clicked (fallback vision) '{element_description_for_vision}' at ({abs_x},{abs_y})."
                                    else:
                                        action_result_data["error"] = (action_result_data.get("error",
                                                                                              "") + f" Vision fallback click failed at ({abs_x},{abs_y}).").strip()
                                else:
                                    reason = coords_info.get("reasoning",
                                                             "Not found") if coords_info else "Perception fail."
                                    action_result_data["error"] = (action_result_data.get("error",
                                                                                          "") + f" Vision fallback: Element '{element_description_for_vision}' not found: {reason}.").strip()
                else:
                    action_result_data = {"error": f"Window '{target_win_title}' not found for accessibility click."}


        elif action_type == "type_text_into_element_by_accessibility":

            text_template = parameters.get("text_to_type")

            target_win_title = self._resolve_context_variable(parameters.get("target_window_title"),

                                                              current_context) or effective_target_title

            element_name = self._resolve_context_variable(parameters.get("element_name"), current_context)

            control_type = parameters.get("control_type", "Edit")

            automation_id = parameters.get("automation_id")

            framework_id = parameters.get("framework_id")

            class_name_re = parameters.get("class_name_re")

            element_description_for_vision = element_name or parameters.get(
                "element_description") or "the described text field"  # Fallback for vision

            if not text_template or not target_win_title or not (element_name or automation_id or class_name_re):

                action_result_data = {"error": "Missing parameters for type_text_into_element_by_accessibility."}

            else:

                text_to_type = self._resolve_context_variable(text_template, current_context)

                if text_to_type is None:

                    action_result_data = {"error": f"Could not resolve text template: '{text_template}'"}

                else:

                    logger.info(

                        f"Attempting ACCESSIBILITY type: Name='{element_name}', Control='{control_type}', AutoID='{automation_id}' in Window='{target_win_title}'"

                    )

                    window_spec = self.accessibility_service._get_window(window_title_hint=target_win_title)

                    if window_spec:

                        element = self.accessibility_service.find_element(

                            window_spec,

                            element_name=element_name,

                            control_type=control_type,

                            automation_id=automation_id,

                            framework_id=framework_id,

                            class_name_re=class_name_re

                        )

                        if element:

                            self.accessibility_service.click_element(element)

                            time.sleep(0.2)

                            log_text_display = self._get_loggable_text(text_template, text_to_type, current_context)

                            logger.info(
                                f"AA: Typing (accessibility) '{log_text_display}' into '{element_name or automation_id}'")

                            if self.accessibility_service.set_element_text(element, text_to_type):

                                success = True

                                action_result_data = {

                                    "info": f"Typed into element '{element_name or automation_id}' via accessibility."

                                }

                            else:

                                # Accessibility type failed - fallback to vision

                                logger.warning(
                                    f"Accessibility type failed for '{element_name or automation_id}'. Falling back to VISION based type.")

                                action_result_data = {

                                    "warning_accessibility_failed": f"Failed to set text for element '{element_name or automation_id}' via accessibility.",

                                    "info": "Attempting vision-based type fallback..."

                                }

                                if not self.perception_agent:

                                    action_result_data["error"] = (

                                            action_result_data.get("error",
                                                                   "") + " PerceptionAgent unavailable for fallback."

                                    ).strip()

                                else:

                                    if effective_target_title and not self.os_interaction.activate_window(
                                            title_substring=effective_target_title):

                                        action_result_data["error"] = (

                                                action_result_data.get("error",
                                                                       "") + f" Could not activate window '{effective_target_title}' for vision fallback."

                                        ).strip()

                                    else:

                                        coords_info, ss_bounds = self.perception_agent.get_element_coordinates_via_vision(

                                            element_description_for_vision, effective_target_title

                                        )

                                        if coords_info and coords_info.get("found") and coords_info.get(
                                                "x_center") is not None:

                                            rel_x, rel_y = coords_info["x_center"], coords_info["y_center"]

                                            abs_x, abs_y = rel_x, rel_y

                                            if ss_bounds and ss_bounds[2] != -1:
                                                abs_x = ss_bounds[0] + rel_x

                                                abs_y = ss_bounds[1] + rel_y

                                            if self.os_interaction.click_at(abs_x, abs_y):

                                                time.sleep(0.3)

                                                if self.os_interaction.type_text(text_to_type,
                                                                                 target_window_title=None):

                                                    success = True

                                                    action_result_data[
                                                        "info"] = f"Typed (fallback vision) into '{element_description_for_vision}'."

                                                else:

                                                    action_result_data["error"] = (

                                                            action_result_data.get("error", "") +

                                                            f" Vision fallback type failed after click '{element_description_for_vision}'."

                                                    ).strip()

                                            else:

                                                action_result_data["error"] = (

                                                        action_result_data.get("error", "") +

                                                        f" Vision fallback click failed for '{element_description_for_vision}'."

                                                ).strip()

                                        else:

                                            reason = coords_info.get("reasoning",
                                                                     "Not found") if coords_info else "Perception fail."

                                            action_result_data["error"] = (

                                                    action_result_data.get("error", "") +

                                                    f" Vision fallback: Element '{element_description_for_vision}' not found: {reason}."

                                            ).strip()

                        else:

                            action_result_data = {

                                "error": f"Element (name='{element_name}', auto_id='{automation_id}', class_re='{class_name_re}') not found for typing in '{target_win_title}'."

                            }

                    else:

                        action_result_data = {

                            "error": f"Window '{target_win_title}' not found for accessibility typing."

                        }


        elif action_type == "get_element_text_by_accessibility":
            # (This action remains largely the same, but ensure the pre-action check for accessibility_service is in place)
            target_win_title = self._resolve_context_variable(parameters.get("target_window_title"),
                                                              current_context) or effective_target_title
            element_name = self._resolve_context_variable(parameters.get("element_name"), current_context)
            control_type = parameters.get("control_type");
            automation_id = parameters.get("automation_id");
            store_as = parameters.get("store_result_as", "last_element_text")
            framework_id = parameters.get("framework_id");
            class_name_re = parameters.get("class_name_re")
            if not target_win_title or not (element_name or automation_id or class_name_re):
                action_result_data = {"error": "Missing parameters for get_element_text_by_accessibility."}
            else:
                window_spec = self.accessibility_service._get_window(window_title_hint=target_win_title)
                if window_spec:
                    element = self.accessibility_service.find_element(window_spec, element_name=element_name,
                                                                      control_type=control_type,
                                                                      automation_id=automation_id,
                                                                      framework_id=framework_id,
                                                                      class_name_re=class_name_re)
                    if element:
                        props = self.accessibility_service.get_element_properties(element);
                        element_text = props.get("name") if props else None
                        if element_text is not None:
                            action_result_data = {store_as: element_text,
                                                  "info": f"Retrieved text '{element_text[:30]}...' from element."}; success = True
                        else:
                            action_result_data = {
                                "error": f"Could not retrieve text from '{element_name or automation_id}'. Props: {props}"}
                    else:
                        action_result_data = {
                            "error": f"Element (name='{element_name}', auto_id='{automation_id}', class_re='{class_name_re}') not found for getting text."}
                else:
                    action_result_data = {"error": f"Window '{target_win_title}' not found for getting element text."}

        # ... (All other existing action handlers like "generate_text_content", "wait", "get_credentials_for_service",
        #      "click_element_by_description" (vision-only), "type_text_into_element_by_description" (vision-only),
        #      general "type_text", "open_application", "activate_window", "close_application", "search_web", "press_key",
        #      "clear_text_in_window", "get_info_from_screen" (general vision), "log_message"
        #      should be here, complete and as per your last working version.)
        elif action_type == "generate_text_content":
            prompt_for_gen_template = parameters.get("prompt_for_generation");
            store_as = parameters.get("store_result_as", "generated_text_content")
            resolved_prompt_for_gen = self._resolve_context_variable(prompt_for_gen_template, current_context)
            if not resolved_prompt_for_gen:
                action_result_data = {"error": "Missing 'prompt_for_generation' or failed to resolve."}
            elif not self.gemini_service:
                action_result_data = {"error": "GeminiService unavailable for text generation."}
            else:
                logger.info(f"Generating text with prompt: {resolved_prompt_for_gen[:100]}...");
                generated_text = self.gemini_service.generate_text_response(resolved_prompt_for_gen)
                if generated_text and "error" not in generated_text.lower():
                    logger.info(
                        f"Content generated (len: {len(generated_text)}). Storing as '{store_as}'."); action_result_data = {
                        store_as: generated_text, "info": "Text content generated."}; success = True
                else:
                    logger.error(f"Failed to generate text. Gemini: {generated_text}"); action_result_data = {
                        "error": f"Failed text gen. Resp: {generated_text}"}
        elif action_type == "wait":
            duration_param = parameters.get("duration_seconds", 1.0);
            duration_to_use = None;
            resolved_var_str_for_log = str(duration_param)
            try:
                if isinstance(duration_param, str) and "{{" in duration_param:
                    resolved_var_str = self._resolve_context_variable(duration_param,
                                                                      current_context); resolved_var_str_for_log = resolved_var_str; duration_to_use = float(
                        resolved_var_str)
                elif isinstance(duration_param, (int, float)):
                    duration_to_use = float(duration_param)
                elif isinstance(duration_param, str):
                    duration_to_use = float(duration_param)
                else:
                    logger.error(f"Unexpected type for wait duration: {type(duration_param)}"); action_result_data = {
                        "error": f"Invalid type for wait: {type(duration_param)}"}
                if duration_to_use is not None:
                    if duration_to_use < 0: logger.warning(
                        f"Wait duration {duration_to_use}s negative, using 0s."); duration_to_use = 0
                    logger.info(f"Waiting for {duration_to_use:.2f} seconds...");
                    time.sleep(duration_to_use);
                    success = True
            except ValueError as e:
                logger.error(
                    f"Invalid value for wait: '{duration_param}' (resolved: '{resolved_var_str_for_log}'). Error: {e}"); action_result_data = {
                    "error": f"Invalid value for wait: {resolved_var_str_for_log}"}
            except Exception as e:
                logger.error(f"Unexpected error in wait: '{duration_param}': {e}",
                             exc_info=True); action_result_data = {"error": "Unexpected error in wait."}
            if not success and not action_result_data: action_result_data = {"error": "Unknown error in wait."}
        elif action_type == "get_credentials_for_service":
            if not self.credential_manager:
                action_result_data = {"error": "CredMan missing."}
            elif not orchestrator_callback:
                action_result_data = {"error": "Orch CB missing."}
            else:
                service_name = parameters.get("service_name")
                if not service_name:
                    action_result_data = {"error": "Missing 'service_name'."}
                else:
                    if not self._ensure_creds_ready_for_action(orchestrator_callback):
                        action_result_data = {"error": f"Cred store for '{service_name}' not ready."}
                    else:
                        creds = self.credential_manager.get_credential(service_name)
                        if creds:
                            action_result_data = {f"{service_name}_username": creds["username"],
                                                  f"{service_name}_password": creds["password"],
                                                  "info": f"Creds for {service_name} retrieved."}; success = True
                        else:
                            user_input = orchestrator_callback.get_service_credential_input_for_action(service_name,
                                                                                                       parameters.get(
                                                                                                           "username_hint",
                                                                                                           ""))
                            if user_input and user_input[0]:
                                _s, u, p, save_ = user_input;
                                action_result_data = {f"{_s}_username": u, f"{_s}_password": p,
                                                      "info": f"Creds for {_s} obtained."};
                                success = True
                                if save_ and self.credential_manager.add_or_update_credential(_s, u, p):
                                    logger.info(f"Creds for {_s} saved.")
                                elif save_:
                                    logger.error(f"Failed to save creds for {_s}."); action_result_data[
                                        "warning"] = "Failed to save."
                            else:
                                action_result_data = {
                                    "error": f"Credential input for {service_name} cancelled/failed."}; success = False
        elif action_type == "click_element_by_description":  # Vision based
            element_desc = parameters.get("element_description");
            context_instr = parameters.get("context_instructions_for_vision", "")
            if not element_desc:
                action_result_data = {"error": "Missing 'element_description'."}
            elif not self.perception_agent:
                action_result_data = {"error": "PerceptionAgent unavailable."}
            else:
                if effective_target_title and not self.os_interaction.activate_window(
                    title_substring=effective_target_title):
                    action_result_data = {"error": f"Could not activate window '{effective_target_title}'."}
                else:
                    logger.info(
                        f"Clicking element (vision): '{element_desc}' in '{effective_target_title or 'screen'}'")
                    coords_info, ss_bounds = self.perception_agent.get_element_coordinates_via_vision(element_desc,
                                                                                                      effective_target_title,
                                                                                                      context_instr)
                    if coords_info and coords_info.get("found") and coords_info.get("x_center") is not None:
                        rel_x, rel_y = coords_info["x_center"], coords_info["y_center"];
                        abs_x, abs_y = rel_x, rel_y
                        if ss_bounds and ss_bounds[2] != -1:
                            abs_x = ss_bounds[0] + rel_x; abs_y = ss_bounds[1] + rel_y; logger.info(
                                f"Adjusted vision coords ({rel_x},{rel_y}) to ({abs_x},{abs_y})")
                        else:
                            logger.info(f"Using absolute vision coords ({abs_x},{abs_y})")
                        if self.os_interaction.click_at(abs_x, abs_y):
                            success = True; action_result_data = {
                                "info": f"Clicked (vision) '{element_desc}' at ({abs_x},{abs_y})."}
                        else:
                            action_result_data = {
                                "error": f"Failed vision click at ({abs_x},{abs_y}) for '{element_desc}'."}
                    else:
                        reason = coords_info.get("reasoning",
                                                 "Not found") if coords_info else "Perception fail."; action_result_data = {
                            "error": f"Element (vision) '{element_desc}' not found: {reason}"}


        elif action_type == "type_text_into_element_by_description":  # Vision based

            txt_tmpl = parameters.get("text_to_type")

            element_desc = parameters.get("element_description")

            context_instr = parameters.get("context_instructions_for_vision", "")

            if not txt_tmpl or not element_desc:

                action_result_data = {"error": "Missing text or element_desc."}

            elif not self.perception_agent:

                action_result_data = {"error": "PerceptionAgent unavailable."}

            else:

                txt_type = self._resolve_context_variable(txt_tmpl, current_context)

                if txt_type is None:

                    action_result_data = {"error": f"Could not resolve: {txt_tmpl}"}

                else:

                    if effective_target_title and not self.os_interaction.activate_window(
                            title_substring=effective_target_title):

                        action_result_data = {"error": f"Could not activate '{effective_target_title}'."}

                    else:

                        logger.info(
                            f"Typing into element (vision): '{element_desc}' in '{effective_target_title or 'screen'}'")

                        coords_info, ss_bounds = self.perception_agent.get_element_coordinates_via_vision(

                            element_desc, effective_target_title, context_instr

                        )

                        if coords_info and coords_info.get("found") and coords_info.get("x_center") is not None:

                            rel_x, rel_y = coords_info["x_center"], coords_info["y_center"]

                            abs_x, abs_y = rel_x, rel_y

                            if ss_bounds and ss_bounds[2] != -1:
                                abs_x = ss_bounds[0] + rel_x

                                abs_y = ss_bounds[1] + rel_y

                                logger.info(
                                    f"Adjusted vision coords for typing: ({rel_x},{rel_y}) to ({abs_x},{abs_y})")

                            if self.os_interaction.click_at(abs_x, abs_y):

                                time.sleep(0.3)

                                log_txt = self._get_loggable_text(txt_tmpl, txt_type, current_context)

                                logger.info(f"AA: Typing (vision) '{log_txt}' (after click)")

                                if self.os_interaction.type_text(txt_type, target_window_title=None):

                                    success = True

                                    action_result_data = {"info": f"Typed (vision) into '{element_desc}'."}

                                else:

                                    action_result_data = {"error": f"Failed type after vision click '{element_desc}'."}

                            else:

                                action_result_data = {"error": f"Failed vision click '{element_desc}' before typing."}

                        else:

                            reason = coords_info.get("reasoning", "Not found") if coords_info else "Perception fail."

                            action_result_data = {
                                "error": f"Element (vision) '{element_desc}' for typing not found: {reason}"}



        elif action_type == "type_text":
            txt_tmpl = parameters.get("text");
            txt_type = self._resolve_context_variable(txt_tmpl, current_context)
            if txt_type is not None:
                log_txt = self._get_loggable_text(txt_tmpl, txt_type, current_context)
                logger.info(f"AA: Typing (general) '{log_txt}' into '{effective_target_title or 'active'}'")
                success = self.os_interaction.type_text(txt_type, target_window_title=effective_target_title)
                if not success: action_result_data = {
                    "error": f"Failed general type in '{effective_target_title or 'active'}'"}
            else:
                action_result_data = {"error": "Missing text/var for general type_text"}
        elif action_type == "open_application":
            app_name = parameters.get("application_name");
            act_if_run = parameters.get("activate_if_running", True);
            use_sm_param = parameters.get("use_start_menu_on_windows");
            use_sm = use_sm_param if use_sm_param is not None else (self.os_interaction.current_os == "windows")
            if use_sm_param is None and self.os_interaction.current_os == "windows": logger.debug(
                "Defaulted use_start_menu to True for Windows")
            if app_name:
                op_s, win_obj = self.os_interaction.open_application(app_name, act_if_run, use_sm)
                success = op_s
                if win_obj and hasattr(win_obj, 'title') and win_obj.title:
                    action_result_data = {"last_opened_window_title": win_obj.title, "last_opened_app_name": app_name}
                elif not op_s:
                    action_result_data = {"error": f"Failed to open/manage {app_name}"}
            else:
                action_result_data = {"error": "Missing application_name"}
        elif action_type == "activate_window":
            title_h_p = parameters.get("window_title_hint");
            title_act = self._resolve_context_variable(title_h_p,
                                                       current_context) if title_h_p else effective_target_title
            if title_act: success = self.os_interaction.activate_window(title_substring=title_act)
            if not success and title_act:
                action_result_data = {"error": f"Failed activate {title_act}"}
            elif not title_act:
                action_result_data = {"error": "Missing window_title_hint"}
        elif action_type == "close_application":
            param_t = parameters.get("application_name") or parameters.get("window_title_hint");
            title_c = self._resolve_context_variable(param_t, current_context) if param_t else effective_target_title
            if title_c: success = self.os_interaction.close_application_window(title_c)
            if success:
                action_result_data = {"last_opened_window_title": None, "last_opened_app_name": None}
            elif not success and title_c:
                action_result_data = {"error": f"Failed close {title_c}"}
            elif not title_c:
                action_result_data = {"error": "No target for close_application"}
        elif action_type == "search_web":
            q = parameters.get("search_query")
            if q: success = self.os_interaction.search_web(q)
            if not success and q:
                action_result_data = {"error": "Failed web search"}
            elif not q:
                action_result_data = {"error": "Missing search_query"}
        elif action_type == "press_key":
            k_param = parameters.get("key_name");
            key_to_press = self._resolve_context_variable(str(k_param), current_context) if isinstance(k_param,
                                                                                                       str) and "{{" in k_param else k_param
            if key_to_press:
                success = self.os_interaction.press_key(key_to_press, target_window_title=effective_target_title)
                if not success: action_result_data = {
                    "error": f"Failed press key in '{effective_target_title or 'active'}'"}
            else:
                action_result_data = {"error": "Missing key_name or failed to resolve for press_key"}
        elif action_type == "clear_text_in_window":
            if effective_target_title:
                if self.os_interaction.activate_window(title_substring=effective_target_title):
                    time.sleep(0.3)
                    if self.os_interaction.press_key(['ctrl', 'a'], target_window_title=None):
                        time.sleep(0.3)
                        success = self.os_interaction.press_key('delete', target_window_title=None)
                        if not success: action_result_data = {"error": "Failed delete after select all"}
                    else:
                        action_result_data = {"error": "Failed select all (Ctrl+A)"};
                        success = False
                else:
                    action_result_data = {"error": f"Failed activate window '{effective_target_title}' for clearing"};
                    success = False
            else:
                action_result_data = {"error": "No target window specified for clear_text"};
                success = False
        elif action_type == "get_info_from_screen":
            if not self.perception_agent:
                action_result_data = {"error": "PerceptionAgent unavailable"}
            else:
                q_details = parameters.get("query_details");
                store_as_key = parameters.get("store_result_as");
                target_win_for_ss = parameters.get("target_window_title")
                final_target_win_title = self._resolve_context_variable(target_win_for_ss,
                                                                        current_context) if target_win_for_ss else effective_target_title
                if q_details:
                    p_result = self.perception_agent.analyze_screen_for_info(q_details,
                                                                             target_window_title=final_target_win_title)
                    if p_result.get("found"):
                        success = True; action_result_data = {
                            store_as_key if store_as_key else "last_perception_data": p_result.get("data")}
                    else:
                        action_result_data = {store_as_key if store_as_key else "last_perception_data": None,
                                              "error": p_result.get("reason", "Info not found")}
                else:
                    action_result_data = {"error": "Missing query_details for get_info_from_screen"}
        elif action_type == "log_message":
            msg_t = parameters.get("message", "No msg");
            msg_l = self._resolve_context_variable(msg_t, current_context)
            lvl = parameters.get("level", "info").lower();
            log_fn = getattr(logger, lvl, logger.info)
            log_fn(f"PLAN_LOG: {msg_l}");
            success = True
        elif action_type == "navigate_url":
            action_result_data = {"info": "Web nav not implemented."}; success = False
        elif action_type == "send_message_whatsapp":
            rec = parameters.get('recipient', 'unknown');
            msg = parameters.get('message_content', '');
            logger.warning(
                f"High-level 'send_message_whatsapp' to '{rec}' with msg '{msg[:20]}...' called. Planner should generate detailed steps.")
            action_result_data = {
                "info": "High-level WhatsApp send; use 'find_contact_and_send_message' intent for detailed planning."};
            success = False
        else:
            logger.warning(f"Unknown or not implemented action_type: '{action_type}'")
            action_result_data = {"error": f"Unknown or unimplemented action type: {action_type}"}

        log_act_res_display = {}
        if isinstance(action_result_data, dict): log_act_res_display = {
            k: ('********' if k.endswith("_password") else v_val) for k, v_val in action_result_data.items()}
        if success:
            logger.info(f"Action '{action_type}' OK. Result for context: {log_act_res_display}")
        else:
            logger.error(f"Action '{action_type}' FAILED. Result: {log_act_res_display}")
            if action_result_data is None: action_result_data = {}
            if "error" not in action_result_data: action_result_data["error"] = f"Action '{action_type}' failed."
        return success, action_result_data


# (Standalone test block __main__ as previously corrected and provided in the full file response)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(levelname)s - [%(name)s:%(module)s:%(lineno)d] - %(message)s")


    class MockOSInteractionService:
        def __init__(self):
            self.current_os = "windows"

        def open_application(self, app_name, activate_if_running=True, use_start_menu_method_on_windows=True):
            logger.debug(f"MOCK OS: Open '{app_name}'")

            class MockWindow:
                title = "Untitled - Notepad"

            if app_name.lower() == "notepad":
                return True, MockWindow()
            return True, None

        def activate_window(self, title_substring=None, window_obj=None, exact_match=False):
            logger.debug(f"MOCK OS: Activate '{title_substring or getattr(window_obj, 'title', 'N/A')}'")
            return True

        def type_text(self, text, target_window_title=None, interval=0.01):
            logger.debug(f"MOCK OS: Type '{text[:20]}...' in '{target_window_title or 'active'}'")
            return True

        def press_key(self, key, target_window_title=None):
            logger.debug(f"MOCK OS: Press '{key}' in '{target_window_title or 'active'}'")
            return True

        def close_application_window(self, title_hint):
            logger.debug(f"MOCK OS: Close '{title_hint}'")
            return True

        def search_web(self, query):
            logger.debug(f"MOCK OS: Search web '{query}'")
            return True

        def click_at(self, x, y, button='left', clicks=1, interval=0.1):
            logger.debug(f"MOCK OS: Click at ({x},{y})")
            return True

        def get_window_bounds(self, title_hint):
            logger.debug(f"MOCK OS: Get bounds for '{title_hint}'")
            if "notepad" in title_hint.lower():
                return (100, 100, 800, 600)
            return None

        def take_screenshot_pyautogui(self, region=None):
            logger.debug(f"MOCK OS: take_screenshot(region={region})")
            return b"dummy_screenshot_bytes"


    class MockPerceptionAgent:
        def __init__(self, os_interaction_service,
                     gemini_service=None): self.os_interaction_service = os_interaction_service; self.gemini_service = gemini_service

        def analyze_screen_for_info(self, query, target_window_title=None): logger.debug(
            f"MOCK PERCEPTION: Analyzing for '{query}' (target: {target_window_title})"); return {"found": False,
                                                                                                  "reason": "Mock info not found"}

        def get_element_coordinates_via_vision(self, element_d, target_win=None, context_i=""):
            logger.debug(f"MOCK PERCEPTION: Get coords for '{element_d}' (target: {target_win})")
            if target_win and "notepad" in target_win.lower() and "file menu" in element_d.lower(): return {
                "found": True, "x_center": 30, "y_center": 15, "x_top_left": 5, "y_top_left": 0, "width": 50,
                "height": 30, "confidence": 0.9}, (100, 100, 800, 600)
            return {"found": False, "reasoning": "Mock element not found by vision"}, None


    class MockAccessibilityService:
        def _get_window(self, title_hint=None, pid=None, class_name=None):
            logger.debug(f"MOCK ACC: Get Win '{title_hint}'")

            class MW:
                def __init__(self, t):
                    self.title = t

                def window_text(self):
                    return self.title

                def exists(self, timeout=1, retry_interval=0.1):
                    return True

            return MW(title_hint or "MockWindow")

        def find_element(self, win_spec, element_name=None, control_type=None, automation_id=None, **kwargs):
            logger.debug(
                f"MOCK ACC: Find '{element_name or automation_id}' type '{control_type}' in '{win_spec.window_text()}'"
            )

            class ME:
                def __init__(self, n):
                    self.name = n

                def window_text(self):
                    return self.name

                def exists(self, timeout=1, retry_interval=0.1):
                    return True

            return ME(element_name or "MockElement")

        def click_element(self, element):
            logger.debug(f"MOCK ACC: Click '{element.window_text()}'")
            return True

        def set_element_text(self, element, text):
            logger.debug(f"MOCK ACC: Set text '{text[:20]}...' on '{element.window_text()}'")
            return True

        def get_element_properties(self, element):
            logger.debug(f"MOCK ACC: Get props for '{element.window_text()}'")
            return {
                "name": element.window_text(),
                "control_type": "MockType",
                "rectangle": [0, 0, 10, 10],
                "is_enabled": True,
                "is_visible": True
            }


    class MockCredentialManager:
        def __init__(self): self.is_unlocked = True; self.creds = {}; logger.debug("MockCredMan: Unlocked.")

        def is_initialized(self): return True

        def get_credential(self, s_name): logger.debug(f"MOCK CREDMAN: Get for '{s_name}'"); return self.creds.get(
            s_name.lower())

        def add_or_update_credential(self, s, u, p): logger.debug(f"MOCK CREDMAN: Add/Update for '{s}'"); self.creds[
            s.lower()] = {"username": u, "password": p}; return True


    class MockOrchestratorCallback:
        def get_service_credential_input_for_action(self, s_name, u_hint=""): return (s_name, "mock_user", "mock_pass",
                                                                                      True)

        def get_master_password_input_for_action(self, setup_mode=False): return "mock_master_password"


    mock_os = MockOSInteractionService();
    mock_gemini_aa = MockGeminiServiceForTesting();
    mock_pa = MockPerceptionAgent(mock_os, mock_gemini_aa);
    mock_cm = MockCredentialManager();
    mock_acc = MockAccessibilityService();
    mock_orch = MockOrchestratorCallback()
    action_agent = ActionAgent(mock_os, mock_pa, mock_cm, mock_gemini_aa, mock_acc)

    print("\n--- Testing ActionAgent with Accessibility Actions (Calc Example) ---")
    ctx_calc = {"last_opened_window_title": "Calculator", "application_name": "Calculator",
                "expression_parts": ["7", "Plus", "8", "Equals"]}
    plan_calc = [
        {"action_type": "click_element_by_accessibility",
         "parameters": {"target_window_title": "Calculator", "element_name": "Seven", "control_type": "Button"}},
        {"action_type": "click_element_by_accessibility",
         "parameters": {"target_window_title": "Calculator", "element_name": "Plus", "control_type": "Button"}},
        {"action_type": "click_element_by_accessibility",
         "parameters": {"target_window_title": "Calculator", "element_name": "Eight", "control_type": "Button"}},
        {"action_type": "click_element_by_accessibility",
         "parameters": {"target_window_title": "Calculator", "element_name": "Equals", "control_type": "Button"}},
        {"action_type": "get_element_text_by_accessibility",
         "parameters": {"target_window_title": "Calculator", "automation_id": "CalculatorResults",
                        "store_result_as": "calc_result"}},
        {"action_type": "log_message", "parameters": {"message": "Calculator result: {{calc_result}}"}}
    ]
    for step in plan_calc:
        s, r = action_agent.execute_action(step, ctx_calc, mock_orch)
        print(f"Step {step['action_type']} - Success: {s}, Result: {r}")
        if r and not r.get("error"): ctx_calc.update(r)
    print(f"Final context for Calc: {ctx_calc}")