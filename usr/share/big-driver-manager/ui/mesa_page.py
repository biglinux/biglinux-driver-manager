#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Video Drivers Page

List-based layout:
  - GPU detection card at top
  - Mesa drivers as boxed-list with human names
  - MHWD drivers as separate boxed-list section
"""

import subprocess
import os
import re
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from core.constants import ICON_SIZE_HEADER, ICON_SIZE_ITEM
from core.mesa_manager import MesaManager
from core.mhwd_manager import MhwdManager, MhwdDriver
from core.package_manager import PackageManager
from ui.base_page import BaseSection
from ui.mesa_data import (
    _CAT_ROW_ICONS,
    _DRIVER_NOTES,
    _ICONS_DIR,
    _MESA_BUNDLED,
    _MESA_HUMAN_NAMES,
    _MESA_ROW_ICONS,
    _PURPOSE_SECTIONS,
    _init_driver_notes,
    _init_mesa_names,
    _init_purpose_sections,
)
from utils.i18n import _


class MesaSection(BaseSection):
    """Video driver management page — list-based layout."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.mesa_manager = MesaManager()
        self.mhwd_manager = MhwdManager()
        self.pkg_manager = PackageManager()
        self.progress_dialog = None
        self._show_all = False
        self._mhwd_all_drivers: list[MhwdDriver] = []
        self._mhwd_row_widgets: list[tuple[Gtk.Box, MhwdDriver]] = []
        self._gpu_vendors: set[str] = set()
        self._active_mesa: str = ""
        self._has_nvidia_proprietary: bool = False
        self._intel_gen: int = 0  # Detected Intel GPU generation (0 = unknown)
        self._is_vm = self._detect_virtual_machine()
        _init_mesa_names()
        _init_driver_notes()
        self._build_page()
        self._show_loading()

    @staticmethod
    def _detect_virtual_machine() -> bool:
        """Return True if running inside a virtual machine."""
        try:
            result = subprocess.run(
                ["systemd-detect-virt"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def set_preloaded_data(
        self,
        drivers: list[dict],
        gpu_info: dict | None,
        mhwd_drivers: list[MhwdDriver],
    ) -> None:
        """Receive pre-computed data from window (skip redundant queries)."""
        self._populate_all(drivers, gpu_info, mhwd_drivers)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_page(self) -> None:
        # Header card — compact summary + detected GPUs
        hdr_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        hdr_card.add_css_class("card")
        hdr_card.add_css_class("purpose-card-mesa")
        hdr_card.set_margin_bottom(8)

        hdr_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hdr_inner.set_margin_start(16)
        hdr_inner.set_margin_end(16)
        hdr_inner.set_margin_top(16)
        hdr_inner.set_margin_bottom(16)

        # Title row: icon + title
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_row.set_valign(Gtk.Align.CENTER)

        svg = Gtk.Image.new_from_file(
            str(self._assets_path("illustrations/banner_mesa.svg"))
        )
        svg.set_pixel_size(48)
        svg.set_valign(Gtk.Align.CENTER)
        title_row.append(svg)

        title = Gtk.Label(label=_("Video Drivers"))
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        title_row.append(title)

        hdr_inner.append(title_row)

        # Brief summary
        desc_label = Gtk.Label()
        desc_label.set_markup(
            _(
                "On Linux, video drivers for AMD, Intel and NVIDIA (free "
                "software Nouveau) are built into a single project called "
                "<b>Mesa</b>. Below you can choose a Mesa variant and manage "
                "extra packages for gaming, video playback, compute and AI."
            )
        )
        desc_label.set_wrap(True)
        desc_label.set_xalign(0)
        desc_label.add_css_class("dim-label")
        hdr_inner.append(desc_label)

        # GPU info label (populated after detection)
        self._gpu_info_label = Gtk.Label()
        self._gpu_info_label.set_wrap(True)
        self._gpu_info_label.set_xalign(0)
        self._gpu_info_label.set_margin_top(8)
        self._gpu_info_label.set_visible(False)
        hdr_inner.append(self._gpu_info_label)

        # NVIDIA-specific label (shown only when NVIDIA GPU detected)
        self._nvidia_desc_label = Gtk.Label()
        self._nvidia_desc_label.set_markup(
            _(
                "Your computer has an <b>NVIDIA</b> graphics card. You can "
                "install the official proprietary driver for the best "
                "performance in gaming, AI and professional applications."
            )
        )
        self._nvidia_desc_label.set_wrap(True)
        self._nvidia_desc_label.set_xalign(0)
        self._nvidia_desc_label.add_css_class("dim-label")
        self._nvidia_desc_label.set_visible(False)
        hdr_inner.append(self._nvidia_desc_label)

        hdr_card.append(hdr_inner)
        self.append(hdr_card)

        # Mesa variant card (single card with variant rows inside)
        self._mesa_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._mesa_card.add_css_class("card")
        self._mesa_card.add_css_class("purpose-card-mesa")
        self._mesa_card.set_margin_top(20)
        self._mesa_card.set_visible(False)

        self._mesa_card_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._mesa_card_inner.set_margin_start(16)
        self._mesa_card_inner.set_margin_end(16)
        self._mesa_card_inner.set_margin_top(16)
        self._mesa_card_inner.set_margin_bottom(16)

        # Card header
        mesa_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        mesa_hdr.set_valign(Gtk.Align.CENTER)
        mesa_icon = Gtk.Image.new_from_icon_name("bkm-mesa-stable")
        mesa_icon.set_pixel_size(ICON_SIZE_HEADER)
        mesa_hdr.append(mesa_icon)
        mesa_title = Gtk.Label(label=_("Mesa Variant"))
        mesa_title.add_css_class("title-4")
        mesa_title.set_halign(Gtk.Align.START)
        mesa_title.set_hexpand(True)
        mesa_title.set_accessible_role(Gtk.AccessibleRole.HEADING)
        mesa_hdr.append(mesa_title)
        self._mesa_card_inner.append(mesa_hdr)

        self._mesa_help_label = Gtk.Label()
        self._mesa_help_label.set_text(
            _(
                "Choose which Mesa build to use. "
                "Only one variant can be active at a time."
            )
        )
        self._mesa_help_label.set_wrap(True)
        self._mesa_help_label.set_xalign(0)
        self._mesa_help_label.add_css_class("dim-label")
        self._mesa_card_inner.append(self._mesa_help_label)

        # Warning label for NVIDIA proprietary users (hidden by default)
        self._mesa_nvidia_note = Gtk.Label()
        self._mesa_nvidia_note.set_markup(
            _(
                "<b>Note:</b> You are using the NVIDIA proprietary driver. "
                "Mesa is only used for minor tasks in this case. "
                "We recommend keeping the <b>Stable</b> variant — "
                "other versions will not improve performance and may "
                "cause instabilities."
            )
        )
        self._mesa_nvidia_note.set_wrap(True)
        self._mesa_nvidia_note.set_xalign(0)
        self._mesa_nvidia_note.add_css_class("dim-label")
        self._mesa_nvidia_note.add_css_class("warning")
        self._mesa_nvidia_note.set_visible(False)
        self._mesa_card_inner.append(self._mesa_nvidia_note)

        # Rows will be added by _update_mesa_list
        self._mesa_card.append(self._mesa_card_inner)
        self.append(self._mesa_card)

        # Per-vendor sections container (NVIDIA, Intel, AMD, Other)
        self._vendor_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0
        )
        self.append(self._vendor_container)

    # ------------------------------------------------------------------
    # GPU detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_gpu_info() -> dict:
        """Detect GPU hardware and NVIDIA proprietary driver status."""
        env = os.environ.copy()
        env["LANG"] = "C"
        info: dict = {"nvidia_loaded": False, "nvidia_pkg": False, "gpus": []}

        try:
            result = subprocess.run(
                ["lsmod"], capture_output=True, text=True, env=env, timeout=10
            )
            info["nvidia_loaded"] = any(
                line.startswith("nvidia ") for line in result.stdout.splitlines()
            )
        except OSError:
            pass

        try:
            result = subprocess.run(
                ["pacman", "-Qs", "nvidia-utils"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
                timeout=10,
            )
            info["nvidia_pkg"] = (
                result.returncode == 0 and "nvidia-utils" in result.stdout
            )
        except OSError:
            pass

        try:
            result = subprocess.run(
                ["lspci"], capture_output=True, text=True, env=env, timeout=10
            )
            for line in result.stdout.splitlines():
                low = line.lower()
                if (
                    "vga" in low
                    or "3d controller" in low
                    or "display controller" in low
                ):
                    parts = line.split(": ", 1)
                    name = parts[1] if len(parts) > 1 else line
                    is_nvidia = "nvidia" in name.lower()
                    is_intel = "intel" in name.lower()
                    gpu_entry: dict = {"name": name, "nvidia": is_nvidia}
                    if is_intel:
                        gpu_entry["intel_gen"] = MesaSection._detect_intel_gen(name)
                    info["gpus"].append(gpu_entry)
        except OSError:
            pass

        return info

    @staticmethod
    def _detect_intel_gen(gpu_name: str) -> int:
        """Estimate Intel GPU generation from lspci name.

        Returns the approximate Intel graphics generation number:
          6 = Sandy Bridge, 7 = Ivy Bridge / Haswell,
          8 = Broadwell, 9 = Skylake / Kaby Lake / Coffee Lake,
          11 = Ice Lake, 12 = Alder Lake / Raptor Lake / Xe / Arc, etc.
        Returns 0 if unrecognized.
        """
        low = gpu_name.lower()

        # Arc discrete GPUs → Gen 12.7+
        if "arc " in low:
            return 12

        # Xe branding → Gen 12+
        if "xe" in low:
            return 12

        # UHD Graphics 7xx → Alder Lake / Raptor Lake (Gen 12)
        m = re.search(r"uhd\s+graphics\s+(\d+)", low)
        if m:
            num = int(m.group(1))
            if num >= 700:
                return 12
            # UHD 6xx → Coffee Lake / Comet Lake (Gen 9.5)
            return 9

        # Iris Plus / Iris Pro patterns
        if "iris plus" in low or "iris pro" in low:
            # Iris Plus G1/G4/G7 → Ice Lake (Gen 11)
            if re.search(r"iris plus\s+g[147]", low):
                return 11
            # Iris Plus 6xx → Kaby Lake / Coffee Lake (Gen 9.5)
            m2 = re.search(r"iris plus\s+(\d+)", low)
            if m2:
                num = int(m2.group(1))
                if num >= 640:
                    return 9
                return 8
            return 9

        # HD Graphics with a number
        m = re.search(r"hd\s+graphics\s+(\d+)", low)
        if m:
            num = int(m.group(1))
            if num >= 5300:
                return 8  # Broadwell
            if num >= 4000:
                return 7  # Haswell / Ivy Bridge
            if num >= 2000:
                return 6  # Sandy Bridge
            # 3-digit low (510, 530, 610, 630) = Skylake+ Gen 9
            if 500 <= num <= 699:
                return 9
            return 6

        return 0

    def _update_gpu_card(self, gpu_info: dict) -> None:
        """Update the GPU info label and NVIDIA description in the header."""
        gpus = gpu_info["gpus"]
        if not gpus:
            self._gpu_info_label.set_visible(False)
            self._nvidia_desc_label.set_visible(False)
            return

        has_nvidia = any(gpu["nvidia"] for gpu in gpus)
        nvidia_active = gpu_info["nvidia_loaded"] and gpu_info["nvidia_pkg"]

        # Show NVIDIA proprietary install suggestion only when:
        # - NVIDIA GPU detected AND driver NOT installed
        # - AND GPU is series 500+ (check lspci name for GeForce x5xx+)
        show_nvidia_hint = False
        if has_nvidia and not nvidia_active:
            for gpu in gpus:
                if gpu["nvidia"]:
                    # Match series numbers like 500, 1050, 2060, 3070, 4090, 5090 etc.
                    m = re.search(r"\b(\d{3,4})\b", gpu["name"])
                    if m:
                        series = int(m.group(1))
                        if series >= 500:
                            show_nvidia_hint = True
                            break
        self._nvidia_desc_label.set_visible(show_nvidia_hint)

        lines: list[str] = ["<b>" + _("Detected graphics cards:") + "</b>"]
        for gpu in gpus:
            name = gpu["name"].split("[")[0].strip()
            if gpu["nvidia"] and nvidia_active:
                driver_desc = _("NVIDIA proprietary driver (not Mesa)")
                lines.append(
                    f"\u2022 <b>{GLib.markup_escape_text(name)}</b> \u2014 {driver_desc}"
                )
            else:
                driver_desc = _("Mesa driver")
                lines.append(
                    f"\u2022 <b>{GLib.markup_escape_text(name)}</b> \u2014 {driver_desc}"
                )

        self._gpu_info_label.set_markup("\n".join(lines))
        self._gpu_info_label.set_visible(True)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_all_async(self) -> None:
        import threading

        threading.Thread(target=self._load_all_thread, daemon=True).start()

    def _load_all_thread(self) -> None:
        try:
            drivers = self.mesa_manager.get_available_drivers()
            gpu_info = self._detect_gpu_info()
            mhwd_drivers = self.mhwd_manager.get_video_drivers()
            GLib.idle_add(self._populate_all, drivers, gpu_info, mhwd_drivers)
        except Exception as e:
            GLib.idle_add(self._show_completion_dialog, _("Error"), str(e), "error")

    def _populate_all(
        self, drivers: list[dict], gpu_info: dict | None, mhwd_drivers: list[MhwdDriver]
    ) -> bool:
        self._hide_loading()
        self._update_gpu_card(gpu_info)
        self._gpu_vendors = self._extract_gpu_vendors(gpu_info)
        # Detect Intel GPU generation for VAAPI driver filtering
        self._intel_gen = 0
        if gpu_info:
            for gpu in gpu_info.get("gpus", []):
                gen = gpu.get("intel_gen", 0)
                if gen > self._intel_gen:
                    self._intel_gen = gen
        # Detect active Mesa variant for package compatibility
        self._active_mesa = ""
        for d in drivers:
            if d.get("active"):
                self._active_mesa = d.get("id", "")
                break
        # Check if NVIDIA proprietary is installed
        has_nvidia_prop = bool(gpu_info and gpu_info.get("nvidia_pkg"))
        self._has_nvidia_proprietary = has_nvidia_prop
        # Show/hide NVIDIA note in Mesa variant card
        self._mesa_nvidia_note.set_visible(has_nvidia_prop)
        self._update_mesa_list(drivers)
        self._build_vendor_sections(mhwd_drivers)
        return False

    def _load_mesa_drivers(self) -> None:
        drivers = self.mesa_manager.get_available_drivers()
        self._update_mesa_list(drivers)

    def _load_mesa_drivers_async(self) -> None:
        self._load_all_async()

    # ------------------------------------------------------------------
    # Mesa driver list
    # ------------------------------------------------------------------

    def _update_mesa_list(self, drivers: list[dict]) -> None:
        # Remove existing variant rows (keep header + help label + nvidia note)
        while self._mesa_card_inner.get_last_child() is not None:
            child = self._mesa_card_inner.get_last_child()
            # Keep the first 3 children (header row + help label + nvidia note)
            count = 0
            c = self._mesa_card_inner.get_first_child()
            while c is not None:
                count += 1
                c = c.get_next_sibling()
            if count <= 3:
                break
            self._mesa_card_inner.remove(child)

        if not drivers:
            self._mesa_card.set_visible(False)
            return

        self._mesa_card.set_visible(True)

        for driver in drivers:
            row = self._build_mesa_variant_row(driver)
            self._mesa_card_inner.append(row)

    def _build_mesa_variant_row(self, driver: dict) -> Gtk.Box:
        """Build a clickable row for a Mesa driver variant inside the card."""
        driver_id = driver.get("id", driver.get("name", ""))
        is_active = driver.get("active", False)
        human = _MESA_HUMAN_NAMES.get(driver_id, {})
        desc_text = human.get("desc", "")

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_valign(Gtk.Align.CENTER)
        row.add_css_class("purpose-pkg-row")

        # Icon per variant (illustration-style SVG)
        icon_file = _MESA_ROW_ICONS.get(driver_id, "icon_mesa_row_stable.svg")
        icon = Gtk.Image.new_from_file(os.path.join(_ICONS_DIR, icon_file))
        icon.set_pixel_size(ICON_SIZE_ITEM)
        row.append(icon)

        # Text column
        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_col.set_hexpand(True)

        # Title: package_name - human_name
        pkg_name = driver.get("detect_package", driver.get("name", ""))
        human_title = human.get("title", driver.get("name", ""))
        title_lbl = Gtk.Label(label=f"{pkg_name} - {human_title}")
        title_lbl.set_xalign(0)
        text_col.append(title_lbl)

        # Description
        sub_lbl = Gtk.Label(label=desc_text)
        sub_lbl.set_xalign(0)
        sub_lbl.set_wrap(True)
        sub_lbl.add_css_class("dim-label")
        sub_lbl.add_css_class("caption")
        text_col.append(sub_lbl)

        row.append(text_col)

        # Right side: active indicator or switch button
        if is_active:
            active_btn = Gtk.Button(label=_("Active"))
            active_btn.add_css_class("suggested-action")
            active_btn.add_css_class("active-status-btn")
            active_btn.set_valign(Gtk.Align.CENTER)
            active_btn.set_can_focus(False)
            active_btn.set_can_target(False)
            active_btn.update_property([Gtk.AccessibleProperty.LABEL], [_("Active")])
            row.append(active_btn)
        else:
            btn = Gtk.Button()
            btn.set_label(_("Switch"))
            btn.add_css_class("suggested-action")
            btn.set_valign(Gtk.Align.CENTER)
            btn.set_tooltip_text(_("Switch to {}").format(human_title))
            btn.connect("clicked", self._on_mesa_switch_clicked, driver)
            btn.update_property(
                [Gtk.AccessibleProperty.LABEL], [btn.get_tooltip_text()]
            )
            row.append(btn)

        return row

    @staticmethod
    def _assets_path(filename: str) -> Path:
        return Path(__file__).resolve().parent.parent / "assets" / filename

    # ------------------------------------------------------------------
    # Mesa actions
    # ------------------------------------------------------------------

    def _on_mesa_switch_clicked(self, button: Gtk.Button, driver: dict) -> None:
        if driver.get("active", False):
            return  # already active, nothing to do
        human = _MESA_HUMAN_NAMES.get(driver.get("id", ""), {})
        name = human.get("title", driver["name"])

        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Change Video Driver"))
        dialog.set_body_use_markup(True)
        dialog.set_body(
            _(
                "Switch to <b>{}</b>?\n\n"
                "A system reboot will be required for the change to take effect."
            ).format(name)
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("apply", _("Apply"))
        dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect(
            "response", self._on_mesa_confirm_response, driver.get("id", driver["name"])
        )
        dialog.present(self.get_root())

    def _on_mesa_confirm_response(
        self, _dialog: Adw.AlertDialog, response: str, driver_id: str
    ) -> None:
        if response != "apply" or not self.progress_dialog:
            return

        self.progress_dialog.show_progress(
            _("Applying {}").format(driver_id),
            _("Preparing to apply driver..."),
            cancel_callback=self.mesa_manager.cancel_operation,
        )
        self.mesa_manager.apply_driver(
            driver_id,
            progress_callback=self._on_progress_update,
            output_callback=self._on_terminal_output,
            complete_callback=lambda success: GLib.idle_add(
                self._mesa_complete, success
            ),
        )

    def _mesa_complete(self, success: bool) -> bool:
        if success:
            window = self.get_root()
            if hasattr(window, "show_reboot_banner"):
                window.show_reboot_banner()
        if self.progress_dialog:
            if success:
                self.progress_dialog.show_success(
                    _(
                        "Video driver changed successfully!\n\n"
                        "You must reboot your system for the new driver to become active."
                    )
                )
            else:
                self.progress_dialog.show_error(
                    _("Driver change failed.\nCheck the terminal output for details.")
                )
        self._show_loading()
        self._load_all_async()
        return False

    # ------------------------------------------------------------------
    # Per-vendor sections (replaces old MHWD + GPU packages sections)
    # ------------------------------------------------------------------

    _HIDDEN_MHWD = frozenset(
        {
            "video-nvidia-390xx",
            "video-rendition",
            "video-s3",
            "video-sisusb",
            "video-voodoo",
            "video-modesetting",
            "video-vesa",
            "video-linux",
        }
    )

    def _build_vendor_sections(self, mhwd_drivers: list[MhwdDriver]) -> None:
        """Build sections by purpose (gaming, video, compute) + NVIDIA proprietary."""
        _init_purpose_sections()
        self._clear_box(self._vendor_container)
        self._mhwd_all_drivers = list(mhwd_drivers)
        self._mhwd_row_widgets = []
        self._nvidia_installed_name = None
        self._nvidia_conflict_cache: dict[str, tuple[bool, str]] = {}
        self.pkg_manager.invalidate_cache()

        # Classify MHWD drivers
        nvidia_drv: list[MhwdDriver] = []
        other_drv: list[MhwdDriver] = []
        for d in mhwd_drivers:
            if d.name in self._HIDDEN_MHWD:
                continue
            if d.name == "video-virtualmachine" and not self._is_vm:
                continue
            if d.is_nvidia:
                nvidia_drv.append(d)
                if d.installed:
                    self._nvidia_installed_name = d.name
            else:
                other_drv.append(d)

        # NVIDIA proprietary section (MHWD drivers)
        if "nvidia" in self._gpu_vendors or nvidia_drv or self._show_all:
            self._build_nvidia_section(nvidia_drv)

        # Purpose-based sections (gaming, video, compute)
        for section in _PURPOSE_SECTIONS:
            self._build_purpose_section(section)

        # Other drivers (e.g. video-virtualmachine)
        if other_drv:
            self._build_other_section(other_drv)

    def _build_nvidia_section(self, nvidia_drv: list[MhwdDriver]) -> None:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card.add_css_class("card")
        card.add_css_class("purpose-card-nvidia")
        card.set_margin_top(20)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_margin_start(16)
        inner.set_margin_end(16)
        inner.set_margin_top(16)
        inner.set_margin_bottom(16)

        # Header
        hdr_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hdr_row.set_valign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("bkm-gpu-driver")
        icon.set_pixel_size(ICON_SIZE_HEADER)
        hdr_row.append(icon)

        lbl = Gtk.Label(label=_("NVIDIA Proprietary Driver"))
        lbl.add_css_class("title-4")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(True)
        lbl.set_accessible_role(Gtk.AccessibleRole.HEADING)
        hdr_row.append(lbl)

        inner.append(hdr_row)

        help_lbl = Gtk.Label()
        help_lbl.set_text(
            _(
                "Official closed-source driver with the best performance "
                "for gaming, AI, and professional workloads."
            )
        )
        help_lbl.set_wrap(True)
        help_lbl.set_xalign(0)
        help_lbl.add_css_class("dim-label")
        inner.append(help_lbl)

        # "Only one version" hint — shown only when multiple versions available
        self._nvidia_one_version_lbl = Gtk.Label()
        self._nvidia_one_version_lbl.set_text(
            _("Only one version can be active at a time.")
        )
        self._nvidia_one_version_lbl.set_wrap(True)
        self._nvidia_one_version_lbl.set_xalign(0)
        self._nvidia_one_version_lbl.add_css_class("dim-label")
        self._nvidia_one_version_lbl.set_visible(
            False
        )  # Updated by _apply_mhwd_visibility
        inner.append(self._nvidia_one_version_lbl)

        rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        sorted_drv = sorted(
            nvidia_drv,
            key=lambda d: (not d.compatible, -d.priority, d.name),
        )
        for drv in sorted_drv:
            row = self._build_mhwd_row(drv)
            rows_box.append(row)
            self._mhwd_row_widgets.append((row, drv))

        inner.append(rows_box)
        card.append(inner)
        self._vendor_container.append(card)
        self._apply_mhwd_visibility()

    def _filter_purpose_packages(self, section: dict) -> list[dict]:
        """Filter packages for a purpose section based on detected GPU vendors."""
        nvidia_prop = self._has_nvidia_proprietary
        has_amd_or_nouveau = "amd" in self._gpu_vendors or (
            "nvidia" in self._gpu_vendors and not nvidia_prop
        )
        intel_gen = self._intel_gen
        relevant: list[dict] = []
        for pkg in section["packages"]:
            if not (self._show_all or pkg["vendors"] & self._gpu_vendors):
                continue
            if pkg["name"] == "vulkan-nouveau" and nvidia_prop:
                continue
            if pkg["name"] == "mesa-vdpau" and not has_amd_or_nouveau:
                continue
            if pkg["name"] == "libva-mesa-driver" and not has_amd_or_nouveau:
                continue
            if not self._show_all and intel_gen > 0:
                if pkg["name"] == "intel-media-driver" and intel_gen < 8:
                    continue
                if pkg["name"] == "libva-intel-driver" and intel_gen >= 8:
                    continue
            relevant.append(pkg)
        return relevant

    def _build_purpose_section(self, section: dict) -> None:
        """Build a card-wrapped section for a purpose (gaming, video, compute)."""
        relevant = self._filter_purpose_packages(section)
        if not relevant:
            return

        # Check section status
        bundled = _MESA_BUNDLED.get(self._active_mesa or "stable", frozenset())
        all_ok = all(
            pkg["name"] in bundled or self.pkg_manager.is_package_installed(pkg["name"])
            for pkg in relevant
            if pkg.get("recommend", True)
        )

        # Outer card container with subtle tinted background
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card.add_css_class("card")
        card.add_css_class(f"purpose-card-{section['id']}")
        card.set_margin_top(20)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_margin_start(16)
        inner.set_margin_end(16)
        inner.set_margin_top(16)
        inner.set_margin_bottom(16)

        # Header: icon + title + status indicator
        hdr_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hdr_row.set_valign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name(section["icon"])
        icon.set_pixel_size(ICON_SIZE_HEADER)
        hdr_row.append(icon)

        lbl = Gtk.Label(label=section["title"])
        lbl.add_css_class("title-4")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(True)
        lbl.set_accessible_role(Gtk.AccessibleRole.HEADING)
        hdr_row.append(lbl)

        # Status indicator
        if all_ok:
            status = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            status.add_css_class("success")
            status.set_pixel_size(16)
            status.set_tooltip_text(_("All recommended packages installed"))
            status.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [_("All recommended packages installed")],
            )
        else:
            status = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            status.add_css_class("warning")
            status.set_pixel_size(16)
            status.set_tooltip_text(_("Some packages not installed"))
            status.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [_("Some packages not installed")],
            )
        hdr_row.append(status)

        inner.append(hdr_row)

        # Description
        help_lbl = Gtk.Label()
        help_lbl.set_text(section["desc"])
        help_lbl.set_wrap(True)
        help_lbl.set_xalign(0)
        help_lbl.add_css_class("dim-label")
        inner.append(help_lbl)

        # Package rows (flat, no boxed-list border — card is the container)
        for pkg in relevant:
            row = self._build_purpose_pkg_card_row(pkg)
            if row:
                inner.append(row)

        card.append(inner)
        self._vendor_container.append(card)

    def _build_purpose_pkg_card_row(self, pkg: dict) -> Gtk.Box | None:
        """Build a package row inside a purpose card."""
        name = pkg["name"]
        active_mesa = self._active_mesa or "stable"
        bundled = _MESA_BUNDLED.get(active_mesa, frozenset())

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_valign(Gtk.Align.CENTER)
        row.add_css_class("purpose-pkg-row")

        # Icon (illustration-style SVG per category)
        icon_file = _CAT_ROW_ICONS.get(pkg.get("cat", ""), "icon_row_gpu_detect.svg")
        icon = Gtk.Image.new_from_file(os.path.join(_ICONS_DIR, icon_file))
        icon.set_pixel_size(ICON_SIZE_ITEM)
        row.append(icon)

        # Text column
        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_col.set_hexpand(True)

        title_lbl = Gtk.Label(label=name)
        title_lbl.set_xalign(0)
        text_col.append(title_lbl)

        sub_lbl = Gtk.Label(label=pkg.get("short", ""))
        sub_lbl.set_xalign(0)
        sub_lbl.set_wrap(True)
        sub_lbl.add_css_class("dim-label")
        sub_lbl.add_css_class("caption")
        text_col.append(sub_lbl)

        row.append(text_col)

        # Action
        if name in bundled:
            lbl = Gtk.Label(label=_("Included"))
            lbl.add_css_class("dim-label")
            lbl.set_valign(Gtk.Align.CENTER)
            row.append(lbl)
            sub_lbl.set_text(
                pkg.get("short", "")
                + " · "
                + _("Already included in your Mesa version ({})").format(active_mesa)
            )
        else:
            installed = self.pkg_manager.is_package_installed(name)
            compat_pkg = {"name": name, "desc": pkg.get("short", "")}
            btn = Gtk.Button()
            btn.set_valign(Gtk.Align.CENTER)
            if installed:
                btn.set_label(_("Remove"))
                btn.add_css_class("destructive-action")
                btn.set_tooltip_text(_("Remove {}").format(name))
                btn.connect("clicked", self._on_gpu_pkg_remove_clicked, compat_pkg)
            else:
                btn.set_label(_("Install"))
                btn.add_css_class("suggested-action")
                btn.set_tooltip_text(_("Install {}").format(name))
                btn.connect("clicked", self._on_gpu_pkg_install_clicked, compat_pkg)
            btn.update_property(
                [Gtk.AccessibleProperty.LABEL], [btn.get_tooltip_text()]
            )
            row.append(btn)

        return row

    def _build_other_section(self, drivers: list[MhwdDriver]) -> None:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card.add_css_class("card")
        card.set_margin_top(20)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        inner.set_margin_start(16)
        inner.set_margin_end(16)
        inner.set_margin_top(16)
        inner.set_margin_bottom(16)

        hdr_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hdr_row.set_valign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("bkm-gpu-detect")
        icon.set_pixel_size(ICON_SIZE_HEADER)
        hdr_row.append(icon)

        lbl = Gtk.Label(label=_("Other Drivers"))
        lbl.add_css_class("title-4")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_hexpand(True)
        lbl.set_accessible_role(Gtk.AccessibleRole.HEADING)
        hdr_row.append(lbl)

        inner.append(hdr_row)

        help_lbl = Gtk.Label()
        help_lbl.set_text(
            _(
                "Additional drivers for special hardware configurations "
                "like virtual machines."
            )
        )
        help_lbl.set_wrap(True)
        help_lbl.set_xalign(0)
        help_lbl.add_css_class("dim-label")
        inner.append(help_lbl)

        rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        for drv in drivers:
            row = self._build_mhwd_row(drv)
            rows_box.append(row)
            self._mhwd_row_widgets.append((row, drv))

        inner.append(rows_box)
        card.append(inner)
        self._vendor_container.append(card)

    @staticmethod
    def _extract_gpu_vendors(gpu_info: dict) -> set[str]:
        """Return a set of vendor keys ('amd', 'intel', 'nvidia')."""
        vendors: set[str] = set()
        for gpu in gpu_info.get("gpus", []):
            name_low = gpu.get("name", "").lower()
            if "nvidia" in name_low:
                vendors.add("nvidia")
            if "amd" in name_low or "radeon" in name_low:
                vendors.add("amd")
            if "intel" in name_low:
                vendors.add("intel")
        return vendors

    def set_show_all(self, show_all: bool) -> None:
        if self._show_all == show_all:
            return
        self._show_all = show_all
        if self._mhwd_all_drivers:
            self._build_vendor_sections(self._mhwd_all_drivers)

    def _apply_mhwd_visibility(self) -> None:
        """Toggle MHWD driver row visibility based on show_all flag."""
        visible_nvidia_count = 0
        for row, drv in self._mhwd_row_widgets:
            if self._show_all:
                show = True
            elif drv.installed:
                show = True
            elif drv.compatible:
                if drv.is_nvidia:
                    # Default view: only show the latest (video-nvidia)
                    show = drv.name == "video-nvidia"
                else:
                    show = True
            else:
                show = False
            row.set_visible(show)
            if show and drv.is_nvidia:
                visible_nvidia_count += 1
        # Only show "one version at a time" when multiple are visible
        if hasattr(self, "_nvidia_one_version_lbl"):
            self._nvidia_one_version_lbl.set_visible(visible_nvidia_count > 1)

    def _build_mhwd_row(self, driver: MhwdDriver) -> Gtk.Box:
        """Build a card-style row for an MHWD driver."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_valign(Gtk.Align.CENTER)
        row.add_css_class("purpose-pkg-row")

        # Icon
        icon = Gtk.Image.new_from_file(os.path.join(_ICONS_DIR, "icon_row_nvidia.svg"))
        icon.set_pixel_size(ICON_SIZE_ITEM)
        row.append(icon)

        # Text column
        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_col.set_hexpand(True)

        title_lbl = Gtk.Label(label=driver.display_name)
        title_lbl.set_xalign(0)
        text_col.append(title_lbl)

        subtitle_parts = [f"v{driver.version}"]
        if driver.compatible:
            subtitle_parts.append(_("Compatible"))
        label = _("Open Source") if driver.free_driver else _("Proprietary")
        subtitle_parts.append(label)

        # Driver-specific notes
        note = _DRIVER_NOTES.get(driver.name, "")
        is_470 = "470xx" in driver.name
        if is_470:
            subtitle_parts.append(_("⚠ No Wayland support · No longer maintained"))
        elif note:
            subtitle_parts.append(note)

        sub_lbl = Gtk.Label(label=" · ".join(subtitle_parts))
        sub_lbl.set_xalign(0)
        sub_lbl.set_wrap(True)
        sub_lbl.add_css_class("dim-label")
        sub_lbl.add_css_class("caption")
        text_col.append(sub_lbl)

        row.append(text_col)

        # Action button
        if driver.installed:
            rm_btn = Gtk.Button(label=_("Remove"))
            rm_btn.add_css_class("destructive-action")
            rm_btn.set_valign(Gtk.Align.CENTER)
            rm_btn.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [_("Remove {}").format(driver.display_name)],
            )
            rm_btn.connect("clicked", self._on_mhwd_remove_clicked, driver)
            row.append(rm_btn)
        elif self._nvidia_installed_name and driver.is_nvidia and driver.compatible:
            btn = Gtk.Button(label=_("Switch"))
            btn.add_css_class("suggested-action")
            btn.set_valign(Gtk.Align.CENTER)
            btn.set_tooltip_text(
                _("Switch from {} to {}").format(
                    self._nvidia_installed_name.replace("-", " "),
                    driver.display_name,
                )
            )
            btn.update_property(
                [Gtk.AccessibleProperty.LABEL],
                [_("Switch to {}").format(driver.display_name)],
            )
            btn.connect("clicked", self._on_mhwd_switch_clicked, driver)
            row.append(btn)
        else:
            allowed, reason = self._can_install_nvidia_cached(driver.name)
            btn = Gtk.Button(label=_("Install"))
            btn.set_valign(Gtk.Align.CENTER)
            if allowed:
                btn.add_css_class("suggested-action")
                btn.update_property(
                    [Gtk.AccessibleProperty.LABEL],
                    [_("Install {}").format(driver.display_name)],
                )
                btn.connect("clicked", self._on_mhwd_install_clicked, driver)
            else:
                btn.set_sensitive(False)
                btn.set_tooltip_text(reason)
            row.append(btn)

        # 470xx warning style
        if is_470:
            row.add_css_class("warning")

        return row

    def _can_install_nvidia_cached(self, driver_name: str) -> tuple[bool, str]:
        """Check nvidia conflict using pre-computed installed driver info."""
        if "nvidia" not in driver_name.lower():
            return True, ""
        existing = self._nvidia_installed_name
        if existing and existing != driver_name:
            return False, _("Remove the installed NVIDIA driver ({}) first.").format(
                existing
            )
        return True, ""

    # ------------------------------------------------------------------
    # MHWD actions
    # ------------------------------------------------------------------

    def _on_mhwd_install_clicked(self, _button: Gtk.Button, driver: MhwdDriver) -> None:
        free_label = _("open-source") if driver.free_driver else _("proprietary")
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Install Driver"))
        dialog.set_body_use_markup(True)
        dialog.set_body(
            _(
                "Install <b>{}</b> ({} driver)?\n\n"
                "A system reboot may be required after installation."
            ).format(driver.display_name, free_label)
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("install", _("Install"))
        dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_mhwd_install_confirm, driver)
        dialog.present(self.get_root())

    def _on_mhwd_install_confirm(
        self, _dialog: Adw.AlertDialog, response: str, driver: MhwdDriver
    ) -> None:
        if response != "install" or not self.progress_dialog:
            return
        self.progress_dialog.show_progress(
            _("Installing {}").format(driver.display_name),
            _("Preparing installation..."),
            cancel_callback=self.mhwd_manager.cancel_operation,
        )
        self.mhwd_manager.install_driver(
            driver,
            progress_callback=self._on_progress_update,
            output_callback=self._on_terminal_output,
            complete_callback=lambda success: GLib.idle_add(
                self._mhwd_complete, success, driver.display_name, "install"
            ),
        )

    def _on_mhwd_switch_clicked(self, _button: Gtk.Button, driver: MhwdDriver) -> None:
        current_name = (self._nvidia_installed_name or "").replace("-", " ")
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Switch NVIDIA Driver"))
        dialog.set_body_use_markup(True)
        dialog.set_body(
            _(
                "Switch from <b>{}</b> to <b>{}</b>?\n\n"
                "The current driver will be replaced automatically.\n"
                "A system reboot will be required."
            ).format(
                GLib.markup_escape_text(current_name),
                GLib.markup_escape_text(driver.display_name),
            )
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("switch", _("Switch"))
        dialog.set_response_appearance("switch", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_mhwd_switch_confirm, driver)
        dialog.present(self.get_root())

    def _on_mhwd_switch_confirm(
        self, _dialog: Adw.AlertDialog, response: str, driver: MhwdDriver
    ) -> None:
        if response != "switch" or not self.progress_dialog:
            return
        self.progress_dialog.show_progress(
            _("Switching to {}").format(driver.display_name),
            _("Replacing current NVIDIA driver..."),
            cancel_callback=self.mhwd_manager.cancel_operation,
        )
        self.mhwd_manager.switch_driver(
            driver,
            progress_callback=self._on_progress_update,
            output_callback=self._on_terminal_output,
            complete_callback=lambda success: GLib.idle_add(
                self._mhwd_complete, success, driver.display_name, "switch"
            ),
        )

    def _on_mhwd_remove_clicked(self, _button: Gtk.Button, driver: MhwdDriver) -> None:
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Remove Driver"))
        dialog.set_body_use_markup(True)
        dialog.set_body(
            _(
                "Remove <b>{}</b>?\n\nA system reboot may be required after removal."
            ).format(driver.display_name)
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_mhwd_remove_confirm, driver)
        dialog.present(self.get_root())

    def _on_mhwd_remove_confirm(
        self, _dialog: Adw.AlertDialog, response: str, driver: MhwdDriver
    ) -> None:
        if response != "remove" or not self.progress_dialog:
            return
        self.progress_dialog.show_progress(
            _("Removing {}").format(driver.display_name),
            _("Preparing removal..."),
            cancel_callback=self.mhwd_manager.cancel_operation,
        )
        self.mhwd_manager.remove_driver(
            driver,
            progress_callback=self._on_progress_update,
            output_callback=self._on_terminal_output,
            complete_callback=lambda success: GLib.idle_add(
                self._mhwd_complete, success, driver.display_name, "remove"
            ),
        )

    def _mhwd_complete(self, success: bool, name: str, action: str) -> bool:
        if success:
            window = self.get_root()
            if hasattr(window, "show_reboot_banner"):
                window.show_reboot_banner()
        if self.progress_dialog:
            if success:
                if action == "switch":
                    verb = _("activated")
                elif action == "install":
                    verb = _("installed")
                else:
                    verb = _("removed")
                self.progress_dialog.show_success(
                    _(
                        "{} was {} successfully!\n\nA system reboot may be required."
                    ).format(name, verb)
                )
            else:
                self.progress_dialog.show_error(
                    _(
                        "Driver operation failed.\n"
                        "Check the terminal output for details."
                    )
                )
        self._show_loading()
        self._load_all_async()
        return False

    # ------------------------------------------------------------------
    # GPU package rows (used inside vendor sections)
    # ------------------------------------------------------------------

    def _build_gpu_pkg_row(self, pkg: dict[str, str]) -> Gtk.Box | None:
        """Build a card-style row for a GPU package.

        Returns None when the package should be hidden entirely
        (e.g. Amber Mesa with modern-only packages).
        """
        pkg_name = pkg["name"]
        bundled_set = _MESA_BUNDLED.get(self._active_mesa, frozenset())
        bundled = pkg_name in bundled_set

        # With Mesa Amber, modern GPU packages are incompatible — skip them
        if self._active_mesa == "amber" and pkg_name in _MESA_BUNDLED.get(
            "tkg-stable", frozenset()
        ):
            return None

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_valign(Gtk.Align.CENTER)
        row.add_css_class("purpose-pkg-row")

        # Icon (illustration-style SVG per category)
        icon_file = _CAT_ROW_ICONS.get(pkg["cat"], "icon_row_compute.svg")
        icon = Gtk.Image.new_from_file(os.path.join(_ICONS_DIR, icon_file))
        icon.set_pixel_size(ICON_SIZE_ITEM)
        row.append(icon)

        # Text column
        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_col.set_hexpand(True)

        title_lbl = Gtk.Label(label=pkg_name)
        title_lbl.set_xalign(0)
        text_col.append(title_lbl)

        if bundled:
            sub_text = (
                f"{pkg['cat']} · "
                + _("Already included in your Mesa version")
                + f" ({self._active_mesa})"
            )
        else:
            sub_text = f"{pkg['cat']} · {pkg['desc']}"

        sub_lbl = Gtk.Label(label=sub_text)
        sub_lbl.set_xalign(0)
        sub_lbl.set_wrap(True)
        sub_lbl.add_css_class("dim-label")
        sub_lbl.add_css_class("caption")
        text_col.append(sub_lbl)

        row.append(text_col)

        # Action
        if bundled:
            lbl = Gtk.Label(label=_("Included"))
            lbl.add_css_class("dim-label")
            lbl.set_valign(Gtk.Align.CENTER)
            row.append(lbl)
        else:
            installed = self.pkg_manager.is_package_installed(pkg_name)
            if installed:
                btn = Gtk.Button(label=_("Remove"))
                btn.add_css_class("destructive-action")
                btn.set_valign(Gtk.Align.CENTER)
                btn.update_property(
                    [Gtk.AccessibleProperty.LABEL],
                    [_("Remove {}").format(pkg_name)],
                )
                btn.connect("clicked", self._on_gpu_pkg_remove_clicked, pkg)
                row.append(btn)
            else:
                btn = Gtk.Button(label=_("Install"))
                btn.add_css_class("suggested-action")
                btn.set_valign(Gtk.Align.CENTER)
                btn.update_property(
                    [Gtk.AccessibleProperty.LABEL],
                    [_("Install {}").format(pkg_name)],
                )
                btn.connect("clicked", self._on_gpu_pkg_install_clicked, pkg)
                row.append(btn)

        return row

    def _on_gpu_pkg_install_clicked(
        self, _button: Gtk.Button, pkg: dict[str, str]
    ) -> None:
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Install Package"))
        dialog.set_body_use_markup(True)
        dialog.set_body(
            _("Install <b>{}</b>?\n\n{}").format(
                GLib.markup_escape_text(pkg["name"]),
                GLib.markup_escape_text(pkg["desc"]),
            )
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("install", _("Install"))
        dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_gpu_pkg_install_confirm, pkg)
        dialog.present(self.get_root())

    def _on_gpu_pkg_install_confirm(
        self, _dialog: Adw.AlertDialog, response: str, pkg: dict[str, str]
    ) -> None:
        if response != "install" or not self.progress_dialog:
            return
        name = pkg["name"]
        self.progress_dialog.show_progress(
            _("Installing {}").format(name),
            _("Downloading package..."),
            cancel_callback=self.mhwd_manager.cancel_operation,
        )
        self.mhwd_manager._run_pacman_command(
            ["pacman", "-S", "--noconfirm", name],
            progress_callback=self._on_progress_update,
            output_callback=self._on_terminal_output,
            complete_callback=lambda success: GLib.idle_add(
                self._gpu_pkg_complete, success, name, "install"
            ),
            operation_name=_("Installing {}").format(name),
        )

    def _on_gpu_pkg_remove_clicked(
        self, _button: Gtk.Button, pkg: dict[str, str]
    ) -> None:
        dialog = Adw.AlertDialog()
        dialog.set_heading(_("Remove Package"))
        dialog.set_body_use_markup(True)
        dialog.set_body(
            _("Remove <b>{}</b>?").format(GLib.markup_escape_text(pkg["name"]))
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_gpu_pkg_remove_confirm, pkg)
        dialog.present(self.get_root())

    def _on_gpu_pkg_remove_confirm(
        self, _dialog: Adw.AlertDialog, response: str, pkg: dict[str, str]
    ) -> None:
        if response != "remove" or not self.progress_dialog:
            return
        name = pkg["name"]
        self.progress_dialog.show_progress(
            _("Removing {}").format(name),
            _("Removing package..."),
            cancel_callback=self.mhwd_manager.cancel_operation,
        )
        self.mhwd_manager._run_pacman_command(
            ["pacman", "-Rns", "--noconfirm", name],
            progress_callback=self._on_progress_update,
            output_callback=self._on_terminal_output,
            complete_callback=lambda success: GLib.idle_add(
                self._gpu_pkg_complete, success, name, "remove"
            ),
            operation_name=_("Removing {}").format(name),
        )

    def _gpu_pkg_complete(self, success: bool, name: str, action: str) -> bool:
        if success:
            window = self.get_root()
            if hasattr(window, "show_reboot_banner"):
                window.show_reboot_banner()
        if self.progress_dialog:
            if success:
                verb = _("installed") if action == "install" else _("removed")
                self.progress_dialog.show_success(
                    _("{} was {} successfully!").format(name, verb)
                )
            else:
                self.progress_dialog.show_error(
                    _(
                        "Package operation failed.\n"
                        "Check the terminal output for details."
                    )
                )
        # Rebuild vendor sections to refresh installed statuses
        self._build_vendor_sections(self._mhwd_all_drivers)
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
    def _clear_listbox(listbox: Gtk.ListBox) -> None:
        while row := listbox.get_first_child():
            listbox.remove(row)

    @staticmethod
    def _clear_flow(flow: Gtk.FlowBox) -> None:
        while child := flow.get_first_child():
            flow.remove(child)

    @staticmethod
    def _clear_box(box: Gtk.Box) -> None:
        while child := box.get_first_child():
            box.remove(child)
