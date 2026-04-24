#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Headless UI smoke tests using fake gi bindings."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "usr", "share", "big-driver-manager"),
)

from gi_fakes import install_fake_gi, reload_ui_modules


install_fake_gi()


def make_item(
    name: str,
    *,
    package: str | None = None,
    description: str = "",
    category: str = "wifi",
    detected: bool = False,
    installed: bool = False,
    compatible: bool = False,
    device_has_driver: bool = True,
    detected_device_name: str | None = None,
):
    return SimpleNamespace(
        name=name,
        package=package or name,
        description=description,
        category=category,
        detected=detected,
        installed=installed,
        compatible=compatible,
        device_has_driver=device_has_driver,
        detected_device_name=detected_device_name,
    )


class ProgressSpy:
    def __init__(self) -> None:
        self.progress = []
        self.output = []
        self.success = []
        self.errors = []
        self.shown = []

    def show_progress(self, title, message, cancel_callback=None) -> None:
        self.shown.append((title, message, cancel_callback))

    def update_progress(self, fraction, text) -> None:
        self.progress.append((fraction, text))

    def append_terminal_output(self, line) -> None:
        self.output.append(line)

    def show_success(self, message) -> None:
        self.success.append(message)

    def show_error(self, message) -> None:
        self.errors.append(message)


class RebootRoot:
    def __init__(self) -> None:
        self.reboot_shown = False
        self._show_all_switch = SimpleNamespace(set_active=lambda value: setattr(self, "show_all_active", value))

    def show_reboot_banner(self) -> None:
        self.reboot_shown = True


class TestStyleAndProgressSmoke(unittest.TestCase):
    def setUp(self):
        reload_ui_modules()

    def test_style_manager_base_section_and_progress_dialog(self):
        style_mod = importlib.import_module("utils.style_manager")
        style_mod.StyleManager._instance = None
        style_mod.StyleManager._provider = None

        manager = style_mod.StyleManager.get_default()
        self.assertTrue(manager.load_styles())
        self.assertTrue(manager.reload_styles())
        manager.unload_styles()
        self.assertIsNone(style_mod.StyleManager._provider)

        with patch.object(style_mod.Gdk.Display, "get_default", return_value=None):
            self.assertFalse(manager.load_styles())

        base_page = importlib.import_module("ui.base_page")
        section = base_page.BaseSection()
        section._show_loading()
        section._on_loading_timeout()
        self.assertIn("carreg", section._loading_label.get_text().lower())
        badge = section._create_badge("LTS", "success")
        self.assertIsNotNone(badge)
        section._hide_loading()
        self.assertIsNone(section._loading_box)

        progress_mod = importlib.import_module("ui.progress_dialog")
        gtk = importlib.import_module("gi.repository.Gtk")
        cancelled = []

        dialog = progress_mod.ProgressDialog(gtk.Window())
        dialog.show_progress("Installing", "Please wait...", cancel_callback=lambda: cancelled.append(True))
        dialog.set_steps(2, 3, "Installing packages")
        dialog.update_progress(0.42, "Downloading")
        dialog.append_terminal_output("error: disk full")
        self.assertEqual(dialog._progress_bar.get_fraction(), 0.42)
        self.assertIn("disk full", dialog._terminal_buffer.text)
        self.assertEqual(dialog._get_line_tag("warning: foo"), "warning")
        dialog.show_success("done")
        self.assertTrue(dialog._is_complete)
        dialog.show_progress("Removing", "Please wait...", cancel_callback=lambda: cancelled.append(True))
        dialog._on_cancel_clicked(None)
        self.assertTrue(cancelled)
        self.assertIn("cancel", dialog._status_label.get_text().lower())


class TestHomePageSmoke(unittest.TestCase):
    def setUp(self):
        reload_ui_modules()

    def test_home_page_updates_cards_alerts_and_install_flows(self):
        home_mod = importlib.import_module("ui.home_page")
        page = home_mod.HomePage(lambda _page: None)

        optional = make_item(
            "rtl8xxxu",
            description="Wireless driver",
            category="wifi",
            detected=True,
            device_has_driver=True,
            detected_device_name="Realtek RTL8192",
        )
        needed = make_item(
            "rtl8852au",
            description="USB wireless driver",
            category="wifi",
            detected=True,
            device_has_driver=False,
            detected_device_name="Realtek RTL8852AU",
        )
        page.set_driver_suggestions([optional, needed])
        self.assertTrue(page._sug_card.get_visible())
        self.assertEqual(len(page._alerts), 1)

        page.set_video_recommendations(
            missing=[{"name": "vulkan-radeon", "short": "AMD Vulkan", "cat": "Vulkan"}],
            installed=[{"name": "lib32-mesa", "short": "32-bit OpenGL"}],
            vendor_names="AMD",
        )
        self.assertTrue(page._rec_card.get_visible())
        page._on_rec_toggle(page._rec_toggle_btn)
        self.assertTrue(page._rec_revealer.get_reveal_child())

        page.add_alert("Kernel obsolete", action_label="Manage", action_page="kernel")
        page.update_banner()
        self.assertTrue(page._content_box.get_visible())

        progress = ProgressSpy()
        manager = MagicMock()
        page.set_install_handler(manager, progress)

        page._on_rec_install_confirm(None, "install", ["vulkan-radeon"])
        manager.run_pacman_command.assert_called_once()
        page._on_rec_install_done(True)
        self.assertTrue(progress.success)
        self.assertFalse(page._rec_card.get_visible())

        button = MagicMock()
        page._on_single_install_confirm(None, "install", "rtl8xxxu", button)
        self.assertEqual(manager.run_pacman_command.call_count, 2)
        page._on_single_install_done(True, "rtl8xxxu", button)
        self.assertTrue(progress.success)
        button.set_label.assert_called()


class TestCategorySectionSmoke(unittest.TestCase):
    def setUp(self):
        reload_ui_modules()

    def test_category_section_covers_flat_grouped_and_actions(self):
        category_mod = importlib.import_module("ui.category_page")
        section = category_mod.CategorySection(
            title="Wi-Fi",
            description="Wireless drivers",
            icon_name="network-wireless-symbolic",
            category_id="wifi",
        )

        section.show_network_scan()
        self.assertTrue(section._net_scan_box.get_visible())
        section.hide_network_scan()

        flat_items = [
            make_item(
                f"wifi-driver-{index}",
                description="Wireless support",
                detected=index < 2,
                installed=index == 1,
                detected_device_name="USB Wi-Fi" if index == 0 else None,
            )
            for index in range(6)
        ]
        section.set_items(flat_items)
        self.assertFalse(section._is_grouped)
        self.assertTrue(section._search_entry.get_visible())
        section._search_entry.set_text("wifi-driver-0")
        section._apply_search_filter(section._search_entry)
        section.set_show_all(True)

        progress = ProgressSpy()
        section.progress_dialog = progress
        section._installer = MagicMock()
        section._installer.build_install_plan.return_value = SimpleNamespace(
            initial_message="Please wait...",
            cancelable=True,
        )

        section._on_install_response(None, "install", flat_items[0])
        section._installer.install_package.assert_called_once()
        section._on_remove_response(None, "remove", flat_items[1])
        section._installer.remove_package.assert_called_once()

        root = RebootRoot()
        section.get_root = lambda: root
        section._refresh_installed_status = MagicMock()
        section._request_refresh = MagicMock()
        section._on_complete(True)
        self.assertTrue(root.reboot_shown)
        section._refresh_installed_status.assert_called_once()
        section._request_refresh.assert_called_once()

        grouped = category_mod.CategorySection(
            title="Printers",
            description="Printer drivers",
            icon_name="printer-symbolic",
            category_id="printer",
        )
        grouped_items = []
        for prefix in ("brother", "epson", "canon", "hp"):
            for idx in range(6):
                grouped_items.append(
                    make_item(
                        f"{prefix}-driver-{idx}",
                        category="printer",
                        detected=idx == 0,
                        installed=idx == 1,
                    )
                )
        grouped.set_items(grouped_items)
        self.assertTrue(grouped._is_grouped)
        grouped.get_root = lambda: root
        grouped._on_show_all_request(None)
        self.assertTrue(getattr(root, "show_all_active", False))
        grouped.show_error("boom")
        self.assertTrue(grouped._empty_status.get_visible())


class TestInstalledAndDriversHubSmoke(unittest.TestCase):
    def setUp(self):
        reload_ui_modules()

    def test_installed_page_and_drivers_hub(self):
        installed_mod = importlib.import_module("ui.installed_page")
        page = installed_mod.InstalledPage()
        module = make_item(
            "rtl8xxxu",
            description="Wi-Fi driver",
            category="wifi",
            detected=True,
            installed=True,
            detected_device_name="RTL8192",
        )
        firmware = make_item(
            "bt-firmware",
            description="Bluetooth firmware",
            category="bluetooth",
            installed=True,
        )
        printer = make_item(
            "brlaser",
            description="Brother printer driver",
            category="printer",
            installed=True,
            detected=True,
            detected_device_name="Brother DCP",
        )
        page.set_installed_data(
            modules=[module],
            firmware=[firmware],
            printers=[printer],
            scanners=[],
            kernels=[{"name": "linux612", "version": "6.12.10-1"}],
            running_kernel="linux612",
            mhwd_video=[SimpleNamespace(name="video-nvidia", info="NVIDIA", installed=True)],
            mesa_drivers=[{"id": "stable", "name": "Mesa Stable", "installed": True, "active": True}],
        )
        self.assertTrue(page._summary_label.get_visible())

        progress = ProgressSpy()
        page.progress_dialog = progress
        page._installer = MagicMock()
        page._on_remove_response(None, "remove", module)
        page._installer.remove_package.assert_called_once()

        root = RebootRoot()
        page.get_root = lambda: root
        page._request_refresh = MagicMock()
        page._on_complete(True, module)
        self.assertTrue(root.reboot_shown)
        page._request_refresh.assert_called_once()

        hub_mod = importlib.import_module("ui.drivers_hub_page")
        navigated = []
        hub = hub_mod.DriversHubPage(navigated.append)
        hub.progress_dialog = progress
        hub._installer = MagicMock()
        hub._installer.build_install_plan.return_value = SimpleNamespace(
            initial_message="Please wait...",
            cancelable=True,
        )
        wifi_item = make_item(
            "rtl8xxxu",
            description="Wi-Fi driver",
            category="wifi",
            detected=True,
            installed=False,
            detected_device_name="RTL8192",
        )
        printer_item = make_item(
            "brlaser",
            description="Printer driver",
            category="printer",
            compatible=True,
            installed=True,
        )
        hub.set_category_items("wifi", [wifi_item])
        hub.set_category_items("printer", [printer_item])
        self.assertTrue(hub._status_banner.get_visible())
        hub.set_show_all(True)
        first_row = next(iter(hub._category_rows.values()))
        hub._on_row_activated(hub._list_box, first_row)
        self.assertTrue(navigated)
        hub._on_install_response(None, "install", wifi_item)
        hub._installer.install_package.assert_called_once()
        hub.get_root = lambda: root
        hub._refresh_installed_status = MagicMock()
        hub._on_complete(True)
        self.assertTrue(root.reboot_shown)
        hub._refresh_installed_status.assert_called_once()


class TestKernelMesaWindowAndApplicationSmoke(unittest.TestCase):
    def setUp(self):
        reload_ui_modules()

    def test_kernel_mesa_window_settings_and_application(self):
        kernel_mod = importlib.import_module("ui.kernel_page")
        section = kernel_mod.KernelSection()
        kernels = [
            {"name": "linux612", "version": "6.12.10-1", "installed": True, "lts": True},
            {"name": "linux66", "version": "6.6.70-1", "installed": True, "lts": True},
            {"name": "linux619", "version": "6.19.1-1", "installed": False},
            {"name": "linux619-xanmod", "version": "6.19.1-1", "installed": False, "xanmod": True},
            {"name": "linux612-rt", "version": "6.12.10-rt1", "installed": False, "rt": True},
        ]
        obsolete = [{"name": "linux66", "version": "6.6.70-1", "obsolete": True}]
        section.set_preloaded_data(kernels, "linux612", obsolete)
        self.assertTrue(section._running_box.get_visible())
        self.assertTrue(section._obsolete_box.get_visible())

        progress = ProgressSpy()
        section.progress_dialog = progress
        section.kernel_manager = MagicMock()
        section._load_kernels_async = MagicMock()
        root = RebootRoot()
        section.get_root = lambda: root
        button = MagicMock()

        section._on_install_response(
            None,
            "install",
            {"name": "linux619"},
            button,
            ["linux619", "linux619-headers"],
        )
        section.kernel_manager.install_kernel.assert_called_once()
        section._install_complete(button, True)
        self.assertTrue(root.reboot_shown)

        root.reboot_shown = False
        section._on_remove_response(
            None,
            "remove",
            {"name": "linux66"},
            button,
            ["linux66"],
        )
        section.kernel_manager.remove_kernel.assert_called_once()
        section._remove_complete(button, True)
        self.assertTrue(root.reboot_shown)

        section._remove_sequence = MagicMock()
        section._on_bulk_remove_response(None, "remove")
        section._remove_sequence.assert_called_once()
        section._on_progress_update(0.5, "half")
        section._on_terminal_output("line")
        self.assertTrue(progress.progress)
        self.assertTrue(progress.output)

        mesa_mod = importlib.import_module("ui.mesa_page")
        from core.mhwd_manager import MhwdDriver

        with patch.object(mesa_mod.MesaSection, "_detect_virtual_machine", return_value=False):
            mesa = mesa_mod.MesaSection()
        mesa.pkg_manager = MagicMock()
        mesa.pkg_manager.is_package_installed.side_effect = lambda name: name in {"lib32-mesa"}
        drivers = [
            {"id": "stable", "name": "mesa", "detect_package": "mesa", "active": True},
            {"id": "tkg-stable", "name": "mesa-tkg-stable", "detect_package": "mesa-tkg-stable", "active": False},
        ]
        gpu_info = {
            "nvidia_loaded": True,
            "nvidia_pkg": True,
            "gpus": [
                {"name": "NVIDIA GeForce RTX 5070", "nvidia": True},
                {"name": "Intel Arc A770", "nvidia": False, "intel_gen": 12},
                {"name": "AMD Radeon 780M", "nvidia": False},
            ],
        }
        mhwd_drivers = [
            MhwdDriver(
                name="video-nvidia",
                version="570.86",
                free_driver=False,
                bus_type="PCI",
                installed=True,
                compatible=True,
                category="video",
            ),
            MhwdDriver(
                name="video-nvidia-570xx",
                version="570.86",
                free_driver=False,
                bus_type="PCI",
                compatible=True,
                category="video",
            ),
            MhwdDriver(
                name="video-virtualmachine",
                version="1.0",
                free_driver=True,
                bus_type="PCI",
                category="video",
            ),
        ]
        mesa.set_preloaded_data(drivers, gpu_info, mhwd_drivers)
        self.assertTrue(mesa._mesa_card.get_visible())
        mesa.set_show_all(True)
        mesa.progress_dialog = progress
        mesa.get_root = lambda: root
        mesa._load_all_async = MagicMock()
        root.reboot_shown = False
        mesa._mesa_complete(True)
        self.assertTrue(root.reboot_shown)
        mesa._on_progress_update(0.25, "installing")
        mesa._on_terminal_output("mesa line")
        self.assertGreaterEqual(len(progress.output), 2)

        window_mod = importlib.import_module("ui.window")
        app = SimpleNamespace(add_action=MagicMock())
        with patch.object(window_mod.GLib, "idle_add", return_value=1), patch.object(
            window_mod.MesaSection, "_detect_virtual_machine", return_value=False
        ):
            win = window_mod.KernelManagerWindow(application=app)

        db = SimpleNamespace(
            modules=[make_item("rtl8xxxu", category="wifi", detected=True)],
            firmware=[make_item("bt-firmware", category="bluetooth", detected=True)],
            printers=[make_item("brlaser", category="printer", detected=True)],
            scanners=[make_item("sane-airscan", category="scanner", detected=False)],
            get_modules_by_category=lambda category: [
                item for item in [make_item("rtl8xxxu", category="wifi", detected=True)] if item.category == category
            ],
            get_firmware_by_category=lambda category: [
                item for item in [
                    make_item("bt-firmware", category="bluetooth", detected=True),
                    make_item("scan-firmware", category="scanner", detected=False),
                ]
                if item.category == category
            ],
        )
        win.mesa_section.pkg_manager = MagicMock()
        win.mesa_section.pkg_manager.is_package_installed.return_value = False
        win._populate_category_sections(db, {"wifi"})
        win._populate_home_dashboard(
            gpu_info,
            [{"id": "stable", "active": True}],
            obsolete,
            db,
            installed_pkgs=set(),
        )
        win._show_all_switch.set_active(True)
        self.assertTrue(win._show_all_label.get_label())
        self.assertTrue(win._on_key_pressed(None, window_mod.Gdk.KEY_Escape, None, None))
        win.show_reboot_banner()
        self.assertTrue(win._reboot_banner._revealed)
        win._on_about_activated(None, None)

        reload_ui_modules()
        app_mod = importlib.import_module("ui.application")
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            app_mod, "CONFIG_DIR", tmpdir
        ), patch.object(
            app_mod, "SETTINGS_FILE", os.path.join(tmpdir, "settings.json")
        ):
            settings = app_mod.SettingsManager()
            self.assertEqual(
                settings._sanitize_settings(
                    {
                        "window_width": 1200,
                        "window_height": 800,
                        "window_maximized": True,
                        "custom": "x",
                        "bad_int": "oops",
                    }
                )["custom"],
                "x",
            )
            self.assertTrue(settings.set("window_width", 1280))
            self.assertEqual(app_mod.SettingsManager().get("window_width"), 1280)

        fake_style = SimpleNamespace(load_styles=lambda: True)
        fake_window = MagicMock()
        fake_window.is_maximized.return_value = False
        fake_window.get_width.return_value = 1024
        fake_window.get_height.return_value = 768
        with patch.object(app_mod.StyleManager, "get_default", return_value=fake_style), patch.object(
            app_mod.Gdk.Display, "get_default", return_value=app_mod.Gdk.Display.get_default()
        ), patch.object(app_mod, "KernelManagerWindow", return_value=fake_window):
            app_instance = app_mod.KernelManagerApplication()
            app_instance.settings_manager = MagicMock()
            app_instance.settings_manager.get.side_effect = lambda key, default=None: {
                "window_width": 900,
                "window_height": 700,
                "window_maximized": True,
            }.get(key, default)
            app_instance._active_window = fake_window
            app_instance.on_activate(app_instance)
            fake_window.set_default_size.assert_called_with(900, 700)
            fake_window.maximize.assert_called_once()
            self.assertFalse(app_instance._on_window_close(fake_window))
            app_instance.show_error_dialog("boom")
