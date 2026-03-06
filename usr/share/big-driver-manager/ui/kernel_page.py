#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Kernel Management Page

List-based layout with:
  - Running kernel card at top
  - Obsolete kernel alerts
  - Installed kernels in boxed-list
  - Available kernels grouped by type (LTS / Standard / Performance)
"""

import gi
import os
import re

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from core.constants import ICON_SIZE_HEADER, ICON_SIZE_ITEM
from core.kernel_manager import KernelManager
from ui.base_page import BaseSection
from ui.kernel_card_builder import KernelTypeInfo, classify_kernel, version_sort_key
from utils.i18n import _

_ICONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "illustrations",
)

# Row-level icons per kernel type (simpler versions of the header icons).
_ROW_ICONS = {
    "lts": "icon_kernel_row_lts.svg",
    "standard": "icon_kernel_row_standard.svg",
    "xanmod": "icon_kernel_row_xanmod.svg",
    "rt": "icon_kernel_row_rt.svg",
}


class KernelSection(BaseSection):
    """Kernel management page — list-based, grouped by type."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.kernel_manager = KernelManager()
        self._running_kernel_package = ""
        self._all_kernels: list = []
        self._obsolete_kernels: list[dict] = []
        self.progress_dialog = None
        self._selected_for_removal: set[str] = set()
        self._build_page()
        self._show_loading()

    def set_preloaded_data(
        self,
        kernels: list,
        running_pkg: str,
        obsolete: list[dict],
    ) -> None:
        """Receive pre-computed data from window (skip redundant queries)."""
        self._update_kernel_list(kernels, running_pkg, obsolete)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_page(self) -> None:
        # Running kernel card (prominent)
        self._running_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._running_box.add_css_class("kernel-running-card")
        self._running_box.set_margin_bottom(20)
        self._running_box.set_visible(False)
        self.append(self._running_box)

        # Obsolete alerts container
        self._obsolete_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._obsolete_box.set_margin_bottom(20)
        self._obsolete_box.set_visible(False)
        self.append(self._obsolete_box)

        # Installed kernels section — wrapped in styled card
        self._installed_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._installed_card.add_css_class("kernel-installed-card")
        self._installed_card.set_margin_bottom(20)
        self._installed_card.set_visible(False)
        self.append(self._installed_card)

        installed_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        installed_inner.set_margin_start(16)
        installed_inner.set_margin_end(16)
        installed_inner.set_margin_top(14)
        installed_inner.set_margin_bottom(14)
        self._installed_card.append(installed_inner)

        installed_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        installed_icon = Gtk.Image.new_from_file(
            os.path.join(_ICONS_DIR, "icon_kernel_installed.svg")
        )
        installed_icon.set_pixel_size(ICON_SIZE_HEADER)
        installed_icon.set_valign(Gtk.Align.CENTER)
        installed_hdr.append(installed_icon)

        self._installed_label = Gtk.Label()
        self._installed_label.set_markup("<b>" + _("Installed Kernels") + "</b>")
        self._installed_label.set_halign(Gtk.Align.START)
        self._installed_label.add_css_class("kernel-group-header")
        self._installed_label.set_accessible_role(Gtk.AccessibleRole.HEADING)
        installed_hdr.append(self._installed_label)
        installed_inner.append(installed_hdr)

        self._installed_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._installed_list.set_visible(False)
        installed_inner.append(self._installed_list)

        # Bulk remove button (for obsolete kernels)
        self._bulk_remove_btn = Gtk.Button(label=_("Remove all obsolete kernels"))
        self._bulk_remove_btn.add_css_class("destructive-action")
        self._bulk_remove_btn.add_css_class("pill")
        self._bulk_remove_btn.set_halign(Gtk.Align.CENTER)
        self._bulk_remove_btn.set_margin_top(4)
        self._bulk_remove_btn.set_margin_bottom(10)
        self._bulk_remove_btn.set_visible(False)
        self._bulk_remove_btn.connect("clicked", self._on_bulk_remove_obsolete)
        self.append(self._bulk_remove_btn)

        # Available kernels — grouped
        self._available_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=20
        )
        self._available_container.set_visible(False)
        self.append(self._available_container)

        # Keep kernel_listbox reference for compatibility (tests)
        self.kernel_listbox = self._installed_list

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_kernels_async(self) -> None:
        import threading

        self.kernel_manager.package_manager.invalidate_cache()
        threading.Thread(target=self._load_kernels_thread, daemon=True).start()

    def _load_kernels_thread(self) -> None:
        try:
            kernels = self.kernel_manager.get_available_kernels()
            running_pkg = self.kernel_manager.get_running_kernel_package()
            # Compute obsolete from already-fetched data (avoid duplicate query)
            installed = self.kernel_manager.get_installed_kernels()
            available_names = {k["name"] for k in kernels}
            obsolete = [
                {**k, "obsolete": True}
                for k in installed
                if k["name"] != running_pkg and k["name"] not in available_names
            ]
            GLib.idle_add(self._update_kernel_list, kernels, running_pkg, obsolete)
        except Exception as e:
            GLib.idle_add(
                self._show_completion_dialog,
                _("Error"),
                str(e),
                "error",
            )

    def _update_kernel_list(
        self,
        kernels: list[dict],
        running_kernel_package: str = "",
        obsolete: list[dict] | None = None,
    ) -> bool:
        self._hide_loading()
        self._running_kernel_package = running_kernel_package
        self._all_kernels = kernels
        self._obsolete_kernels = obsolete or []
        self._rebuild_ui()
        return False

    def _load_kernels(self) -> None:
        kernels = self.kernel_manager.get_available_kernels()
        running_pkg = self.kernel_manager.get_running_kernel_package()
        self._update_kernel_list(kernels, running_pkg)

    # ------------------------------------------------------------------
    # UI rebuild
    # ------------------------------------------------------------------

    def _rebuild_ui(self) -> None:
        self._selected_for_removal.clear()

        installed = sorted(
            [k for k in self._all_kernels if k.get("installed")],
            key=version_sort_key,
            reverse=True,
        )
        available = sorted(
            [k for k in self._all_kernels if not k.get("installed")],
            key=version_sort_key,
            reverse=True,
        )

        running = None
        other_installed = []
        for k in installed:
            if k["name"] == self._running_kernel_package:
                running = k
            else:
                other_installed.append(k)

        # Running kernel card
        self._build_running_card(running)

        # Obsolete alerts
        self._build_obsolete_alerts()

        # Installed list (excluding running)
        self._clear_box(self._installed_list)
        has_installed = len(other_installed) > 0
        self._installed_card.set_visible(has_installed)
        self._installed_list.set_visible(has_installed)

        num_removable = len(other_installed)
        for k in other_installed:
            row = self._build_installed_row(k, num_removable)
            self._installed_list.append(row)

        # Available kernels — grouped
        self._build_available_groups(available)

    def _build_running_card(self, running: dict | None) -> None:
        """Build the prominent running kernel card with gradient style."""
        self._clear_box(self._running_box)
        if not running:
            self._running_box.set_visible(False)
            return

        self._running_box.set_visible(True)
        ktype = classify_kernel(running)

        # Inner padding
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        inner.set_margin_start(20)
        inner.set_margin_end(20)
        inner.set_margin_top(18)
        inner.set_margin_bottom(18)

        # Title row with icon and in-use pill
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icon = Gtk.Image.new_from_file(
            os.path.join(_ICONS_DIR, "icon_kernel_running.svg")
        )
        icon.set_pixel_size(ICON_SIZE_HEADER)
        icon.set_valign(Gtk.Align.CENTER)
        title_row.append(icon)

        title = Gtk.Label()
        title.set_markup("<b>" + _("Kernel in use") + "</b>")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-4")
        title_row.append(title)

        # In-use pill badge
        in_use = Gtk.Label(label=_("In Use"))
        in_use.add_css_class("in-use-pill")
        in_use.set_halign(Gtk.Align.END)
        in_use.set_valign(Gtk.Align.CENTER)
        in_use.set_hexpand(True)

        # Info button before the pill
        mm = self._kernel_major_minor(running)
        if mm:
            # Spacer to push info+pill to the right
            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            title_row.append(spacer)
            in_use.set_hexpand(False)
            title_row.append(self._build_info_button(running, mm))

        title_row.append(in_use)

        inner.append(title_row)

        # Kernel name and version
        name_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name_row.set_margin_top(8)
        name_lbl = Gtk.Label()
        name_lbl.set_markup(
            f"<big><b>{GLib.markup_escape_text(running['name'])}</b></big>  "
            f"<small>{GLib.markup_escape_text(running['version'])}</small>"
        )
        name_lbl.set_halign(Gtk.Align.START)
        name_row.append(name_lbl)

        inner.append(name_row)

        # Type description
        desc = Gtk.Label(label=ktype.type_desc)
        desc.set_halign(Gtk.Align.START)
        desc.set_wrap(True)
        desc.add_css_class("dim-label")
        inner.append(desc)

        # Full description
        full = Gtk.Label(label=ktype.full_desc)
        full.set_halign(Gtk.Align.START)
        full.set_wrap(True)
        full.add_css_class("dim-label")
        full.add_css_class("caption")
        full.set_margin_top(4)
        inner.append(full)

        self._running_box.append(inner)

    def _build_obsolete_alerts(self) -> None:
        """Build alert cards for obsolete kernels."""
        self._clear_box(self._obsolete_box)
        obsolete = self._obsolete_kernels
        has_obsolete = len(obsolete) > 0
        self._obsolete_box.set_visible(has_obsolete)
        self._bulk_remove_btn.set_visible(len(obsolete) > 1)

        if not has_obsolete:
            return

        # Section heading
        heading = Gtk.Label()
        heading.set_markup("<b>" + _("Obsolete Kernels — Removal Recommended") + "</b>")
        heading.set_halign(Gtk.Align.START)
        heading.set_margin_start(4)
        heading.set_accessible_role(Gtk.AccessibleRole.HEADING)
        self._obsolete_box.append(heading)

        for k in obsolete:
            card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            card.add_css_class("alert-card")
            card.add_css_class("warning")

            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            icon.set_pixel_size(24)
            icon.set_valign(Gtk.Align.CENTER)
            icon.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [_("Warning")],
            )
            card.append(icon)

            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info.set_hexpand(True)
            name_lbl = Gtk.Label()
            name_lbl.set_markup(
                f"<b>{GLib.markup_escape_text(k['name'])}</b>  <small>{GLib.markup_escape_text(k['version'])}</small>"
            )
            name_lbl.set_halign(Gtk.Align.START)
            info.append(name_lbl)

            desc = Gtk.Label(label=_("No longer receives security updates"))
            desc.set_halign(Gtk.Align.START)
            desc.add_css_class("dim-label")
            desc.add_css_class("caption")
            info.append(desc)
            card.append(info)

            btn = Gtk.Button(label=_("Remove"))
            btn.add_css_class("destructive-action")
            btn.set_valign(Gtk.Align.CENTER)
            btn.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [_("Remove kernel {}").format(k["name"])],
            )
            btn.connect("clicked", self._on_remove_clicked, k)
            card.append(btn)

            self._obsolete_box.append(card)

    def _build_installed_row(self, kernel: dict, total_removable: int) -> Gtk.Box:
        """Build a card-style row for an installed (non-running) kernel."""
        ktype = classify_kernel(kernel)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_valign(Gtk.Align.CENTER)
        row.add_css_class("purpose-pkg-row")

        # Type icon (xanmod takes priority over lts)
        row.append(self._row_type_icon(ktype))

        # Text column
        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_col.set_hexpand(True)

        # Title row: kernel name + badges
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_lbl = Gtk.Label(label=kernel["name"])
        title_lbl.set_xalign(0)
        title_row.append(title_lbl)
        for badge_text, badge_style in ktype.badge_entries:
            title_row.append(self._create_badge(badge_text, badge_style))
        text_col.append(title_row)

        subtitle_parts = [kernel["version"]]
        if ktype.type_desc:
            subtitle_parts.append(ktype.type_desc)
        sub_lbl = Gtk.Label(label=" · ".join(subtitle_parts))
        sub_lbl.set_xalign(0)
        sub_lbl.set_wrap(True)
        sub_lbl.add_css_class("dim-label")
        sub_lbl.add_css_class("caption")
        text_col.append(sub_lbl)

        row.append(text_col)

        # Info button for kernelnewbies (before action button)
        mm = self._kernel_major_minor(kernel)
        if mm:
            row.append(self._build_info_button(kernel, mm))

        if total_removable <= 1:
            safe_lbl = Gtk.Label(label=_("Last backup"))
            safe_lbl.add_css_class("dim-label")
            safe_lbl.add_css_class("caption")
            safe_lbl.set_tooltip_text(
                _("At least one backup kernel must remain installed")
            )
            safe_lbl.set_valign(Gtk.Align.CENTER)
            row.append(safe_lbl)
        else:
            btn = Gtk.Button(label=_("Remove"))
            btn.add_css_class("destructive-action")
            btn.set_valign(Gtk.Align.CENTER)
            btn.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [_("Remove kernel {}").format(kernel["name"])],
            )
            btn.connect("clicked", self._on_remove_clicked, kernel)
            row.append(btn)

        return row

    _GROUP_DESCRIPTIONS = {
        "kernel-group-lts": _(
            "Recommended for most users. These kernels receive "
            "security updates for years and are thoroughly tested."
        ),
        "kernel-group-standard": _(
            "Always up to date with the latest features and hardware support. "
            "Good if you need the newest drivers."
        ),
        "kernel-group-xanmod": _(
            "Tuned for gaming and desktop responsiveness. "
            "A good option for daily use with extra performance."
        ),
        "kernel-group-rt": _(
            "Built for audio/video production needing precise timing. "
            "May be incompatible with some drivers (e.g. NVIDIA). "
            "Only for advanced users."
        ),
    }

    _GROUP_ICONS = {
        "kernel-group-lts": "icon_kernel_lts.svg",
        "kernel-group-standard": "icon_kernel_standard.svg",
        "kernel-group-xanmod": "icon_kernel_xanmod.svg",
        "kernel-group-rt": "icon_kernel_rt.svg",
    }

    def _build_available_groups(self, available: list[dict]) -> None:
        """Build available kernels grouped by type, each in a styled card."""
        self._clear_box(self._available_container)
        if not available:
            self._available_container.set_visible(False)
            return

        self._available_container.set_visible(True)

        # Classify kernels by type
        buckets: dict[str, list[dict]] = {
            "kernel-group-lts": [],
            "kernel-group-standard": [],
            "kernel-group-xanmod": [],
            "kernel-group-rt": [],
        }
        for k in available:
            ktype = classify_kernel(k)
            if ktype.is_rt:
                buckets["kernel-group-rt"].append(k)
            elif ktype.is_xanmod:
                buckets["kernel-group-xanmod"].append(k)
            elif ktype.is_lts:
                buckets["kernel-group-lts"].append(k)
            else:
                buckets["kernel-group-standard"].append(k)

        groups = [
            (_("LTS — Long Term Support (Recommended)"), "kernel-group-lts"),
            (_("Standard"), "kernel-group-standard"),
            (_("Xanmod (Performance)"), "kernel-group-xanmod"),
            (_("Real-Time (Advanced)"), "kernel-group-rt"),
        ]

        for group_title, css_class in groups:
            kernels = buckets[css_class]
            if kernels:
                card = self._build_group_card(group_title, kernels, css_class)
                self._available_container.append(card)

    def _build_group_card(
        self, group_title: str, kernels: list[dict], css_class: str
    ) -> Gtk.Box:
        """Build a single group card with header, description, and kernel rows."""
        group_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        group_card.add_css_class(css_class)

        group_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        group_inner.set_margin_start(16)
        group_inner.set_margin_end(16)
        group_inner.set_margin_top(14)
        group_inner.set_margin_bottom(14)
        group_card.append(group_inner)

        # Header
        group_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon_file = self._GROUP_ICONS.get(css_class)
        if icon_file:
            grp_icon = Gtk.Image.new_from_file(os.path.join(_ICONS_DIR, icon_file))
            grp_icon.set_pixel_size(ICON_SIZE_HEADER)
            grp_icon.set_valign(Gtk.Align.CENTER)
            group_hdr.append(grp_icon)

        label = Gtk.Label()
        label.set_markup(f"<b>{group_title}</b>")
        label.set_halign(Gtk.Align.START)
        label.add_css_class("kernel-group-header")
        label.set_accessible_role(Gtk.AccessibleRole.HEADING)
        group_hdr.append(label)
        group_inner.append(group_hdr)

        # Description
        desc_text = self._GROUP_DESCRIPTIONS.get(css_class, "")
        if desc_text:
            desc_lbl = Gtk.Label(label=desc_text)
            desc_lbl.set_halign(Gtk.Align.START)
            desc_lbl.set_wrap(True)
            desc_lbl.add_css_class("dim-label")
            desc_lbl.add_css_class("caption")
            desc_lbl.set_margin_bottom(4)
            group_inner.append(desc_lbl)

        # Kernel rows
        rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for k in kernels:
            rows_box.append(self._build_available_row(k))

        # RT kernels are hidden by default behind a toggle
        if css_class == "kernel-group-rt":
            self._build_rt_toggle(group_inner, rows_box, len(kernels))
        else:
            group_inner.append(rows_box)

        return group_card

    def _build_rt_toggle(self, parent: Gtk.Box, rows_box: Gtk.Box, count: int) -> None:
        """Build the RT kernel toggle button with revealer."""
        toggle_btn = Gtk.Button()
        toggle_btn.add_css_class("flat")
        toggle_btn.set_halign(Gtk.Align.START)
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toggle_icon = Gtk.Image.new_from_icon_name("pan-end-symbolic")
        toggle_lbl = Gtk.Label(label=_("Show {} available").format(count))
        toggle_box.append(toggle_icon)
        toggle_box.append(toggle_lbl)
        toggle_btn.set_child(toggle_box)
        toggle_btn.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [toggle_lbl.get_label()],
        )

        revealer = Gtk.Revealer()
        revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        revealer.set_reveal_child(False)
        revealer.set_child(rows_box)

        def _on_rt_toggle(
            btn,
            rev=revealer,
            cnt=count,
            ico=toggle_icon,
            lbl=toggle_lbl,
        ):
            revealed = rev.get_reveal_child()
            rev.set_reveal_child(not revealed)
            if revealed:
                ico.set_from_icon_name("pan-end-symbolic")
                lbl.set_label(_("Show {} available").format(cnt))
            else:
                ico.set_from_icon_name("pan-down-symbolic")
                lbl.set_label(_("Hide available kernels"))
            btn.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [lbl.get_label()],
            )

        toggle_btn.connect("clicked", _on_rt_toggle)
        parent.append(toggle_btn)
        parent.append(revealer)

    def _build_available_row(self, kernel: dict) -> Gtk.Box:
        """Build a card-style row for an available kernel."""
        ktype = classify_kernel(kernel)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_valign(Gtk.Align.CENTER)
        row.add_css_class("purpose-pkg-row")

        row.append(self._row_type_icon(ktype))

        # Text column
        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_col.set_hexpand(True)

        # Title row: kernel name + badges
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_lbl = Gtk.Label(label=kernel["name"])
        title_lbl.set_xalign(0)
        title_row.append(title_lbl)
        for badge_text, badge_style in ktype.badge_entries:
            title_row.append(self._create_badge(badge_text, badge_style))
        text_col.append(title_row)

        sub_lbl = Gtk.Label(label=ktype.type_desc)
        sub_lbl.set_xalign(0)
        sub_lbl.set_wrap(True)
        sub_lbl.add_css_class("dim-label")
        sub_lbl.add_css_class("caption")
        text_col.append(sub_lbl)

        row.append(text_col)

        # Info button for kernelnewbies (before install button)
        mm = self._kernel_major_minor(kernel)
        if mm:
            row.append(self._build_info_button(kernel, mm))

        btn = Gtk.Button(label=_("Install"))
        btn.add_css_class("suggested-action")
        btn.set_valign(Gtk.Align.CENTER)
        btn.set_tooltip_text(_("Install kernel {}").format(kernel["name"]))
        btn.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [_("Install kernel {}").format(kernel["name"])],
        )
        btn.connect("clicked", self._on_install_clicked, kernel)
        row.append(btn)

        return row

    # ------------------------------------------------------------------
    # Actions — install
    # ------------------------------------------------------------------

    def _on_install_clicked(self, button: Gtk.Button, kernel: dict) -> None:
        kernel_name = kernel["name"]
        modules = self.kernel_manager._get_kernel_modules(kernel_name)
        packages = [kernel_name] + modules

        pkg_list = "\n".join(f"  • {p}" for p in packages)
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Install {}").format(kernel_name))
        dialog.set_body(_("The following packages will be installed:"))

        pkg_label = Gtk.Label(label=pkg_list)
        pkg_label.set_halign(Gtk.Align.START)
        pkg_label.set_margin_start(12)
        dialog.set_extra_child(pkg_label)

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("install", _("Install"))
        dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_install_response, kernel, button, packages)
        dialog.present(self.get_root())

    def _on_install_response(
        self,
        _dialog: Adw.AlertDialog,
        response: str,
        kernel: dict,
        button: Gtk.Button,
        packages: list[str],
    ) -> None:
        if response != "install" or not self.progress_dialog:
            return

        self.progress_dialog.show_progress(
            _("Installing {}").format(kernel["name"]),
            _("Preparing installation..."),
            cancel_callback=self.kernel_manager.cancel_operation,
        )
        button.set_sensitive(False)
        self.kernel_manager.install_kernel(
            kernel,
            packages=packages,
            progress_callback=self._on_progress_update,
            output_callback=self._on_terminal_output,
            complete_callback=lambda success: GLib.idle_add(
                self._install_complete, button, success
            ),
        )

    def _install_complete(self, button: Gtk.Button, success: bool) -> bool:
        button.set_sensitive(True)
        if success:
            window = self.get_root()
            if hasattr(window, "show_reboot_banner"):
                window.show_reboot_banner()
        if self.progress_dialog:
            if success:
                self.progress_dialog.show_success(
                    _(
                        "Kernel installed successfully.\n"
                        "You may need to reboot to use it."
                    )
                )
            else:
                self.progress_dialog.show_error(
                    _(
                        "Kernel installation failed.\n"
                        "Check the terminal output for details."
                    )
                )
        self._load_kernels_async()
        return False

    # ------------------------------------------------------------------
    # Actions — remove (with undo countdown)
    # ------------------------------------------------------------------

    def _on_remove_clicked(self, button: Gtk.Button, kernel: dict) -> None:
        if kernel["name"] == self._running_kernel_package:
            self._show_completion_dialog(
                _("Cannot Remove Running Kernel"),
                _(
                    "This kernel is currently in use. Boot into a different kernel first."
                ),
                status="warning",
            )
            return

        kernel_name = kernel["name"]
        modules = self.kernel_manager._get_installed_kernel_modules(kernel_name)
        packages = [kernel_name] + modules

        pkg_list = "\n".join(f"  • {p}" for p in packages)
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Remove {}").format(kernel_name))
        dialog.set_body(_("The following packages will be removed:"))

        pkg_label = Gtk.Label(label=pkg_list)
        pkg_label.set_halign(Gtk.Align.START)
        pkg_label.set_margin_start(12)
        dialog.set_extra_child(pkg_label)

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_remove_response, kernel, button, packages)
        dialog.present(self.get_root())

    def _on_remove_response(
        self,
        _dialog: Adw.AlertDialog,
        response: str,
        kernel: dict,
        button: Gtk.Button,
        packages: list[str],
    ) -> None:
        if response != "remove" or not self.progress_dialog:
            return

        button.set_sensitive(False)
        self.progress_dialog.show_progress(
            _("Removing {}").format(kernel["name"]),
            _("Preparing removal…"),
            cancel_callback=self.kernel_manager.cancel_operation,
        )
        self.kernel_manager.remove_kernel(
            kernel,
            packages=packages,
            progress_callback=self._on_progress_update,
            output_callback=self._on_terminal_output,
            complete_callback=lambda success: GLib.idle_add(
                self._remove_complete, button, success
            ),
        )

    def _remove_complete(self, button: Gtk.Button, success: bool) -> bool:
        button.set_sensitive(True)
        if success:
            window = self.get_root()
            if hasattr(window, "show_reboot_banner"):
                window.show_reboot_banner()
        if self.progress_dialog:
            if success:
                self.progress_dialog.show_success(_("Kernel removed successfully."))
            else:
                self.progress_dialog.show_error(
                    _("Kernel removal failed.\nCheck the terminal output for details.")
                )
        self._load_kernels_async()
        return False

    # ------------------------------------------------------------------
    # Bulk remove obsolete
    # ------------------------------------------------------------------

    def _on_bulk_remove_obsolete(self, _button: Gtk.Button) -> None:
        if not self._obsolete_kernels:
            return
        names = ", ".join(k["name"] for k in self._obsolete_kernels)
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Remove Obsolete Kernels"))
        dialog.set_body_use_markup(True)
        dialog.set_body(
            _(
                "Remove all obsolete kernels?\n\n<b>{}</b>\n\n"
                "These kernels no longer receive security updates."
            ).format(GLib.markup_escape_text(names))
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove All"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_bulk_remove_response)
        dialog.present(self.get_root())

    def _on_bulk_remove_response(self, _dialog: Adw.AlertDialog, response: str) -> None:
        if response != "remove":
            return
        kernels = list(self._obsolete_kernels)
        if kernels:
            self._remove_sequence(kernels, 0)

    def _remove_sequence(self, kernels: list, index: int) -> None:
        if index >= len(kernels):
            self._load_kernels_async()
            return
        kernel = kernels[index]
        if not self.progress_dialog:
            return
        self.progress_dialog.show_progress(
            _("Removing {}").format(kernel["name"]),
            _("Removing kernel {} ({}/{})...").format(
                kernel["name"], index + 1, len(kernels)
            ),
            cancel_callback=self.kernel_manager.cancel_operation,
        )
        self.kernel_manager.remove_kernel(
            kernel,
            progress_callback=self._on_progress_update,
            output_callback=self._on_terminal_output,
            complete_callback=lambda success: GLib.idle_add(
                self._sequence_step_done, kernels, index, success
            ),
        )

    def _sequence_step_done(self, kernels: list, index: int, success: bool) -> bool:
        if not success:
            if self.progress_dialog:
                self.progress_dialog.show_error(
                    _("Failed to remove {}. Stopping.").format(kernels[index]["name"])
                )
            self._load_kernels_async()
            return False
        next_idx = index + 1
        if next_idx >= len(kernels):
            window = self.get_root()
            if hasattr(window, "show_reboot_banner"):
                window.show_reboot_banner()
            if self.progress_dialog:
                self.progress_dialog.show_success(
                    _("All obsolete kernels removed successfully.")
                )
            self._load_kernels_async()
        else:
            self._remove_sequence(kernels, next_idx)
        return False

    # ------------------------------------------------------------------
    # Progress callbacks
    # ------------------------------------------------------------------

    def _on_progress_update(self, fraction: float, text: str | None = None) -> None:
        if self.progress_dialog:
            self.progress_dialog.update_progress(fraction, text)

    def _on_terminal_output(self, text: str) -> None:
        if self.progress_dialog and text:
            self.progress_dialog.append_terminal_output(text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _kernel_major_minor(kernel: dict) -> str | None:
        """Extract major.minor version from kernel version string."""
        version = kernel.get("version", "")
        m = re.match(r"(\d+)\.(\d+)", version)
        return f"{m.group(1)}.{m.group(2)}" if m else None

    @staticmethod
    def _build_info_button(kernel: dict, major_minor: str) -> Gtk.Button:
        """Build a circular info button that opens kernelnewbies."""
        url = f"https://kernelnewbies.org/Linux_{major_minor}"
        btn = Gtk.Button()
        btn.set_icon_name("help-about-symbolic")
        btn.add_css_class("flat")
        btn.add_css_class("circular")
        btn.set_valign(Gtk.Align.CENTER)
        btn.set_tooltip_text(_("What's new in Linux {}").format(major_minor))
        btn.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [_("What's new in Linux {}").format(major_minor)],
        )
        btn.connect(
            "clicked",
            lambda _b, u=url: Gtk.UriLauncher(uri=u).launch(
                _b.get_root(), None, None, None
            ),
        )
        return btn

    @staticmethod
    def _icon(name: str) -> Gtk.Image:
        img = Gtk.Image.new_from_icon_name(name)
        img.set_pixel_size(ICON_SIZE_ITEM)
        return img

    @staticmethod
    def _row_type_icon(ktype: KernelTypeInfo) -> Gtk.Image:
        """Return an SVG icon matching the kernel type."""
        if ktype.is_xanmod:
            key = "xanmod"
        elif ktype.is_lts:
            key = "lts"
        elif ktype.is_rt:
            key = "rt"
        else:
            key = "standard"
        img = Gtk.Image.new_from_file(os.path.join(_ICONS_DIR, _ROW_ICONS[key]))
        img.set_pixel_size(ICON_SIZE_ITEM)
        return img

    @staticmethod
    def _clear_listbox(listbox: Gtk.ListBox) -> None:
        while row := listbox.get_first_child():
            listbox.remove(row)

    @staticmethod
    def _clear_box(box: Gtk.Box) -> None:
        while child := box.get_first_child():
            box.remove(child)
