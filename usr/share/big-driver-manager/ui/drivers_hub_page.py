#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Drivers Hub — central page for all driver categories.

Shows a status banner, recommended drivers (detected but not installed),
and a category list using boxed-list with human-readable counts.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from core.driver_database import DriverModule, FirmwareEntry, PeripheralEntry
from core.driver_installer import DriverInstaller
from utils.i18n import _

if TYPE_CHECKING:
    from ui.progress_dialog import ProgressDialog


# Lazy-initialized category definitions
_DRIVER_CATEGORIES: list[tuple[str, str, str]] = []


def _init_driver_categories() -> None:
    if _DRIVER_CATEGORIES:
        return
    _DRIVER_CATEGORIES.extend(
        [
            ("video", "video-display-symbolic", _("Video / GPU")),
            ("wifi", "network-wireless-symbolic", _("Wi-Fi")),
            ("ethernet", "network-wired-symbolic", _("Ethernet")),
            ("bluetooth", "bluetooth-symbolic", _("Bluetooth")),
            ("dvb", "video-television-symbolic", _("DVB / TV")),
            ("sound", "audio-speakers-symbolic", _("Audio")),
            ("webcam", "camera-web-symbolic", _("Webcam")),
            ("touchscreen", "input-touchpad-symbolic", _("Touchscreen")),
            ("printer", "printer-symbolic", _("Printers")),
            ("printer3d", "printer-symbolic", _("3D Printers")),
            ("scanner", "document-scan-symbolic", _("Scanners")),
            ("other", "application-x-firmware-symbolic", _("Other")),
        ]
    )


# Icon lookup for recommended items
_CATEGORY_ICONS: dict[str, str] = {}


def _get_category_icon(category_id: str) -> str:
    if not _CATEGORY_ICONS:
        _init_driver_categories()
        for cid, icon, _title in _DRIVER_CATEGORIES:
            _CATEGORY_ICONS[cid] = icon
    return _CATEGORY_ICONS.get(category_id, "application-x-firmware-symbolic")


class DriversHubPage(Gtk.Box):
    """Hub listing driver categories with status banner and recommended drivers."""

    def __init__(self, on_navigate: Callable[[str], None]) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._on_navigate = on_navigate
        self._show_all = False
        self._installer = DriverInstaller()
        self.progress_dialog = None
        self._category_data: dict[str, list] = {}
        self._category_rows: dict[str, Adw.ActionRow] = {}
        _init_driver_categories()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.set_margin_top(16)
        self.set_margin_bottom(24)
        self.set_margin_start(24)
        self.set_margin_end(24)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

        # Status banner
        self._status_banner = Adw.StatusPage()
        self._status_banner.set_icon_name("emblem-ok-symbolic")
        self._status_banner.set_title(_("All drivers are installed"))
        self._status_banner.set_description(
            _("All necessary drivers are already installed on your system.")
        )
        self._status_banner.add_css_class("status-banner")
        self._status_banner.add_css_class("ok")
        self._status_banner.set_visible(False)
        content.append(self._status_banner)

        # Recommended section (detected but not installed)
        self._recommended_label = Gtk.Label()
        self._recommended_label.set_markup(
            f"<b>{GLib.markup_escape_text(_('Recommended'))}</b>"
        )
        self._recommended_label.set_halign(Gtk.Align.START)
        self._recommended_label.set_margin_start(4)
        self._recommended_label.set_visible(False)
        self._recommended_label.set_accessible_role(Gtk.AccessibleRole.HEADING)
        content.append(self._recommended_label)

        self._recommended_list = Gtk.ListBox()
        self._recommended_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._recommended_list.add_css_class("boxed-list")
        self._recommended_list.set_visible(False)
        content.append(self._recommended_list)

        # Categories heading
        self._categories_label = Gtk.Label()
        self._categories_label.set_markup(
            f"<b>{GLib.markup_escape_text(_('Categories'))}</b>"
        )
        self._categories_label.set_halign(Gtk.Align.START)
        self._categories_label.set_margin_start(4)
        self._categories_label.set_visible(False)
        self._categories_label.set_accessible_role(Gtk.AccessibleRole.HEADING)
        content.append(self._categories_label)

        # Category list
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.connect("row-activated", self._on_row_activated)

        for cat_id, icon_name, cat_title in _DRIVER_CATEGORIES:
            row = self._build_category_row(cat_id, icon_name, cat_title)
            self._list_box.append(row)
            self._category_rows[cat_id] = row

        content.append(self._list_box)

        # Loading spinner
        self._spinner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._spinner_box.set_valign(Gtk.Align.CENTER)
        self._spinner_box.set_halign(Gtk.Align.CENTER)
        self._spinner_box.set_margin_top(32)
        spinner = Gtk.Spinner()
        spinner.set_size_request(32, 32)
        spinner.start()
        spinner.update_property(
            [Gtk.AccessibleProperty.LABEL], [_("Detecting hardware")]
        )
        self._spinner_box.append(spinner)
        spin_lbl = Gtk.Label(label=_("Detecting hardware..."))
        spin_lbl.add_css_class("dim-label")
        self._spinner_box.append(spin_lbl)
        content.append(self._spinner_box)

        self.append(content)

    def _build_category_row(
        self, cat_id: str, icon_name: str, title: str
    ) -> Adw.ActionRow:
        row = Adw.ActionRow()
        row.set_title(title)
        row.set_activatable(True)
        row.set_name(cat_id)
        row.update_property([Gtk.AccessibleProperty.LABEL], [title])

        prefix_icon = Gtk.Image.new_from_icon_name(icon_name)
        prefix_icon.set_pixel_size(24)
        row.add_prefix(prefix_icon)

        # Human-readable count label as suffix
        count_lbl = Gtk.Label()
        count_lbl.add_css_class("dim-label")
        count_lbl.add_css_class("caption")
        count_lbl.set_visible(False)
        row.add_suffix(count_lbl)

        arrow = Gtk.Image.new_from_icon_name("go-next-symbolic")
        row.add_suffix(arrow)

        row._count_lbl = count_lbl
        return row

    # ------------------------------------------------------------------
    # Data population (called from window.py after detection)
    # ------------------------------------------------------------------

    def set_category_items(self, category_id: str, items: list) -> None:
        """Register items for a category and refresh the UI."""
        self._category_data[category_id] = items
        self._refresh_ui()
        self._spinner_box.set_visible(False)

    def set_progress_dialog(self, dialog: "ProgressDialog | None") -> None:
        self.progress_dialog = dialog

    def _refresh_ui(self) -> None:
        """Rebuild recommended section and update category rows."""
        self._rebuild_recommended()
        self._update_categories()
        self._update_status_banner()

    def _rebuild_recommended(self) -> None:
        """Build boxed-list of detected-but-not-installed drivers."""
        # Clear
        while True:
            child = self._recommended_list.get_first_child()
            if child is None:
                break
            self._recommended_list.remove(child)

        recommended = []
        for cat_id, items in self._category_data.items():
            for item in items:
                detected = getattr(item, "detected", False) or getattr(
                    item, "compatible", False
                )
                installed = getattr(item, "installed", False)
                if detected and not installed:
                    recommended.append((cat_id, item))

        has_recommended = len(recommended) > 0
        self._recommended_label.set_visible(has_recommended)
        self._recommended_list.set_visible(has_recommended)

        for cat_id, item in recommended:
            row = Adw.ActionRow()
            display_name = getattr(item, "name", str(item))
            row.set_title(display_name.replace("-", " ").title())

            desc = getattr(item, "description", "")
            device_name = getattr(item, "detected_device_name", None)
            subtitle = device_name or desc
            if subtitle:
                row.set_subtitle(GLib.markup_escape_text(subtitle.strip()))

            icon = Gtk.Image.new_from_icon_name(_get_category_icon(cat_id))
            icon.set_pixel_size(24)
            row.add_prefix(icon)

            btn = Gtk.Button(label=_("Install"))
            btn.add_css_class("suggested-action")
            btn.set_valign(Gtk.Align.CENTER)
            btn.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [_("Install {}").format(display_name)],
            )
            btn.connect("clicked", self._on_install_clicked, item)
            row.add_suffix(btn)

            self._recommended_list.append(row)

    def _update_categories(self) -> None:
        """Update category row subtitles and visibility."""
        has_any = False
        for cat_id, row in self._category_rows.items():
            items = self._category_data.get(cat_id, [])
            total = len(items)
            detected = sum(
                1
                for i in items
                if getattr(i, "detected", False) or getattr(i, "compatible", False)
            )
            installed = sum(1 for i in items if getattr(i, "installed", False))

            if self._show_all:
                visible = total > 0
            else:
                visible = detected > 0 or installed > 0

            row.set_visible(visible)
            if visible:
                has_any = True

            # Human-readable count: "2 drivers · 1 installed"
            if total > 0:
                parts = []
                if total == 1:
                    parts.append(_("1 driver"))
                else:
                    parts.append(_("{n} drivers").format(n=total))
                if installed > 0:
                    if installed == 1:
                        parts.append(_("1 installed"))
                    else:
                        parts.append(_("{n} installed").format(n=installed))
                row._count_lbl.set_text(" · ".join(parts))
                row._count_lbl.set_visible(True)
                row.set_subtitle(" · ".join(parts))
            else:
                row._count_lbl.set_visible(False)
                row.set_subtitle("")

        self._list_box.set_visible(has_any)
        self._categories_label.set_visible(has_any)

    def _update_status_banner(self) -> None:
        """Show status banner based on whether there are pending recommendations."""
        if self._spinner_box.get_visible():
            self._status_banner.set_visible(False)
            return

        needs_install = 0
        for items in self._category_data.values():
            for item in items:
                detected = getattr(item, "detected", False) or getattr(
                    item, "compatible", False
                )
                installed = getattr(item, "installed", False)
                if detected and not installed:
                    needs_install += 1

        if needs_install > 0:
            self._status_banner.set_icon_name("dialog-warning-symbolic")
            self._status_banner.set_title(
                _("{n} drivers available to install").format(n=needs_install)
            )
            self._status_banner.set_description(
                _("Install recommended drivers for better hardware support.")
            )
            self._status_banner.remove_css_class("ok")
            self._status_banner.add_css_class("warning")
        else:
            self._status_banner.set_icon_name("emblem-ok-symbolic")
            self._status_banner.set_title(_("All drivers are installed"))
            self._status_banner.set_description(
                _("All necessary drivers are already installed on your system.")
            )
            self._status_banner.remove_css_class("warning")
            self._status_banner.add_css_class("ok")

        self._status_banner.set_visible(bool(self._category_data))

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def set_show_all(self, show_all: bool) -> None:
        """Update the show-all mode from external toggle."""
        self._show_all = show_all
        self._update_categories()

    def _on_row_activated(self, _listbox: Gtk.ListBox, row: Adw.ActionRow) -> None:
        cat_id = row.get_name()
        if cat_id:
            self._on_navigate(cat_id)

    # ------------------------------------------------------------------
    # Install recommended drivers
    # ------------------------------------------------------------------

    def _on_install_clicked(
        self,
        _btn: Gtk.Button,
        item: DriverModule | FirmwareEntry | PeripheralEntry,
    ) -> None:
        pkg = getattr(item, "package", getattr(item, "name", str(item)))
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Install Driver"))
        dialog.set_body(_("Install {}?").format(pkg))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("install", _("Install"))
        dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_install_response, item)
        dialog.present(self._get_window())

    def _on_install_response(
        self,
        _dialog: Adw.AlertDialog,
        response: str,
        item: DriverModule | FirmwareEntry | PeripheralEntry,
    ) -> None:
        if response != "install":
            return
        pkg = getattr(item, "package", getattr(item, "name", str(item)))
        if self.progress_dialog:
            self.progress_dialog.show_progress(
                _("Installing {}").format(pkg), _("Please wait...")
            )
        self._installer.install_package(
            package=pkg,
            progress_callback=self._on_progress,
            output_callback=self._on_output,
            complete_callback=self._on_complete,
        )

    def _on_progress(self, fraction: float, text: str) -> None:
        if self.progress_dialog:
            self.progress_dialog.update_progress(fraction, text)

    def _on_output(self, line: str) -> None:
        if self.progress_dialog:
            self.progress_dialog.append_terminal_output(line)

    def _on_complete(self, success: bool) -> None:
        def _update() -> bool:
            if success:
                self._refresh_installed_status()
                window = self.get_root()
                if hasattr(window, "show_reboot_banner"):
                    window.show_reboot_banner()
            if self.progress_dialog:
                if success:
                    self.progress_dialog.show_success(
                        _("Driver installed successfully.")
                    )
                else:
                    self.progress_dialog.show_error(
                        _("Installation failed. Check logs for details.")
                    )
            return False

        GLib.idle_add(_update)

    def _refresh_installed_status(self) -> None:
        """Re-check installed state and rebuild recommended list."""
        from core.hardware_detect import check_installed_packages

        for items in self._category_data.values():
            packages = [getattr(i, "package", getattr(i, "name", "")) for i in items]
            installed_map = check_installed_packages(packages)
            for item in items:
                pkg = getattr(item, "package", getattr(item, "name", ""))
                item.installed = installed_map.get(pkg, False)
        self._refresh_ui()

    def _get_window(self) -> Gtk.Window | None:
        widget = self
        while widget:
            if isinstance(widget, Gtk.Window):
                return widget
            widget = widget.get_parent()
        return None
