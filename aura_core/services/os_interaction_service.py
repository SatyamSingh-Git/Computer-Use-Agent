import logging
import subprocess
import platform
import webbrowser

import pyautogui
import time
import pygetwindow  # For window management
import urllib.parse  # For URL encoding in web search
import os  # For os.environ check (e.g., DISPLAY on Linux)

logger = logging.getLogger(__name__)


class OSInteractionService:
    def __init__(self):
        self.current_os = platform.system().lower()
        logger.info(f"OSInteractionService initialized for OS: {self.current_os}")

    def _get_attribute_safe(self, obj, attr_name: str, default_value=None):
        """Safely gets an attribute from an object, returning a default if not found."""
        return getattr(obj, attr_name, default_value)

    def find_window(self, title_substring: str, exact_match: bool = False,
                    case_sensitive: bool = False) -> pygetwindow.BaseWindow | None:
        """
        Finds a window based on its title.
        Prioritizes active and visible windows if multiple matches occur.
        """
        try:
            all_windows = pygetwindow.getAllWindows()
            if not all_windows:
                logger.debug("find_window: No windows returned by getAllWindows().")
                return None

            candidates = []
            for w in all_windows:
                window_title = self._get_attribute_safe(w, 'title', "")
                if not window_title:
                    continue

                title_to_check = window_title if case_sensitive else window_title.lower()
                substring_to_check = title_substring if case_sensitive else title_substring.lower()

                if exact_match:
                    if title_to_check == substring_to_check:
                        candidates.append(w)
                else:
                    if substring_to_check in title_to_check:
                        candidates.append(w)

            if candidates:
                active_visible_candidates = [
                    win for win in candidates if
                    self._get_attribute_safe(win, 'isActive', False) and \
                    self._get_attribute_safe(win, 'visible', True) and \
                    not self._get_attribute_safe(win, 'isMinimized', False)
                ]
                if active_visible_candidates:
                    logger.info(
                        f"Found ACTIVE & VISIBLE window(s) for '{title_substring}': {[win.title for win in active_visible_candidates]}")
                    return active_visible_candidates[0]

                visible_candidates = [
                    win for win in candidates if
                    self._get_attribute_safe(win, 'visible', True) and \
                    not self._get_attribute_safe(win, 'isMinimized', False)
                ]
                if visible_candidates:
                    logger.info(
                        f"Found VISIBLE (not minimized) window(s) for '{title_substring}': {[win.title for win in visible_candidates]}")
                    return visible_candidates[0]

                logger.info(
                    f"Found window(s) (any state) matching '{title_substring}': {[win.title for win in candidates]}. Returning first one.")
                return candidates[0]

            logger.info(
                f"No window found {'with exact title' if exact_match else 'containing title substring'} '{title_substring}'.")
            return None
        except Exception as e:
            logger.error(f"Error in find_window for '{title_substring}': {e}",
                         exc_info=True if not isinstance(e, pygetwindow.PyGetWindowException) else False)
            return None

    def activate_window(self, window_obj: pygetwindow.BaseWindow = None, title_substring: str = None,
                        exact_title_match: bool = False) -> bool:
        target_window = window_obj
        if not target_window and title_substring:
            target_window = self.find_window(title_substring, exact_match=exact_title_match)

        if target_window:
            try:
                window_title = self._get_attribute_safe(target_window, 'title', 'Unknown Window')
                if not hasattr(target_window, 'activate'):  # Check if activate method exists
                    logger.error(f"Window object '{window_title}' lacks 'activate' method. Cannot activate.")
                    return False

                is_minimized = self._get_attribute_safe(target_window, 'isMinimized', False)
                if is_minimized:
                    if hasattr(target_window, 'restore'):
                        try:
                            logger.debug(f"Restoring minimized window: '{window_title}'")
                            target_window.restore()
                            time.sleep(0.3)  # Give time for restore animation/state change
                        except Exception as e_restore:
                            logger.warning(f"Could not restore minimized window '{window_title}': {e_restore}")
                    else:
                        logger.warning(f"Window '{window_title}' is minimized but 'restore' method not available.")

                logger.debug(f"Attempting to activate window: '{window_title}'")
                target_window.activate()
                time.sleep(0.2)

                is_active_now = self._get_attribute_safe(target_window, 'isActive', False)
                if not is_active_now:
                    logger.warning(
                        f"Window '{window_title}' not immediately active after activate(). Trying focus/raise.")
                    if hasattr(target_window, 'focus'):
                        target_window.focus()  # Try focus first
                    elif hasattr(target_window, 'raise_'):
                        target_window.raise_()  # Then try raise_
                    time.sleep(0.2)  # Pause after alternative activation attempts
                    is_active_now = self._get_attribute_safe(target_window, 'isActive', False)

                if is_active_now:
                    logger.info(f"Successfully activated window: '{window_title}'")
                    time.sleep(0.3)
                    return True
                else:
                    logger.warning(f"Failed to confirm activation for window: '{window_title}'")
                    return False
            except Exception as e:
                title_attr = self._get_attribute_safe(target_window, 'title', title_substring or "Unknown Target")
                logger.error(f"Error during activation of window '{title_attr}': {e}", exc_info=True)
                return False
        else:
            logger.warning(f"Cannot activate window: No window found for '{title_substring or 'given object'}'.")
            return False

    def get_window_bounds(self, window_title_hint: str) -> tuple[int, int, int, int] | None:
        window = self.find_window(window_title_hint)
        if window:
            try:
                left = self._get_attribute_safe(window, 'left')
                top = self._get_attribute_safe(window, 'top')
                width = self._get_attribute_safe(window, 'width')
                height = self._get_attribute_safe(window, 'height')

                if all(isinstance(val, (int, float)) and val >= 0 for val in
                       [left, top, width, height]):  # Basic sanity check
                    logger.info(
                        f"Found bounds for window '{getattr(window, 'title', 'N/A')}': L:{left}, T:{top}, W:{width}, H:{height}")
                    return int(left), int(top), int(width), int(height)
                else:
                    logger.warning(
                        f"Window '{getattr(window, 'title', 'N/A')}' found, but bounds attributes are invalid: L={left}, T={top}, W={width}, H={height}")
            except Exception as e:
                logger.error(f"Error getting bounds for window '{getattr(window, 'title', 'N/A')}': {e}", exc_info=True)
        else:
            logger.warning(f"Window with hint '{window_title_hint}' not found for getting bounds.")
        return None

    def open_application_windows_start_menu(self, app_name: str) -> bool:
        logger.info(f"Attempting to open '{app_name}' via Windows Start Menu search.")
        try:
            pyautogui.press('win')
            time.sleep(0.8)
            pyautogui.typewrite(app_name, interval=0.03)
            time.sleep(1.5)
            pyautogui.press('enter')
            time.sleep(0.7)
            logger.info(f"Sent '{app_name}' to Start Menu search and pressed Enter.")
            return True
        except Exception as e:
            logger.error(f"Error opening '{app_name}' via Start Menu: {e}", exc_info=True)
            return False

    def open_application(self, app_name: str, activate_if_running: bool = True,
                         use_start_menu_method_on_windows: bool = True) -> tuple[bool, pygetwindow.BaseWindow | None]:
        logger.info(f"Managing application: {app_name}")

        app_name_lower = app_name.lower()
        is_browser = "edge" in app_name_lower or "chrome" in app_name_lower or "firefox" in app_name_lower

        search_title_hint = app_name
        if app_name_lower == "notepad":
            search_title_hint = "Notepad"
        elif "edge" in app_name_lower:
            search_title_hint = "Microsoft Edge"
        elif "chrome" in app_name_lower:
            search_title_hint = "Google Chrome"
        elif "firefox" in app_name_lower:
            search_title_hint = "Firefox"
        elif app_name_lower == "whatsapp" and self.current_os == "windows":
            search_title_hint = "WhatsApp"

        if activate_if_running:
            existing_window = self.find_window(search_title_hint)
            if existing_window:
                logger.info(f"Found existing window for '{search_title_hint}': '{existing_window.title}'. Activating.")
                if self.activate_window(window_obj=existing_window):
                    return True, existing_window
                logger.warning(f"Failed to activate existing window '{existing_window.title}'. Will try launching new.")
            else:
                logger.info(f"No readily identifiable existing window for '{search_title_hint}'. Will launch new.")

        launched_successfully = False
        exec_name_for_log = app_name  # For logging in case of direct launch failure
        if self.current_os == "windows" and use_start_menu_method_on_windows:
            launched_successfully = self.open_application_windows_start_menu(app_name)
        else:
            try:
                exec_name = app_name
                if self.current_os == "windows":  # Define exec_name for Windows direct launch
                    if "edge" in app_name_lower:
                        exec_name = "msedge"
                    elif "chrome" in app_name_lower:
                        exec_name = "chrome"
                    elif "firefox" in app_name_lower:
                        exec_name = "firefox"
                exec_name_for_log = exec_name  # Update for logging if changed

                if self.current_os == "windows":
                    subprocess.Popen([exec_name])
                elif self.current_os == "darwin":
                    subprocess.Popen(["open", "-a", app_name])  # macOS uses app name
                elif self.current_os == "linux":
                    subprocess.Popen([app_name.lower()])
                else:
                    logger.warning(f"Unsupported OS for open_application: {self.current_os}");
                    return False, None
                launched_successfully = True
            except FileNotFoundError:
                logger.error(f"App '{app_name}' (or exec '{exec_name_for_log}') not found via direct command.");
                return False, None
            except Exception as e:
                logger.error(f"Error opening app '{app_name}' via direct command: {e}", exc_info=True);
                return False, None

        if not launched_successfully:
            logger.error(f"Failed to launch '{app_name}'.");
            return False, None

        logger.info(
            f"Initiated opening of '{app_name}'. Waiting up to 5s for new window to appear and be discoverable...")
        newly_opened_window = None;
        max_wait_time = 5.0;
        check_interval = 0.5;
        elapsed_time = 0.0

        title_priority_list = []
        if app_name_lower == "notepad" and self.current_os == "windows":
            title_priority_list.append("Untitled - Notepad")
        title_priority_list.append(search_title_hint)
        if app_name not in title_priority_list and app_name != search_title_hint:
            title_priority_list.append(app_name)

        while elapsed_time < max_wait_time:
            for title_to_try in title_priority_list:
                is_exact_for_new = (title_to_try == "Untitled - Notepad")
                logger.debug(
                    f"Post-launch search: Looking for window '{title_to_try}' (exact: {is_exact_for_new}), elapsed: {elapsed_time:.1f}s")
                candidate_window = self.find_window(title_to_try, exact_match=is_exact_for_new)
                if candidate_window:
                    newly_opened_window = candidate_window
                    logger.info(
                        f"Post-launch search: Found candidate new window: '{newly_opened_window.title}' for app '{app_name}'")
                    break
            if newly_opened_window: break
            time.sleep(check_interval);
            elapsed_time += check_interval

        if newly_opened_window:
            if self.activate_window(window_obj=newly_opened_window):
                logger.info(
                    f"Successfully activated newly managed window: '{newly_opened_window.title}' for app '{app_name}'")
                return True, newly_opened_window
            logger.warning(
                f"Launched '{app_name}' and found window '{newly_opened_window.title}', but failed to activate.")
            return True, newly_opened_window  # Return window even if activation confirmation fails, it might still be usable

        logger.warning(
            f"Launched '{app_name}' but could not find its window after {max_wait_time}s with hints: {title_priority_list}.")
        return True, None  # Launched, but couldn't grab a specific window reliably

    def close_application_window(self, window_title_hint: str) -> bool:
        logger.info(f"Attempting to close window with title hint: '{window_title_hint}'")
        window_to_close = self.find_window(window_title_hint)

        if not window_to_close:
            logger.warning(f"No window found with title hint '{window_title_hint}' to close.")
            return False

        original_title = self._get_attribute_safe(window_to_close, 'title', window_title_hint)

        if not self.activate_window(window_obj=window_to_close):
            logger.warning(
                f"Failed to activate window '{original_title}' before attempting to close. Will still try sending close keys to currently active window.")

        close_keys = []
        if self.current_os == "windows":
            close_keys = ['alt', 'f4']
        elif self.current_os == "darwin":
            close_keys = ['command', 'w']  # Usually closes window, 'q' quits app
        elif self.current_os == "linux":
            close_keys = ['ctrl', 'w']  # Common, but can vary

        if close_keys:
            logger.info(f"Sending close keys {close_keys} (intended for '{original_title}')")
            # press_key will target the active window if target_window_title is None
            if self.press_key(close_keys, target_window_title=None):  # Send to currently active window
                logger.info(f"Close command sent (intended for '{original_title}').")
                time.sleep(0.7)
                # Check if window with the *original* title is still present
                if self.find_window(original_title, exact_match=True):  # Check for exact original title
                    logger.warning(
                        f"Window '{original_title}' might still be open (e.g., save dialog or did not close).")
                else:
                    logger.info(f"Window '{original_title}' appears to be closed.")
                return True
            else:
                logger.error(f"Failed to send close keys while '{original_title}' was (assumed) active.")
                return False
        else:
            logger.warning(f"No standard close key combination defined for OS: {self.current_os}")
            return False

    def search_web(self, query: str) -> bool:
        logger.info(f"Searching web for: '{query}'")
        try:
            search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
            webbrowser.open_new_tab(search_url)
            logger.info(f"Opened browser for search: {search_url}")
            return True
        except Exception as e:
            logger.error(f"Error opening web browser for search: {e}", exc_info=True)
            return False

    def type_text(self, text_to_type: str, interval: float = 0.01, target_window_title: str = None) -> bool:
        if target_window_title:
            if not self.activate_window(title_substring=target_window_title):
                logger.error(f"Failed to activate window '{target_window_title}' for typing.")
                return False
        logger.info(f"Typing text: '{text_to_type[:30]}...' in '{target_window_title or 'active window'}'")
        try:
            pyautogui.typewrite(text_to_type, interval=interval)
            return True
        except Exception as e:
            if "pyautogui.FailSafeException" in str(type(e)):
                logger.error(f"PyAutoGUI FailSafe triggered during typing: {e}", exc_info=False)
            else:
                logger.error(f"Error typing text: {e}", exc_info=True)
            return False

    def press_key(self, key_name: str | list[str], target_window_title: str = None) -> bool:
        if target_window_title:
            if not self.activate_window(title_substring=target_window_title):
                logger.warning(
                    f"Press_key: Failed to ensure window '{target_window_title}' is active. Keys will be sent to current active window.")

        logger.info(f"Pressing key(s): {key_name} (intended target: '{target_window_title or 'currently active'}')")
        try:
            if isinstance(key_name, list):
                pyautogui.hotkey(*key_name)
            else:
                pyautogui.press(key_name)
            return True
        except Exception as e:
            if "pyautogui.FailSafeException" in str(type(e)):
                logger.error(f"PyAutoGUI FailSafe triggered during key press: {e}", exc_info=False)
            else:
                logger.error(f"Error pressing key(s) '{key_name}': {e}", exc_info=True)
            return False

    def click_at(self, x: int, y: int, button: str = 'left', clicks: int = 1, interval: float = 0.1) -> bool:
        logger.info(f"Clicking at ({x}, {y}) with {button} button, {clicks} times.")
        try:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=interval)
            logger.info("Click successful.")
            return True
        except Exception as e:
            if "pyautogui.FailSafeException" in str(type(e)):  # More specific check
                logger.error(f"PyAutoGUI FailSafe triggered during click: {e}", exc_info=False)
            else:
                logger.error(f"Error clicking at ({x},{y}): {e}", exc_info=True)
            return False

    def take_screenshot_pyautogui(self, region: tuple[int, int, int, int] | None = None) -> bytes | None:
        import io
        action_desc = f"region '{region}'" if region else "full screen"
        logger.info(f"Taking screenshot of {action_desc} using PyAutoGUI.")
        try:
            if platform.system() == "Linux" and not os.environ.get('DISPLAY'):
                logger.error("No DISPLAY environment variable found on Linux. PyAutoGUI screenshot might fail.")

            screenshot_pil = pyautogui.screenshot(region=region)
            img_byte_arr = io.BytesIO()
            screenshot_pil.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            logger.info(f"Screenshot captured successfully ({len(img_bytes)} bytes).")
            return img_bytes
        except Exception as e:
            logger.error(f"Error taking screenshot with PyAutoGUI (region: {region}): {e}", exc_info=True)
            return None


# Example usage block for testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(levelname)s - [%(name)s:%(module)s:%(lineno)d] - %(message)s")
    os_interaction = OSInteractionService()

    print("\n--- Testing find_window ---")
    # Manually open Notepad or some other app for this test
    # input("Please open Notepad (or any app with a known title part) and press Enter...")
    # test_title_hint = "Notepad"
    # found_win = os_interaction.find_window(test_title_hint)
    # if found_win:
    #     print(f"Found window: {found_win.title}")
    #     print(f"  Active: {os_interaction._get_attribute_safe(found_win, 'isActive', 'N/A')}")
    #     print(f"  Visible: {os_interaction._get_attribute_safe(found_win, 'visible', 'N/A')}") # Test the safe getter
    #     print(f"  Minimized: {os_interaction._get_attribute_safe(found_win, 'isMinimized', 'N/A')}")
    #     bounds = os_interaction.get_window_bounds(found_win.title) # Test get_window_bounds
    #     print(f"  Bounds: {bounds}")
    # else:
    #     print(f"Window containing '{test_title_hint}' not found.")

    print("\n--- Testing Start Menu App Opener (Windows only) ---")
    if os_interaction.current_os == "windows":
        APP_NAME = "Notepad"
        print(f"Attempting to open '{APP_NAME}' via Start Menu...")
        success, window_obj = os_interaction.open_application(APP_NAME, use_start_menu_method_on_windows=True)
        if success:
            title = getattr(window_obj, 'title', 'N/A (check if app opened)')
            print(f"Managed '{APP_NAME}'. Window: {title}")
            if window_obj and title != 'N/A':
                time.sleep(1)
                print(f"Attempting to type into '{title}'...")
                os_interaction.type_text("Hello from Aura Start Menu test!", target_window_title=title)
                time.sleep(1)
                # input(f"Press Enter to try closing '{title}'...")
                # if os_interaction.close_application_window(title):
                #     print(f"Attempted to close '{title}'.")
                # else:
                #     print(f"Failed to send close command to '{title}'.")
        else:
            print(f"Failed to open '{APP_NAME}' via Start Menu.")
    else:
        print("Skipping Windows Start Menu test as OS is not Windows.")

    print("\n--- Testing Web Search ---")
    os_interaction.search_web("pygetwindow attributes")