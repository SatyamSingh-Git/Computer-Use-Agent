import os


class ThemeManager:
    @staticmethod
    def load_stylesheet(theme_name="dark_theme.qss"):
        script_dir = os.path.dirname(__file__)  # Directory of theme_manager.py
        stylesheet_path = os.path.join(script_dir, theme_name)

        try:
            with open(stylesheet_path, "r") as f:
                return f.read()
        except FileNotFoundError:
            print(f"Warning: Stylesheet '{theme_name}' not found at '{stylesheet_path}'.")
            return ""

    @staticmethod
    def apply_theme(app, theme_name="dark_theme.qss"):
        stylesheet = ThemeManager.load_stylesheet(theme_name)
        if stylesheet:
            app.setStyleSheet(stylesheet)
            print(f"Applied theme: {theme_name}")
        else:
            print("No theme applied.")