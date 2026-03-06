#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Main Window

Sidebar navigation using Adw.NavigationSplitView:
  Sidebar categories → Content pages (Stack)
"""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gio, Adw, GLib, Gdk, Pango

from core.constants import APP_NAME, WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT
from core.driver_database import DriverDatabase
from core.hardware_detect import (
    detect_all_devices,
    detect_network_printers,
    fetch_installed_set,
    match_firmware,
    match_modules,
    match_network_printers,
    update_peripheral_install_status,
)
from core.kernel_manager import KernelManager
from core.logging_config import get_logger
from core.mesa_manager import MesaManager
from core.mhwd_manager import MhwdManager
from ui.home_page import HomePage
from ui.mesa_page import MesaSection
from ui.kernel_page import KernelSection
from ui.category_page import CategorySection
from ui.progress_dialog import ProgressDialog
from utils.i18n import _

# Category definitions: (id, icon, title, description)
_CATEGORY_DEFS = [
    (
        "video",
        "video-display-symbolic",
        _("Video / GPU"),
        _("Mesa, NVIDIA, and GPU drivers."),
    ),
    (
        "wifi",
        "network-wireless-symbolic",
        _("Wi-Fi"),
        _("Wireless network adapter drivers."),
    ),
    (
        "ethernet",
        "network-wired-symbolic",
        _("Ethernet"),
        _("Wired network adapter drivers."),
    ),
    (
        "bluetooth",
        "bluetooth-symbolic",
        _("Bluetooth"),
        _("Bluetooth adapter drivers."),
    ),
    (
        "dvb",
        "tv-symbolic",
        _("DVB / TV"),
        _("Digital TV tuner firmware."),
    ),
    (
        "sound",
        "audio-speakers-symbolic",
        _("Audio"),
        _("Audio device firmware."),
    ),
    (
        "webcam",
        "camera-web-symbolic",
        _("Webcam"),
        _("Webcam device firmware."),
    ),
    (
        "touchscreen",
        "input-touchpad-symbolic",
        _("Touchscreen"),
        _("Touchscreen device firmware."),
    ),
    (
        "printer",
        "printer-symbolic",
        _("Printers"),
        _("Printer drivers and support packages."),
    ),
    (
        "printer3d",
        "printer-symbolic",
        _("3D Printers"),
        _("3D printer firmware."),
    ),
    (
        "scanner",
        "scanner-symbolic",
        _("Scanners"),
        _("Scanner drivers and SANE backends."),
    ),
    (
        "other",
        "application-x-firmware-symbolic",
        _("Other"),
        _("Additional firmware packages."),
    ),
]


class KernelManagerWindow(Adw.ApplicationWindow):
    """Main window with sidebar navigation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._logger = get_logger("Window")
        self.set_title(APP_NAME)
        self.set_default_size(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)
        self.set_size_request(360, 480)
        self.set_resizable(True)
        self._category_sections: dict[str, CategorySection] = {}
        self._build_ui()
        GLib.idle_add(self._start_detection)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        sidebar_page = self._build_sidebar()
        content_page = self._build_content_stack()

        # === SPLIT VIEW ===
        self._split_view = Adw.NavigationSplitView()
        self._split_view.set_min_sidebar_width(140)
        self._split_view.set_max_sidebar_width(220)
        self._split_view.set_sidebar(sidebar_page)
        self._split_view.set_content(content_page)

        # Responsive breakpoints
        all_sections = [self.mesa_section, self.kernel_section] + list(
            self._category_sections.values()
        )
        self._setup_breakpoints(all_sections)

        # Progress dialog
        self.progress_dialog = ProgressDialog(self)
        self.mesa_section.set_progress_dialog(self.progress_dialog)
        self.kernel_section.set_progress_dialog(self.progress_dialog)
        for sec in self._category_sections.values():
            sec.set_progress_dialog(self.progress_dialog)
        self._home.set_install_handler(
            self.mesa_section.mhwd_manager, self.progress_dialog
        )

        # Initial state — select Home
        first_row = self._sidebar_list.get_row_at_index(0)
        if first_row:
            self._sidebar_list.select_row(first_row)

        self.set_content(self._split_view)

        # Escape key goes home
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

    def _build_sidebar(self) -> Adw.NavigationPage:
        """Build the navigation sidebar."""
        sidebar_toolbar = Adw.ToolbarView()

        sidebar_header = Adw.HeaderBar()
        sidebar_title = Adw.WindowTitle.new(APP_NAME, "")
        sidebar_header.set_title_widget(sidebar_title)
        sidebar_toolbar.add_top_bar(sidebar_header)

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_vexpand(True)

        self._sidebar_list = Gtk.ListBox()
        self._sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._sidebar_list.add_css_class("navigation-sidebar")
        self._sidebar_list.connect("row-selected", self._on_sidebar_row_selected)

        _SIDEBAR_ITEMS = [
            ("welcome", "go-home-symbolic", _("Home")),
            ("kernel", "utilities-terminal-symbolic", _("Kernel")),
            ("video", "video-display-symbolic", _("Video")),
        ] + [
            (cat_id, icon, title)
            for cat_id, icon, title, _desc in _CATEGORY_DEFS
            if cat_id != "video"
        ]

        for page_id, icon_name, label_text in _SIDEBAR_ITEMS:
            row = Gtk.ListBoxRow()
            row.set_name(page_id)
            row.update_property([Gtk.AccessibleProperty.LABEL], [label_text])
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_start(4)
            box.set_margin_end(4)
            box.set_margin_top(2)
            box.set_margin_bottom(2)
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(18)
            box.append(icon)
            lbl = Gtk.Label(label=label_text)
            lbl.set_halign(Gtk.Align.START)
            lbl.set_hexpand(True)
            box.append(lbl)
            row.set_child(box)
            self._sidebar_list.append(row)

        sidebar_scroll.set_child(self._sidebar_list)
        sidebar_toolbar.set_content(sidebar_scroll)
        return Adw.NavigationPage.new(sidebar_toolbar, _("Categories"))

    def _build_content_stack(self) -> Adw.NavigationPage:
        """Build the content area with all pages in a stack."""
        content_toolbar = Adw.ToolbarView()
        content_toolbar.set_top_bar_style(Adw.ToolbarStyle.FLAT)

        self._content_header = self._create_content_header()
        content_toolbar.add_top_bar(self._content_header)

        # Persistent reboot banner
        self._reboot_banner = Adw.Banner()
        self._reboot_banner.set_title(
            _("A system reboot is recommended to apply changes.")
        )
        self._reboot_banner.set_button_label("")
        self._reboot_banner.set_revealed(False)
        content_toolbar.add_top_bar(self._reboot_banner)

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.set_transition_duration(150)

        self._home = HomePage(on_navigate=self._navigate_to)
        self._stack.add_named(self._wrap_scroll(self._home, clamp=900), "welcome")

        self.kernel_section = KernelSection()
        self._stack.add_named(
            self._wrap_scroll(self.kernel_section, clamp=1200, margin=32), "kernel"
        )

        self.mesa_section = MesaSection()
        self._stack.add_named(
            self._wrap_scroll(self.mesa_section, clamp=1200, margin=32), "video"
        )

        for cat_id, icon_name, cat_title, cat_desc in _CATEGORY_DEFS:
            if cat_id == "video":
                continue
            section = CategorySection(
                title=cat_title,
                description=cat_desc,
                icon_name=icon_name,
                category_id=cat_id,
            )
            self._stack.add_named(
                self._wrap_scroll(section, clamp=1200, margin=32), cat_id
            )
            self._category_sections[cat_id] = section

        content_toolbar.set_content(self._stack)
        return Adw.NavigationPage.new(content_toolbar, _("Content"))

    def _setup_breakpoints(self, sections: list) -> None:
        """Configure responsive breakpoints for content sections."""
        bp1 = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 700sp"))
        bp1.add_setter(self._split_view, "collapsed", True)
        for sec in sections:
            bp1.add_setter(sec, "margin-start", 16)
            bp1.add_setter(sec, "margin-end", 16)
        self.add_breakpoint(bp1)

        bp2 = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 500sp"))
        for sec in sections:
            bp2.add_setter(sec, "margin-start", 8)
            bp2.add_setter(sec, "margin-end", 8)
        self.add_breakpoint(bp2)

    @staticmethod
    def _wrap_scroll(
        child: Gtk.Widget, clamp: int = 0, margin: int = 0
    ) -> Gtk.ScrolledWindow:
        """Wrap a widget in ScrolledWindow with optional Clamp and margins."""
        if margin:
            child.set_margin_start(margin)
            child.set_margin_end(margin)
            child.set_margin_top(16)
            child.set_margin_bottom(24)

        target = child
        if clamp:
            clamped = Adw.Clamp(
                maximum_size=clamp, tightening_threshold=int(clamp * 0.75)
            )
            clamped.set_child(child)
            target = clamped

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(target)
        return scroll

    def _create_content_header(self) -> Adw.HeaderBar:
        header = Adw.HeaderBar()
        header.set_show_title(True)

        # Centered title widget with description + switch
        center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        center_box.set_halign(Gtk.Align.FILL)
        center_box.set_valign(Gtk.Align.CENTER)
        center_box.set_hexpand(True)

        self._show_all_label = Gtk.Label()
        self._show_all_label.set_label(
            _("Showing drivers detected as compatible with your computer")
        )
        self._show_all_label.add_css_class("dim-label")
        self._show_all_label.add_css_class("caption")
        self._show_all_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._show_all_label.set_hexpand(True)
        center_box.append(self._show_all_label)

        self._show_all_switch = Gtk.Switch()
        self._show_all_switch.set_valign(Gtk.Align.CENTER)
        self._show_all_switch.set_tooltip_text(_("Show all drivers"))
        self._show_all_switch.update_property(
            [Gtk.AccessibleProperty.LABEL], [_("Show all drivers")]
        )
        self._show_all_switch.connect("notify::active", self._on_show_all_toggled)
        center_box.append(self._show_all_switch)

        self._show_all_box = center_box
        self._show_all_box.set_visible(False)
        header.set_title_widget(self._show_all_box)

        # Menu (rightmost)
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_tooltip_text(_("Menu"))
        menu_btn.update_property(
            [Gtk.AccessibleProperty.LABEL], [_("Application menu")]
        )
        menu = Gio.Menu()
        menu.append(_("About"), "app.about")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        self._setup_actions()
        return header

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    # Pages where the show-all toggle is relevant
    _DRIVER_PAGES = {"video"} | {
        cat_id for cat_id, *_ in _CATEGORY_DEFS if cat_id != "video"
    }

    def _on_sidebar_row_selected(
        self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None
    ) -> None:
        if row is None:
            return
        page_id = row.get_name()
        self._stack.set_visible_child_name(page_id)
        self._show_all_box.set_visible(page_id in self._DRIVER_PAGES)
        # On collapsed split view, show content pane
        self._split_view.set_show_content(True)

    def _navigate_to(self, page_name: str) -> None:
        """Navigate to a page (used by home page action rows)."""
        # Find and select the sidebar row for the target page
        idx = 0
        row = self._sidebar_list.get_row_at_index(idx)
        while row is not None:
            if row.get_name() == page_name:
                self._sidebar_list.select_row(row)
                return
            idx += 1
            row = self._sidebar_list.get_row_at_index(idx)
        # Page not in sidebar (shouldn't happen) — direct fallback
        self._stack.set_visible_child_name(page_name)

    def _on_key_pressed(self, _ctrl, keyval, _keycode, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            # Go home
            first_row = self._sidebar_list.get_row_at_index(0)
            if first_row:
                self._sidebar_list.select_row(first_row)
            return True
        return False

    # ------------------------------------------------------------------
    # Hardware detection (background thread)
    # ------------------------------------------------------------------

    def _start_detection(self) -> bool:
        threading.Thread(target=self._detect_hardware, daemon=True).start()
        return False

    def _detect_hardware(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        try:
            db = DriverDatabase()

            # Phase 1: run independent I/O tasks in parallel
            with ThreadPoolExecutor(max_workers=5) as pool:
                fut_devices = pool.submit(detect_all_devices)
                fut_installed = pool.submit(fetch_installed_set)
                fut_mhwd = pool.submit(MhwdManager().get_video_drivers)
                fut_gpu = pool.submit(MesaSection._detect_gpu_info)

                km = KernelManager()
                fut_kernels = pool.submit(km.get_available_kernels)

                devices = fut_devices.result()
                installed_pkgs = fut_installed.result()
                mhwd_video = fut_mhwd.result()
                gpu_info = fut_gpu.result()
                available_kernels = fut_kernels.result()

            # Phase 2: match drivers (depends on installed_pkgs)
            match_modules(db, devices, installed_cache=installed_pkgs)
            match_firmware(db, installed_cache=installed_pkgs)
            update_peripheral_install_status(db, installed_cache=installed_pkgs)

            # Kernel info
            running_pkg = km.get_running_kernel_package()
            installed_kernels = km.get_installed_kernels()
            available_names = {k["name"] for k in available_kernels}
            obsolete_kernels = [
                {**k, "obsolete": True}
                for k in installed_kernels
                if k["name"] != running_pkg and k["name"] not in available_names
            ]
            # Mesa info
            mesa = MesaManager()
            mesa_drivers = mesa.get_available_drivers(installed_set=installed_pkgs)

            def _populate_phase1() -> bool:
                """Home, kernel, mesa — lightweight, show content fast."""
                self._populate_home_dashboard(
                    gpu_info, mesa_drivers, obsolete_kernels, db,
                    installed_pkgs=installed_pkgs,
                )
                self.kernel_section.set_preloaded_data(
                    available_kernels,
                    running_pkg,
                    obsolete_kernels,
                )
                self.mesa_section.set_preloaded_data(
                    mesa_drivers,
                    gpu_info,
                    mhwd_video,
                )
                GLib.idle_add(_populate_phase2)
                return False

            def _populate_phase2() -> bool:
                """Category sections — heavier (printers/scanners)."""
                self._populate_category_sections(db)
                # Start async network printer discovery
                cat = self._category_sections
                if "printer" in cat:
                    cat["printer"].show_network_scan()
                    threading.Thread(
                        target=self._detect_network_printers,
                        args=(db,),
                        daemon=True,
                    ).start()
                return False

            GLib.idle_add(_populate_phase1)
        except Exception as exc:
            self._logger.error("Hardware detection failed: %s", exc)

            def _show_error() -> bool:
                for section in self._category_sections.values():
                    section.show_error(
                        _("Hardware detection failed. Check system logs for details.")
                    )
                return False

            GLib.idle_add(_show_error)

    def _detect_network_printers(self, db: DriverDatabase) -> None:
        """Run network printer discovery in background and update UI."""
        try:
            net_printers = detect_network_printers(timeout=10)
            newly_detected = match_network_printers(db, net_printers)

            def _update_ui() -> bool:
                cat = self._category_sections
                if "printer" in cat:
                    cat["printer"].hide_network_scan()
                    if newly_detected > 0:
                        cat["printer"].set_items(db.printers)
                return False

            GLib.idle_add(_update_ui)
        except Exception as exc:
            self._logger.warning("Network printer discovery failed: %s", exc)

            def _hide_scan() -> bool:
                cat = self._category_sections
                if "printer" in cat:
                    cat["printer"].hide_network_scan()
                return False

            GLib.idle_add(_hide_scan)

    # ------------------------------------------------------------------
    # Populate helpers (called from GLib.idle_add in _detect_hardware)
    # ------------------------------------------------------------------

    def _populate_category_sections(self, db) -> None:
        """Populate each category page with detected items."""
        cat = self._category_sections
        if "wifi" in cat:
            cat["wifi"].set_items(
                [
                    *db.get_modules_by_category("wifi"),
                    *db.get_firmware_by_category("wifi"),
                ]
            )
        if "ethernet" in cat:
            cat["ethernet"].set_items(db.get_modules_by_category("ethernet"))
        if "bluetooth" in cat:
            cat["bluetooth"].set_items(
                [
                    *db.get_modules_by_category("bluetooth"),
                    *db.get_firmware_by_category("bluetooth"),
                ]
            )
        if "dvb" in cat:
            cat["dvb"].set_items(db.get_firmware_by_category("dvb"))
        if "sound" in cat:
            cat["sound"].set_items(db.get_firmware_by_category("sound"))
        if "webcam" in cat:
            cat["webcam"].set_items(db.get_firmware_by_category("webcam"))
        if "touchscreen" in cat:
            cat["touchscreen"].set_items(db.get_firmware_by_category("touchscreen"))
        if "printer" in cat:
            cat["printer"].set_items(db.printers)
        if "printer3d" in cat:
            cat["printer3d"].set_items(db.get_firmware_by_category("printer3d"))
        if "scanner" in cat:
            cat["scanner"].set_items(
                [*db.scanners, *db.get_firmware_by_category("scanner")]
            )
        if "other" in cat:
            cat["other"].set_items(db.get_firmware_by_category("other"))

    def _populate_home_dashboard(
        self,
        gpu_info,
        mesa_drivers: list[dict],
        obsolete_kernels: list[dict],
        db,
        installed_pkgs: set[str] | None = None,
    ) -> None:
        """Populate the home dashboard with video recs, driver suggestions, and alerts."""
        from ui.mesa_data import _get_recommendations
        from ui.mesa_page import MesaSection as _Mesa

        home = self._home

        gpu_vendors = _Mesa._extract_gpu_vendors(gpu_info)
        active_mesa_id = ""
        for d in mesa_drivers:
            if d.get("active"):
                active_mesa_id = d.get("id", "")
                break
        has_nvidia_prop = bool(gpu_info and gpu_info.get("nvidia_pkg"))
        missing, installed = _get_recommendations(
            gpu_vendors,
            self.mesa_section.pkg_manager,
            active_mesa_id,
            has_nvidia_prop,
            installed_set=installed_pkgs,
        )
        vendor_label = ", ".join(
            v.upper() if v == "amd" else v.capitalize() for v in sorted(gpu_vendors)
        )
        home.set_video_recommendations(missing, installed, vendor_label)

        detected_mods = [m for m in db.modules if m.detected and not m.installed]
        home.set_driver_suggestions(detected_mods)

        for obs in obsolete_kernels or []:
            home.add_alert(
                _("Obsolete kernel: {} — no longer receives security updates").format(
                    obs["name"]
                ),
                alert_type="warning",
                action_label=_("Manage"),
                action_page="kernel",
            )
        home.update_banner()

    # ------------------------------------------------------------------
    # Reboot banner
    # ------------------------------------------------------------------

    def show_reboot_banner(self) -> None:
        """Reveal the persistent reboot-recommended banner."""
        self._reboot_banner.set_revealed(True)

    # ------------------------------------------------------------------
    # Show-all toggle
    # ------------------------------------------------------------------

    def _on_show_all_toggled(self, switch: Gtk.Switch, _pspec: object) -> None:
        show_all = switch.get_active()
        if show_all:
            self._show_all_label.set_label(
                _("Showing all drivers, including incompatible ones")
            )
        else:
            self._show_all_label.set_label(
                _("Showing drivers detected as compatible with your computer")
            )
        self.mesa_section.set_show_all(show_all)
        for sec in self._category_sections.values():
            sec.set_show_all(show_all)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _setup_actions(self) -> None:
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about_activated)
        self.get_application().add_action(about_action)

    def _on_about_activated(self, _action, _param) -> None:
        from core.constants import APP_VERSION, APP_AUTHOR, APP_WEBSITE

        about = Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon="big-driver-manager",
            version=APP_VERSION,
            developer_name=APP_AUTHOR,
            website=APP_WEBSITE,
            issue_url="https://github.com/communitybig/big-driver-manager/issues",
            copyright="© 2024-2025 BigLinux Team",
            license_type=Gtk.License.GPL_3_0,
            developers=[APP_AUTHOR],
            artists=[APP_AUTHOR],
        )
        about.present(self)
