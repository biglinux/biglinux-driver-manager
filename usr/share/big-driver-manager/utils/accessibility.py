"""Accessibility helpers for GTK runtime behavior."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


def animations_enabled() -> bool:
    """Return whether GTK animations are enabled for the current session.

    Safe to call from headless/test contexts where ``Gtk.Settings`` may be a
    stub without ``get_default``. In any ambiguity we assume animations are
    enabled (matches GTK default when a display is available).
    """
    get_default = getattr(Gtk.Settings, "get_default", None)
    if not callable(get_default):
        return True

    try:
        settings = get_default()
    except Exception:
        return True

    if settings is None:
        return True

    try:
        return bool(settings.get_property("gtk-enable-animations"))
    except (AttributeError, TypeError):
        return True
