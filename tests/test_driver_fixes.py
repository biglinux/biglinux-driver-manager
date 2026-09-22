#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for driver detection and installation fixes: USB driver bindings,
wired link diagnostics, category normalization, repo/AUR routing,
cancellation and the asset database consistency.
"""

import os
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "usr", "share", "big-driver-manager"),
)

_ASSETS = (
    Path(__file__).resolve().parent.parent
    / "usr"
    / "share"
    / "big-driver-manager"
    / "assets"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _make_usb_device(
    base: Path, name: str, vid: str, pid: str, driver: str | None
) -> None:
    """Create a fake /sys/bus/usb/devices entry with one interface."""
    dev = base / name
    _write(dev / "idVendor", f"{vid}\n")
    _write(dev / "idProduct", f"{pid}\n")
    intf = base / f"{name}:1.0"
    intf.mkdir(parents=True)
    # Real sysfs has interfaces both as siblings and inside the device dir
    (dev / f"{name}:1.0").symlink_to(intf)
    if driver:
        drv_dir = base.parent / "drivers" / driver
        drv_dir.mkdir(parents=True, exist_ok=True)
        (intf / "driver").symlink_to(drv_dir)


class TestUsbDriverBindings(unittest.TestCase):
    """USB devices must report the kernel driver bound to their interfaces."""

    def test_bound_driver_is_reported(self):
        from core.hardware_detect import _usb_drivers_by_id

        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "devices"
            _make_usb_device(base, "2-2.3", "0bda", "8153", "r8152")
            _make_usb_device(base, "3-1", "0bda", "8179", None)
            drivers = _usb_drivers_by_id(base)

        self.assertEqual(drivers, {("0BDA", "8153"): "r8152"})

    def test_usbfs_claim_is_not_a_driver(self):
        from core.hardware_detect import _usb_drivers_by_id

        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "devices"
            _make_usb_device(base, "1-4", "1234", "5678", "usbfs")
            self.assertEqual(_usb_drivers_by_id(base), {})

    def test_missing_sysfs_returns_empty(self):
        from core.hardware_detect import _usb_drivers_by_id

        self.assertEqual(_usb_drivers_by_id(Path("/nonexistent/usb")), {})

    @patch("core.hardware_detect._usb_drivers_by_id")
    @patch("core.hardware_detect._run")
    def test_detect_usb_devices_sets_driver(self, mock_run, mock_drivers):
        from core.hardware_detect import detect_usb_devices

        mock_run.return_value = (
            "Bus 002 Device 005: ID 0bda:8153 Realtek Semiconductor Corp. "
            "RTL8153 Gigabit Ethernet Adapter\n"
        )
        mock_drivers.return_value = {("0BDA", "8153"): "r8152"}
        devices = detect_usb_devices()
        self.assertEqual(devices[0].driver_in_use, "r8152")

    def test_working_usb_adapter_is_not_flagged_as_needed(self):
        """The RTL8153 case: in-kernel r8152 driver means no alert."""
        from core.driver_database import DriverModule
        from core.hardware_detect import DetectedDevice, match_modules

        module = DriverModule(
            name="r8152",
            category="ethernet",
            description="",
            package="r8152-dkms",
            usb_ids=[("0BDA", "8153")],
        )
        db = MagicMock()
        db.modules = [module]
        device = DetectedDevice(
            bus="usb",
            vendor_id="0BDA",
            device_id="8153",
            name="RTL8153",
            driver_in_use="r8152",
        )
        match_modules(db, [device], installed_cache=set())
        self.assertTrue(module.device_has_driver)
        self.assertEqual(module.device_driver, "r8152")


class TestWiredLinks(unittest.TestCase):
    """Wired link diagnostics read from /sys/class/net."""

    def _iface(self, base: Path, name: str, driver: str = "r8152", **files):
        iface = base / name
        iface.mkdir(parents=True)
        dev = base.parent / "dev" / name
        drv = base.parent / "drivers" / driver
        dev.mkdir(parents=True)
        drv.mkdir(parents=True, exist_ok=True)
        (dev / "driver").symlink_to(drv)
        (iface / "device").symlink_to(dev)
        _write(iface / "type", files.pop("type", "1") + "\n")
        for fname, value in files.items():
            _write(iface / fname, value + "\n")
        return iface

    def test_link_states(self):
        from core.hardware_detect import detect_wired_links

        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "net"
            self._iface(base, "enp0s13f0u2u3", carrier="0", speed="-1")
            self._iface(base, "enp3s0", driver="r8169", carrier="1", speed="1000")
            self._iface(base, "enp4s0", driver="e1000e")  # down: no carrier
            wifi = self._iface(base, "wlp2s0", driver="rtw89_8852be", carrier="1")
            (wifi / "wireless").mkdir()
            (base / "docker0").mkdir()  # virtual: no device link
            links = {link.interface: link for link in detect_wired_links(base)}

        self.assertEqual(set(links), {"enp0s13f0u2u3", "enp3s0", "enp4s0"})
        self.assertIs(links["enp0s13f0u2u3"].carrier, False)
        self.assertEqual(links["enp0s13f0u2u3"].driver, "r8152")
        self.assertIsNone(links["enp0s13f0u2u3"].speed_mbps)
        self.assertIs(links["enp3s0"].carrier, True)
        self.assertEqual(links["enp3s0"].speed_mbps, 1000)
        self.assertIsNone(links["enp4s0"].carrier)


class TestCategoryNormalization(unittest.TestCase):
    def test_normalize(self):
        from core.driver_database import normalize_category

        self.assertEqual(normalize_category("Bluetooth"), "bluetooth")
        self.assertEqual(normalize_category(" WIFI\n"), "wifi")
        self.assertEqual(normalize_category("wireless"), "wifi")
        self.assertEqual(normalize_category("Network"), "other")
        self.assertEqual(normalize_category("banana"), "other")

    def test_loader_normalizes(self):
        from core.driver_database import DriverDatabase

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write(base / "device-ids" / "x" / "category", "Bluetooth")
            _write(base / "device-ids" / "x" / "pkg", "x-dkms\n")
            db = DriverDatabase(assets_dir=base)
        self.assertEqual(db.modules[0].category, "bluetooth")


class TestAssetDatabase(unittest.TestCase):
    """The shipped asset files must only use categories the UI shows."""

    # Firmware categories that have a page (see Window._populate_category_sections)
    _FIRMWARE_PAGES = {
        "wifi",
        "bluetooth",
        "dvb",
        "sound",
        "webcam",
        "touchscreen",
        "printer3d",
        "scanner",
        "other",
    }

    def test_device_id_categories_are_valid(self):
        from core.driver_database import MODULE_CATEGORIES

        for cat_file in sorted((_ASSETS / "device-ids").glob("*/category")):
            raw = cat_file.read_text().strip()
            with self.subTest(module=cat_file.parent.name):
                self.assertIn(raw, MODULE_CATEGORIES)

    def test_firmware_categories_have_pages(self):
        for cat_file in sorted((_ASSETS / "firmware").glob("*/category")):
            with self.subTest(firmware=cat_file.parent.name):
                cats = cat_file.read_text().split()
                self.assertTrue(cats)
                self.assertTrue(set(cats) <= self._FIRMWARE_PAGES, cats)

    def test_text_files_end_with_newline(self):
        for pattern in ("device-ids/*/pkg", "device-ids/*/category"):
            for path in sorted(_ASSETS.glob(pattern)):
                with self.subTest(path=str(path.relative_to(_ASSETS))):
                    data = path.read_bytes()
                    self.assertTrue(data.strip(), "empty file")
                    self.assertTrue(data.endswith(b"\n"))


class TestRepoAvailability(unittest.TestCase):
    def test_mark_repo_availability(self):
        from core.driver_database import DriverModule
        from core.hardware_detect import mark_repo_availability

        in_repo = DriverModule("a", "wifi", "", "broadcom-wl-dkms")
        aur = DriverModule("b", "wifi", "", "rtw89-dkms-git")
        db = MagicMock()
        db.all_entries.return_value = [in_repo, aur]

        mark_repo_availability(db, {"broadcom-wl-dkms"})
        self.assertTrue(in_repo.in_repo)
        self.assertFalse(aur.in_repo)

        mark_repo_availability(db, set())  # pacman query failed
        self.assertIsNone(aur.in_repo)

    def test_missing_dkms_prerequisites(self):
        from core.driver_installer import missing_dkms_prerequisites

        installed = {"linux618", "linux618-headers", "linux72-comm", "linux-firmware"}
        available = {
            "dkms",
            "base-devel",
            "linux618-headers",
            "linux72-comm-headers",
        }
        self.assertEqual(
            missing_dkms_prerequisites(installed, available),
            ["dkms", "base-devel", "linux72-comm-headers"],
        )
        self.assertEqual(
            missing_dkms_prerequisites(installed | available, available), []
        )


class TestDriverInstallerRouting(unittest.TestCase):
    """Repo packages use pacman; AUR ones go to pamac after prerequisites."""

    def _installer(self):
        from core.driver_installer import DriverInstaller

        return DriverInstaller()

    @patch("core.driver_installer.fetch_repo_package_set")
    def test_repo_package_uses_pacman(self, mock_repo):
        mock_repo.return_value = {"broadcom-wl-dkms"}
        inst = self._installer()
        with (
            patch.object(inst, "_run_pacman_command") as run,
            patch.object(inst, "_launch_pamac") as pamac,
        ):
            inst.install_package("broadcom-wl-dkms")
        self.assertIn("broadcom-wl-dkms", run.call_args.kwargs["args"])
        pamac.assert_not_called()

    @patch("core.driver_installer.fetch_installed_set")
    @patch("core.driver_installer.fetch_repo_package_set")
    def test_aur_dkms_installs_prerequisites_then_pamac(self, mock_repo, mock_inst):
        mock_repo.return_value = {"dkms", "base-devel", "linux72-comm-headers"}
        mock_inst.return_value = {"linux72-comm", "base-devel"}
        inst = self._installer()
        with (
            patch.object(inst, "_run_pacman_command") as run,
            patch.object(inst, "_launch_pamac") as pamac,
        ):
            inst.install_package("rtw89-dkms-git")
            args = run.call_args.kwargs["args"]
            self.assertIn("dkms", args)
            self.assertIn("linux72-comm-headers", args)
            pamac.assert_not_called()
            # pacman finished successfully -> pamac builds the AUR package
            run.call_args.kwargs["complete_callback"](True)
        pamac.assert_called_once()
        self.assertEqual(pamac.call_args.args[0], "rtw89-dkms-git")

    @patch("core.driver_installer.fetch_installed_set")
    @patch("core.driver_installer.fetch_repo_package_set")
    def test_failed_prerequisites_skip_pamac(self, mock_repo, mock_inst):
        mock_repo.return_value = {"dkms"}
        mock_inst.return_value = set()
        done = MagicMock()
        inst = self._installer()
        with (
            patch.object(inst, "_run_pacman_command") as run,
            patch.object(inst, "_launch_pamac") as pamac,
        ):
            inst.install_package("rtw89-dkms-git", complete_callback=done)
            run.call_args.kwargs["complete_callback"](False)
        pamac.assert_not_called()
        done.assert_called_once_with(False)

    @patch("core.driver_installer.fetch_repo_package_set")
    def test_aur_non_dkms_goes_straight_to_pamac(self, mock_repo):
        mock_repo.return_value = set()
        inst = self._installer()
        with (
            patch.object(inst, "_run_pacman_command") as run,
            patch.object(inst, "_launch_pamac") as pamac,
        ):
            inst.install_package("some-printer-driver")
        run.assert_not_called()
        pamac.assert_called_once()


class TestCancelAndHints(unittest.TestCase):
    def test_cancel_privileged_process_reports_failure(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        proc = MagicMock()
        proc.poll.return_value = None
        proc.pid = 42
        proc.terminate.side_effect = PermissionError
        mgr._current_process = proc

        self.assertFalse(mgr.cancel_operation())
        self.assertFalse(mgr._cancelled)

    def test_cancel_without_process_succeeds(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        self.assertTrue(mgr.cancel_operation())

    def test_target_not_found_sets_hint(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        mgr._last_output_lines = ["error: target not found: rtw89-dkms-git"]
        out = MagicMock()
        mgr._suggest_error_recovery(out)
        self.assertIsNotNone(mgr.last_error_hint)
        self.assertIn("AUR", mgr.last_error_hint)
        self.assertNotIn("-Sy'", mgr.last_error_hint)  # no partial upgrades


class TestSyncAge(unittest.TestCase):
    def test_uses_last_sync_from_log(self):
        import core.package_manager as pm

        with TemporaryDirectory() as tmp:
            sync = Path(tmp) / "sync"
            sync.mkdir()
            old = time.time() - 40 * 86400
            os.utime(sync, (old, old))
            log = Path(tmp) / "pacman.log"
            recent = time.strftime(
                "%Y-%m-%dT%H:%M:%S-0300", time.localtime(time.time() - 2 * 86400)
            )
            log.write_text(
                "[2020-01-01T10:00:00-0300] [PACMAN] synchronizing package lists\n"
                f"[{recent}] [PACMAN] synchronizing package lists\n"
            )
            with (
                patch.object(pm, "_PACMAN_SYNC_DIR", sync),
                patch.object(pm, "_PACMAN_LOG", log),
            ):
                age = pm.last_sync_age_days()
        self.assertAlmostEqual(age, 2, delta=0.1)

    def test_unknown_when_nothing_readable(self):
        import core.package_manager as pm

        with (
            patch.object(pm, "_PACMAN_SYNC_DIR", Path("/nonexistent/sync")),
            patch.object(pm, "_PACMAN_LOG", Path("/nonexistent/pacman.log")),
        ):
            self.assertIsNone(pm.last_sync_age_days())


class TestRecommendationsAvailability(unittest.TestCase):
    def test_unavailable_packages_are_not_recommended(self):
        from ui.mesa_data import _get_recommendations

        pkg_manager = MagicMock()
        all_missing, _ = _get_recommendations(
            {"amd"}, pkg_manager, "stable", False, installed_set=set()
        )
        self.assertTrue(all_missing)
        keep = all_missing[0]["name"]
        filtered, _ = _get_recommendations(
            {"amd"},
            pkg_manager,
            "stable",
            False,
            installed_set=set(),
            available_set={keep},
        )
        self.assertEqual([p["name"] for p in filtered], [keep])


class TestKernelCoveredDrivers(unittest.TestCase):
    """Third-party drivers are not suggested for devices that already work."""

    def test_suggestion_rules(self):
        from core.driver_database import DriverModule
        from ui.category_page import _covered_by_kernel, _is_suggested

        working = DriverModule("r8152", "ethernet", "", "r8152-dkms")
        working.detected, working.device_has_driver = True, True
        missing = DriverModule("rtl8821cu", "wifi", "", "rtl8821cu-dkms-git")
        missing.detected = True
        absent = DriverModule("mt76", "wifi", "", "mt76-dkms-git")

        self.assertTrue(_covered_by_kernel(working))
        self.assertFalse(_is_suggested(working))
        self.assertTrue(_is_suggested(missing))
        self.assertFalse(_is_suggested(absent))

    def test_confirm_dialog_warns_about_builtin_driver(self):
        from ui.base_page import install_confirm_body
        from utils.i18n import _

        body = install_confirm_body("r8152-dkms", False, "r8152")
        self.assertIn("r8152", body.split("\n\n", 1)[1])
        # Compare with the translated string: the suite runs in any locale
        self.assertEqual(install_confirm_body("x", True), _("Install {}?").format("x"))


class TestNotificationIgnoreList(unittest.TestCase):
    """ "Don't alert again" must also silence hotplug notifications."""

    def _load_dialog(self):
        import importlib.util

        path = _ASSETS.parent / "udev-driver-dialog.py"
        spec = importlib.util.spec_from_file_location("udev_driver_dialog", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_ignored_device_is_detected_case_insensitively(self):
        dlg = self._load_dialog()
        with (
            TemporaryDirectory() as tmp,
            patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}),
        ):
            key = dlg._blacklist_key("device-ids", "0bda", "8153", "r8152-dkms")
            self.assertFalse(dlg._is_blacklisted(key))
            dlg._save_blacklist(["0BDA:8153"])
            self.assertTrue(dlg._is_blacklisted(key))
            other = dlg._blacklist_key("device-ids", "0BDA", "8179", "x")
            self.assertFalse(dlg._is_blacklisted(other))

    def test_firmware_key_uses_package(self):
        dlg = self._load_dialog()
        self.assertEqual(
            dlg._blacklist_key("firmware", "0000", "0000", "b43-firmware"),
            "fw:b43-firmware",
        )


if __name__ == "__main__":
    unittest.main()
