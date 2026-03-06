#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generic Category Page — reusable section for any driver/peripheral category.

Uses Gtk.Box rows with .purpose-pkg-row for each driver, with search and status text.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, GLib, Adw

from collections.abc import Sequence

from core.constants import ICON_SIZE_ITEM
from core.driver_database import DriverModule, FirmwareEntry, PeripheralEntry
from core.driver_installer import DriverInstaller
from ui.base_page import BaseSection
from utils.desc_translate import translate_description
from utils.i18n import _
from utils.tooltip_helper import TooltipHelper, build_tooltip_body

# Threshold above which items are grouped by brand instead of flat list.
_GROUP_THRESHOLD = 20

# Map package-name prefixes to human brand names.
# Longer prefixes checked first (sorted by -len at init time).
_BRAND_PREFIXES: list[tuple[str, str]] = []


def _init_brand_prefixes() -> None:
    if _BRAND_PREFIXES:
        return
    _raw: dict[str, str] = {
        "brother": "Brother",
        "brscan": "Brother",
        "epson": "Epson",
        "iscan": "Epson",
        "canon": "Canon",
        "cnijfilter": "Canon",
        "scangearmp": "Canon",
        "hp": "HP",
        "hplip": "HP",
        "samsung": "Samsung",
        "pantum": "Pantum",
        "kyocera": "Kyocera",
        "ricoh": "Ricoh",
        "xerox": "Xerox",
        "lexmark": "Lexmark",
        "konica": "Konica Minolta",
        "dell": "Dell",
        "oki": "OKI",
        "cura": "Ultimaker",
        "libsane": "SANE",
    }
    _BRAND_PREFIXES.extend(sorted(_raw.items(), key=lambda x: -len(x[0])))


def _detect_brand(name: str) -> str:
    """Return brand name for a package name, or 'Other'."""
    _init_brand_prefixes()
    low = name.lower()
    for prefix, brand in _BRAND_PREFIXES:
        if low.startswith(prefix):
            return brand
    return _("Other")


class CategorySection(BaseSection):
    """A generic driver/peripheral category section with boxed-list layout."""

    def __init__(
        self,
        title: str,
        description: str,
        icon_name: str,
        category_id: str,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._title = title
        self._description = description
        self._icon_name = icon_name
        self._category_id = category_id
        self._installer = DriverInstaller()
        self._items: list[DriverModule | FirmwareEntry | PeripheralEntry] = []
        self._show_all = False
        self._is_grouped = False
        self._row_data: list[
            tuple[Gtk.Box, DriverModule | FirmwareEntry | PeripheralEntry]
        ] = []
        self._brand_expanders: list[
            tuple[
                Gtk.Expander, str, list[DriverModule | FirmwareEntry | PeripheralEntry]
            ]
        ] = []
        self.progress_dialog = None
        self._search_timeout_id: int = 0
        self._tooltip = TooltipHelper()
        self._create_content()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _create_content(self) -> None:
        # Title heading
        title_lbl = Gtk.Label()
        title_lbl.set_markup(
            f"<span size='large' weight='bold'>"
            f"{GLib.markup_escape_text(self._title)}</span>"
        )
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_margin_start(4)
        title_lbl.set_margin_bottom(4)
        title_lbl.set_accessible_role(Gtk.AccessibleRole.HEADING)
        self.append(title_lbl)

        desc_lbl = Gtk.Label(label=self._description)
        desc_lbl.set_halign(Gtk.Align.START)
        desc_lbl.set_wrap(True)
        desc_lbl.add_css_class("dim-label")
        desc_lbl.set_margin_start(4)
        desc_lbl.set_margin_bottom(12)
        self.append(desc_lbl)

        # Search entry at the top
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text(_("Search drivers..."))
        self._search_entry.set_margin_bottom(8)
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.update_property(
            [Gtk.AccessibleProperty.LABEL], [_("Search drivers")]
        )
        self._search_entry.set_visible(False)
        self.append(self._search_entry)

        # Status label
        self._status_label = Gtk.Label()
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.add_css_class("dim-label")
        self._status_label.add_css_class("caption")
        self._status_label.set_margin_start(4)
        self._status_label.set_margin_bottom(8)
        self._status_label.set_visible(False)
        self.append(self._status_label)

        # Network scan banner (hidden by default)
        self._net_scan_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._net_scan_box.set_halign(Gtk.Align.CENTER)
        self._net_scan_box.set_margin_top(4)
        self._net_scan_box.set_margin_bottom(8)
        self._net_scan_box.set_visible(False)
        net_spinner = Gtk.Spinner()
        net_spinner.set_spinning(True)
        net_spinner.set_size_request(16, 16)
        self._net_scan_box.append(net_spinner)
        net_label = Gtk.Label(label=_("Searching for printers on the network…"))
        net_label.add_css_class("dim-label")
        net_label.add_css_class("caption")
        self._net_scan_box.append(net_label)
        self.append(self._net_scan_box)

        # Driver list
        self._list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.append(self._list_box)

        # "Show all" footer area (visible when items are hidden)
        self._show_all_footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._show_all_footer.set_halign(Gtk.Align.CENTER)
        self._show_all_footer.set_margin_top(24)
        self._show_all_footer.set_margin_bottom(8)
        self._show_all_footer.set_visible(False)

        footer_info = Gtk.Label(
            label=_(
                "No more automatically detected compatible drivers in this category."
            )
        )
        footer_info.add_css_class("dim-label")
        footer_info.set_wrap(True)
        footer_info.set_justify(Gtk.Justification.CENTER)
        self._show_all_footer.append(footer_info)

        footer_btn = Gtk.Button(label=_("Show drivers without detected compatibility"))
        footer_btn.add_css_class("pill")
        footer_btn.add_css_class("suggested-action")
        footer_btn.set_halign(Gtk.Align.CENTER)
        footer_btn.connect("clicked", self._on_show_all_request)
        self._show_all_footer.append(footer_btn)

        self.append(self._show_all_footer)

        # Empty state
        self._empty_status = Adw.StatusPage()
        self._empty_status.set_icon_name("dialog-information-symbolic")
        self._empty_status.set_title(_("No drivers needed for this category"))
        self._empty_status.set_description(
            _(
                "No drivers in this category were automatically detected "
                "as compatible with your hardware."
            )
        )
        self._empty_status.set_valign(Gtk.Align.CENTER)
        self._empty_status.set_vexpand(True)
        self._empty_status.set_visible(False)

        show_all_btn = Gtk.Button(
            label=_("Show drivers without detected compatibility")
        )
        show_all_btn.add_css_class("suggested-action")
        show_all_btn.add_css_class("pill")
        show_all_btn.set_halign(Gtk.Align.CENTER)
        show_all_btn.connect("clicked", self._on_show_all_request)
        self._empty_status.set_child(show_all_btn)

        self.append(self._empty_status)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def set_items(
        self, items: Sequence[DriverModule | FirmwareEntry | PeripheralEntry]
    ) -> None:
        """Set the items to display. Called after detection completes."""
        self._items = list(items)
        self._rebuild_list()

    def show_network_scan(self) -> None:
        """Show the 'searching network printers' banner."""
        self._net_scan_box.set_visible(True)

    def hide_network_scan(self) -> None:
        """Hide the network scan banner."""
        self._net_scan_box.set_visible(False)

    def set_show_all(self, show_all: bool) -> None:
        """Toggle between showing all items or only detected/installed ones."""
        if self._show_all == show_all:
            return
        self._show_all = show_all
        self._apply_visibility()

    def _on_show_all_request(self, _btn: Gtk.Button) -> None:
        """Handle click on 'Show all' button inside the empty state."""
        root = self.get_root()
        if hasattr(root, "_show_all_switch"):
            root._show_all_switch.set_active(True)

    def show_error(self, message: str) -> None:
        """Display an error message in place of the items list."""
        self._hide_loading()
        self._empty_status.set_icon_name("dialog-error-symbolic")
        self._empty_status.set_title(_("Detection Error"))
        self._empty_status.set_description(message)
        self._empty_status.set_visible(True)
        self._list_box.set_visible(False)
        self._status_label.set_visible(False)
        self._search_entry.set_visible(False)

    def _rebuild_list(self) -> None:
        """Rebuild the entire list from self._items."""
        # Clear
        while True:
            child = self._list_box.get_first_child()
            if child is None:
                break
            self._list_box.remove(child)
        self._row_data.clear()
        self._brand_expanders.clear()
        self._is_grouped = False

        if not self._items:
            self._empty_status.set_icon_name("dialog-information-symbolic")
            self._empty_status.set_title(_("No drivers needed for this category"))
            self._empty_status.set_description(
                _(
                    "No drivers in this category were detected as necessary "
                    "for your hardware."
                )
            )
            self._empty_status.set_visible(True)
            self._list_box.set_visible(False)
            self._status_label.set_visible(False)
            self._search_entry.set_visible(False)
            return

        # Use brand grouping only when detection is meaningful
        if len(self._items) > _GROUP_THRESHOLD:
            brands = {_detect_brand(i.name) for i in self._items}
            named_brands = {b for b in brands if b != _("Other")}
            if len(named_brands) >= 2:
                self._rebuild_list_grouped()
                return

        self._rebuild_list_flat()

    def _rebuild_list_flat(self) -> None:
        """Flat list for small categories (WiFi, Bluetooth, etc.)."""

        def sort_key(
            item: DriverModule | FirmwareEntry | PeripheralEntry,
        ) -> tuple[bool, bool, str]:
            detected = getattr(item, "detected", False)
            installed = getattr(item, "installed", False)
            return (not detected, installed, item.name.lower())

        sorted_items = sorted(self._items, key=sort_key)

        for item in sorted_items:
            row = self._build_row(item)
            self._list_box.append(row)
            self._row_data.append((row, item))

        self._list_box.set_visible(True)
        self._search_entry.set_visible(len(sorted_items) > 5)
        self._apply_visibility()

    def _rebuild_list_grouped(self) -> None:
        """Brand-grouped list for large categories (printers, scanners)."""
        self._is_grouped = True

        groups: dict[str, list[DriverModule | FirmwareEntry | PeripheralEntry]] = {}
        for item in self._items:
            brand = _detect_brand(item.name)
            groups.setdefault(brand, []).append(item)

        def brand_sort_key(
            pair: tuple[str, list[DriverModule | FirmwareEntry | PeripheralEntry]],
        ) -> tuple[bool, bool, int, str]:
            brand, items = pair
            has_detected = any(getattr(i, "detected", False) for i in items)
            has_installed = any(getattr(i, "installed", False) for i in items)
            return (not has_detected, not has_installed, -len(items), brand.lower())

        sorted_groups = sorted(groups.items(), key=brand_sort_key)

        for brand, items in sorted_groups:
            items.sort(
                key=lambda i: (
                    not getattr(i, "detected", False),
                    getattr(i, "installed", False),
                    i.name.lower(),
                )
            )

            detected = sum(1 for i in items if getattr(i, "detected", False))
            installed = sum(1 for i in items if getattr(i, "installed", False))

            # Brand header with counts
            count_parts = []
            n = len(items)
            count_parts.append(_("1 driver") if n == 1 else _("{} drivers").format(n))
            if detected:
                count_parts.append(_("{} detected").format(detected))
            if installed:
                count_parts.append(_("{} installed").format(installed))

            header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            icon = Gtk.Image.new_from_icon_name(self._icon_name)
            icon.set_pixel_size(ICON_SIZE_ITEM)
            header_box.append(icon)
            title_lbl = Gtk.Label()
            title_lbl.set_markup(
                f"<b>{GLib.markup_escape_text(brand)}</b>"
                f"  <small>{GLib.markup_escape_text(' · '.join(count_parts))}</small>"
            )
            title_lbl.set_halign(Gtk.Align.START)
            header_box.append(title_lbl)

            items_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            for item in items:
                child = self._build_row(item)
                items_box.append(child)
                self._row_data.append((child, item))

            expander = Gtk.Expander()
            expander.set_label_widget(header_box)
            expander.set_child(items_box)
            expander.set_expanded(detected > 0 or installed > 0)
            expander.set_margin_bottom(4)

            self._list_box.append(expander)
            self._brand_expanders.append((expander, brand, items))

        self._list_box.set_visible(True)
        self._search_entry.set_visible(True)
        self._apply_visibility()

    def _build_row(
        self, item: DriverModule | FirmwareEntry | PeripheralEntry
    ) -> Gtk.Box:
        """Build a Gtk.Box row for a single driver/firmware/peripheral."""
        detected = getattr(item, "detected", False)
        installed = getattr(item, "installed", False)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_valign(Gtk.Align.CENTER)
        row.add_css_class("purpose-pkg-row")

        # Category icon
        icon = Gtk.Image.new_from_icon_name(self._icon_name)
        icon.set_pixel_size(ICON_SIZE_ITEM)
        row.append(icon)

        # Text column
        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_col.set_hexpand(True)

        display_name = item.name.replace("-", " ").title()
        title_lbl = Gtk.Label(label=display_name)
        title_lbl.set_xalign(0)
        title_lbl.add_css_class("heading")
        text_col.append(title_lbl)

        # Subtitle: status + description
        status_parts: list[str] = []
        if detected:
            status_parts.append(_("Detected") + " ✓")
        if installed:
            status_parts.append(_("Installed") + " ✓")
        elif detected:
            status_parts.append(_("Not installed"))

        desc = getattr(item, "description", "")
        device_name = getattr(item, "detected_device_name", None)
        info = device_name or translate_description(desc.strip())

        subtitle_parts: list[str] = []
        if status_parts:
            subtitle_parts.append(" · ".join(status_parts))
        if info:
            subtitle_parts.append(info)
        if subtitle_parts:
            sub_lbl = Gtk.Label(label="\n".join(subtitle_parts))
            sub_lbl.set_xalign(0)
            sub_lbl.set_wrap(True)
            sub_lbl.add_css_class("dim-label")
            sub_lbl.add_css_class("caption")
            text_col.append(sub_lbl)

        row.append(text_col)

        # Action button
        if installed:
            btn = Gtk.Button(label=_("Remove"))
            btn.add_css_class("destructive-action")
            btn.connect("clicked", self._on_remove_clicked, item)
        else:
            btn = Gtk.Button(label=_("Install"))
            btn.add_css_class("suggested-action")
            btn.connect("clicked", self._on_install_clicked, item)

        btn.set_valign(Gtk.Align.CENTER)
        btn.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [
                _("Install {}").format(item.name)
                if not installed
                else _("Remove {}").format(item.name)
            ],
        )
        row.append(btn)

        row.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [f"{item.name}: {'installed' if installed else 'not installed'}"],
        )

        # Rich tooltip on hover
        display_name = item.name.replace("-", " ").title()
        tooltip_body = build_tooltip_body(item, self._category_id)
        self._tooltip.add_tooltip(row, display_name, tooltip_body, self._icon_name)

        return row

    def _apply_visibility(self) -> None:
        """Show/hide rows based on _show_all flag."""
        visible_count = 0
        installed_count = 0
        detected_count = 0

        if self._is_grouped:
            for expander, _brand, items in self._brand_expanders:
                has_relevant = any(
                    getattr(i, "detected", False) or getattr(i, "installed", False)
                    for i in items
                )
                show = self._show_all or has_relevant
                expander.set_visible(show)
                expander.set_expanded(has_relevant)
                if show:
                    # Restore individual row visibility
                    for row, item in self._row_data:
                        if item in items:
                            row.set_visible(True)
                    for i in items:
                        if getattr(i, "installed", False):
                            installed_count += 1
                        if getattr(i, "detected", False):
                            detected_count += 1
                    visible_count += len(items)
        else:
            # Flat mode: toggle individual rows
            for row, item in self._row_data:
                detected = getattr(item, "detected", False)
                installed = getattr(item, "installed", False)
                show = self._show_all or detected or installed
                row.set_visible(show)
                if show:
                    visible_count += 1
                    if installed:
                        installed_count += 1
                    if detected:
                        detected_count += 1

        if visible_count == 0:
            self._empty_status.set_visible(True)
            self._list_box.set_visible(False)
            self._status_label.set_visible(False)
            self._show_all_footer.set_visible(False)
        else:
            self._empty_status.set_visible(False)
            self._list_box.set_visible(True)
            self._status_label.set_text(
                _(
                    "{total} drivers · {detected} detected · {installed} installed"
                ).format(
                    total=visible_count,
                    detected=detected_count,
                    installed=installed_count,
                )
            )
            self._status_label.set_visible(True)

            # Show footer "Show all" button when not all items are visible
            total_items = (
                len(self._row_data)
                if not self._is_grouped
                else sum(len(items) for _, _, items in self._brand_expanders)
            )
            has_hidden = not self._show_all and visible_count < total_items
            self._show_all_footer.set_visible(has_hidden)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        if self._search_timeout_id:
            GLib.source_remove(self._search_timeout_id)
        self._search_timeout_id = GLib.timeout_add(
            300, self._apply_search_filter, entry
        )

    def _apply_search_filter(self, entry: Gtk.SearchEntry) -> bool:
        self._search_timeout_id = 0
        query = entry.get_text().strip().lower()
        if not query:
            self._apply_visibility()
            return False

        def _searchable(item) -> str:
            parts = [
                item.name,
                getattr(item, "description", ""),
                getattr(item, "package", ""),
                getattr(item, "detected_device_name", "") or "",
            ]
            return " ".join(parts).lower()

        if self._is_grouped:
            for expander, brand_name, items in self._brand_expanders:
                brand_match = query in brand_name.lower()
                group_visible = False
                for row, item in self._row_data:
                    if item not in items:
                        continue
                    match = brand_match or query in _searchable(item)
                    row.set_visible(match)
                    if match:
                        group_visible = True
                expander.set_visible(group_visible)
                if group_visible:
                    expander.set_expanded(True)
        else:
            for row, item in self._row_data:
                row.set_visible(query in _searchable(item))
        return False

    # ------------------------------------------------------------------
    # Install / Remove
    # ------------------------------------------------------------------

    def _on_install_clicked(
        self,
        _btn: Gtk.Button,
        item: DriverModule | FirmwareEntry | PeripheralEntry,
    ) -> None:
        pkg = getattr(item, "package", item.name)
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
        dialog: Adw.AlertDialog,
        response: str,
        item: DriverModule | FirmwareEntry | PeripheralEntry,
    ) -> None:
        if response != "install":
            return
        pkg = getattr(item, "package", item.name)
        if self.progress_dialog:
            self.progress_dialog.show_progress(
                _("Installing {}").format(pkg),
                _("Please wait..."),
            )
        self._installer.install_package(
            package=pkg,
            progress_callback=self._on_progress,
            output_callback=self._on_output,
            complete_callback=self._on_complete,
        )

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
            )
        self._installer.remove_package(
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
                        _("Operation completed successfully.")
                    )
                else:
                    self.progress_dialog.show_error(
                        _("Operation failed. Check logs for details.")
                    )
            return False

        GLib.idle_add(_update)

    def _refresh_installed_status(self) -> None:
        """Re-check installed state for all items and rebuild list."""
        from core.hardware_detect import check_installed_packages

        packages = [getattr(i, "package", i.name) for i in self._items]
        installed_map = check_installed_packages(packages)
        for item in self._items:
            pkg = getattr(item, "package", item.name)
            item.installed = installed_map.get(pkg, False)
        self._rebuild_list()
