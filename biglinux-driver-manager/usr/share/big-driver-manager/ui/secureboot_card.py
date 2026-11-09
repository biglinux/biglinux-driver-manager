#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Secure Boot card (kernel page)

Secure Boot with the BigCommunity key. Enabling installs big-secureboot,
disabling removes it (core/secureboot.py). The card says where the machine is and what
is left to do; it is hidden where big-secureboot does not exist (outside
BigCommunity) or the machine did not boot in UEFI mode.
"""

import functools
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from core.package_manager import PackageManager, fetch_repo_package_set
from core.secureboot import (
    ACTIVE,
    MOK_PASSWORD,
    NO_CA,
    NO_SPACE,
    OFF,
    PENDING,
    UNAVAILABLE,
    SecureBootManager,
)
from ui.base_page import PackageOperationMixin
from utils.i18n import _
from utils.ui_constants import ICON_SIZE_HEADER


def confirm_steps() -> str:
    """The blue screen, as the user will meet it after restarting."""
    return _(
        "Restart. On the blue screen, press a key, choose “Enroll MOK”, "
        "“Continue” and “Yes”, type the password {} and choose “Reboot”."
    ).format(MOK_PASSWORD)


def state_text(state: str) -> str:
    """What the card says in each state."""
    if state == OFF:
        return _(
            "Start with Secure Boot using the BigCommunity key: the computer "
            "then only starts boot loaders and kernels with a trusted "
            "signature."
        )
    if state == NO_CA:
        return _(
            "This computer's firmware does not accept boot loaders signed by "
            "Microsoft for other systems, which Secure Boot with the "
            "BigCommunity key needs. Turn on “Allow Microsoft 3rd Party UEFI "
            "CA” in the firmware settings, then open this page again."
        )
    if state == NO_SPACE:
        return _(
            "The firmware does not have enough free space to add the "
            "BigCommunity key. Old crash reports it keeps usually fill it."
        )
    if state == PENDING:
        return "\n".join(
            [
                _("Two steps are left, each done only once:"),
                "1. " + confirm_steps(),
                "2. "
                + _(
                    "Turn on Secure Boot in the computer's firmware settings "
                    "(UEFI), if it is off."
                ),
            ]
        )
    if state == ACTIVE:
        return _(
            "Secure Boot is on with the BigCommunity key. Only signed kernel "
            "modules load."
        )
    return ""


class SecureBootCard(PackageOperationMixin, Gtk.Box):
    """The Secure Boot card of the kernel page."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add_css_class("kernel-installed-card")
        self.set_margin_bottom(20)
        self.set_visible(False)
        self.manager = SecureBootManager(
            PackageManager.get_default(), fetch_repo_package_set
        )
        self._state = UNAVAILABLE

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for side in ("start", "end"):
            getattr(inner, f"set_margin_{side}")(16)
        inner.set_margin_top(14)
        inner.set_margin_bottom(14)
        self.append(inner)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name("security-high-symbolic")
        icon.set_pixel_size(ICON_SIZE_HEADER)
        icon.set_valign(Gtk.Align.CENTER)
        header.append(icon)
        title = Gtk.Label()
        title.set_markup("<b>" + _("Secure Boot") + "</b>")
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        title.add_css_class("kernel-group-header")
        title.set_accessible_role(Gtk.AccessibleRole.HEADING)
        header.append(title)

        self._button = Gtk.Button()
        self._button.add_css_class("pill")
        self._button.set_valign(Gtk.Align.CENTER)
        self._button.connect("clicked", self._on_button_clicked)
        header.append(self._button)
        inner.append(header)

        self._text = Gtk.Label()
        self._text.set_halign(Gtk.Align.START)
        self._text.set_xalign(0)
        self._text.set_wrap(True)
        self._text.set_selectable(True)
        self._text.add_css_class("dim-label")
        inner.append(self._text)

    def set_progress_dialog(self, dialog) -> None:
        self.progress_dialog = dialog

    # -- state ---------------------------------------------------------

    def refresh(self) -> None:
        """Read the state off the main loop (pacman -Slq can take a while)."""
        threading.Thread(target=self._read_state, daemon=True).start()

    def _read_state(self) -> None:
        try:
            state = self.manager.current_state()
        except Exception:  # never let the card break the kernel page
            state = UNAVAILABLE
        GLib.idle_add(self._show_state, state)

    def _show_state(self, state: str) -> bool:
        self._state = state
        self.set_visible(state != UNAVAILABLE)
        self._text.set_text(state_text(state))
        enabling = state == OFF
        # Enabling would not work here: nothing to click until it is fixed.
        self._button.set_visible(state not in (NO_CA, NO_SPACE))
        self._button.set_label(_("Enable") if enabling else _("Disable"))
        self._button.remove_css_class(
            "destructive-action" if enabling else "suggested-action"
        )
        self._button.add_css_class(
            "suggested-action" if enabling else "destructive-action"
        )
        return False

    # -- actions -------------------------------------------------------

    def _on_button_clicked(self, _button: Gtk.Button) -> None:
        dialog = Adw.AlertDialog()
        if self._state == OFF:
            dialog.set_heading(_("Enable Secure Boot?"))
            dialog.set_body(
                _(
                    "This installs the boot loaders signed with the "
                    "BigCommunity key. Your boot menu stays as it is."
                )
                + "\n\n"
                + _(
                    "With Secure Boot on, the system only loads signed kernel "
                    "modules: the BigCommunity ones are signed, modules built "
                    "locally with DKMS are not. Hibernation is not available "
                    "either."
                )
                + "\n\n"
                + confirm_steps()
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("go", _("Enable"))
            dialog.set_response_appearance("go", Adw.ResponseAppearance.SUGGESTED)
        else:
            dialog.set_heading(_("Disable Secure Boot?"))
            dialog.set_body(
                _(
                    "This removes the BigCommunity boot loaders.\n\n"
                    "If Secure Boot is on, turn it off in the firmware "
                    "settings before restarting, or the computer will not "
                    "start."
                )
            )
            dialog.add_response("cancel", _("Cancel"))
            dialog.add_response("go", _("Disable"))
            dialog.set_response_appearance("go", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_response)
        dialog.present(self.get_root())

    def _on_response(self, _dialog: Adw.AlertDialog, response: str) -> None:
        if response != "go":
            return
        enabling = self._state == OFF
        title = _("Enabling Secure Boot") if enabling else _("Disabling Secure Boot")
        action = self.manager.enable if enabling else self.manager.disable
        self._button.set_sensitive(False)
        self._start_package_operation(
            self.manager,
            title,
            functools.partial(action, title),
            functools.partial(self._on_done, enabling),
        )

    def _on_done(self, enabling: bool, success: bool, hint: str | None) -> None:
        self._button.set_sensitive(True)
        PackageManager.get_default().invalidate_cache()
        self._report_operation_result(
            success,
            _("Secure Boot is set up. Restart to confirm the key.")
            if enabling
            else _("Secure Boot setup removed."),
            _(
                "Could not change the Secure Boot setup. Check the terminal "
                "output for details."
            ),
            hint,
        )
        if success and enabling:
            window = self.get_root()
            if hasattr(window, "show_reboot_banner"):
                window.show_reboot_banner()
        self.refresh()
