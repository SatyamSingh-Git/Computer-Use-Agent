# aura_project/config/constants.py (Create if it doesn't exist, or add to existing constants file)
import os

# --- Application Paths ---
# Determine a user-specific directory for storing app data
APP_NAME = "AuraAI"
if os.name == 'nt': # Windows
    APP_DATA_DIR = os.path.join(os.environ['APPDATA'], APP_NAME)
elif os.name == 'posix': # macOS, Linux
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), '.config', APP_NAME)
else:
    APP_DATA_DIR = os.path.join(os.path.expanduser('~'), APP_NAME) # Fallback

if not os.path.exists(APP_DATA_DIR):
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create app data directory {APP_DATA_DIR}: {e}")
        # Fallback to current directory if creation fails (not ideal for production)
        APP_DATA_DIR = os.path.join(os.getcwd(), "user_data_aura")
        if not os.path.exists(APP_DATA_DIR):
            os.makedirs(APP_DATA_DIR, exist_ok=True)


# --- Credential Management ---
CREDENTIAL_FILE_NAME = "aura_creds.dat"
CREDENTIAL_FILE_PATH = os.path.join(APP_DATA_DIR, CREDENTIAL_FILE_NAME)
SALT_FILE_NAME = "aura_salt.dat" # Salt for KDF
SALT_FILE_PATH = os.path.join(APP_DATA_DIR, SALT_FILE_NAME)

# --- Logging ---
LOG_DIR = os.path.join(APP_DATA_DIR, "logs")
LOG_FILE_PATH = os.path.join(LOG_DIR, "aura_app.log")

# --- Other Constants ---
# Example: DEFAULT_BROWSER = "chrome"