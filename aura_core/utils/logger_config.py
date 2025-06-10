import logging
import os
from logging.handlers import RotatingFileHandler

# Import constants for log paths
try:
    from config.constants import LOG_DIR, LOG_FILE_PATH
except ImportError:
    # Fallback if constants.py is not found or paths are not defined
    # This is mainly for standalone testing or if constants.py structure changes.
    # In the main app, constants.py should be resolvable.
    print("Warning: Could not import LOG_DIR, LOG_FILE_PATH from config.constants. Using fallback paths.")
    _fallback_app_data_dir = os.path.join(os.path.expanduser('~'), '.AuraAI_fallback_data')
    LOG_DIR = os.path.join(_fallback_app_data_dir, "logs")
    LOG_FILE_PATH = os.path.join(LOG_DIR, "aura_app_fallback.log")
    # Ensure fallback directory exists if we're forced to use it
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)


def setup_logging(log_level_str: str = "INFO", log_to_console: bool = True, log_to_file: bool = True) -> str:
    """
    Sets up application-wide logging.
    Returns a message indicating the logging status or path to the log file.

    :param log_level_str: Logging level as a string (e.g., "DEBUG", "INFO", "WARNING").
    :param log_to_console: Boolean, whether to log to console.
    :param log_to_file: Boolean, whether to log to file.
    :return: Path to the log file or a status message.
    """
    # Convert log level string to logging constant
    numeric_log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    # Get the root logger
    # Important: If other parts of your app get loggers before this setup, they might not inherit these handlers.
    # Call this setup EARLY in your main.py.
    root_logger = logging.getLogger()

    # Clear existing handlers from the root logger to avoid duplicate messages if this function is called multiple times
    # (though ideally it's called once).
    if root_logger.hasHandlers():
        # print("Clearing existing root logger handlers.") # For debugging if you see duplicate logs
        root_logger.handlers.clear()

    root_logger.setLevel(numeric_log_level)  # Set level on the root logger

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - [%(name)s:%(module)s:%(funcName)s:%(lineno)d] - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S'  # Added date format
    )

    effective_log_file_path = "File logging disabled."

    # --- File Handler ---
    if log_to_file:
        # LOG_DIR and LOG_FILE_PATH are imported from constants
        log_dir_to_use = LOG_DIR
        log_file_to_use = LOG_FILE_PATH

        if not os.path.exists(log_dir_to_use):
            try:
                os.makedirs(log_dir_to_use, exist_ok=True)
                print(f"Log directory created: {log_dir_to_use}")
            except OSError as e:
                print(f"Error creating log directory {log_dir_to_use}: {e}. Disabling file logging.")
                log_to_file = False  # Can't log to file if directory creation fails

        if log_to_file:  # Check again in case it was disabled
            try:
                # Rotating file handler: 5MB per file, keep 5 backup files
                file_handler = RotatingFileHandler(
                    log_file_to_use,
                    maxBytes=5 * 1024 * 1024,
                    backupCount=5,
                    encoding='utf-8'
                )
                file_handler.setFormatter(formatter)
                file_handler.setLevel(numeric_log_level)  # Set level on handler too
                root_logger.addHandler(file_handler)
                effective_log_file_path = log_file_to_use
                print(f"Logging to file: {effective_log_file_path} with level {log_level_str.upper()}")
            except Exception as e:
                print(f"Error setting up file logger for {log_file_to_use}: {e}. File logging might be impacted.")
                effective_log_file_path = f"Error setting up file log: {e}"

    # --- Console Handler ---
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(numeric_log_level)  # Set level on handler
        root_logger.addHandler(console_handler)
        if not log_to_file or not os.path.exists(
                effective_log_file_path):  # Avoid double printing if file logging is also on
            print(f"Logging to console with level: {log_level_str.upper()}")

    if not log_to_console and not (log_to_file and os.path.exists(effective_log_file_path)):
        print("Warning: Console and File logging are both disabled or failed. No logs will be visible/saved.")

    return effective_log_file_path


if __name__ == "__main__":
    # Example of setting up logging when running this file directly for testing
    # In a real app, main.py would call setup_logging() once at the start.

    print("--- Testing Logger Config ---")

    # Test with default settings (INFO to console and file)
    log_path1 = setup_logging()
    logging.debug("This is a DEBUG message (should not appear with INFO level).")
    logging.info("This is an INFO message (test 1).")
    logging.warning("This is a WARNING message (test 1).")
    print(f"Log setup attempt 1 returned: {log_path1}")

    # Test with different level and console only
    print("\n--- Testing DEBUG to console only ---")
    log_path2 = setup_logging(log_level_str="DEBUG", log_to_file=False, log_to_console=True)
    logging.debug("This is a DEBUG message (test 2 - should appear).")
    logging.info("This is an INFO message (test 2).")
    print(f"Log setup attempt 2 returned: {log_path2}")

    # Test file only
    print("\n--- Testing WARNING to file only ---")
    log_path3 = setup_logging(log_level_str="WARNING", log_to_console=False, log_to_file=True)
    logging.info("This is an INFO message (test 3 - should not appear in console, written to file if level WARNING).")
    logging.warning("This is a WARNING message (test 3 - should be in file).")
    logging.error("This is an ERROR message (test 3 - should be in file).")
    print(f"Log setup attempt 3 returned: {log_path3}")
    if os.path.exists(LOG_FILE_PATH):
        print(f"Check the log file for test 3 messages: {LOG_FILE_PATH}")
    else:
        print(f"Log file {LOG_FILE_PATH} was not created for test 3, check permissions or path.")

    # Test fallback if constants cannot be imported (simulated)
    # To truly test this, you'd need to temporarily rename/remove config/constants.py
    # or trigger the ImportError in the try-except block at the top.
    # print("\n--- Simulating ImportError for constants (manual test needed) ---")