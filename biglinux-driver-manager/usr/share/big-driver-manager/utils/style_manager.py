"""Style Manager — Singleton for CSS loading and hot-reloading."""

from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

from core.logging_config import get_logger

_logger = get_logger("StyleManager")


class StyleManager:
    """Singleton CSS provider manager."""

    _instance: StyleManager | None = None
    _provider: Gtk.CssProvider | None = None

    def __new__(cls) -> StyleManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_default(cls) -> StyleManager:
        return cls()

    def load_styles(self) -> bool:
        """Load the application CSS from the assets directory."""
        if self._provider is not None:
            return True

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        css_path = os.path.join(base_dir, "assets", "css", "style.css")

        provider = Gtk.CssProvider()
        try:
            provider.load_from_path(css_path)
        except Exception as exc:
            _logger.warning("Failed to load CSS from %s: %s", css_path, exc)
            return False

        display = Gdk.Display.get_default()
        if display is None:
            _logger.warning("No display available for CSS provider")
            return False

        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self._provider = provider
        _logger.debug("Loaded CSS from %s", css_path)
        return True

    def reload_styles(self) -> bool:
        """Unload and re-load styles (useful during development)."""
        self.unload_styles()
        return self.load_styles()

    def unload_styles(self) -> None:
        """Remove the CSS provider from the display."""
        if self._provider is None:
            return

        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.remove_provider_for_display(display, self._provider)

        self._provider = None
