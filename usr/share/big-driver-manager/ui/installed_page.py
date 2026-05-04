#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Installed Drivers Page — consolidated view of all installed drivers.

Groups installed items by category (Video, Wi-Fi, Kernel, etc.) so
the user can see at a glance everything that is currently active.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, Adw

from core.constants import ICON_SIZE_ITEM
from core.driver_database import DriverModule, FirmwareEntry, PeripheralEntry
from core.driver_installer import DriverInstaller
from ui.base_page import BaseSection
from utils.desc_translate import translate_description
from utils.i18n import _

# Category display order and metadata: (id, icon, label)
_INSTALLED_CATEGORIES = [
    ("kernel", "utilities-terminal-symbolic", _("Kernels")),
    ("video", "video-display-symbolic", _("Video / GPU")),
    ("wifi", "network-wireless-symbolic", _("Wi-Fi")),
    ("ethernet", "network-wired-symbolic", _("Ethernet")),
    ("bluetooth", "bluetooth-symbolic", _("Bluetooth")),
    ("dvb", "tv-symbolic", _("DVB / TV")),
    ("sound", "audio-speakers-symbolic", _("Audio")),
    ("webcam", "camera-web-symbolic", _("Webcam")),
    ("touchscreen", "input-touchpad-symbolic", _("Touchscreen")),
    ("printer", "printer-symbolic", _("Printers")),
    ("printer3d", "printer-symbolic", _("3D Printers")),
    ("scanner", "scanner-symbolic", _("Scanners")),
    ("other", "application-x-firmware-symbolic", _("Other")),
]


class InstalledPage(BaseSection):
    """Consolidated page showing every installed driver grouped by category."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._installer = DriverInstaller()
        self._groups: dict[str, list] = {}
        self._row_data: list[tuple[Adw.ActionRow, object]] = []
        self.progress_dialog = None
        self._create_content()
        self._show_loading()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _create_content(self) -> None:
        # Page header — matches category_page header scale (size='large').
        title_lbl = Gtk.Label()
        title_lbl.set_markup(
            f"<span size='large' weight='bold'>"
            f"{GLib.markup_escape_text(_('Installed Drivers'))}</span>"
        )
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_margin_start(4)
        title_lbl.set_margin_bottom(4)
        title_lbl.set_accessible_role(Gtk.AccessibleRole.HEADING)
        self.append(title_lbl)

        desc_lbl = Gtk.Label(
            label=_(
                "All drivers and firmware currently installed on your system, "
                "grouped by category."
            )
        )
        desc_lbl.set_halign(Gtk.Align.START)
        desc_lbl.set_wrap(True)
        desc_lbl.add_css_class("dim-label")
        desc_lbl.set_margin_start(4)
        desc_lbl.set_margin_bottom(12)
        self.append(desc_lbl)

        # Summary label
        self._summary_label = Gtk.Label()
        self._summary_label.set_halign(Gtk.Align.START)
        self._summary_label.add_css_class("dim-label")
        self._summary_label.add_css_class("caption")
        self._summary_label.set_margin_start(4)
        self._summary_label.set_margin_bottom(12)
        self._summary_label.set_visible(False)
        self.append(self._summary_label)

        # Container for per-category Adw.PreferencesGroup blocks.
        self._list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.append(self._list_box)

        # Empty state
        self._empty_status = Adw.StatusPage()
        self._empty_status.set_icon_name("emblem-ok-symbolic")
        self._empty_status.set_title(_("No extra drivers installed"))
        self._empty_status.set_description(
            _("Your system is using only default drivers.")
        )
        self._empty_status.set_valign(Gtk.Align.CENTER)
        self._empty_status.set_vexpand(True)
        self._empty_status.set_visible(False)
        self.append(self._empty_status)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def set_installed_data(
        self,
        *,
        modules: list[DriverModule],
        firmware: list[FirmwareEntry],
        printers: list[PeripheralEntry],
        scanners: list[PeripheralEntry],
        kernels: list[dict],
        running_kernel: str,
        mhwd_video: list,
        mesa_drivers: list[dict],
    ) -> None:
        """Receive all data and rebuild the view with only installed items."""
        self._hide_loading()
        self._groups.clear()
        self._row_data.clear()

        # Kernel group
        kernel_items = []
        for k in kernels:
            kernel_items.append(
                {
                    "name": k["name"],
                    "description": k.get("version", ""),
                    "running": k["name"] == running_kernel,
                    "kind": "kernel",
                }
            )
        if kernel_items:
            self._groups["kernel"] = kernel_items

        # MHWD video drivers (installed)
        mhwd_items = []
        for drv in mhwd_video:
            if getattr(drv, "installed", False):
                mhwd_items.append(
                    {
                        "name": drv.name,
                        "description": getattr(drv, "info", ""),
                        "kind": "mhwd",
                    }
                )
        # Mesa installed drivers
        mesa_items = []
        for d in mesa_drivers:
            if d.get("installed"):
                mesa_items.append(
                    {
                        "name": d.get("id", d.get("name", "")),
                        "description": d.get("name", ""),
                        "active": d.get("active", False),
                        "kind": "mesa",
                    }
                )
        video_items = mhwd_items + mesa_items
        if video_items:
            self._groups["video"] = video_items

        # Modules by category
        for mod in modules:
            if mod.installed:
                cat = mod.category or "other"
                self._groups.setdefault(cat, []).append(mod)

        # Firmware by category
        for fw in firmware:
            if fw.installed:
                cat = fw.category or "other"
                self._groups.setdefault(cat, []).append(fw)

        # Printers
        installed_printers = [p for p in printers if p.installed]
        if installed_printers:
            self._groups.setdefault("printer", []).extend(installed_printers)

        # Scanners
        installed_scanners = [s for s in scanners if s.installed]
        if installed_scanners:
            self._groups.setdefault("scanner", []).extend(installed_scanners)

        self._rebuild_ui()

    # ------------------------------------------------------------------
    # UI rebuild
    # ------------------------------------------------------------------

    def _rebuild_ui(self) -> None:
        """Rebuild the categorized list from self._groups."""
        while True:
            child = self._list_box.get_first_child()
            if child is None:
                break
            self._list_box.remove(child)
        self._row_data.clear()

        total_installed = 0

        for cat_id, icon_name, cat_label in _INSTALLED_CATEGORIES:
            items = self._groups.get(cat_id)
            if not items:
                continue

            total_installed += len(items)
            self._list_box.append(
                self._build_category_group(cat_label, icon_name, items)
            )

        if total_installed == 0:
            self._empty_status.set_visible(True)
            self._list_box.set_visible(False)
            self._summary_label.set_visible(False)
        else:
            self._empty_status.set_visible(False)
            self._list_box.set_visible(True)
            n_cats = len([c for c in _INSTALLED_CATEGORIES if c[0] in self._groups])
            self._summary_label.set_text(
                _("{total} installed drivers across {cats} categories").format(
                    total=total_installed, cats=n_cats
                )
            )
            self._summary_label.set_visible(True)

    def _build_category_group(
        self,
        cat_label: str,
        icon_name: str,
        items: list,
    ) -> Adw.PreferencesGroup:
        """Build an Adw.PreferencesGroup for a single category.

        Matches the visual idiom used by drivers_hub_page (boxed-list of
        Adw.ActionRow): title in the group header, per-row prefix icon and
        optional remove-button suffix.
        """
        group = Adw.PreferencesGroup()
        group.set_title(cat_label)
        # Put the count in the group description slot so it aligns with the
        # standard Adwaita group layout instead of a bespoke header bar.
        group.set_description(_("{n} installed").format(n=len(items)))
        # Left-edge accent for visual parity with kernel/mesa/purpose cards.
        group.add_css_class("installed-group")

        for item in items:
            group.add(self._build_action_row(item, icon_name))

        return group

    def _describe_item(self, item: object) -> tuple[str, str]:
        """Return (display_name, subtitle) for a row, regardless of item kind."""
        if isinstance(item, dict):
            display_name = item["name"].replace("-", " ").title()
            parts: list[str] = []
            kind = item.get("kind", "")
            if kind == "kernel":
                parts.append(
                    _("Running") + " ✓"
                    if item.get("running")
                    else _("Installed") + " ✓"
                )
            elif kind == "mhwd":
                parts.append(_("MHWD driver") + " · " + _("Installed") + " ✓")
            elif kind == "mesa":
                parts.append(
                    _("Active") + " ✓" if item.get("active") else _("Installed") + " ✓"
                )
            if item.get("description"):
                parts.append(item["description"])
            return display_name, " · ".join(parts)

        display_name = item.name.replace("-", " ").title()
        status = _("Installed") + " ✓"
        if getattr(item, "detected", False):
            status = _("Detected") + " · " + status
        desc = getattr(item, "description", "")
        device_name = getattr(item, "detected_device_name", None)
        info = device_name or translate_description(desc.strip())
        parts = [status]
        if info:
            parts.append(info)
        return display_name, " · ".join(parts)

    def _build_action_row(self, item: object, icon_name: str) -> Adw.ActionRow:
        """Build an Adw.ActionRow for one installed item."""
        display_name, subtitle = self._describe_item(item)

        row = Adw.ActionRow()
        row.set_title(GLib.markup_escape_text(display_name))
        if subtitle:
            row.set_subtitle(GLib.markup_escape_text(subtitle))

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(ICON_SIZE_ITEM)
        row.add_prefix(icon)

        raw_name = item["name"] if isinstance(item, dict) else item.name
        row.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["{}: {}".format(raw_name, "installed")],
        )

        # Remove button — skip for kernel/mesa/mhwd (managed via their own pages).
        if not isinstance(item, dict):
            pkg = getattr(item, "package", item.name)
            btn = Gtk.Button(label=_("Remove"))
            btn.add_css_class("destructive-action")
            btn.add_css_class("flat")
            btn.set_valign(Gtk.Align.CENTER)
            btn.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [_("Remove {}").format(pkg)],
            )
            btn.connect("clicked", self._on_remove_clicked, item)
            row.add_suffix(btn)
            self._row_data.append((row, item))

        return row

    # ------------------------------------------------------------------
    # Remove action
    # ------------------------------------------------------------------

    def _on_remove_clicked(
        self,
        _btn: Gtk.Button,
        item: DriverModule | FirmwareEntry | PeripheralEntry,
    ) -> None:
        pkg = getattr(item, "package", item.name)
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Remove Driver"))
        dialog.set_body(_("Remove {}?").format(pkg))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_remove_response, item)
        dialog.present(self._get_window())

    def _on_remove_response(
        self,
        dialog: Adw.AlertDialog,
        response: str,
        item: DriverModule | FirmwareEntry | PeripheralEntry,
    ) -> None:
        if response != "remove":
            return
        pkg = getattr(item, "package", item.name)
        if self.progress_dialog:
            self.progress_dialog.show_progress(
                _("Removing {}").format(pkg),
                _("Please wait..."),
                cancel_callback=self._installer.cancel_operation,
            )
        self._installer.remove_package(
            package=pkg,
            progress_callback=self._on_progress,
            output_callback=self._on_output,
            complete_callback=lambda success: self._on_complete(success, item),
        )

    def _on_progress(self, fraction: float, text: str) -> None:
        if self.progress_dialog:
            self.progress_dialog.update_progress(fraction, text)

    def _on_output(self, line: str) -> None:
        if self.progress_dialog:
            self.progress_dialog.append_terminal_output(line)

    def _remove_item_from_groups(
        self, item: DriverModule | FirmwareEntry | PeripheralEntry
    ) -> None:
        """Remove an item from the grouped view after successful uninstall."""
        empty_categories: list[str] = []
        for category, items in self._groups.items():
            self._groups[category] = [
                existing for existing in items if existing is not item
            ]
            if not self._groups[category]:
                empty_categories.append(category)
        for category in empty_categories:
            self._groups.pop(category, None)

    def _on_complete(
        self,
        success: bool,
        item: DriverModule | FirmwareEntry | PeripheralEntry | None = None,
    ) -> None:
        def _update() -> bool:
            if success:
                if item is not None:
                    self._remove_item_from_groups(item)
                    self._rebuild_ui()
                self._request_refresh()
                window = self.get_root()
                if hasattr(window, "show_reboot_banner"):
                    window.show_reboot_banner()
            if self.progress_dialog:
                if success:
                    self.progress_dialog.show_success(
                        _("Operation completed successfully.")
                    )
                else:
                    self.progress_dialog.show_error(
                        _("Operation failed. Check logs for details.")
                    )
            return False

        GLib.idle_add(_update)
