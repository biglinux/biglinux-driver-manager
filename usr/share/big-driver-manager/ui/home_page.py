#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Home Page (Dashboard)

System health dashboard that answers "Is everything OK?"
without requiring the user to click anything.
"""

from collections.abc import Callable
import os
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from core.constants import ICON_SIZE_HEADER, ICON_SIZE_ITEM
from utils.i18n import _

if TYPE_CHECKING:
    from core.driver_database import DriverModule
    from core.mhwd_manager import MhwdManager
    from ui.progress_dialog import ProgressDialog


class HomePage(Gtk.Box):
    """Dashboard landing page with status banner, summary cards, and alerts."""

    def __init__(self, on_navigate: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.set_margin_top(24)
        self.set_margin_bottom(24)
        self._on_navigate = on_navigate

        self._alerts: list[dict] = []
        self._video_missing_count: int = 0
        self._video_missing_pkgs: list[dict] = []
        self._rec_total_count: int = 0
        self._mhwd_manager = None
        self._progress_dialog = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._build_loading_box()

        # Content container — hidden until detection finishes
        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._content_box.set_visible(False)
        self._content_box.set_margin_start(8)
        self._content_box.set_margin_end(8)
        self.append(self._content_box)

        # Didactic introduction — two visual cards side by side
        self._intro_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self._intro_row.set_homogeneous(True)
        self._content_box.append(self._intro_row)

        # -- Kernel card --
        kernel_card = self._build_intro_card(
            illustration="banner_kernel.svg",
            title=_("What is Kernel?"),
            text=_(
                "The kernel is the heart of your operating system. "
                "It controls your processor, memory, and all hardware. "
                "Most drivers already come built-in with the kernel."
            ),
            css_variant="intro-kernel",
        )
        self._intro_row.append(kernel_card)

        # -- Drivers card --
        drivers_card = self._build_intro_card(
            illustration="banner_drivers.svg",
            title=_("What are Drivers?"),
            text=_(
                "Drivers allow each device — like your video card, "
                "Wi-Fi, or sound — to communicate with the system. "
                "If everything is already working, you probably "
                "don't need to change anything."
            ),
            css_variant="intro-drivers",
        )
        self._intro_row.append(drivers_card)

        # Alert container (populated dynamically)
        self._alert_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._content_box.append(self._alert_box)

        self._build_rec_card()
        self._build_sug_card()

    def _build_loading_box(self) -> None:
        """Build the centered loading spinner shown during detection."""
        self._loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._loading_box.set_valign(Gtk.Align.CENTER)
        self._loading_box.set_vexpand(True)

        self._spinner = Gtk.Spinner()
        self._spinner.set_size_request(48, 48)
        self._spinner.set_halign(Gtk.Align.CENTER)
        self._spinner.set_spinning(True)
        self._loading_box.append(self._spinner)

        self._loading_label = Gtk.Label(label=_("Checking your system…"))
        self._loading_label.add_css_class("title-2")
        self._loading_label.set_halign(Gtk.Align.CENTER)
        self._loading_box.append(self._loading_label)

        self._loading_desc = Gtk.Label(
            label=_("Detecting hardware and installed drivers.")
        )
        self._loading_desc.add_css_class("dim-label")
        self._loading_desc.set_halign(Gtk.Align.CENTER)
        self._loading_box.append(self._loading_desc)

        self.append(self._loading_box)

    def _build_rec_card(self) -> None:
        """Build the video recommendation card (populated after detection)."""
        self._rec_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._rec_card.add_css_class("card")
        self._rec_card.add_css_class("purpose-card-recommend")
        self._rec_card.set_visible(False)
        self._rec_card.set_margin_bottom(8)

        self._rec_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._rec_inner.set_margin_start(16)
        self._rec_inner.set_margin_end(16)
        self._rec_inner.set_margin_top(12)
        self._rec_inner.set_margin_bottom(0)

        rec_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        rec_hdr.set_valign(Gtk.Align.CENTER)
        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rec_icon = Gtk.Image.new_from_file(
            os.path.join(_base, "assets", "illustrations", "icon_recommended.svg")
        )
        rec_icon.set_pixel_size(ICON_SIZE_HEADER)
        rec_hdr.append(rec_icon)
        rec_title = Gtk.Label(label=_("Recommended for your hardware"))
        rec_title.add_css_class("title-4")
        rec_title.set_halign(Gtk.Align.START)
        rec_title.set_hexpand(True)
        rec_title.set_accessible_role(Gtk.AccessibleRole.HEADING)
        rec_hdr.append(rec_title)
        self._rec_inner.append(rec_hdr)

        self._rec_desc = Gtk.Label()
        self._rec_desc.set_wrap(True)
        self._rec_desc.set_xalign(0)
        self._rec_desc.add_css_class("dim-label")
        self._rec_inner.append(self._rec_desc)

        self._rec_rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._rec_inner.append(self._rec_rows_box)

        # "Show all" revealer for installed packages
        self._rec_toggle_btn = Gtk.Button()
        self._rec_toggle_btn.add_css_class("flat")
        self._rec_toggle_btn.set_margin_top(2)
        self._rec_toggle_btn.set_margin_bottom(0)
        self._rec_toggle_btn.set_halign(Gtk.Align.START)
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._rec_toggle_icon = Gtk.Image.new_from_icon_name("pan-end-symbolic")
        self._rec_toggle_lbl = Gtk.Label()
        toggle_box.append(self._rec_toggle_icon)
        toggle_box.append(self._rec_toggle_lbl)
        self._rec_toggle_btn.set_child(toggle_box)
        self._rec_toggle_btn.connect("clicked", self._on_rec_toggle)
        self._rec_toggle_btn.set_visible(False)
        self._rec_inner.append(self._rec_toggle_btn)

        self._rec_revealer = Gtk.Revealer()
        self._rec_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._rec_revealer.set_reveal_child(False)
        self._rec_installed_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=4
        )
        self._rec_installed_box.set_margin_top(8)
        self._rec_revealer.set_child(self._rec_installed_box)
        self._rec_inner.append(self._rec_revealer)

        # Action buttons row
        self._rec_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._rec_btn_box.set_margin_top(8)

        self._rec_details_btn = Gtk.Button()
        self._rec_details_btn.set_label(_("Install recommended"))
        self._rec_details_btn.add_css_class("suggested-action")
        self._rec_details_btn.connect("clicked", self._on_install_recommended)
        self._rec_btn_box.append(self._rec_details_btn)

        self._rec_inner.append(self._rec_btn_box)
        self._rec_card.append(self._rec_inner)
        self._content_box.append(self._rec_card)

    def _build_sug_card(self) -> None:
        """Build the optional driver suggestions card."""
        self._sug_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._sug_card.add_css_class("card")
        self._sug_card.add_css_class("purpose-card-suggest")
        self._sug_card.set_visible(False)

        self._sug_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._sug_inner.set_margin_start(16)
        self._sug_inner.set_margin_end(16)
        self._sug_inner.set_margin_top(16)
        self._sug_inner.set_margin_bottom(16)

        sug_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        sug_hdr.set_valign(Gtk.Align.CENTER)
        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sug_icon = Gtk.Image.new_from_file(
            os.path.join(_base, "assets", "illustrations", "icon_compatible.svg")
        )
        sug_icon.set_pixel_size(ICON_SIZE_HEADER)
        sug_hdr.append(sug_icon)
        sug_title = Gtk.Label(label=_("Compatible drivers available"))
        sug_title.add_css_class("title-4")
        sug_title.set_halign(Gtk.Align.START)
        sug_title.set_hexpand(True)
        sug_title.set_accessible_role(Gtk.AccessibleRole.HEADING)
        sug_hdr.append(sug_title)
        self._sug_inner.append(sug_hdr)

        self._sug_desc = Gtk.Label()
        self._sug_desc.set_wrap(True)
        self._sug_desc.set_xalign(0)
        self._sug_desc.add_css_class("dim-label")
        self._sug_inner.append(self._sug_desc)

        self._sug_rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._sug_inner.append(self._sug_rows_box)

        self._sug_card.append(self._sug_inner)
        self._content_box.append(self._sug_card)

    # ------------------------------------------------------------------
    # Public API — called by Window after hardware detection
    # ------------------------------------------------------------------

    def set_driver_suggestions(self, modules: "list[DriverModule]") -> None:
        """Show compatible but optional driver modules.

        Only shows modules where the device already works (has a kernel driver)
        so they are presented as optional improvements, not critical needs.
        """
        # Clear previous rows
        child = self._sug_rows_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._sug_rows_box.remove(child)
            child = nxt

        # Separate: device works (optional) vs device has no driver (needed)
        optional = [m for m in modules if m.device_has_driver]
        needed = [m for m in modules if not m.device_has_driver]

        # Add needed drivers as warnings in the alert system
        for m in needed:
            device_name = m.detected_device_name or m.name
            cat_page = m.category if m.category else "wifi"
            self.add_alert(
                _("{} — no driver loaded, install {} for this device").format(
                    device_name, m.package
                ),
                alert_type="warning",
                action_label=_("Go to drivers"),
                action_page=cat_page,
            )

        if not optional:
            self._sug_card.set_visible(False)
            return

        self._sug_desc.set_text(
            _(
                "Your devices are already working with the built-in driver, "
                "which is usually the most stable and recommended option. "
                "If you experience issues, you can try a driver detected as "
                "compatible that may improve performance or add features."
            )
        )

        _CAT_ICONS = {
            "wifi": "network-wireless-symbolic",
            "ethernet": "network-wired-symbolic",
            "bluetooth": "bluetooth-symbolic",
            "sound": "audio-card-symbolic",
            "webcam": "camera-video-symbolic",
            "dvb": "video-display-symbolic",
            "touchscreen": "input-touchscreen-symbolic",
        }

        for mod in optional:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.add_css_class("purpose-pkg-row")

            icon_name = _CAT_ICONS.get(mod.category, "application-x-firmware-symbolic")
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(ICON_SIZE_ITEM)
            row.append(icon)

            text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text_box.set_hexpand(True)

            name_lbl = Gtk.Label(label=mod.package)
            name_lbl.set_xalign(0)
            text_box.append(name_lbl)

            details = mod.description or ""
            if mod.detected_device_name:
                details = f"{mod.detected_device_name}"
                if mod.description:
                    details += f" — {mod.description}"
            desc_lbl = Gtk.Label(label=details)
            desc_lbl.set_xalign(0)
            desc_lbl.set_wrap(True)
            desc_lbl.add_css_class("dim-label")
            desc_lbl.add_css_class("caption")
            text_box.append(desc_lbl)
            row.append(text_box)

            install_btn = Gtk.Button(label=_("Install"))
            install_btn.add_css_class("suggested-action")
            install_btn.set_valign(Gtk.Align.CENTER)
            install_btn.set_tooltip_text(_("Install {}").format(mod.package))
            install_btn.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [install_btn.get_tooltip_text()],
            )
            pkg_name = mod.package
            install_btn.connect(
                "clicked",
                lambda _, p=pkg_name, b=install_btn: self._on_install_single(p, b),
            )
            row.append(install_btn)

            self._sug_rows_box.append(row)

        self._sug_card.set_visible(True)

    def set_video_recommendations(
        self,
        missing: list[dict],
        installed: list[dict],
        vendor_names: str,
    ) -> None:
        """Show video driver recommendations on the home page."""
        # Clear previous rows
        child = self._rec_rows_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._rec_rows_box.remove(child)
            child = nxt

        total = len(missing) + len(installed)
        self._video_missing_count = len(missing)
        self._video_missing_pkgs = list(missing)
        self._rec_total_count = total
        if not missing and total == 0:
            self._rec_card.set_visible(False)
            return

        if not missing:
            self._rec_desc.set_text(
                _(
                    "All {} recommended video packages for your {} hardware "
                    "are installed."
                ).format(total, vendor_names)
            )
            self._rec_details_btn.set_visible(False)
            self._rec_btn_box.set_visible(False)
            self._rec_card.set_visible(True)
            return

        self._rec_desc.set_text(
            _("{} of {} recommended packages are not installed.").format(
                len(missing), total
            )
        )

        for pkg in missing:
            self._rec_rows_box.append(self._build_missing_row(pkg))

        if len(missing) > 1:
            self._rec_details_btn.set_label(
                _("Install all {} recommended").format(len(missing))
            )
            self._rec_details_btn.set_visible(True)
            self._rec_btn_box.set_visible(True)
        else:
            self._rec_details_btn.set_visible(False)
            self._rec_btn_box.set_visible(False)

        self._populate_installed_revealer(installed)
        self._rec_card.set_visible(True)

    def _build_missing_row(self, pkg: dict) -> Gtk.Box:
        """Build a single row for a missing recommended package."""
        from ui.mesa_data import _CAT_ROW_ICONS, _ICONS_DIR

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("purpose-pkg-row")
        icon_file = _CAT_ROW_ICONS.get(pkg.get("cat", ""), "icon_row_gpu_detect.svg")
        icon = Gtk.Image.new_from_file(os.path.join(_ICONS_DIR, icon_file))
        icon.set_pixel_size(ICON_SIZE_ITEM)
        row.append(icon)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        text_box.set_hexpand(True)
        name_lbl = Gtk.Label(label=pkg["name"])
        name_lbl.set_xalign(0)
        text_box.append(name_lbl)
        desc_lbl = Gtk.Label(label=pkg.get("short", ""))
        desc_lbl.set_xalign(0)
        desc_lbl.set_wrap(True)
        desc_lbl.add_css_class("dim-label")
        desc_lbl.add_css_class("caption")
        text_box.append(desc_lbl)
        row.append(text_box)

        pkg_btn = Gtk.Button(label=_("Install"))
        pkg_btn.add_css_class("suggested-action")
        pkg_btn.set_valign(Gtk.Align.CENTER)
        pkg_btn.set_tooltip_text(_("Install {}").format(pkg["name"]))
        pkg_btn.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [pkg_btn.get_tooltip_text()],
        )
        pkg_name = pkg["name"]
        pkg_btn.connect(
            "clicked",
            lambda _, p=pkg_name, b=pkg_btn: self._on_install_single(p, b),
        )
        row.append(pkg_btn)
        return row

    def _populate_installed_revealer(self, installed: list[dict]) -> None:
        """Populate the revealer with already-installed packages."""
        child = self._rec_installed_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._rec_installed_box.remove(child)
            child = nxt

        if installed:
            installed_hdr = Gtk.Label(
                label=_("Already installed ({})").format(len(installed))
            )
            installed_hdr.set_xalign(0)
            installed_hdr.add_css_class("dim-label")
            installed_hdr.add_css_class("caption")
            installed_hdr.set_margin_bottom(4)
            self._rec_installed_box.append(installed_hdr)

            for pkg in installed:
                self._rec_installed_box.append(self._build_installed_row(pkg))

            self._rec_toggle_icon.set_from_icon_name("pan-end-symbolic")
            self._rec_toggle_lbl.set_label(_("Show installed packages"))
            self._rec_toggle_btn.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [_("Show installed packages")],
            )
            self._rec_revealer.set_reveal_child(False)
            self._rec_toggle_btn.set_visible(True)
        else:
            self._rec_toggle_btn.set_visible(False)

    def _build_installed_row(self, pkg: dict) -> Gtk.Box:
        """Build a single row for an already-installed recommended package."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("purpose-pkg-row")
        row.set_opacity(0.7)
        chk = Gtk.Image.new_from_icon_name("object-select-symbolic")
        chk.set_pixel_size(16)
        chk.set_opacity(0.6)
        chk.update_property([Gtk.AccessibleProperty.LABEL], [_("Installed")])
        row.append(chk)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        text_box.set_hexpand(True)
        name_lbl = Gtk.Label(label=pkg["name"])
        name_lbl.set_xalign(0)
        text_box.append(name_lbl)
        desc_lbl = Gtk.Label(label=pkg.get("short", ""))
        desc_lbl.set_xalign(0)
        desc_lbl.set_wrap(True)
        desc_lbl.add_css_class("dim-label")
        desc_lbl.add_css_class("caption")
        text_box.append(desc_lbl)
        row.append(text_box)

        badge = Gtk.Label(label=_("Installed"))
        badge.add_css_class("dim-label")
        badge.add_css_class("caption")
        badge.set_valign(Gtk.Align.CENTER)
        row.append(badge)
        return row

    def add_alert(
        self,
        message: str,
        alert_type: str = "warning",
        action_label: str = "",
        action_page: str = "",
    ) -> None:
        """Add an inline alert card."""
        self._alerts.append(
            {
                "message": message,
                "type": alert_type,
                "action_label": action_label,
                "action_page": action_page,
            }
        )
        self._rebuild_alerts()

    def update_banner(self) -> None:
        """Reveal content after detection finishes."""
        self._spinner.set_spinning(False)
        self._loading_box.set_visible(False)
        self._content_box.set_visible(True)

    # ------------------------------------------------------------------
    # Intro card builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_intro_card(
        illustration: str, title: str, text: str, css_variant: str = ""
    ) -> Gtk.Box:
        """Build a compact intro card with inline icon + title."""

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class("card")
        card.add_css_class("intro-card")
        if css_variant:
            card.add_css_class(css_variant)

        # Header: icon left, title centered (same line)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        svg_path = os.path.join(base, "assets", "illustrations", illustration)
        img = Gtk.Image.new_from_file(svg_path)
        img.set_pixel_size(40)

        lbl_title = Gtk.Label(label=title, xalign=0.5)
        lbl_title.add_css_class("title-3")
        lbl_title.set_accessible_role(Gtk.AccessibleRole.HEADING)

        header = Gtk.CenterBox()
        header.set_start_widget(img)
        header.set_center_widget(lbl_title)
        header.set_margin_top(14)
        header.set_margin_start(24)
        header.set_margin_end(24)
        card.append(header)

        # Separator accent
        sep = Gtk.Box()
        sep.set_size_request(40, 2)
        sep.set_halign(Gtk.Align.CENTER)
        sep.set_margin_top(10)
        sep.set_margin_bottom(8)
        sep.add_css_class("intro-sep")
        card.append(sep)

        # Description
        lbl_desc = Gtk.Label(label=text, xalign=0.5, wrap=True)
        lbl_desc.set_justify(Gtk.Justification.CENTER)
        lbl_desc.set_margin_start(16)
        lbl_desc.set_margin_end(16)
        lbl_desc.set_margin_bottom(16)
        lbl_desc.set_opacity(0.65)
        card.append(lbl_desc)

        return card

    # ------------------------------------------------------------------
    # Install handler
    # ------------------------------------------------------------------

    def set_install_handler(
        self, mhwd_manager: "MhwdManager", progress_dialog: "ProgressDialog"
    ) -> None:
        """Set the mhwd manager and progress dialog for installing packages."""
        self._mhwd_manager = mhwd_manager
        self._progress_dialog = progress_dialog

    def _on_rec_toggle(self, _btn: Gtk.Button) -> None:
        """Toggle the installed packages revealer."""
        revealed = self._rec_revealer.get_reveal_child()
        self._rec_revealer.set_reveal_child(not revealed)
        if not revealed:
            self._rec_toggle_icon.set_from_icon_name("pan-down-symbolic")
            self._rec_toggle_lbl.set_label(_("Hide installed packages"))
        else:
            self._rec_toggle_icon.set_from_icon_name("pan-end-symbolic")
            self._rec_toggle_lbl.set_label(_("Show installed packages"))
        _btn.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [self._rec_toggle_lbl.get_label()],
        )

    def _on_install_recommended(self, _btn: Gtk.Button) -> None:
        """Install all recommended packages at once after confirmation."""
        if not self._video_missing_pkgs or not self._mhwd_manager:
            return
        names = [p["name"] for p in self._video_missing_pkgs]
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Install Recommended Packages"))
        dialog.set_body_use_markup(True)
        dialog.set_body(
            _("Install <b>{}</b> packages?\n\n{}").format(
                len(names),
                ", ".join(names),
            )
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("install", _("Install All"))
        dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_rec_install_confirm, names)
        dialog.present(self.get_root())

    def _on_rec_install_confirm(
        self, _dialog: Adw.AlertDialog, response: str, names: list[str]
    ) -> None:
        if response != "install" or not self._progress_dialog:
            return
        self._progress_dialog.show_progress(
            _("Installing {} packages").format(len(names)),
            _("Downloading packages..."),
            cancel_callback=self._mhwd_manager.cancel_operation,
        )
        self._mhwd_manager._run_pacman_command(
            ["pacman", "-S", "--noconfirm", "--needed", *names],
            progress_callback=self._on_progress_update,
            output_callback=self._on_terminal_output,
            complete_callback=lambda success: GLib.idle_add(
                self._on_rec_install_done, success
            ),
            operation_name=_("Installing recommended packages"),
        )

    def _on_progress_update(self, fraction: float, text: str) -> bool:
        if self._progress_dialog:
            self._progress_dialog.update_progress(fraction, text)
        return False

    def _on_terminal_output(self, line: str) -> bool:
        if self._progress_dialog:
            self._progress_dialog.append_terminal_output(line)
        return False

    def _on_rec_install_done(self, success: bool) -> bool:
        if self._progress_dialog:
            if success:
                self._progress_dialog.show_success(
                    _("All recommended packages installed successfully!")
                )
                # Hide the rec card and update banner
                self._video_missing_count = 0
                self._video_missing_pkgs = []
                self._rec_card.set_visible(False)
                self.update_banner()
            else:
                self._progress_dialog.show_error(
                    _(
                        "Package installation failed.\n"
                        "Check the terminal output for details."
                    )
                )
        return False

    def _on_install_single(self, pkg_name: str, btn: Gtk.Button) -> None:
        """Install a single optional driver package."""
        if not self._mhwd_manager:
            return
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Install Driver"))
        dialog.set_body(_("Install {}?").format(pkg_name))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("install", _("Install"))
        dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect(
            "response",
            self._on_single_install_confirm,
            pkg_name,
            btn,
        )
        dialog.present(self.get_root())

    def _on_single_install_confirm(
        self, _dialog: Adw.AlertDialog, response: str, pkg_name: str, btn: Gtk.Button
    ) -> None:
        if response != "install" or not self._progress_dialog:
            return
        self._progress_dialog.show_progress(
            _("Installing {}").format(pkg_name),
            _("Downloading package..."),
            cancel_callback=self._mhwd_manager.cancel_operation,
        )
        self._mhwd_manager._run_pacman_command(
            ["pacman", "-S", "--noconfirm", "--needed", pkg_name],
            progress_callback=self._on_progress_update,
            output_callback=self._on_terminal_output,
            complete_callback=lambda success: GLib.idle_add(
                self._on_single_install_done, success, pkg_name, btn
            ),
            operation_name=_("Installing {}").format(pkg_name),
        )

    def _on_single_install_done(
        self, success: bool, pkg_name: str, btn: Gtk.Button
    ) -> bool:
        if self._progress_dialog:
            if success:
                self._progress_dialog.show_success(
                    _("{} installed successfully!").format(pkg_name)
                )
                btn.set_label(_("Installed"))
                btn.set_sensitive(False)
                btn.remove_css_class("pill")
                btn.add_css_class("success")
            else:
                self._progress_dialog.show_error(
                    _("Installation of {} failed.").format(pkg_name)
                )
        return False

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _rebuild_alerts(self) -> None:
        """Rebuild all alert cards from the alert list."""
        while child := self._alert_box.get_first_child():
            self._alert_box.remove(child)

        for alert in self._alerts:
            card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            card.add_css_class("alert-card")
            card.add_css_class(alert["type"])
            card.set_margin_start(4)
            card.set_margin_end(4)

            icon_name = (
                "dialog-warning-symbolic"
                if alert["type"] == "warning"
                else "dialog-information-symbolic"
            )
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(24)
            icon.set_valign(Gtk.Align.CENTER)
            icon.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [_("Warning") if alert["type"] == "warning" else _("Information")],
            )
            card.append(icon)

            lbl = Gtk.Label(label=alert["message"])
            lbl.set_wrap(True)
            lbl.set_xalign(0)
            lbl.set_hexpand(True)
            card.append(lbl)

            if alert["action_label"] and alert["action_page"]:
                btn = Gtk.Button(label=alert["action_label"])
                btn.add_css_class("suggested-action")
                btn.add_css_class("pill")
                btn.set_valign(Gtk.Align.CENTER)
                btn.update_property(
                    [Gtk.AccessibleProperty.LABEL],
                    [alert["action_label"]],
                )
                page = alert["action_page"]
                btn.connect("clicked", lambda _, p=page: self._on_navigate(p))
                card.append(btn)

            self._alert_box.append(card)
