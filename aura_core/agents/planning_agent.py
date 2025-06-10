import logging
import json
from aura_core.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class PlanningAgent:
    def __init__(self, gemini_service: GeminiService):
        self.gemini_service = gemini_service
        if not self.gemini_service:
            logger.error("PlanningAgent initialized without a valid GeminiService.")
            raise ValueError("GeminiService is required for PlanningAgent.")
        logger.info("PlanningAgent initialized for goal decomposition.")

    def create_plan_for_goal(self, goal_description: str, nlu_entities: dict,
                             available_actions_override: list = None) -> list[dict] | None:

        # --- DEBUGGING: DRASTICALLY REDUCED ACTIONS FOR THIS TEST ---
        if "take a picture" in goal_description.lower():  # Specific hack for this test
            logger.warning("PlanningAgent: USING REDUCED ACTION SET FOR 'take a picture' TEST!")
            current_available_actions = [
                {"action_type": "open_application",
                 "parameters": {"application_name": "string", "use_start_menu_on_windows": "boolean (default true)"}},
                {"action_type": "wait", "parameters": {"duration_seconds": "float"}},
                {"action_type": "click_element_by_accessibility",
                 "parameters": {"target_window_title": "string", "automation_id": "string (preferred)",
                                "element_name": "string (alt)", "control_type": "string (e.g. Button)"}},
                {"action_type": "click_element_by_description",
                 "parameters": {"element_description": "string", "target_window_title": "string (opt)"}},
                {"action_type": "log_message", "parameters": {"message": "string", "level": "string"}},
            ]
        elif available_actions_override:
            current_available_actions = available_actions_override
        else:  # Full list (keep this for other scenarios, but it's likely too big)
            current_available_actions = [
                {"action_type": "open_application",
                 "parameters": {"application_name": "string", "activate_if_running": "boolean",
                                "use_start_menu_on_windows": "boolean"}},
                {"action_type": "get_credentials_for_service",
                 "parameters": {"service_name": "string", "username_hint": "string"}},
                {"action_type": "activate_window", "parameters": {"window_title_hint": "string"}},
                {"action_type": "close_application", "parameters": {"application_name": "string"}},
                {"action_type": "search_web", "parameters": {"search_query": "string"}},
                {"action_type": "type_text",
                 "parameters": {"text": "string", "target_window_title": "string (optional)"}},
                {"action_type": "press_key",
                 "parameters": {"key_name": "string or list", "target_window_title": "string (optional)"}},
                {"action_type": "clear_text_in_window", "parameters": {"target_window_title": "string"}},
                {"action_type": "wait", "parameters": {"duration_seconds": "float"}},
                {"action_type": "click_element_by_description",
                 "parameters": {"element_description": "string", "target_window_title": "string (optional)",
                                "context_instructions_for_vision": "string (optional)"}},
                {"action_type": "type_text_into_element_by_description",
                 "parameters": {"text_to_type": "string", "element_description": "string",
                                "target_window_title": "string (optional)",
                                "context_instructions_for_vision": "string (optional)"}},
                {"action_type": "click_element_by_accessibility",
                 "parameters": {"target_window_title": "string", "element_name": "string (opt)",
                                "control_type": "string (opt)", "automation_id": "string (opt)",
                                "framework_id": "string(opt)", "class_name_re": "string(opt)"}},
                {"action_type": "type_text_into_element_by_accessibility",
                 "parameters": {"text_to_type": "string", "target_window_title": "string",
                                "element_name": "string (opt)", "control_type": "string (opt)",
                                "automation_id": "string (opt)"}},
                {"action_type": "get_element_text_by_accessibility",
                 "parameters": {"target_window_title": "string", "element_name": "string (opt)",
                                "control_type": "string (opt)", "automation_id": "string (opt)",
                                "store_result_as": "string"}},
                {"action_type": "navigate_url", "parameters": {"url": "string"}},
                {"action_type": "get_info_from_screen",
                 "parameters": {"query_details": "string", "store_result_as": "string",
                                "target_window_title": "string (optional)"}},
                {"action_type": "generate_text_content",
                 "parameters": {"prompt_for_generation": "string", "store_result_as": "string"}},
                {"action_type": "log_message", "parameters": {"message": "string", "level": "string"}},
            ]
        # --- END DEBUGGING REDUCTION ---

        try:
            available_actions_str = json.dumps(current_available_actions, indent=2)
        except Exception as e:
            logger.error(f"PlanningAgent: Error dumping available_actions to JSON: {e}");
            return [{"action_type": "error", "parameters": {"message": "Internal error: Bad available_actions."}}]

        entities_for_prompt = nlu_entities.copy()
        entities_for_prompt.pop("goal_description", None)
        try:
            entities_json_for_prompt = json.dumps(entities_for_prompt, indent=2)
        except Exception as e:
            logger.error(f"PlanningAgent: Error dumping nlu_entities to JSON: {e}");
            return [{"action_type": "error", "parameters": {"message": "Internal error: Bad NLU entities."}}]

        # --- DEBUGGING: REDUCED EXAMPLES ---
        example_take_photo_camera_str = """
        [
          {{"action_type": "open_application", "parameters": {{"application_name": "Camera", "use_start_menu_on_windows": true}}}},
          {{"action_type": "wait", "parameters": {{"duration_seconds": 3.0}} }}, 
          {{"action_type": "click_element_by_accessibility", "parameters": {{
              "target_window_title": "Camera", 
              "automation_id": "PhotoTakenButton", 
              "element_name": "Take photo", 
              "control_type": "Button"
          }}}},
          {{"action_type": "log_message", "parameters": {{"message": "Photo capture initiated.", "level": "info"}}}}
        ]"""

        # Build prompt piece by piece
        prompt_parts = [
            "You are an AI Planning Agent for Aura. Decompose the user's goal into a sequence of executable steps using ONLY actions from 'Available actions'.",
            "Output ONLY a VALID JSON list of action objects: `[{\"action_type\": \"...\", \"parameters\": {...}}, ...]`. No other text.",
            f"\nUser's Goal Description: \"{goal_description}\"",
            f"\nAdditional User Entities: {entities_json_for_prompt}",
            f"\nAvailable Primitive Actions:\n{available_actions_str}",  # This will be smaller for the test
            "\nKey Planning Considerations:",
            "1. Prefer Accessibility: Use 'click_element_by_accessibility' for desktop UI if properties known.",
            "2. Vision Fallback: Use 'click_element_by_description' if accessibility fails or for visual cues.",
            "3. Window Focus: Ensure window is active before interactions.",
            "4. Context & Delays: Use {{variable_name}} and 'wait' action.",
            "5. Windows Apps: Include `\"use_start_menu_on_windows\": true` for 'open_application'.",
        ]

        # Conditionally add examples to keep prompt smaller for this test
        if "take a picture" in goal_description.lower() or "camera" in goal_description.lower():
            prompt_parts.append("\nExample Plan for Goal: 'Take a picture using the Camera app'")
            prompt_parts.append(f"(NLU Entities might be: {{\"application_hint\": \"Camera\"}})")
            prompt_parts.append(f"Expected JSON Plan: {example_take_photo_camera_str}")
        # else:
        # Add other examples here if needed, but keep it minimal for now
        # example_open_type_str = """[ {{"action_type": "open_application", ...}} ]"""
        # prompt_parts.append("\nExample Plan for Goal: 'Open Notepad and type meeting notes'")
        # prompt_parts.append(f"Expected JSON Plan: {example_open_type_str}")

        prompt_parts.extend([
            "\nNow, generate the plan for the provided User's Goal Description and Entities.",
            "Your JSON Plan:"
        ])
        prompt = "\n".join(prompt_parts)
        # --- END DEBUGGING PROMPT REDUCTION ---

        logger.debug(f"PlanningAgent: Total prompt length: {len(prompt)}")
        if len(prompt) > 25000:  # Increased threshold a bit, but still be wary
            logger.warning(f"PlanningAgent: Prompt length ({len(prompt)}) is very large!")
        # logger.debug(f"PlanningAgent: Full prompt being sent:\n{prompt}") # Only if really necessary

        raw_response = self.gemini_service.generate_text_response(prompt)

        # (JSON parsing logic - same as before)
        if not raw_response: logger.error("PA: No response from Gemini."); return [
            {"action_type": "error", "parameters": {"message": "Planner no response."}}]
        try:
            cleaned = raw_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            plan = json.loads(cleaned)
            if not isinstance(plan, list): logger.error(f"PA: Plan not list. Raw: {cleaned}"); return [
                {"action_type": "error", "parameters": {"message": "Plan not list.", "raw": cleaned}}]
            for i, step in enumerate(plan):
                if not (isinstance(step, dict) and "action_type" in step and isinstance(step.get("action_type"),
                                                                                        str) and "parameters" in step and isinstance(
                        step.get("parameters"), dict)):
                    logger.error(f"PA: Invalid step {i}. Step: {step}. Plan: {str(plan)[:300]}");
                    return [
                        {"action_type": "error", "parameters": {"message": f"Invalid plan step {i}.", "raw": cleaned}}]
            logger.info(f"PA: Plan generated ({len(plan)} steps).");
            logger.debug(f"Plan: {json.dumps(plan, indent=2)}");
            return plan
        except json.JSONDecodeError as e:
            logger.error(f"PA: JSONDecodeError: {e}. Raw: {raw_response[:300]}"); return [
                {"action_type": "error", "parameters": {"message": f"JSON decode error: {e}", "raw": raw_response}}]
        except Exception as e:
            logger.error(f"PA: Unexpected planning error: {e}. Raw: {raw_response[:300]}", exc_info=True); return [
                {"action_type": "error", "parameters": {"message": f"Unexpected error: {e}", "raw": raw_response}}]

# (Standalone test block __main__ can remain as is, or be updated with specific cases for this debug)