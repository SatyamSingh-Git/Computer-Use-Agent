aura_project/
├── main.py                     # Main application entry point. Initializes UI and Core.
│
├── aura_core/                  # Backend logic, agents, services
│   │
│   ├── __init__.py
│   ├── main_orchestrator.py    # Central coordinator of all agents and task execution flow.
│   │
│   ├── agents/                 # Core intelligent components
│   │   ├── __init__.py
│   │   ├── base_agent.py       # (Optional) Base class for all agents
│   │   ├── nlu_agent.py        # Natural Language Understanding (interfaces with Gemini for intent/entity)
│   │   ├── planning_agent.py   # Task decomposition and strategy generation (uses Gemini)
│   │   ├── perception_agent.py # Screen analysis (screenshots, vision LLM, accessibility APIs)
│   │   ├── action_agent.py     # Executes actions (mouse, keyboard, app control, web)
│   │   ├── knowledge_agent.py  # Manages user preferences, learned procedures, context
│   │   └── content_agent.py    # Generates textual content (e.g., messages, summaries via Gemini)
│   │
│   ├── services/               # Wrappers for external tools and APIs
│   │   ├── __init__.py
│   │   ├── gemini_service.py   # Handles all communication with Google Gemini API
│   │   ├── whisper_service.py  # Manages local Whisper STT operations
│   │   ├── tts_service.py      # Manages local Tortoise TTS (or other TTS) operations
│   │   ├── credential_manager.py # Securely handles storing and retrieving credentials
│   │   ├── os_interaction_service.py # Low-level OS interactions (e.g., process management)
│   │   └── web_automation_service.py # Wrapper for Selenium/Playwright
│   │
│   └── utils/                  # Utility functions, constants, shared resources
│       ├── __init__.py
│       ├── constants.py        # Application-wide constants (e.g., API endpoints, default settings)
│       ├── helpers.py          # General helper functions (e.g., file I/O, data formatting)
│       ├── logger_config.py    # Configuration for application logging
│       └── exceptions.py       # Custom exception classes for Aura
│
├── aura_ui/                    # PyQt UI components and logic
│   │
│   ├── __init__.py
│   ├── main_window.py          # Defines the main application window (QMainWindow)
│   │
│   ├── widgets/                # Custom PyQt widgets
│   │   ├── __init__.py
│   │   ├── command_input_bar.py # The text input field for commands
│   │   ├── status_display.py   # Area to show Aura's current status/actions
│   │   ├── stop_button.py      # The prominent stop button widget
│   │   ├── settings_dialog.py  # Dialog for application settings
│   │   ├── credential_prompt_dialog.py # Secure dialog for entering credentials
│   │   └── notification_widget.py # For displaying brief notifications
│   │
│   ├── views/                  # (If using more complex views beyond simple dialogs)
│   │   ├── __init__.py
│   │   └── ...
│   │
│   ├── themes/                 # Styling information
│   │   ├── __init__.py
│   │   ├── dark_theme.qss      # Qt StyleSheet for dark mode
│   │   ├── light_theme.qss     # Qt StyleSheet for light mode (optional)
│   │   └── theme_manager.py    # Logic to apply and switch themes
│   │
│   └── utils_ui/               # UI-specific helper functions
│       ├── __init__.py
│       └── ui_helpers.py       # Functions for UI manipulations, icon loading etc.
│
├── assets/                     # Static resources
│   ├── icons/                  # Application icons, button icons (e.g., .png, .svg)
│   │   ├── aura_icon.png
│   │   ├── microphone_on.svg
│   │   ├── microphone_off.svg
│   │   └── ...
│   ├── sounds/                 # (Optional) Short sound effects for feedback
│   │   ├── listening.wav
│   │   └── error.wav
│   └── fonts/                  # (Optional) Custom fonts if not relying on system fonts
│
├── config/                     # Configuration files (user-specific or default)
│   ├── default_settings.json   # Default application settings
│   ├── user_settings.json      # User's customized settings (should be in user's app data dir)
│   └── api_keys_template.json  # Template for API keys (actual keys should NOT be in Git)
│
├── logs/                       # Directory for log files (should be in user's app data dir)
│   └── aura_app.log
│
├── tests/                      # Unit and integration tests
│   ├── __init__.py
│   ├── test_core/
│   │   ├── test_nlu_agent.py
│   │   ├── test_perception_agent.py
│   │   └── ...
│   ├── test_ui/
│   │   └── test_main_window.py
│   └── test_integration/
│       └── test_end_to_end_scenarios.py
│
├── docs/                       # Documentation
│   ├── README.md               # Project overview, setup, usage
│   ├── architecture.md         # Details on the system architecture
│   └── api_reference.md        # (If exposing any internal APIs)
│
├── venv/                       # Python virtual environment (add to .gitignore)
│
├── .gitignore                  # Specifies intentionally untracked files that Git should ignore
├── requirements.txt            # List of Python dependencies for pip install
└── setup.py                    # (If planning to package as a library/distributable)