# Project Aura: Development Plan
Project Aura: Development Plan

Guiding Principles for AI-Assisted Development:

Modularity: Break down into smallest possible, independently testable functions/classes.

Clear Interfaces (APIs): Define precise inputs and outputs for every module and function.

Explicit Instructions: Provide detailed prompts for the AI coder for each step.

Iterative Refinement: Expect to generate, test, and refine code segments.

Version Control: Use Git rigorously from the very beginning.

Core Technologies:

LLM (NLU, Planning, Vision): Google Gemini 1.5 Flash (via API)

UI Framework: PyQt6 (Python bindings for Qt)

Speech-to-Text (STT): OpenAI Whisper (local instance for speed and privacy)

Text-to-Speech (TTS): Tortoise TTS (local instance for quality, be mindful of generation speed)

OS Interaction: pyautogui, pyperclip, subprocess, OS-specific libraries (e.g., pyobjc for macOS, pywin32 for Windows for accessibility).

Web Automation: Selenium or Playwright.

Programming Language: Python.

# Phase 0: Project Setup & Environment

Objective: Establish the foundational project structure and development environment.

Tasks for AI Coder:

Set up a Python virtual environment (e.g., venv or conda).

Install core dependencies: PyQt6, openai-whisper, tortoise-tts (and its dependencies like torchaudio, transformers), google-generativeai, pyautogui, pyperclip, selenium/playwright.

Create a project directory structure:

aura/
├── aura_core/              # Backend logic, agents
│   ├── agents/             # Individual agent modules
│   ├── utils/              # Helper functions, constants
│   ├── services/           # Wrappers for external APIs (Gemini, Whisper, TTS)
│   └── main_orchestrator.py
├── aura_ui/                # PyQt UI components
│   ├── widgets/
│   ├── themes/
│   └── main_window.py
├── assets/                 # Icons, images
├── config/                 # Configuration files (API keys, user prefs)
├── tests/                  # Unit and integration tests
└── main.py                 # Main application entry point


Initialize Git repository.

Set up basic logging.






# Phase 1: UI Shell & Basic Interaction (PyQt)

Objective: Create a modern, clean, and attractive main application window.

Tasks for AI Coder (aura_ui/main_window.py & themes/):

Design a QMainWindow with:

A prominent, minimalist input bar for text commands.

A status display area (to show what Aura is thinking/doing).

A clear "STOP" button (highly visible, easily clickable).

A settings access point (e.g., a gear icon).

Implement basic styling using Qt Stylesheets or QML (if a more declarative approach is desired and manageable by the AI coder for modern look).

Prompt for AI: "Create a dark theme with accent colors. Ensure fonts are modern and readable. Use subtle hover effects for interactive elements."

Connect the input bar to a simple function that logs the entered text.

Ensure the window is resizable and closes gracefully.





# Phase 2: Voice Input with Wake Word & STT (Whisper)

Objective: Enable voice commands via a wake word and transcribe them.

Tasks for AI Coder (aura_core/services/voice_service.py):

Integrate a wake word detection library (e.g., Picovoice Porcupine, or research simpler Python alternatives if Porcupine's licensing is an issue for open source).

Prompt for AI: "Implement a class WakeWordDetector that listens to the microphone and triggers an event when 'Hey Aura' (or configurable word) is detected."

Upon wake word detection, activate Whisper for STT.

Prompt for AI: "Create a SpeechToTextService class using openai-whisper. It should have methods to start_listening_and_transcribe() and stop_listening(). Optimize for speed (e.g., using a smaller Whisper model initially if local resources are a concern, but aim for good accuracy)."

Feed transcribed text to the UI input bar or directly to the NLU module.

Provide visual feedback in the UI when Aura is listening (e.g., a microphone icon changes).





# Phase 3: Natural Language Understanding (NLU) with Gemini

Objective: Interpret user commands (text or transcribed voice).

Tasks for AI Coder (aura_core/agents/nlu_agent.py, aura_core/services/gemini_service.py):

Create GeminiService to handle API calls to Gemini 1.5 Flash. Include error handling and retry mechanisms.

Implement NLUAgent with a method parse_command(text: str) -> dict.

This method will send the text to Gemini with a prompt designed to extract intent and entities.

Prompt for AI (for Gemini prompt engineering): "You are an NLU parser for a desktop AI assistant. Given user input, identify the primary intent (e.g., 'open_application', 'find_information_on_screen', 'send_message') and any relevant entities (e.g., application_name: 'LinkedIn', contact_name: 'John Doe', search_query: 'number of connections'). Output a JSON object."

Example output: {"intent": "find_linkedin_connections", "target_app": "linkedin"} or {"intent": "send_whatsapp_message", "contact": "top 10", "customization_basis": "tone_and_language"}.

Display "Aura is thinking..." in the UI while NLU is processing.





# Phase 4: Orchestration Agent - Initial Planning

Objective: The "Brain" agent that receives NLU output and decides on a high-level plan.

Tasks for AI Coder (aura_core/main_orchestrator.py, aura_core/agents/orchestrator_agent.py):

Create OrchestratorAgent. This will be the central coordinator.

Method create_initial_plan(parsed_command: dict) -> list_of_steps.

Initially, this can be rule-based for simple intents. For complex tasks like the examples, it will eventually use Gemini for planning.

Example for simple rule: If intent == "open_application", plan is ["launch_app(app_name)"].

Gemini for complex planning: "You are a task planner for a desktop AI assistant. Given the user's goal: [parsed_command], and knowing the available actions are [list of agent capabilities], generate a sequence of high-level steps to achieve this goal. Output as a JSON list of strings or action objects."

The main_orchestrator.py will house the main loop: Input -> NLU -> Orchestrator (Plan) -> Execute Steps.






# Phase 5: Perception Agent - Screen Analysis

Objective: Enable Aura to "see" and understand the screen.

Tasks for AI Coder (aura_core/agents/perception_agent.py):

Screenshot Module:

Function take_screenshot(region=None) -> image_object. (Use pyautogui).

Visual Analysis with Gemini Vision:

Method analyze_screen(image_object, prompt_question: str) -> analysis_result.

This sends the image and a question (e.g., "Where is the login button?", "What is the number of connections displayed?") to Gemini 1.5 Flash Vision endpoint.

Handle API responses, extract relevant information.

Accessibility API Integration (Crucial for Speed & Robustness):

Research and implement basic functions to interact with OS accessibility APIs (e.g., identify UI elements, get their properties like name, role, value, bounding box). This is OS-dependent (pywinauto/UIAutomation for Windows, pyobjc for AppKit/Accessibility on macOS).

Prompt for AI: "Create functions get_ui_elements_via_accessibility(window_title=None) and get_element_properties(element_id, properties_list)."

Decision Logic for Screenshot: The Orchestrator will decide.

Orchestrator logic refinement: "If task requires UI interaction, first try to get info via Accessibility API. If that fails or isn't sufficient, then PerceptionAgent.take_screenshot() and PerceptionAgent.analyze_screen()."







# Phase 6: Action Execution Agent

Objective: Enable Aura to perform actions on the computer.

Tasks for AI Coder (aura_core/agents/action_agent.py):

OS Interaction:

click(x, y) or click_element(element_info_from_perception)

type_text(text_to_type)

press_key(key_name) (e.g., 'enter', 'tab')

open_application(app_name) (using subprocess or OS-specific commands)

open_url_in_browser(url)

Web Automation (Selenium/Playwright):

navigate(url)

find_element_on_web(selector)

click_web_element(element)

fill_web_form_field(selector, text)

Ensure actions can be interrupted by the "STOP" command.







# Phase 7: Integrating Core Loop & First End-to-End Task (Example: Open LinkedIn)

Objective: Connect NLU, Orchestrator, Perception, and Action for a simple task.

Tasks for AI Coder:

Scenario: User says/types "Open LinkedIn."

Flow:

Input processed by STT (if voice).

NLU Agent (Gemini) -> {"intent": "open_application", "application_name": "LinkedIn"}.

Orchestrator Agent -> Plan: ["action_agent.open_application('LinkedIn')"].

Action Agent executes open_application('LinkedIn').

UI Feedback: Update status: "Opening LinkedIn...", "LinkedIn opened."

Fast Response Consideration: For open_application, the response is inherently fast once the command is understood. The bottleneck might be STT or initial NLU. Optimize Gemini prompts for speed.






# Phase 8: Credential Management & Secure Input

Objective: Handle application/website logins securely.

Tasks for AI Coder (aura_core/services/credential_manager.py, aura_ui/widgets/credential_prompt.py):

CredentialManager class:

Integrate with OS secure storage (macOS Keychain, Windows Credential Manager). Prompt for AI: "Implement functions to securely store and retrieve credentials using the native OS credential manager."

If OS manager is too complex, implement a simple encrypted local file (use cryptography library), protected by a master password for Aura.

CredentialPromptDialog (PyQt QDialog):

A secure, modal dialog for Aura to ask for username/password when needed.

Prompt for AI: "Create a PyQt QDialog that securely takes username and password input. Mask password input."

Workflow:

Orchestrator determines login is needed (e.g., Perception Agent sees a login page).

Orchestrator checks CredentialManager for saved credentials.

If not found, Orchestrator triggers CredentialPromptDialog via the UI.

User enters credentials.

Action Agent types them into the application/browser.

Aura asks if the user wants to save credentials for next time.






# Phase 9: Text-to-Speech (TTS) Output

Objective: Allow Aura to speak its responses.

Tasks for AI Coder (aura_core/services/tts_service.py):

Create TextToSpeechService using Tortoise TTS.

Prompt for AI: "Implement a class TextToSpeechService using tortoise-tts. It should have a method speak(text: str). Be mindful of Tortoise's generation time; explore options for faster voices or pre-caching common phrases if initial generation is too slow."

Integrate with UI: Add a toggle in settings "Enable spoken responses."

Orchestrator/UI will call tts_service.speak() for status updates, questions, etc.

Fast Response: Tortoise can be slow. For very quick acknowledgments ("Okay," "Got it"), consider a faster, lower-quality TTS or even pre-recorded soundbites, and use Tortoise for more substantial responses. This is a trade-off.






# Phase 10: Implementing Complex Scenarios (LinkedIn Connections, WhatsApp Messages)

Objective: Tackle the more advanced examples, requiring deeper LLM integration for planning and content generation.

Tasks for AI Coder:



LinkedIn Connections Example:

Orchestrator (using Gemini for planning) might generate steps like:

action_agent.open_application_or_browser('LinkedIn')

perception_agent.wait_for_element_or_analyze_screen('Profile icon/link', 'click') (Action agent performs click based on perception)

perception_agent.wait_for_element_or_analyze_screen('Connections count', 'extract_text')

ui.display_message(f"You have {connections_count} connections.") / tts_service.speak(...)




WhatsApp Customized Messages Example:

Orchestrator (using Gemini for planning):

action_agent.open_application_or_browser('WhatsApp')

perception_agent.identify_contacts_on_screen(count=10) (this is complex, might need OCR + Gemini Vision or accessibility if WhatsApp Web DOM is hard to parse directly)

For each contact:
a. action_agent.click_contact(contact_info)
b. perception_agent.extract_last_chat_messages(count=15) (very challenging via pure vision, relies on good OCR and structure understanding; accessibility or direct DOM might be better if possible)
c. content_generation_agent.generate_custom_message(chat_history, theme='Happy New Year') (using Gemini)
d. action_agent.type_message_in_chat(generated_message)
e. action_agent.send_message() (optional: ask for confirmation first)

Content Generation Agent (aura_core/agents/content_agent.py): Uses Gemini to generate text based on prompts (e.g., "Given this chat history: [...], write a short, friendly Happy New Year message in a similar tone and language.").

Fast Response: These are inherently multi-step. Provide continuous feedback in UI/TTS: "Opening WhatsApp...", "Analyzing chats with John...", "Generating message for John...". Each sub-step involving Gemini needs optimized prompting.






# Phase 11: Robustness, Error Handling & User Control

Objective: Make Aura reliable and give the user ultimate control.

Tasks for AI Coder:

Global STOP command: Ensure the "STOP" button/hotkey/voice command immediately halts current actions in Orchestrator and Action Agent. This requires careful state management and interrupt flags.

Confirmation Prompts: For sensitive actions (sending messages, deleting files), Orchestrator prompts user via UI/TTS and waits for confirmation.

Retry Mechanisms: Implement retries in Action Agent for common failures (e.g., element not found immediately).

Alternative Strategies: If one perception/action method fails (e.g., accessibility), Orchestrator could try another (e.g., screenshot + vision).

Graceful Failure: If a task cannot be completed, Aura explains why (UI and TTS).

Logging: Comprehensive logging for debugging.






# Phase 12: Advanced Features & Continuous Improvement

Objective: Add "polish" and make Aura smarter over time.

Tasks for AI Coder (can be iterative):

Knowledge & Memory Agent (aura_core/agents/knowledge_agent.py):

Store user preferences (e.g., default browser, preferred apps).

Learn successful task flows (e.g., if user manually corrects a step, Aura could try to learn). This is complex and requires careful design.

Proactive Assistance (Future): Based on patterns, suggest actions. (e.g., "It's 9 AM, shall I open your work apps?").

Explainability (XAI): Basic ability for Aura to state why it took a certain step, based on its plan.

Refine Gemini Prompts: Continuously iterate on prompts for NLU, planning, vision, and content generation for better accuracy and speed.

Performance Optimization: Profile code, optimize slow parts (especially image processing, LLM API calls by making them asynchronous, TTS generation).

For TTS speed: Explore if Tortoise TTS can use faster voice models or if there are alternative local TTS engines that offer a better speed/quality balance.

For LLM speed: Ensure prompts are concise. Use Gemini 1.5 Flash specifically because it's designed for speed. Consider local, smaller LLMs for very specific, high-frequency NLU tasks if feasible in the future.





# Phase 13: Testing and Packaging

Objective: Ensure quality and prepare for potential distribution.

Tasks for AI Coder:

Write unit tests for individual agent functions and services.

Write integration tests for common user scenarios.

Manual testing across different OS versions (if aiming for cross-platform).

Package the application (e.g., using PyInstaller or Nuitka) for easier distribution.

This plan is a roadmap. Each step, especially those involving AI coding and LLM interaction, will require significant iteration and prompt engineering. The "fast response" goal needs to be balanced with accuracy – giving immediate feedback while complex operations run asynchronously is key. The "modern, clean, attractive UI" will heavily depend on the AI's ability to interpret stylistic PyQt instructions or leverage QML effectively. Good luck, this is an exciting challenge!