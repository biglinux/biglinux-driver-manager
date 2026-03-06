#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for driver database, hardware detection, and driver installer modules.
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from tempfile import TemporaryDirectory

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "usr", "share", "big-driver-manager"),
)


class TestDriverDatabase(unittest.TestCase):
    """Tests for DriverDatabase loading."""

    def _make_temp_db(self):
        """Create a minimal database structure in a temp dir."""
        tmpdir = TemporaryDirectory()
        base = Path(tmpdir.name)

        # device-ids module
        mod_dir = base / "device-ids" / "test-wifi"
        mod_dir.mkdir(parents=True)
        (mod_dir / "category").write_text("wifi\n")
        (mod_dir / "description").write_text("Test WiFi driver\n")
        (mod_dir / "pkg").write_text("test-wifi-pkg\n")
        (mod_dir / "usb.ids").write_text("0BDA:8178\n0BDA:8179\n")

        # firmware entry
        fw_dir = base / "firmware" / "test-firmware"
        fw_dir.mkdir(parents=True)
        (fw_dir / "category").write_text("wifi\n")
        (fw_dir / "description").write_text("Test firmware\n")
        (fw_dir / "test-firmware").write_text("/usr/lib/firmware/test.fw\n")

        # printer entry
        pr_dir = base / "printer" / "test-printer"
        pr_dir.mkdir(parents=True)
        (pr_dir / "description").write_text("Test printer driver\n")

        # scanner entry
        sc_dir = base / "scanner" / "test-scanner"
        sc_dir.mkdir(parents=True)
        (sc_dir / "description").write_text("Test scanner driver\n")

        return tmpdir, base

    def test_load_device_ids(self):
        tmpdir, base = self._make_temp_db()
        with tmpdir:
            from core.driver_database import DriverDatabase

            db = DriverDatabase(assets_dir=base)
            self.assertEqual(len(db.modules), 1)
            mod = db.modules[0]
            self.assertEqual(mod.name, "test-wifi")
            self.assertEqual(mod.category, "wifi")
            self.assertEqual(mod.package, "test-wifi-pkg")
            self.assertEqual(len(mod.usb_ids), 2)
            self.assertEqual(mod.usb_ids[0], ("0BDA", "8178"))

    def test_load_firmware(self):
        tmpdir, base = self._make_temp_db()
        with tmpdir:
            from core.driver_database import DriverDatabase

            db = DriverDatabase(assets_dir=base)
            self.assertEqual(len(db.firmware), 1)
            fw = db.firmware[0]
            self.assertEqual(fw.name, "test-firmware")
            self.assertEqual(fw.firmware_files, ["/usr/lib/firmware/test.fw"])

    def test_load_printers(self):
        tmpdir, base = self._make_temp_db()
        with tmpdir:
            from core.driver_database import DriverDatabase

            db = DriverDatabase(assets_dir=base)
            self.assertEqual(len(db.printers), 1)
            self.assertEqual(db.printers[0].name, "test-printer")

    def test_load_scanners(self):
        tmpdir, base = self._make_temp_db()
        with tmpdir:
            from core.driver_database import DriverDatabase

            db = DriverDatabase(assets_dir=base)
            self.assertEqual(len(db.scanners), 1)
            self.assertEqual(db.scanners[0].name, "test-scanner")

    def test_get_modules_by_category(self):
        tmpdir, base = self._make_temp_db()
        with tmpdir:
            from core.driver_database import DriverDatabase

            db = DriverDatabase(assets_dir=base)
            wifi = db.get_modules_by_category("wifi")
            self.assertEqual(len(wifi), 1)
            other = db.get_modules_by_category("ethernet")
            self.assertEqual(len(other), 0)

    def test_get_all_categories(self):
        tmpdir, base = self._make_temp_db()
        with tmpdir:
            from core.driver_database import DriverDatabase

            db = DriverDatabase(assets_dir=base)
            cats = db.get_all_categories()
            self.assertEqual(cats, ["wifi"])

    def test_empty_database(self):
        tmpdir = TemporaryDirectory()
        with tmpdir:
            from core.driver_database import DriverDatabase

            db = DriverDatabase(assets_dir=Path(tmpdir.name))
            self.assertEqual(len(db.modules), 0)
            self.assertEqual(len(db.firmware), 0)
            self.assertEqual(len(db.printers), 0)
            self.assertEqual(len(db.scanners), 0)

    def test_parse_ids_comma_separated(self):
        tmpdir = TemporaryDirectory()
        base = Path(tmpdir.name)
        with tmpdir:
            mod_dir = base / "device-ids" / "combo"
            mod_dir.mkdir(parents=True)
            (mod_dir / "category").write_text("wifi")
            (mod_dir / "description").write_text("")
            (mod_dir / "pkg").write_text("combo-pkg")
            (mod_dir / "pci.ids").write_text("1234:5678,ABCD:EF01\n")
            from core.driver_database import DriverDatabase

            db = DriverDatabase(assets_dir=base)
            self.assertEqual(len(db.modules[0].pci_ids), 2)


class TestHardwareDetect(unittest.TestCase):
    """Tests for hardware detection functions."""

    @patch("core.hardware_detect._run")
    def test_detect_pci_devices(self, mock_run):
        mock_run.return_value = (
            "00:02.0 VGA compatible controller [0300]: Intel Corp Device [8086:5917] (rev 04)\n"
            "01:00.0 Network controller [0280]: Qualcomm Atheros Device [168C:003E] (rev 32)\n"
        )
        from core.hardware_detect import detect_pci_devices

        devices = detect_pci_devices()
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0].vendor_id, "8086")
        self.assertEqual(devices[0].device_id, "5917")
        self.assertEqual(devices[0].bus, "pci")

    @patch("core.hardware_detect._run")
    def test_detect_usb_devices(self, mock_run):
        mock_run.return_value = (
            "Bus 001 Device 003: ID 0bda:8178 Realtek Semiconductor Corp. RTL8192CU\n"
            "Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub\n"
        )
        from core.hardware_detect import detect_usb_devices

        devices = detect_usb_devices()
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0].vendor_id, "0BDA")
        self.assertEqual(devices[0].device_id, "8178")
        self.assertEqual(devices[0].name, "Realtek Semiconductor Corp. RTL8192CU")

    @patch("core.hardware_detect._run")
    def test_detect_missing_firmware(self, mock_run):
        mock_run.return_value = (
            "[    1.234] Direct firmware load for rtl_nic/rtl8125a-3.fw failed\n"
            "[    2.345] firmware: failed to load iwlwifi-QuZ-a0-hr-b0-77.ucode\n"
        )
        from core.hardware_detect import detect_missing_firmware

        missing = detect_missing_firmware()
        self.assertEqual(len(missing), 2)
        self.assertIn("/usr/lib/firmware/rtl_nic/rtl8125a-3.fw", missing)
        self.assertIn("/usr/lib/firmware/iwlwifi-QuZ-a0-hr-b0-77.ucode", missing)

    @patch("core.hardware_detect.check_installed_packages")
    @patch("core.hardware_detect.detect_all_devices")
    def test_match_modules(self, mock_devices, mock_installed):
        from core.hardware_detect import match_modules, DetectedDevice
        from core.driver_database import DriverModule

        mock_devices.return_value = [
            DetectedDevice(
                bus="usb", vendor_id="0BDA", device_id="8178", name="RTL8192CU"
            )
        ]
        mock_installed.return_value = {"test-pkg": False}

        # Create a minimal database mock
        db = MagicMock()
        mod = DriverModule(
            name="test-wifi",
            category="wifi",
            description="Test",
            package="test-pkg",
            usb_ids=[("0BDA", "8178")],
        )
        db.modules = [mod]

        matched = match_modules(db, mock_devices.return_value)
        self.assertEqual(len(matched), 1)
        self.assertTrue(matched[0].detected)
        self.assertEqual(matched[0].detected_device_name, "RTL8192CU")

    @patch("core.hardware_detect.check_installed_packages")
    def test_match_firmware(self, mock_installed):
        from core.hardware_detect import match_firmware
        from core.driver_database import FirmwareEntry

        mock_installed.return_value = {"test-fw": True}

        db = MagicMock()
        fw = FirmwareEntry(
            name="test-fw",
            category="wifi",
            description="Test",
            package="test-fw",
            firmware_files=["/usr/lib/firmware/test.fw"],
        )
        db.firmware = [fw]

        matched = match_firmware(db, {"/usr/lib/firmware/test.fw"})
        self.assertEqual(len(matched), 1)
        self.assertTrue(matched[0].detected)
        self.assertTrue(matched[0].installed)

    @patch("core.hardware_detect._run")
    def test_check_installed_packages(self, mock_run):
        mock_run.return_value = "mesa\nlinux\nbase\n"
        from core.hardware_detect import check_installed_packages

        result = check_installed_packages(["mesa", "nvidia", "linux"])
        self.assertTrue(result["mesa"])
        self.assertFalse(result["nvidia"])
        self.assertTrue(result["linux"])


class TestDriverInstaller(unittest.TestCase):
    """Tests for DriverInstaller."""

    def test_inherits_base_manager(self):
        with patch("core.driver_installer.get_logger"):
            from core.driver_installer import DriverInstaller
            from core.base_manager import BaseManager

            installer = DriverInstaller()
            self.assertIsInstance(installer, BaseManager)

    @patch("core.base_manager.BaseManager._run_pacman_command")
    def test_install_package_calls_pacman(self, mock_run):
        with patch("core.driver_installer.get_logger"):
            from core.driver_installer import DriverInstaller

            installer = DriverInstaller()
            installer.install_package("test-pkg")
            mock_run.assert_called_once()
            args = mock_run.call_args[1]["args"]
            self.assertIn("-S", args)
            self.assertIn("test-pkg", args)

    @patch("core.base_manager.BaseManager._run_pacman_command")
    def test_remove_package_calls_pacman(self, mock_run):
        with patch("core.driver_installer.get_logger"):
            from core.driver_installer import DriverInstaller

            installer = DriverInstaller()
            installer.remove_package("test-pkg")
            mock_run.assert_called_once()
            args = mock_run.call_args[1]["args"]
            self.assertIn("-R", args)
            self.assertIn("test-pkg", args)


class TestNetworkPrinterDiscovery(unittest.TestCase):
    """Tests for mDNS network printer discovery and matching."""

    def test_parse_avahi_output_extracts_printer(self):
        from core.hardware_detect import _parse_avahi_output

        avahi_output = (
            "+;eth0;IPv4;Brother MFC-J480DW;_ipp._tcp;local\n"
            "=;eth0;IPv4;Brother MFC-J480DW;_ipp._tcp;local;"
            "mfc-j480dw.local;192.168.1.50;631;"
            '"ty=Brother MFC-J480DW" "usb_MFG=Brother" "usb_MDL=MFC-J480DW"\n'
        )
        printers = _parse_avahi_output(avahi_output, "_ipp._tcp")
        self.assertEqual(len(printers), 1)
        p = printers[0]
        self.assertEqual(p.manufacturer, "Brother")
        self.assertEqual(p.model, "MFC-J480DW")
        self.assertEqual(p.ip, "192.168.1.50")

    def test_parse_avahi_output_guesses_manufacturer_from_name(self):
        from core.hardware_detect import _parse_avahi_output

        avahi_output = (
            "=;wlan0;IPv4;Epson L3150;_ipp._tcp;local;"
            'epson-l3150.local;192.168.1.60;631;"ty=Epson L3150"\n'
        )
        printers = _parse_avahi_output(avahi_output, "_ipp._tcp")
        self.assertEqual(len(printers), 1)
        self.assertEqual(printers[0].manufacturer, "Epson")
        self.assertEqual(printers[0].model, "Epson L3150")

    def test_parse_avahi_output_empty(self):
        from core.hardware_detect import _parse_avahi_output

        printers = _parse_avahi_output("", "_ipp._tcp")
        self.assertEqual(printers, [])

    def test_match_network_printers_detects_correct_packages(self):
        from core.driver_database import PeripheralEntry
        from core.hardware_detect import NetworkPrinter, match_network_printers

        db = MagicMock()
        db.printers = [
            PeripheralEntry(
                name="brother-mfc-j480dw",
                description="Brother MFC-J480DW",
                package="brother-mfc-j480dw",
                detected=False,
            ),
            PeripheralEntry(
                name="epson-l3150",
                description="Epson L3150",
                package="epson-inkjet-printer-escpr",
                detected=False,
            ),
            PeripheralEntry(
                name="canon-mg3600",
                description="Canon MG3600",
                package="cnijfilter2",
                detected=False,
            ),
        ]

        net_printers = [
            NetworkPrinter(
                name="Brother MFC-J480DW",
                manufacturer="Brother",
                model="MFC-J480DW",
                ip="192.168.1.50",
                service_type="_ipp._tcp",
            ),
        ]

        newly = match_network_printers(db, net_printers)
        self.assertTrue(db.printers[0].detected)
        self.assertFalse(db.printers[1].detected)
        self.assertFalse(db.printers[2].detected)
        self.assertEqual(newly, 1)

    def test_match_network_printers_empty(self):
        from core.hardware_detect import match_network_printers

        db = MagicMock()
        db.printers = []
        result = match_network_printers(db, [])
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
