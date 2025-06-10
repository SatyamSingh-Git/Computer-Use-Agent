import logging
import pywinauto
from pywinauto.findwindows import ElementNotFoundError, WindowNotFoundError
from pywinauto.uia_defines import NoPatternInterfaceError  # For checking if click is supported

logger = logging.getLogger(__name__)

# Commonly used control types (can be expanded)
# Reference: https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.controltype
UIA_CONTROL_TYPES = {
    "button": "ButtonControl",
    "edit": "EditControl",  # Text input
    "text": "TextControl",  # Static text, labels
    "document": "DocumentControl",
    "list": "ListControl",
    "list_item": "ListItemControl",
    "menu": "MenuControl",
    "menu_item": "MenuItemControl",
    "pane": "PaneControl",  # Often a container
    "window": "WindowControl",
    "title_bar": "TitleBarControl",
    "combo_box": "ComboBoxControl",
    "check_box": "CheckBoxControl",
    "radio_button": "RadioButtonControl",
    "slider": "SliderControl",
    "hyperlink": "HyperlinkControl",
    "image": "ImageControl",
    "tab": "TabControl",
    "tab_item": "TabItemControl",
    "table": "TableControl",
    "custom": "CustomControl",
    "data_grid": "DataGridControl",
    "data_item": "DataItemControl",
    "group": "GroupControl",
    "header": "HeaderControl",
    "header_item": "HeaderItemControl",
    "progress_bar": "ProgressBarControl",
    "scroll_bar": "ScrollBarControl",
    "separator": "SeparatorControl",
    "spinner": "SpinnerControl",
    "status_bar": "StatusBarControl",
    "tool_bar": "ToolBarControl",
    "tool_tip": "ToolTipControl",
    "tree": "TreeControl",
    "tree_item": "TreeItemControl",
    "calendar": "CalendarControl",
    "split_button": "SplitButtonControl"
}


class AccessibilityService:
    def __init__(self):
        # For now, we connect to Desktop on demand or to a specific app window
        logger.info("AccessibilityService initialized (using pywinauto with UIA backend).")
        self.desktop = None
        try:
            # Using backend='uia' is generally recommended for modern apps
            self.desktop = pywinauto.Desktop(backend="uia", allow_magic_lookup=False)
            logger.info("pywinauto.Desktop(backend='uia') initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize pywinauto.Desktop: {e}", exc_info=True)
            # Aura can continue but accessibility features will fail.

    def _get_window(self, window_title_hint: str = None, process_id: int = None,
                    class_name: str = None) -> pywinauto.WindowSpecification | None:
        """
        Connects to an application window.
        Prioritizes process_id if given, then title_hint, then class_name.
        """
        if not self.desktop:
            logger.error("AccessibilityService: pywinauto.Desktop not available.")
            return None
        try:
            app_spec = None
            if process_id:
                logger.debug(f"Attempting to connect to window by process_id: {process_id}")
                app_spec = self.desktop.window(process=process_id, top_level_only=True, visible_only=True)
            elif window_title_hint:
                logger.debug(f"Attempting to connect to window by title_hint: '{window_title_hint}'")
                # Use regex=True for more flexible title matching (e.g., contains)
                # We use `title_re` for substring matching, `title` for exact.
                # For now, let's assume window_title_hint might be a substring.
                app_spec = self.desktop.window(title_re=f".*{window_title_hint}.*", top_level_only=True,
                                               visible_only=True, found_index=0)
            elif class_name:
                logger.debug(f"Attempting to connect to window by class_name: '{class_name}'")
                app_spec = self.desktop.window(class_name=class_name, top_level_only=True, visible_only=True,
                                               found_index=0)
            else:
                logger.warning("No valid identifier (title, process_id, class_name) provided to get window.")
                return None

            if app_spec and app_spec.exists(timeout=2, retry_interval=0.5):  # Check if window actually exists
                logger.info(f"Successfully connected to window: '{app_spec.window_text()}'")
                return app_spec
            else:
                logger.warning(
                    f"Window not found or does not exist for given criteria (title: {window_title_hint}, pid: {process_id}, class: {class_name}).")
                return None
        except (ElementNotFoundError, WindowNotFoundError):
            logger.warning(
                f"Window not found for criteria (title: {window_title_hint}, pid: {process_id}, class: {class_name}).")
            return None
        except RuntimeError as e:  # Can happen if backend issue or window closed during operation
            logger.error(f"RuntimeError connecting to window: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error connecting to window: {e}", exc_info=True)
            return None

    def find_element(self, window_spec: pywinauto.WindowSpecification,
                     element_name: str = None,
                     control_type: str = None,
                     automation_id: str = None,
                     framework_id: str = None,  # e.g. "Win32", "XAML"
                     class_name_re: str = None,  # For regex matching class name
                     search_depth: int = 8,  # How deep to search in the UI tree
                     found_index: int = 0) -> pywinauto.base_wrapper.BaseWrapper | None:
        """
        Finds a UI element within a given window specification.
        Uses a combination of properties. `element_name` is often the most useful.
        `control_type` should be one of the UIA standard names (e.g., "Button", "Edit").
        """
        if not window_spec or not window_spec.exists():
            logger.warning("Provided window specification is invalid or window does not exist.")
            return None

        criteria = {}
        if element_name: criteria['title_re'] = f".*{element_name}.*"  # Substring match for name/title
        # Map common names to pywinauto's expected control type strings if necessary
        if control_type:
            # pywinauto often expects "ButtonControl", "EditControl" etc. or just "Button", "Edit"
            # The UIA_CONTROL_TYPES dict maps friendly names to more specific ones if needed,
            # but pywinauto's `control_type` parameter is quite flexible.
            # Let's assume user passes one of pywinauto's accepted types for now.
            criteria['control_type'] = control_type
        if automation_id: criteria['auto_id'] = automation_id
        if framework_id: criteria['framework_id'] = framework_id
        if class_name_re: criteria['class_name_re'] = class_name_re

        if not criteria:
            logger.error("No criteria provided to find_element.")
            return None

        try:
            logger.debug(f"Searching for element with criteria: {criteria} in window '{window_spec.window_text()}'")
            # Use child_window for more robust finding than direct descendent access
            element = window_spec.child_window(**criteria, found_index=found_index)

            if element.exists(timeout=1, retry_interval=0.2):  # Quick check if found element actually exists
                logger.info(
                    f"Element found: Name='{element.window_text()}', ControlType='{element.element_info.control_type}'")
                return element
            else:
                logger.warning(
                    f"Element matching {criteria} reported by child_window but does not exist on quick check.")
                return None
        except ElementNotFoundError:
            logger.warning(f"Element not found with criteria: {criteria} in window '{window_spec.window_text()}'")
            return None
        except Exception as e:
            logger.error(f"Error finding element: {e}", exc_info=True)
            return None

    def get_element_properties(self, element: pywinauto.base_wrapper.BaseWrapper) -> dict | None:
        """Gets common properties of a found UI element."""
        if not element or not element.exists():
            logger.warning("Cannot get properties: Element is invalid or does not exist.")
            return None
        try:
            props = {
                "name": element.window_text(),
                "control_type": element.element_info.control_type,  # More reliable than friendly_class_name()
                "rectangle": element.rectangle().tolist() if hasattr(element, 'rectangle') else None,  # [L,T,R,B]
                "is_enabled": element.is_enabled(),
                "is_visible": element.is_visible(),  # Note: pywinauto's is_visible might be more reliable
                "automation_id": self._get_attribute_safe(element.element_info, 'automation_id'),
                "class_name": self._get_attribute_safe(element.element_info, 'class_name'),
                "framework_id": self._get_attribute_safe(element.element_info, 'framework_id'),
                "process_id": self._get_attribute_safe(element.element_info, 'process_id')
            }
            logger.debug(f"Properties for element '{props['name']}': {props}")
            return props
        except Exception as e:
            logger.error(f"Error getting properties for element: {e}", exc_info=True)
            return None

    def click_element(self, element: pywinauto.base_wrapper.BaseWrapper, click_type: str = "left", coords=None) -> bool:
        """
        Performs a click on the given element.
        `click_type` can be 'left', 'right', 'double_left', etc.
        `coords` can be a tuple (x,y) relative to the element's top-left for offset clicks.
        """
        if not element or not element.exists():
            logger.warning("Cannot click: Element is invalid or does not exist.")
            return False
        try:
            if not element.is_enabled():
                logger.warning(f"Element '{element.window_text()}' is not enabled. Click might fail or do nothing.")

            logger.info(
                f"Attempting to click element: '{element.window_text()}' (Type: {element.element_info.control_type})")

            # Different ways to click based on element capabilities
            if hasattr(element, 'click_input'):  # Preferred for UIA, more like human click
                if coords:
                    element.click_input(button=click_type, coords=coords)
                else:
                    element.click_input(button=click_type)
                logger.info("Clicked element using click_input().")
                return True
            elif hasattr(element, 'click'):  # Fallback
                element.click()  # Simple click, might not support button type or coords
                logger.info("Clicked element using click().")
                return True
            # Check for specific patterns if direct click methods fail or aren't ideal
            elif element.has_pattern(pywinauto.uia_defines.InvokePattern):
                element.invoke()
                logger.info("Clicked element using InvokePattern.")
                return True
            else:
                logger.warning(
                    f"Element '{element.window_text()}' does not have a standard click method (click_input, click) or InvokePattern. Click may not be possible directly.")
                # As a last resort, could try to get its clickable point and use pyautogui,
                # but that's less ideal than using pywinauto's own interaction methods.
                # rect = element.rectangle()
                # clickable_point = element.clickable_point() # Returns Point(x,y)
                # pyautogui.click(clickable_point.x, clickable_point.y)
                return False
        except NoPatternInterfaceError as npe:  # E.g. trying to invoke something not invokable
            logger.error(f"Element '{element.window_text()}' does not support the requested click pattern: {npe}",
                         exc_info=False)
            return False
        except Exception as e:
            element_name = self._get_attribute_safe(element, 'window_text', 'Unknown Element')
            logger.error(f"Error clicking element '{element_name}': {e}", exc_info=True)
            return False

    def set_element_text(self, element: pywinauto.base_wrapper.BaseWrapper, text: str) -> bool:
        """Sets the text of an editable UI element (e.g., an Edit control)."""
        if not element or not element.exists():
            logger.warning("Cannot set text: Element is invalid or does not exist.")
            return False
        try:
            if not element.is_enabled():
                logger.warning(f"Element '{element.window_text()}' is not enabled. Set text might fail.")

            # For UIA backend, set_edit_text or type_keys are common
            if hasattr(element, 'set_edit_text'):
                logger.info(f"Setting text of '{element.window_text()}' to '{text[:20]}...' using set_edit_text().")
                element.set_edit_text(text, pos_start=0, pos_end=-1)  # Replace all text
                return True
            elif hasattr(element, 'type_keys'):
                logger.info(f"Setting text of '{element.window_text()}' to '{text[:20]}...' using type_keys().")
                element.type_keys(text, with_spaces=True, set_foreground=True, click=True)  # Click to focus first
                return True
            else:
                logger.warning(f"Element '{element.window_text()}' does not have set_edit_text or type_keys method.")
                return False
        except Exception as e:
            element_name = self._get_attribute_safe(element, 'window_text', 'Unknown Element')
            logger.error(f"Error setting text for element '{element_name}': {e}", exc_info=True)
            return False


# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(levelname)s - [%(name)s:%(module)s:%(lineno)d] - %(message)s")
    acc_service = AccessibilityService()

    if not acc_service.desktop:
        print("Failed to initialize pywinauto Desktop. Cannot run tests.")
    else:
        # Test with Calculator (ensure Calculator is open)
        # You might need to adjust "Calculator" title if your OS locale is different
        input("Please open Calculator and press Enter to continue tests...")

        calc_window_title_hint = "Calculator"
        calc_window = acc_service._get_window(window_title_hint=calc_window_title_hint)

        if calc_window:
            print(f"\n--- Found Calculator window: {calc_window.window_text()} ---")

            # Example: Find and click the "7" button
            # Automation IDs can be found using tools like Inspect.exe (Windows SDK) or py_inspect() from pywinauto
            # For Windows 10/11 Calculator, number buttons often have automation_id like "num7Button"
            seven_button = acc_service.find_element(calc_window, automation_id="num7Button", control_type="Button")
            # As a fallback, try by name if automation_id fails or is unknown
            if not seven_button:
                seven_button = acc_service.find_element(calc_window, element_name="Seven", control_type="Button")

            if seven_button:
                props = acc_service.get_element_properties(seven_button)
                print(f"Properties of 'Seven' button: {props}")
                print("Clicking 'Seven' button...")
                if acc_service.click_element(seven_button):
                    print("Clicked 'Seven' successfully.")
                else:
                    print("Failed to click 'Seven'.")
            else:
                print("Could not find the 'Seven' button by auto_id or name.")

            # Example: Find the "Add" button (Plus button)
            add_button = acc_service.find_element(calc_window, automation_id="plusButton", control_type="Button")
            if not add_button:
                add_button = acc_service.find_element(calc_window, element_name="Add", control_type="Button")

            if add_button:
                print("Clicking 'Add' button...")
                acc_service.click_element(add_button)
            else:
                print("Could not find the 'Add' button.")

            # Example: Find and click the "8" button
            eight_button = acc_service.find_element(calc_window, automation_id="num8Button", control_type="Button")
            if not eight_button:
                eight_button = acc_service.find_element(calc_window, element_name="Eight", control_type="Button")

            if eight_button:
                print("Clicking 'Eight' button...")
                acc_service.click_element(eight_button)
            else:
                print("Could not find the 'Eight' button.")

            # Example: Find and click the "Equals" button
            equals_button = acc_service.find_element(calc_window, automation_id="equalButton", control_type="Button")
            if not equals_button:
                equals_button = acc_service.find_element(calc_window, element_name="Equals", control_type="Button")

            if equals_button:
                print("Clicking 'Equals' button...")
                acc_service.click_element(equals_button)
                print("Pressed Equals. Check Calculator for result (e.g., 15 if 7+8 was pressed).")
            else:
                print("Could not find the 'Equals' button.")

            # Example: Get text from the results display (can be tricky)
            # The results display in Calculator might be a "Text" control or part of a "Group" or "Custom" control.
            # Its automation_id is often "CalculatorResults" or similar.
            time.sleep(0.5)  # Wait for result to display
            results_display = acc_service.find_element(calc_window, automation_id="CalculatorResults",
                                                       control_type="Text")
            if not results_display:  # Fallback for different Calculator versions
                results_display = acc_service.find_element(calc_window, control_type="Text",
                                                           found_index=0)  # Try first text control

            if results_display:
                props = acc_service.get_element_properties(results_display)
                if props and "name" in props:  # 'name' usually holds the displayed text for Text controls
                    print(f"Calculator Result Display Text: '{props['name']}'")
                else:
                    print(f"Found results display, but could not get its text. Properties: {props}")
            else:
                print("Could not find the Calculator results display element.")

        else:
            print(f"Could not connect to '{calc_window_title_hint}'. Ensure it is open.")