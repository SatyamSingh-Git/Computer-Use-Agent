# aura_project/aura_core/agents/nlu_agent.py (REVISED FOR GENERAL GOAL EXTRACTION)
import logging
import json
from aura_core.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class NLUAgent:
    def __init__(self, gemini_service: GeminiService):
        self.gemini_service = gemini_service
        if not self.gemini_service:
            logger.error("NLUAgent initialized without a valid GeminiService.")
            raise ValueError("GeminiService is required for NLUAgent.")
        logger.info("NLUAgent initialized for general goal extraction.")

    def parse_command(self, user_command: str, previous_context: dict = None) -> dict | None:
        context_hint = ""
        if previous_context:
            last_app = previous_context.get("last_opened_app_name")
            if last_app:
                context_hint = (
                    f"\n\nRelevant Context from Previous Interaction:\n"
                    f"- The user was likely last interacting with or referring to: {last_app}.\n"
                    f"- If the current command uses pronouns like 'it', 'that', 'there', or implies continuation, "
                    f"it might refer to this application or its content."
                )
        else:
            context_hint = "\n\n(No specific application context from the immediately preceding turn.)"

        prompt = f"""
        You are an NLU parser for Aura, a desktop AI assistant. Your primary task is to understand the user's overall GOAL from their command.
        Analyze the user's command and extract:
        1. A concise "goal_description": A clear, self-contained statement of what the user wants to achieve. If the command is multi-part, combine it into a single goal.
        2. An "entities" object: This should contain any specific pieces of information, data, application names, or hints provided by the user that are relevant to achieving the goal.

        Output your analysis as a VALID JSON object with an "intent" (which will usually be "achieve_goal") and the "entities" object (containing "goal_description" and other extracted data).
        Do not include any explanatory text, comments, or markdown formatting before or after the JSON. Pure JSON only.
        {context_hint}

        Examples:
        1. User command: "open calculator, and find the sum of 7 + 8"
           Expected JSON:
           {{
             "intent": "achieve_goal",
             "entities": {{
               "goal_description": "Open calculator and find the sum of 7 + 8",
               "application_hint": "Calculator",
               "data_involved": ["7", "8", "+"]
             }}
           }}

        2. User command: "write an application to the principle for leave regarding fever in Notepad"
           Expected JSON:
           {{
             "intent": "achieve_goal",
             "entities": {{
               "goal_description": "Write a leave application to the principle regarding fever in Notepad",
               "document_type": "leave application",
               "recipient_role": "principle",
               "topic": "fever",
               "tool_hint": "Notepad"
             }}
           }}

        3. User command: "In WhatsApp, search for Nancy and send her 'Hi there!'"
           Expected JSON:
           {{
             "intent": "achieve_goal",
             "entities": {{
               "goal_description": "In WhatsApp, search for the contact Nancy and send her the message 'Hi there!'",
               "application_hint": "WhatsApp",
               "contact_to_find": "Nancy",
               "message_to_send": "Hi there!"
             }}
           }}

        4. User command: "what is 15 times 3"
           Expected JSON:
           {{
             "intent": "achieve_goal",
             "entities": {{
               "goal_description": "Calculate 15 times 3",
               "data_involved": ["15", "3", "*"]
             }}
           }}

        5. User command: "close all my applications"
           Expected JSON:
           {{
             "intent": "achieve_goal",
             "entities": {{
               "goal_description": "Close all currently open user applications"
             }}
           }}

        If the command is too vague or nonsensical for a clear goal, use intent "unknown_command".
        User command: "gibberish blah" -> {{"intent": "unknown_command", "entities": {{"original_command": "gibberish blah"}}}}

        Now, parse the following user command:
        User command: "{user_command}"
        Your JSON output:
        """
        logger.debug(
            f"NLUAgent (Goal-Oriented): Sending command to Gemini. Command: '{user_command}', Context: {context_hint.strip()}'")
        raw_response = self.gemini_service.generate_text_response(prompt)

        # (JSON parsing logic - same as before, ensure it validates "intent" and "entities" exist)
        if not raw_response: logger.error("NLUAgent: No response from Gemini."); return {"intent": "nlu_error",
                                                                                         "entities": {
                                                                                             "error_message": "NLU service no response."}}
        try:
            cleaned = raw_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(cleaned)
            logger.info(
                f"NLUAgent (Goal-Oriented): Parsed. Intent: '{parsed.get('intent')}', Entities: {parsed.get('entities')}")
            if not (isinstance(parsed, dict) and "intent" in parsed and isinstance(parsed.get("intent"),
                                                                                   str) and "entities" in parsed and isinstance(
                    parsed.get("entities"), dict)):
                logger.warning(f"NLUAgent: Malformed NLU JSON. Raw: {cleaned}")
                return {"intent": "nlu_parsing_error",
                        "entities": {"error_message": "Malformed NLU structure.", "raw": cleaned}}
            if parsed.get("intent") == "achieve_goal" and "goal_description" not in parsed.get("entities", {}):
                logger.warning(
                    f"NLUAgent: 'achieve_goal' intent missing 'goal_description' in entities. Raw: {cleaned}")
                return {"intent": "nlu_parsing_error",
                        "entities": {"error_message": "'goal_description' missing for 'achieve_goal' intent.",
                                     "raw": cleaned}}
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"NLUAgent: JSONDecodeError: {e}. Raw: {raw_response[:300]}"); return {
                "intent": "nlu_parsing_error",
                "entities": {"error_message": f"JSON decode error: {e}", "raw": raw_response}}
        except Exception as e:
            logger.error(f"NLUAgent: Unexpected NLU parse error: {e}. Raw: {raw_response[:300]}",
                         exc_info=True); return {"intent": "nlu_error",
                                                 "entities": {"error_message": f"Unexpected NLU parse error: {e}",
                                                              "raw": raw_response}}

# (Standalone test block __main__ should be updated to reflect this new NLU philosophy)