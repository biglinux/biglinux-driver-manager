#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Base Section

Shared functionality for UI sections (Kernel, Mesa):
progress handling, dialogs, badges and loading spinner.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from utils.i18n import _


class BaseSection(Gtk.Box):
    """Base class for management sections with shared UI functionality."""

    def __init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=12):
        super().__init__(orientation=orientation, spacing=spacing)
        # No margins — the parent Clamp + content box handles them
        self._loading_box = None

    def _show_loading(self) -> None:
        if self._loading_box is not None:
            return

        self._loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._loading_box.set_valign(Gtk.Align.CENTER)
        self._loading_box.set_halign(Gtk.Align.CENTER)
        self._loading_box.set_vexpand(True)

        spinner = Gtk.Spinner()
        spinner.set_size_request(32, 32)
        spinner.set_tooltip_text(_("Loading..."))
        spinner.update_property([Gtk.AccessibleProperty.LABEL], [_("Loading")])
        spinner.start()
        self._loading_box.append(spinner)

        self._loading_label = Gtk.Label(label=_("Loading..."))
        self._loading_label.add_css_class("dim-label")
        self._loading_box.append(self._loading_label)

        self.append(self._loading_box)
        self._loading_timeout_id = GLib.timeout_add(30000, self._on_loading_timeout)

    def _on_loading_timeout(self) -> bool:
        self._loading_timeout_id = None
        if self._loading_box is not None and self._loading_label is not None:
            self._loading_label.set_text(
                _("Still loading… Check your network connection.")
            )
        return False

    def _hide_loading(self) -> None:
        if hasattr(self, "_loading_timeout_id") and self._loading_timeout_id:
            GLib.source_remove(self._loading_timeout_id)
            self._loading_timeout_id = None
        self._loading_label = None
        if self._loading_box is not None:
            self.remove(self._loading_box)
            self._loading_box = None

    def _show_completion_dialog(
        self,
        title: str,
        message: str,
        status: str = "success",  # noqa: ARG002
    ) -> bool:
        dialog = Adw.AlertDialog()
        dialog.set_heading(title)
        dialog.set_body(message)
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.present(self._get_window())
        return False

    def _get_window(self) -> Gtk.Window:
        widget = self
        while widget:
            if isinstance(widget, Gtk.Window):
                return widget
            widget = widget.get_parent()
        return None

    def set_progress_dialog(self, dialog) -> None:
        self.progress_dialog = dialog

    def _create_badge(self, text: str, style_class: str) -> Gtk.Box:
        """Create a colored pill badge (badge-box + color class)."""
        badge = Gtk.Label.new(text)
        badge.add_css_class("caption")
        badge.add_css_class("badge")

        box = Gtk.Box()
        box.add_css_class(style_class)
        box.add_css_class("badge-box")
        box.set_valign(Gtk.Align.CENTER)
        box.update_property([Gtk.AccessibleProperty.LABEL], [text])
        box.append(badge)
        return box


# Backward compatibility alias
BasePage = BaseSection
