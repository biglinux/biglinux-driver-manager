#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Application Class

This module defines the main application class for the Big Driver Manager.
"""

import json
import os
import tempfile
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, Gio, Gtk, Adw

from core.constants import (
    APP_ID,
    APP_NAME,
    CONFIG_DIR,
    SETTINGS_FILE,
    WINDOW_DEFAULT_HEIGHT,
    WINDOW_DEFAULT_WIDTH,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
)
from core.logging_config import init_app_logging, get_logger
from utils import _
from utils.style_manager import StyleManager
from ui.window import KernelManagerWindow


class SettingsManager:
    """Settings manager for the Big Driver Manager application."""

    _INT_SETTINGS = {
        "window_width": (WINDOW_MIN_WIDTH, 7680),
        "window_height": (WINDOW_MIN_HEIGHT, 4320),
    }
    _BOOL_SETTINGS = {"window_maximized"}

    def __init__(self):
        """Initialize the settings manager."""
        self.settings_file = SETTINGS_FILE
        self._logger = get_logger("SettingsManager")
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self._settings = self._load_settings()

    def _sanitize_settings(self, data: object) -> dict:
        """Return validated known settings while preserving unknown keys."""
        if not isinstance(data, dict):
            self._logger.warning("Ignoring invalid settings payload of type %s", type(data))
            return {}

        sanitized = {
            key: value
            for key, value in data.items()
            if key not in self._INT_SETTINGS and key not in self._BOOL_SETTINGS
        }
        for key, (minimum, maximum) in self._INT_SETTINGS.items():
            if key not in data:
                continue
            value = data[key]
            if type(value) is not int:
                self._logger.warning("Ignoring non-integer setting %s=%r", key, value)
                continue
            if not minimum <= value <= maximum:
                self._logger.warning(
                    "Ignoring out-of-range setting %s=%r (expected %d-%d)",
                    key,
                    value,
                    minimum,
                    maximum,
                )
                continue
            sanitized[key] = value

        for key in self._BOOL_SETTINGS:
            if key not in data:
                continue
            value = data[key]
            if isinstance(value, bool):
                sanitized[key] = value
            else:
                self._logger.warning("Ignoring non-boolean setting %s=%r", key, value)

        return sanitized

    def _load_settings(self) -> dict:
        """Load settings from file."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    return self._sanitize_settings(json.load(f))
            except Exception as e:
                self._logger.error("Error loading settings: %s", e)
        return {}

    def _save_settings(self) -> bool:
        """Save settings to file."""
        sanitized = self._sanitize_settings(self._settings)
        self._settings = sanitized
        try:
            settings_dir = os.path.dirname(self.settings_file) or CONFIG_DIR
            os.makedirs(settings_dir, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                prefix="settings.",
                suffix=".tmp",
                dir=settings_dir,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(sanitized, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.settings_file)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
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
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect("activate", self.on_activate)

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

        # Register keyboard shortcuts
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.about", ["F1"])

        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)

        # Restore window size from settings
        sm = self.settings_manager
        width = sm.get("window_width", WINDOW_DEFAULT_WIDTH)
        height = sm.get("window_height", WINDOW_DEFAULT_HEIGHT)

        win = KernelManagerWindow(application=app)
        win.set_default_size(width, height)
        if sm.get("window_maximized", False):
            win.maximize()

        win.connect("close-request", self._on_window_close)
        win.present()

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
