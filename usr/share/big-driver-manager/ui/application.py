#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Application Class

This module defines the main application class for the Big Driver Manager.
"""

import os
import json
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, Gio, GLib, Gtk, Adw

from core.constants import APP_ID, APP_NAME, CONFIG_DIR, SETTINGS_FILE
from core.logging_config import init_app_logging, get_logger
from utils import _
from utils.style_manager import StyleManager
from ui.window import KernelManagerWindow


class SettingsManager:
    """Settings manager for the Big Driver Manager application."""

    def __init__(self):
        """Initialize the settings manager."""
        self.settings_file = SETTINGS_FILE
        self._logger = get_logger("SettingsManager")
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self._settings = self._load_settings()

    def _load_settings(self) -> dict:
        """Load settings from file."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self._logger.error("Error loading settings: %s", e)
        return {}

    def _save_settings(self) -> bool:
        """Save settings to file."""
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self._logger.error("Error saving settings: %s", e)
            return False

    def get(self, key: str, default=None):
        """Get a setting value."""
        return self._settings.get(key, default)

    def set(self, key: str, value) -> bool:
        """Set a setting value and save."""
        self._settings[key] = value
        return self._save_settings()


class KernelManagerApplication(Adw.Application):
    """Main application class for Big Driver Manager."""

    def __init__(self):
        """Initialize the application."""
        super().__init__(
            application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        )
        self.connect("activate", self.on_activate)
        self.connect("command-line", self._on_command_line)
        self.add_main_option(
            "install",
            0,
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            _("Open the page of a driver package and offer to install it"),
            "PACKAGE",
        )

        # Initialize logging
        self._logger = init_app_logging()
        self._logger.info(f"Starting {APP_NAME}")

        # Initialize settings manager
        self.settings_manager = SettingsManager()

        # Load custom CSS via singleton StyleManager
        style_mgr = StyleManager.get_default()
        if not style_mgr.load_styles():
            self._logger.warning("Failed to load application CSS")

        # Register custom icon search path
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icons_path = os.path.join(base_dir, "assets", "icons")
        display = Gdk.Display.get_default()
        if display:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            icon_theme.add_search_path(icons_path)

    def on_activate(self, app) -> None:
        """
        Callback for the application activation.

        Args:
            app: The application instance.
        """
        self._logger.info("Application activated")

        # A second launch reuses the running instance: just raise the window
        existing = self.get_active_window()
        if existing is not None:
            existing.present()
            return

        # Register keyboard shortcuts
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.about", ["F1"])

        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)

        # Restore window size from settings
        sm = self.settings_manager
        width = sm.get("window_width", None)
        height = sm.get("window_height", None)

        win = KernelManagerWindow(application=app)
        if width and height:
            win.set_default_size(int(width), int(height))
        if sm.get("window_maximized", False):
            win.maximize()

        win.connect("close-request", self._on_window_close)
        win.present()

    def _on_command_line(self, _app, command_line: Gio.ApplicationCommandLine) -> int:
        """Handle a launch (first or remote) with its options."""
        self.activate()
        options = command_line.get_options_dict().end().unpack()
        package = options.get("install")
        window = self.get_active_window()
        if package and window is not None and hasattr(window, "request_install"):
            window.request_install(package)
        return 0

    def _on_window_close(self, window) -> bool:
        """Persist window geometry before closing."""
        sm = self.settings_manager
        if not window.is_maximized():
            sm.set("window_width", window.get_width())
            sm.set("window_height", window.get_height())
        sm.set("window_maximized", window.is_maximized())
        return False  # allow close to proceed

    def show_error_dialog(self, message: str) -> None:
        """
        Show an error dialog with the given message.

        Args:
            message: Error message to display.
        """
        self._logger.error(f"Error dialog: {message}")
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Error"))
        dialog.set_body(message)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.present(self.get_active_window())
