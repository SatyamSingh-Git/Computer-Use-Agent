import logging
import json
from aura_core.services.gemini_service import GeminiService
from aura_core.services.os_interaction_service import OSInteractionService  # Assumed to be updated

logger = logging.getLogger(__name__)


class PerceptionAgent:
    def __init__(self, gemini_service: GeminiService, os_interaction_service: OSInteractionService):
        self.gemini_service = gemini_service
        self.os_interaction_service = os_interaction_service
        if not self.gemini_service: logger.error("PerceptionAgent: GeminiService missing.")
        if not self.os_interaction_service: logger.error(
            "PerceptionAgent: OSInteractionService missing."); raise ValueError("OSInteractionService required.")
        logger.info("PerceptionAgent initialized.")

    def take_screenshot_of_window(self, window_title_hint: str) -> tuple[
        bytes | None, tuple[int, int, int, int] | None]:
        """
        Takes a screenshot specifically of the window matching the title hint.
        Returns (screenshot_bytes, window_bounds_tuple (left,top,width,height)) or (None, None).
        """
        window_bounds = self.os_interaction_service.get_window_bounds(window_title_hint)
        if window_bounds:
            logger.info(f"Taking screenshot of window region: {window_bounds} for title hint '{window_title_hint}'")
            screenshot_bytes = self.os_interaction_service.take_screenshot_pyautogui(region=window_bounds)
            if screenshot_bytes:
                return screenshot_bytes, window_bounds
            else:
                logger.warning(f"Failed to take screenshot for window region of '{window_title_hint}'.")
        else:
            logger.warning(
                f"Could not get bounds for window '{window_title_hint}'. Taking full screenshot as fallback.")
            # Fallback to full screenshot if window bounds not found, but then coordinates are absolute
            full_screenshot_bytes = self.os_interaction_service.take_screenshot_pyautogui()
            if full_screenshot_bytes:
                # For full screenshot, effective bounds are (0,0, screen_width, screen_height)
                # This is harder to get reliably here, so we'll signal it's a full screen.
                return full_screenshot_bytes, (0, 0, -1, -1)  # (-1, -1 for width/height indicates full screen)
        return None, None

    def analyze_screen_for_info(self, query_details: str, target_window_title: str = None) -> dict:
        logger.info(
            f"PerceptionAgent: Analyzing screen for general info: '{query_details}' (Window hint: {target_window_title})")
        if not self.gemini_service: return {"found": False, "reason": "Vision service unavailable."}

        screenshot_bytes = None
        if target_window_title:
            screenshot_bytes, _ = self.take_screenshot_of_window(
                target_window_title)  # We don't need bounds for this general query

        if not screenshot_bytes:  # Fallback or if no target_window_title
            screenshot_bytes = self.os_interaction_service.take_screenshot_pyautogui()  # Full screen

        if not screenshot_bytes: return {"found": False, "reason": "Failed to capture screen."}

        vision_prompt = f"""
        Analyze the provided screenshot. The user wants to find: "{query_details}"
        Respond with the information if found, or state if not found.
        Observation:
        """
        analysis_result_text = self.gemini_service.analyze_image_with_prompt(
            image_bytes=screenshot_bytes, mime_type='image/png', prompt=vision_prompt
        )
        if analysis_result_text: return {"found": True, "data": analysis_result_text, "source": "gemini_vision"}
        return {"found": False, "reason": "No response/empty response from vision."}

    def get_element_coordinates_via_vision(
            self, element_description: str, target_window_title: str | None = None, context_instructions: str = ""
    ) -> tuple[dict | None, tuple[int, int, int, int] | None]:
        """
        Asks Gemini Vision for element coordinates. Takes screenshot of target_window_title if provided.
        Returns (parsed_coords_dict, screenshot_window_bounds_tuple) or (None, None).
        parsed_coords_dict is like {"x_center": X, "y_center": Y, ...}
        screenshot_window_bounds is (left, top, width, height) of the window the screenshot was taken from,
        or (0,0,-1,-1) if it was a full screen screenshot (width/height -1 indicates full).
        Coordinates in parsed_coords_dict are relative to the screenshot taken.
        """
        if not self.gemini_service: logger.error("PA: GeminiService missing for get_element_coords."); return None, None

        screenshot_bytes, window_bounds = None, None
        if target_window_title:
            screenshot_bytes, window_bounds = self.take_screenshot_of_window(target_window_title)
        else:  # Full screen screenshot
            screenshot_bytes = self.os_interaction_service.take_screenshot_pyautogui()
            window_bounds = (0, 0, -1, -1)  # Signal full screen screenshot

        if not screenshot_bytes:
            logger.error("PA: No screenshot bytes for get_element_coords.");
            return None, None

        # (The vision_prompt for coordinates remains the same as your last correct version)
        vision_prompt = f"""
        You are an AI visual analysis expert. Analyze the provided screenshot.
        Task: Identify UI element: "{element_description}".
        {context_instructions} 
        Respond ONLY with VALID JSON: {{"found": boolean, "x_center": int/null, "y_center": int/null, "x_top_left": int/null, "y_top_left": int/null, "width": int/null, "height": int/null, "confidence": float/null, "reasoning": "string"}}
        Coordinates are relative to the top-left (0,0) of THIS image.
        """

        logger.debug(
            f"PA: Requesting coords from Vision for: '{element_description}' (Window: {target_window_title or 'Full Screen'})")
        raw_response_text = self.gemini_service.analyze_image_with_prompt(
            image_bytes=screenshot_bytes, mime_type='image/png', prompt=vision_prompt
        )

        if not raw_response_text:
            logger.warning(f"PA: No text response from Vision for coords ('{element_description}').")
            return {"found": False, "reasoning": "Vision service no response."}, window_bounds

        try:  # (JSON parsing logic remains the same)
            cleaned = raw_response_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed_coords = json.loads(cleaned)
            if not isinstance(parsed_coords, dict) or "found" not in parsed_coords:
                return {"found": False, "reasoning": "Malformed JSON from vision.", "raw": cleaned}, window_bounds
            if parsed_coords.get("found"):
                keys = ["x_center", "y_center", "x_top_left", "y_top_left", "width", "height"]
                for k in keys:
                    if parsed_coords.get(k) is None or not isinstance(parsed_coords.get(k), (int, float)):
                        parsed_coords["found"] = False;
                        parsed_coords["reasoning"] = (parsed_coords.get("reasoning", "") + f" Invalid coord: {k}.");
                        break
            parsed_coords["raw_output"] = raw_response_text
            logger.info(f"PA: Parsed coords for '{element_description}': Found={parsed_coords.get('found')}")
            return parsed_coords, window_bounds
        except Exception as e:
            logger.error(f"PA: Error parsing coords JSON. E: {e}. Raw: {raw_response_text[:300]}", exc_info=True)
            return {"found": False, "reasoning": f"JSON parse error: {e}", "raw": raw_response_text}, window_bounds

# (Example Usage __main__ block should be updated to reflect new return types)