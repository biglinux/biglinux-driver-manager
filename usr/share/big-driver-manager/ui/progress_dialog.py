#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Progress Dialog

Modal Adw.Dialog with:
  - Step indicator ("Step 2 of 3")
  - Human-readable status messages
  - Terminal output hidden by default (expandable)
  - Post-completion action buttons
"""

import re

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, Adw

from utils.i18n import _

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


class ProgressDialog(Adw.Dialog):
    """Modal progress dialog for package operations."""

    def __init__(self, parent_window: Gtk.Widget) -> None:
        super().__init__()
        self._parent_window = parent_window
        self._is_complete = False
        self._success = False
        self._cancel_callback = None
        self._current_step = 0
        self._total_steps = 0

        self.set_title("")
        self.set_content_width(550)
        self.set_content_height(-1)
        self.set_can_close(False)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)
        toolbar_view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(16)
        content.set_margin_bottom(24)

        # Icon + title row
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header_row.set_halign(Gtk.Align.CENTER)

        self._icon_stack = Gtk.Stack()
        self._icon_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._icon_stack.set_transition_duration(300)

        self._spinner = Gtk.Spinner()
        self._spinner.set_size_request(32, 32)
        self._icon_stack.add_named(self._spinner, "spinner")

        ok_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        ok_icon.set_pixel_size(32)
        ok_icon.add_css_class("success-icon")
        self._icon_stack.add_named(ok_icon, "success")

        err_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        err_icon.set_pixel_size(32)
        err_icon.add_css_class("error-icon")
        self._icon_stack.add_named(err_icon, "error")

        header_row.append(self._icon_stack)

        self._title_label = Gtk.Label()
        self._title_label.add_css_class("title-2")
        self._title_label.set_halign(Gtk.Align.START)
        header_row.append(self._title_label)
        content.append(header_row)

        # Step indicator (e.g. "Step 2 of 3: Installing packages")
        self._step_label = Gtk.Label()
        self._step_label.add_css_class("dim-label")
        self._step_label.set_halign(Gtk.Align.CENTER)
        self._step_label.set_visible(False)
        content.append(self._step_label)

        # Status message (ALERT role for screen reader announcements)
        self._status_label = Gtk.Label()
        self._status_label.add_css_class("dim-label")
        self._status_label.set_halign(Gtk.Align.CENTER)
        self._status_label.set_wrap(True)
        self._status_label.set_max_width_chars(50)
        self._status_label.set_accessible_role(Gtk.AccessibleRole.ALERT)
        content.append(self._status_label)

        # Progress bar
        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_show_text(True)
        self._progress_bar.add_css_class("osd")
        content.append(self._progress_bar)

        # Terminal (hidden by default inside expander)
        self._terminal_expander = Gtk.Expander()
        self._terminal_expander.set_label(_("Technical details"))
        self._terminal_expander.set_expanded(False)

        term_scroll = Gtk.ScrolledWindow()
        term_scroll.set_min_content_height(200)
        term_scroll.set_max_content_height(280)
        term_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self._terminal_view = Gtk.TextView()
        self._terminal_view.set_editable(False)
        self._terminal_view.set_cursor_visible(False)
        self._terminal_view.set_monospace(True)
        self._terminal_view.add_css_class("terminal")
        self._terminal_view.update_property(
            [Gtk.AccessibleProperty.LABEL], [_("Terminal output")]
        )
        self._terminal_buffer = self._terminal_view.get_buffer()
        self._create_terminal_tags()

        term_scroll.set_child(self._terminal_view)
        self._terminal_expander.set_child(term_scroll)
        content.append(self._terminal_expander)

        # Button box
        self._button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._button_box.set_halign(Gtk.Align.CENTER)
        self._button_box.set_margin_top(8)

        self._cancel_btn = Gtk.Button(label=_("Cancel"))
        self._cancel_btn.add_css_class("destructive-action")
        self._cancel_btn.add_css_class("pill")
        self._cancel_btn.connect("clicked", self._on_cancel_clicked)
        self._button_box.append(self._cancel_btn)

        self._close_btn = Gtk.Button(label=_("Close"))
        self._close_btn.add_css_class("suggested-action")
        self._close_btn.add_css_class("pill")
        self._close_btn.connect("clicked", lambda _: self.hide_dialog())
        self._close_btn.set_visible(False)
        self._button_box.append(self._close_btn)

        content.append(self._button_box)
        toolbar_view.set_content(content)
        self.set_child(toolbar_view)

    def _create_terminal_tags(self) -> None:
        from gi.repository import Gdk

        tag_colors = {
            "error": "@error_color",
            "success": "@success_color",
            "warning": "@warning_color",
            "info": "@accent_color",
            "dim": "@borders",
        }
        fallbacks = {
            "error": "#c01c28",
            "success": "#26a269",
            "warning": "#e5a50a",
            "info": "#1c71d8",
            "dim": "#888888",
        }
        for tag_name, named_color in tag_colors.items():
            rgba = Gdk.RGBA()
            if rgba.parse(named_color):
                self._terminal_buffer.create_tag(tag_name, foreground_rgba=rgba)
            else:
                self._terminal_buffer.create_tag(
                    tag_name, foreground=fallbacks.get(tag_name, "#888888")
                )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_progress(
        self,
        title: str,
        initial_message: str = "",
        cancel_callback=None,
    ) -> None:
        """Present the dialog in progress state."""
        self._is_complete = False
        self._success = False
        self._cancel_callback = cancel_callback
        self._current_step = 0
        self._total_steps = 0
        self.set_can_close(False)

        self._title_label.set_text(title)
        self._status_label.set_text(initial_message or _("Please wait..."))
        self._step_label.set_visible(False)
        self._progress_bar.set_fraction(0.0)
        self._progress_bar.set_text("0%")
        self._terminal_buffer.set_text("", 0)
        self._terminal_expander.set_expanded(False)

        self._cancel_btn.set_visible(True)
        self._close_btn.set_visible(False)

        self._icon_stack.set_visible_child_name("spinner")
        self._spinner.start()

        self.present(self._parent_window)

    def set_steps(self, current: int, total: int, description: str = "") -> None:
        """Update step indicator (e.g. 'Step 2 of 3: Installing packages')."""
        self._current_step = current
        self._total_steps = total

        def _update() -> bool:
            if description:
                text = _("Step {} of {}: {}").format(current, total, description)
            else:
                text = _("Step {} of {}").format(current, total)
            self._step_label.set_text(text)
            self._step_label.set_visible(True)
            return False

        GLib.idle_add(_update)

    def update_progress(self, fraction: float, text: str | None = None) -> None:
        """Update the progress bar (0.0–1.0)."""
        GLib.idle_add(self._update_progress_idle, fraction, text)

    def _update_progress_idle(self, fraction: float, text: str | None) -> bool:
        fraction = max(0.0, min(1.0, fraction))
        self._progress_bar.set_fraction(fraction)
        self._progress_bar.set_text(f"{int(fraction * 100)}%")
        if text:
            self._status_label.set_text(text)
        return False

    def append_terminal_output(self, text: str) -> None:
        """Append text to the terminal output area."""
        if not text:
            return
        text = _ANSI_RE.sub("", text)
        if not text.endswith("\n"):
            text += "\n"
        GLib.idle_add(self._append_terminal_idle, text)

    # Terminal coloring heuristics
    _PREFIX_TAGS: list[tuple[str, str]] = [
        ("❌", "error"),
        ("✅", "success"),
        ("⚠️", "warning"),
    ]
    _KEYWORD_TAGS: list[tuple[str, str]] = [
        ("error", "error"),
        ("failed", "error"),
        ("successfully", "success"),
        ("success", "success"),
        ("warning", "warning"),
    ]
    _STARTSWITH_TAGS: list[tuple[tuple[str, ...], str]] = [
        (
            (
                "Starting",
                "Installing",
                "Removing",
                "Checking",
                "Applying",
                "resolving",
                "looking",
            ),
            "info",
        ),
        (("Package", "Total", "::"), "dim"),
    ]

    def _get_line_tag(self, line: str) -> str | None:
        stripped = line.strip()
        for prefix, tag in self._PREFIX_TAGS:
            if stripped.startswith(prefix):
                return tag
        stripped_lower = stripped.lower()
        for keyword, tag in self._KEYWORD_TAGS:
            if keyword in stripped_lower:
                return tag
        for prefixes, tag in self._STARTSWITH_TAGS:
            if stripped.startswith(prefixes):
                return tag
        return None

    _TAG_TEXT_PREFIX: dict[str, str] = {
        "error": "[ERROR] ",
        "success": "[OK] ",
        "warning": "[WARNING] ",
    }

    def _append_terminal_idle(self, text: str) -> bool:
        try:
            # Limit terminal buffer to prevent unbounded memory growth
            line_count = self._terminal_buffer.get_line_count()
            if line_count > 2000:
                start = self._terminal_buffer.get_start_iter()
                trim_end = self._terminal_buffer.get_iter_at_line(line_count - 1500)
                self._terminal_buffer.delete(start, trim_end)

            end_iter = self._terminal_buffer.get_end_iter()
            tag_name = self._get_line_tag(text)
            if tag_name:
                tag = self._terminal_buffer.get_tag_table().lookup(tag_name)
                prefix = self._TAG_TEXT_PREFIX.get(tag_name, "")
                display = (
                    prefix + text
                    if prefix and not text.lstrip().startswith(("❌", "✅", "⚠️", "["))
                    else text
                )
                self._terminal_buffer.insert_with_tags(end_iter, display, tag)
            else:
                self._terminal_buffer.insert(end_iter, text)

            vadj = self._terminal_view.get_vadjustment()
            if vadj:
                vadj.set_value(vadj.get_upper() - vadj.get_page_size())
        except Exception:
            pass
        return False

    def show_success(self, message: str | None = None) -> None:
        if message is None:
            message = _("Operation completed successfully!")
        GLib.idle_add(self._show_result_idle, True, message)

    def show_error(self, message: str | None = None) -> None:
        if message is None:
            message = _("Operation failed. Check terminal output for details.")
        GLib.idle_add(self._show_result_idle, False, message)

    def complete(
        self,
        success: bool,
        title: str | None = None,
        message: str | None = None,
    ) -> None:
        """Convenience: mark operation finished."""
        if title:
            GLib.idle_add(self._title_label.set_text, title)
        if success:
            self.show_success(message)
        else:
            self.show_error(message)

    def _show_result_idle(self, success: bool, message: str) -> bool:
        self._is_complete = True
        self._success = success
        self._spinner.stop()
        self.set_can_close(True)

        if success:
            self._icon_stack.set_visible_child_name("success")
            self._progress_bar.set_fraction(1.0)
            self._progress_bar.set_text(_("Completed!"))
        else:
            self._icon_stack.set_visible_child_name("error")
            self._progress_bar.set_text(_("Failed"))
            # Auto-expand terminal on error so user can see what went wrong
            self._terminal_expander.set_expanded(True)

        self._status_label.set_text(message)
        self._step_label.set_visible(False)

        # Announce for screen readers
        self.update_property([Gtk.AccessibleProperty.LABEL], [message])

        self._cancel_btn.set_visible(False)
        self._close_btn.set_visible(True)
        return False

    def hide_dialog(self) -> None:
        """Close the dialog."""
        self._spinner.stop()
        self.set_can_close(True)
        self.close()

    def is_visible(self) -> bool:
        """Check if dialog is currently presented."""
        return self.get_visible()

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def _on_cancel_clicked(self, _button) -> None:
        if self._cancel_callback:
            try:
                self._cancel_callback()
            except Exception:
                pass

        self._spinner.stop()
        self._is_complete = True
        self._success = False
        self.set_can_close(True)
        self._icon_stack.set_visible_child_name("error")
        self._status_label.set_text(_("Operation cancelled by user."))
        self._progress_bar.set_text(_("Cancelled"))
        self._step_label.set_visible(False)
        self._cancel_btn.set_visible(False)
        self._close_btn.set_visible(True)
