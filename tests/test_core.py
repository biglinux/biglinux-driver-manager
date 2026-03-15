#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Test Suite

Unit tests for core functionality covering:
- Mesa driver detection and _is_real_package_installed
- _get_active_driver logic
- Kernel package identification (_is_kernel_package)
- Kernel flag assignment (_add_kernel_flags)
- LTS version fetching with urllib
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add the application source to path
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "usr", "share", "big-driver-manager"),
)


class TestIsRealPackageInstalled(unittest.TestCase):
    """Tests for MesaManager._is_real_package_installed."""

    def _make_manager(self):
        with patch("core.mesa_manager.get_logger"):
            from core.mesa_manager import MesaManager

            return MesaManager()

    @patch("subprocess.run")
    def test_exact_match_returns_true(self, mock_run):
        """Package name matches exactly -> True."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Name            : mesa-tkg-stable\nVersion         : 24.3.4-1\n",
        )
        mgr = self._make_manager()
        self.assertTrue(mgr._is_real_package_installed("mesa-tkg-stable"))

    @patch("subprocess.run")
    def test_virtual_provides_returns_false(self, mock_run):
        """Query for 'mesa' but Name is mesa-tkg-stable -> False."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Name            : mesa-tkg-stable\nVersion         : 24.3.4-1\n",
        )
        mgr = self._make_manager()
        self.assertFalse(mgr._is_real_package_installed("mesa"))

    @patch("subprocess.run")
    def test_not_installed_returns_false(self, mock_run):
        """Package not installed (returncode != 0) -> False."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        mgr = self._make_manager()
        self.assertFalse(mgr._is_real_package_installed("mesa-tkg-git"))

    @patch("subprocess.run")
    def test_lang_c_is_forced(self, mock_run):
        """Verify LANG=C is set in subprocess environment."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        mgr = self._make_manager()
        mgr._is_real_package_installed("mesa")

        call_kwargs = mock_run.call_args
        env = call_kwargs.kwargs.get("env") or call_kwargs[1].get("env")
        self.assertEqual(env.get("LANG"), "C")

    @patch("subprocess.run")
    def test_no_name_field_returns_false(self, mock_run):
        """Output has no Name field -> False."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Version         : 24.3.4-1\nDescription     : Mesa\n"
        )
        mgr = self._make_manager()
        self.assertFalse(mgr._is_real_package_installed("mesa"))


class TestGetActiveDriver(unittest.TestCase):
    """Tests for MesaManager._get_active_driver."""

    def _make_manager(self):
        with patch("core.mesa_manager.get_logger"):
            from core.mesa_manager import MesaManager

            return MesaManager()

    @patch("subprocess.run")
    def test_tkg_stable_detected(self, mock_run):
        """When mesa-tkg-stable is installed, returns 'tkg-stable'."""

        def side_effect(cmd, **kwargs):
            pkg = cmd[2]
            if pkg == "mesa-tkg-stable":
                return MagicMock(
                    returncode=0,
                    stdout=f"Name            : {pkg}\nVersion         : 24.3.4-1\n",
                )
            return MagicMock(returncode=1, stdout="")

        mock_run.side_effect = side_effect
        mgr = self._make_manager()
        self.assertEqual(mgr._get_active_driver(), "tkg-stable")

    @patch("subprocess.run")
    def test_stable_detected(self, mock_run):
        """When only mesa is installed, returns 'stable'."""

        def side_effect(cmd, **kwargs):
            pkg = cmd[2]
            if pkg == "mesa":
                return MagicMock(
                    returncode=0,
                    stdout=f"Name            : {pkg}\nVersion         : 24.3.4-1\n",
                )
            return MagicMock(returncode=1, stdout="")

        mock_run.side_effect = side_effect
        mgr = self._make_manager()
        self.assertEqual(mgr._get_active_driver(), "stable")

    @patch("subprocess.run")
    def test_fallback_to_stable(self, mock_run):
        """When no driver is detected, falls back to 'stable'."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        mgr = self._make_manager()
        self.assertEqual(mgr._get_active_driver(), "stable")


class TestIsKernelPackage(unittest.TestCase):
    """Tests for KernelManager._is_kernel_package."""

    def _make_manager(self):
        with patch("core.kernel_manager.get_logger"):
            from core.kernel_manager import KernelManager

            mgr = KernelManager()
            # Force LTS versions to avoid network call
            mgr._lts_versions = ["66", "612", "614"]
            return mgr

    def test_standard_kernel(self):
        mgr = self._make_manager()
        self.assertTrue(mgr._is_kernel_package("linux612"))
        self.assertTrue(mgr._is_kernel_package("linux66"))
        self.assertTrue(mgr._is_kernel_package("linux"))

    def test_lts_kernel(self):
        mgr = self._make_manager()
        self.assertTrue(mgr._is_kernel_package("linux-lts"))
        self.assertTrue(mgr._is_kernel_package("linux612-lts"))

    def test_xanmod_kernel(self):
        mgr = self._make_manager()
        self.assertTrue(mgr._is_kernel_package("linux-xanmod"))
        self.assertTrue(mgr._is_kernel_package("linux612-xanmod"))

    def test_cachyos_kernel(self):
        mgr = self._make_manager()
        self.assertTrue(mgr._is_kernel_package("linux-cachyos"))
        self.assertTrue(mgr._is_kernel_package("linux-cachyos-lts"))

    def test_excludes_cachyos_modules(self):
        mgr = self._make_manager()
        self.assertFalse(mgr._is_kernel_package("linux-cachyos-headers"))

    def test_rt_kernel(self):
        mgr = self._make_manager()
        self.assertTrue(mgr._is_kernel_package("linux612-rt"))

    def test_excludes_modules(self):
        mgr = self._make_manager()
        self.assertFalse(mgr._is_kernel_package("linux612-headers"))
        self.assertFalse(mgr._is_kernel_package("linux612-nvidia"))
        self.assertFalse(mgr._is_kernel_package("linux612-virtualbox"))
        self.assertFalse(mgr._is_kernel_package("linux612-zfs"))

    def test_excludes_non_kernel(self):
        mgr = self._make_manager()
        self.assertFalse(mgr._is_kernel_package("python"))
        self.assertFalse(mgr._is_kernel_package("mesa"))


class TestAddKernelFlags(unittest.TestCase):
    """Tests for KernelManager._add_kernel_flags."""

    def _make_manager(self):
        with patch("core.kernel_manager.get_logger"):
            from core.kernel_manager import KernelManager

            mgr = KernelManager()
            mgr._lts_versions = ["66", "612", "614"]
            return mgr

    def test_rt_flag(self):
        mgr = self._make_manager()
        kernel = {"name": "linux612-rt", "version": "6.12.10-1"}
        mgr._add_kernel_flags(kernel)
        self.assertTrue(kernel.get("rt"))

    def test_explicit_lts_flag(self):
        mgr = self._make_manager()
        kernel = {"name": "linux-lts", "version": "6.6.70-1"}
        mgr._add_kernel_flags(kernel)
        self.assertTrue(kernel.get("lts"))

    def test_implicit_lts_flag_from_version_list(self):
        mgr = self._make_manager()
        kernel = {"name": "linux66", "version": "6.6.70-1"}
        mgr._add_kernel_flags(kernel)
        self.assertTrue(kernel.get("lts"))

    def test_non_lts_kernel_no_flag(self):
        mgr = self._make_manager()
        kernel = {"name": "linux613", "version": "6.13.1-1"}
        mgr._add_kernel_flags(kernel)
        self.assertFalse(kernel.get("lts", False))

    def test_xanmod_flag(self):
        mgr = self._make_manager()
        kernel = {"name": "linux-xanmod", "version": "6.12.10-1"}
        mgr._add_kernel_flags(kernel)
        self.assertTrue(kernel.get("xanmod"))

    def test_optimized_flag(self):
        mgr = self._make_manager()
        kernel = {"name": "linux-xanmod-x64v3", "version": "6.12.10-1"}
        mgr._add_kernel_flags(kernel)
        self.assertTrue(kernel.get("optimized"))
        self.assertEqual(kernel.get("opt_level"), "3")

    def test_xanmod_not_flagged_as_lts(self):
        """Xanmod kernels should not get implicit LTS flag."""
        mgr = self._make_manager()

    def test_cachyos_flag(self):
        mgr = self._make_manager()
        kernel = {"name": "linux-cachyos", "version": "6.19.8-1"}
        mgr._add_kernel_flags(kernel)
        self.assertTrue(kernel.get("cachyos"))
        self.assertFalse(kernel.get("lts", False))

    def test_cachyos_lts_flag(self):
        mgr = self._make_manager()
        kernel = {"name": "linux-cachyos-lts", "version": "6.18.18-1"}
        mgr._add_kernel_flags(kernel)
        self.assertTrue(kernel.get("cachyos"))
        self.assertTrue(kernel.get("lts"))
        kernel = {"name": "linux-xanmod", "version": "6.12.10-1"}
        mgr._add_kernel_flags(kernel)
        self.assertFalse(kernel.get("lts", False))


class TestGetLtsKernelVersions(unittest.TestCase):
    """Tests for KernelManager._get_lts_kernel_versions with urllib."""

    def _make_manager(self):
        with patch("core.kernel_manager.get_logger"):
            from core.kernel_manager import KernelManager

            mgr = KernelManager()
            return mgr

    @patch("core.kernel_manager.urlopen")
    def test_parses_lts_versions(self, mock_urlopen):
        """Verify LTS versions are parsed from XML feed."""
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss><channel>
  <item><title>6.12.10: longterm</title></item>
  <item><title>6.6.70: longterm</title></item>
  <item><title>6.14.1: mainline</title></item>
  <item><title>6.1.120: longterm</title></item>
</channel></rss>"""

        mock_response = MagicMock()
        mock_response.read.return_value = xml
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        mgr = self._make_manager()
        versions = mgr._get_lts_kernel_versions()
        self.assertIn("612", versions)
        self.assertIn("66", versions)
        self.assertIn("61", versions)
        self.assertNotIn("614", versions)  # mainline, not longterm

    @patch("core.kernel_manager.urlopen")
    def test_fallback_on_error(self, mock_urlopen):
        """On network error, returns DEFAULT_LTS_VERSIONS."""
        mock_urlopen.side_effect = OSError("Connection refused")
        mgr = self._make_manager()
        versions = mgr._get_lts_kernel_versions()
        from core.constants import DEFAULT_LTS_VERSIONS

        self.assertEqual(versions, DEFAULT_LTS_VERSIONS)


class TestPackageManager(unittest.TestCase):
    """Tests for PackageManager methods."""

    @patch("subprocess.run")
    def test_is_package_installed_true(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        from core.package_manager import PackageManager

        pm = PackageManager()
        self.assertTrue(pm.is_package_installed("linux612"))

    @patch("subprocess.run")
    def test_is_package_installed_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        from core.package_manager import PackageManager

        pm = PackageManager()
        self.assertFalse(pm.is_package_installed("linux999"))

    @patch("subprocess.run")
    def test_get_installed_packages(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="linux612 6.12.10-1\nmesa 24.3.4-1\n"
        )
        from core.package_manager import PackageManager

        pm = PackageManager()
        packages = pm.get_installed_packages()
        self.assertEqual(len(packages), 2)
        self.assertEqual(packages[0]["name"], "linux612")
        self.assertEqual(packages[0]["version"], "6.12.10-1")
        self.assertEqual(packages[1]["name"], "mesa")


class TestParseProgress(unittest.TestCase):
    """Tests for BaseManager._parse_progress."""

    def _make_manager(self):
        from core.base_manager import BaseManager

        return BaseManager()

    def test_download_percentage(self):
        mgr = self._make_manager()
        progress, text = mgr._parse_progress("Downloading linux612 (50%)", 0.1)
        self.assertAlmostEqual(progress, 0.1 + 0.5 * 0.4)
        self.assertIsNotNone(text)

    def test_download_fraction(self):
        mgr = self._make_manager()
        progress, text = mgr._parse_progress("downloading packages (2/4)...", 0.1)
        self.assertAlmostEqual(progress, 0.1 + 0.5 * 0.4)
        self.assertIsNotNone(text)

    def test_installing_phase(self):
        mgr = self._make_manager()
        progress, text = mgr._parse_progress("installing linux612...", 0.3)
        self.assertEqual(progress, 0.5)
        self.assertIsNotNone(text)

    def test_installing_does_not_decrease(self):
        mgr = self._make_manager()
        progress, _text = mgr._parse_progress("installing linux612...", 0.7)
        self.assertEqual(progress, 0.7)

    def test_removing_phase(self):
        mgr = self._make_manager()
        progress, text = mgr._parse_progress("removing linux612...", 0.3)
        self.assertEqual(progress, 0.5)
        self.assertIsNotNone(text)

    def test_post_transaction_hooks(self):
        mgr = self._make_manager()
        progress, text = mgr._parse_progress("running post-transaction hooks...", 0.5)
        self.assertEqual(progress, 0.8)
        self.assertIsNotNone(text)

    def test_grub_configuration(self):
        mgr = self._make_manager()
        progress, text = mgr._parse_progress(
            "Generating grub configuration file...", 0.8
        )
        self.assertEqual(progress, 0.9)
        self.assertIsNotNone(text)

    def test_checking_dependencies(self):
        mgr = self._make_manager()
        progress, text = mgr._parse_progress("checking dependencies...", 0.1)
        self.assertEqual(progress, 0.2)
        self.assertIsNotNone(text)

    def test_checking_file_conflicts(self):
        mgr = self._make_manager()
        progress, text = mgr._parse_progress("checking for file conflicts...", 0.2)
        self.assertEqual(progress, 0.4)
        self.assertIsNotNone(text)

    def test_synchronizing_databases(self):
        mgr = self._make_manager()
        progress, text = mgr._parse_progress("synchronizing package databases...", 0.0)
        self.assertEqual(progress, 0.1)
        self.assertIsNotNone(text)

    def test_unrecognized_line_keeps_current(self):
        mgr = self._make_manager()
        progress, text = mgr._parse_progress("some random output", 0.42)
        self.assertEqual(progress, 0.42)
        self.assertIsNone(text)

    def test_download_no_percent_no_fraction(self):
        mgr = self._make_manager()
        progress, text = mgr._parse_progress("downloading packages...", 0.15)
        self.assertEqual(progress, 0.15)
        self.assertIsNone(text)


class TestSettingsManager(unittest.TestCase):
    """Tests for SettingsManager load/save roundtrip."""

    def setUp(self):
        import tempfile

        self._tmpdir = tempfile.mkdtemp()
        self._settings_file = os.path.join(self._tmpdir, "settings.json")
        self._patch_dir = patch("ui.application.CONFIG_DIR", self._tmpdir)
        self._patch_file = patch("ui.application.SETTINGS_FILE", self._settings_file)
        self._patch_dir.start()
        self._patch_file.start()

    def tearDown(self):
        import shutil

        self._patch_file.stop()
        self._patch_dir.stop()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _make_manager(self):
        from ui.application import SettingsManager

        return SettingsManager()

    def test_save_and_load(self):
        mgr = self._make_manager()
        mgr._settings["show_warning"] = False
        mgr._save_settings()

        mgr2 = self._make_manager()
        self.assertFalse(mgr2.get("show_warning"))

    def test_default_value(self):
        mgr = self._make_manager()
        self.assertIsNone(mgr.get("show_warning"))

    def test_get_with_default(self):
        mgr = self._make_manager()
        mgr._settings["key1"] = "value1"

        self.assertEqual(mgr.get("key1"), "value1")
        self.assertEqual(mgr.get("nonexistent", "fallback"), "fallback")

    def test_set_persists(self):
        mgr = self._make_manager()
        result = mgr.set("theme", "dark")
        self.assertTrue(result)

        mgr2 = self._make_manager()
        self.assertEqual(mgr2.get("theme"), "dark")

    def test_load_corrupted_file(self):
        with open(self._settings_file, "w") as f:
            f.write("{invalid json")

        mgr = self._make_manager()
        self.assertEqual(mgr._settings, {})


class TestProgressDialogGetLineTag(unittest.TestCase):
    """Tests for ProgressDialog._get_line_tag."""

    def _make_dialog(self):
        """Create a minimal ProgressDialog-like object with the tag method."""
        # Import only the class attributes we need without GTK initialization
        from ui.progress_dialog import ProgressDialog

        # Access the static tag maps via the class directly
        class FakeDialog:
            _PREFIX_TAGS = ProgressDialog._PREFIX_TAGS
            _KEYWORD_TAGS = ProgressDialog._KEYWORD_TAGS
            _STARTSWITH_TAGS = ProgressDialog._STARTSWITH_TAGS
            _get_line_tag = ProgressDialog._get_line_tag

        return FakeDialog()

    def test_error_emoji(self):
        d = self._make_dialog()
        self.assertEqual(d._get_line_tag("❌ Operation failed"), "error")

    def test_success_emoji(self):
        d = self._make_dialog()
        self.assertEqual(d._get_line_tag("✅ Done!"), "success")

    def test_warning_emoji(self):
        d = self._make_dialog()
        self.assertEqual(d._get_line_tag("⚠️ Caution"), "warning")

    def test_error_keyword(self):
        d = self._make_dialog()
        self.assertEqual(d._get_line_tag("error: target not found"), "error")

    def test_success_keyword(self):
        d = self._make_dialog()
        self.assertEqual(d._get_line_tag("installed successfully"), "success")

    def test_info_prefix(self):
        d = self._make_dialog()
        self.assertEqual(d._get_line_tag("Installing linux612..."), "info")

    def test_dim_prefix(self):
        d = self._make_dialog()
        self.assertEqual(d._get_line_tag(":: Processing package changes..."), "dim")

    def test_no_tag(self):
        d = self._make_dialog()
        self.assertIsNone(d._get_line_tag("random output line"))


class TestRetryableError(unittest.TestCase):
    """Tests for BaseManager._is_retryable_error."""

    def test_lock_error_is_retryable(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        mgr._last_output_lines = [
            "error: failed to init transaction (unable to lock database)",
            "error: could not lock database: File exists",
        ]
        self.assertTrue(mgr._is_retryable_error())

    def test_no_lock_error_not_retryable(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        mgr._last_output_lines = [
            "error: target not found: linux999",
        ]
        self.assertFalse(mgr._is_retryable_error())

    def test_empty_output_not_retryable(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        mgr._last_output_lines = []
        self.assertFalse(mgr._is_retryable_error())

    def test_no_output_attr_not_retryable(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        self.assertFalse(mgr._is_retryable_error())


class TestRetryDelays(unittest.TestCase):
    """Tests for BaseManager retry delay configuration."""

    def test_retry_delays_are_increasing(self):
        from core.base_manager import BaseManager

        delays = BaseManager._RETRY_DELAYS
        self.assertEqual(len(delays), 2)
        self.assertLess(delays[0], delays[1])

    def test_retry_delays_values(self):
        from core.base_manager import BaseManager

        self.assertEqual(BaseManager._RETRY_DELAYS, (5, 10))


# ======================================================================
# MHWD Manager tests
# ======================================================================


class TestMhwdManager(unittest.TestCase):
    """Tests for MhwdManager parsing and conflict detection."""

    def _make_manager(self):
        with patch("core.mhwd_manager.get_logger"):
            from core.mhwd_manager import MhwdManager

            return MhwdManager()

    SAMPLE_LA_OUTPUT = """> All PCI configs:
--------------------------------------------------------------------------------
                  NAME               VERSION          FREEDRIVER           TYPE
--------------------------------------------------------------------------------
          video-nvidia            2025.09.29               false            PCI
    video-nvidia-570xx            2025.09.29               false            PCI
           video-linux            2024.05.06                true            PCI
     video-modesetting            2020.01.13                true            PCI
     network-r8168            2023.09.12                true            PCI

Warning: No USB configs found!
"""

    @patch("subprocess.run")
    def test_parse_all_drivers(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=self.SAMPLE_LA_OUTPUT)
        mgr = self._make_manager()
        drivers = mgr.get_all_drivers()
        self.assertEqual(len(drivers), 5)
        names = [d.name for d in drivers]
        self.assertIn("video-nvidia", names)
        self.assertIn("video-linux", names)
        self.assertIn("network-r8168", names)

    @patch("subprocess.run")
    def test_driver_categories(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=self.SAMPLE_LA_OUTPUT)
        mgr = self._make_manager()
        drivers = mgr.get_all_drivers()
        nvidia = next(d for d in drivers if d.name == "video-nvidia")
        r8168 = next(d for d in drivers if d.name == "network-r8168")
        self.assertEqual(nvidia.category, "video")
        self.assertEqual(r8168.category, "network")

    @patch("subprocess.run")
    def test_free_driver_flag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=self.SAMPLE_LA_OUTPUT)
        mgr = self._make_manager()
        drivers = mgr.get_all_drivers()
        nvidia = next(d for d in drivers if d.name == "video-nvidia")
        linux = next(d for d in drivers if d.name == "video-linux")
        self.assertFalse(nvidia.free_driver)
        self.assertTrue(linux.free_driver)

    @patch("subprocess.run")
    def test_is_nvidia_property(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=self.SAMPLE_LA_OUTPUT)
        mgr = self._make_manager()
        drivers = mgr.get_all_drivers()
        nvidia = next(d for d in drivers if d.name == "video-nvidia")
        linux = next(d for d in drivers if d.name == "video-linux")
        self.assertTrue(nvidia.is_nvidia)
        self.assertFalse(linux.is_nvidia)

    def test_nvidia_conflict_detection(self):
        mgr = self._make_manager()
        from core.mhwd_manager import MhwdDriver

        installed_nvidia = MhwdDriver(
            name="video-nvidia",
            version="2025",
            free_driver=False,
            bus_type="PCI",
            installed=True,
        )
        with patch.object(
            mgr, "get_installed_drivers", return_value=[installed_nvidia]
        ):
            allowed, reason = mgr.can_install_nvidia("video-nvidia-570xx")
            self.assertFalse(allowed)
            self.assertIn("video-nvidia", reason)

    def test_nvidia_same_driver_allowed(self):
        mgr = self._make_manager()
        from core.mhwd_manager import MhwdDriver

        installed = MhwdDriver(
            name="video-nvidia",
            version="2025",
            free_driver=False,
            bus_type="PCI",
            installed=True,
        )
        with patch.object(mgr, "get_installed_drivers", return_value=[installed]):
            allowed, _ = mgr.can_install_nvidia("video-nvidia")
            self.assertTrue(allowed)

    def test_non_nvidia_always_allowed(self):
        mgr = self._make_manager()
        allowed, _ = mgr.can_install_nvidia("video-linux")
        self.assertTrue(allowed)

    @patch("subprocess.run")
    def test_display_name(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=self.SAMPLE_LA_OUTPUT)
        mgr = self._make_manager()
        drivers = mgr.get_all_drivers()
        nvidia570 = next(d for d in drivers if d.name == "video-nvidia-570xx")
        self.assertEqual(nvidia570.display_name, "video nvidia 570xx")

    SAMPLE_DETAILED_OUTPUT = """--------------------------------------------------------------------------------
> PCI Device: /devices/pci0000:00/0000:01:00.0 (0300:10de:2182)
  Display controller nVidia Corporation TU116 [GeForce GTX 1660 Ti]
--------------------------------------------------------------------------------
  > INSTALLED:

   NAME:        video-nvidia
   ATTACHED:    PCI
   VERSION:     2025.09.29
   INFO:        Closed source NVIDIA drivers for linux.
   PRIORITY:    7
   FREEDRIVER:  false

  > AVAILABLE:

   NAME:        video-nvidia-570xx
   ATTACHED:    PCI
   VERSION:     2025.09.29
   INFO:        Closed source NVIDIA 570xx drivers for linux.
   PRIORITY:    5
   FREEDRIVER:  false

"""

    @patch("subprocess.run")
    def test_parse_detailed(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout=self.SAMPLE_DETAILED_OUTPUT
        )
        mgr = self._make_manager()
        devices = mgr.get_detailed_devices()
        self.assertEqual(len(devices), 1)
        dev = devices[0]
        self.assertEqual(dev.class_id, "0300")
        self.assertIn("nVidia", dev.description)
        self.assertEqual(len(dev.installed_configs), 1)
        self.assertEqual(dev.installed_configs[0].name, "video-nvidia")
        self.assertEqual(len(dev.available_configs), 1)
        self.assertEqual(dev.available_configs[0].name, "video-nvidia-570xx")


# ======================================================================
# Obsolete Kernel Detection tests
# ======================================================================


class TestObsoleteKernels(unittest.TestCase):
    """Tests for KernelManager.get_obsolete_kernels."""

    def _make_manager(self):
        with patch("core.kernel_manager.get_logger"):
            from core.kernel_manager import KernelManager

            mgr = KernelManager()
            return mgr

    @patch("core.kernel_manager.KernelManager.get_running_kernel_package")
    @patch("core.kernel_manager.KernelManager.get_available_kernels")
    @patch("core.kernel_manager.KernelManager.get_installed_kernels")
    def test_obsolete_detected(self, mock_inst, mock_avail, mock_running):
        mock_running.return_value = "linux612"
        mock_inst.return_value = [
            {"name": "linux612", "version": "6.12.10", "installed": True},
            {"name": "linux510", "version": "5.10.0", "installed": True},
        ]
        mock_avail.return_value = [
            {"name": "linux612", "version": "6.12.10"},
            {"name": "linux614", "version": "6.14.1"},
        ]
        mgr = self._make_manager()
        obsolete = mgr.get_obsolete_kernels()
        self.assertEqual(len(obsolete), 1)
        self.assertEqual(obsolete[0]["name"], "linux510")
        self.assertTrue(obsolete[0].get("obsolete"))

    @patch("core.kernel_manager.KernelManager.get_running_kernel_package")
    @patch("core.kernel_manager.KernelManager.get_available_kernels")
    @patch("core.kernel_manager.KernelManager.get_installed_kernels")
    def test_running_kernel_not_flagged(self, mock_inst, mock_avail, mock_running):
        """Running kernel should never be flagged obsolete even if not in repos."""
        mock_running.return_value = "linux510"
        mock_inst.return_value = [
            {"name": "linux510", "version": "5.10.0", "installed": True},
        ]
        mock_avail.return_value = []
        mgr = self._make_manager()
        obsolete = mgr.get_obsolete_kernels()
        self.assertEqual(len(obsolete), 0)

    @patch("core.kernel_manager.KernelManager.get_running_kernel_package")
    @patch("core.kernel_manager.KernelManager.get_available_kernels")
    @patch("core.kernel_manager.KernelManager.get_installed_kernels")
    def test_no_obsolete_when_all_available(self, mock_inst, mock_avail, mock_running):
        mock_running.return_value = "linux612"
        mock_inst.return_value = [
            {"name": "linux612", "version": "6.12.10", "installed": True},
            {"name": "linux614", "version": "6.14.1", "installed": True},
        ]
        mock_avail.return_value = [
            {"name": "linux612", "version": "6.12.10"},
            {"name": "linux614", "version": "6.14.1"},
        ]
        mgr = self._make_manager()
        obsolete = mgr.get_obsolete_kernels()
        self.assertEqual(len(obsolete), 0)


class TestFilterExistingInRepos(unittest.TestCase):
    """Tests for KernelManager._filter_existing_in_repos."""

    def _make_manager(self):
        from core.kernel_manager import KernelManager

        with patch("core.kernel_manager.PackageManager"):
            return KernelManager()

    @patch("subprocess.run")
    def test_filters_to_available(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="linux614\nlinux614-headers\n"
        )
        mgr = self._make_manager()
        result = mgr._filter_existing_in_repos(
            ["linux614", "linux614-headers", "linux614-zfs"], "linux614"
        )
        self.assertEqual(result, ["linux614", "linux614-headers"])

    @patch("subprocess.run")
    def test_empty_list_returns_empty(self, mock_run):
        mgr = self._make_manager()
        result = mgr._filter_existing_in_repos([], "linux614")
        self.assertEqual(result, [])
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_pacman_failure_returns_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        mgr = self._make_manager()
        result = mgr._filter_existing_in_repos(["linux614-headers"], "linux614")
        self.assertEqual(result, [])


class TestBaseManagerCancelOperation(unittest.TestCase):
    """Tests for BaseManager.cancel_operation."""

    def test_cancel_sets_flag(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        self.assertFalse(mgr._cancelled)
        mgr.cancel_operation()
        self.assertTrue(mgr._cancelled)

    def test_cancel_terminates_process(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.wait.return_value = None
        mgr._current_process = mock_proc

        mgr.cancel_operation()
        mock_proc.terminate.assert_called_once()

    def test_cancel_force_kills_on_timeout(self):
        import subprocess as sp

        from core.base_manager import BaseManager

        mgr = BaseManager()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.wait.side_effect = [sp.TimeoutExpired("cmd", 2), None]
        mgr._current_process = mock_proc

        mgr.cancel_operation()
        mock_proc.kill.assert_called_once()


class TestThreadLauncherInjection(unittest.TestCase):
    """Tests for BaseManager thread_launcher parameter."""

    def test_default_launcher(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        self.assertEqual(mgr._thread_launcher, BaseManager._default_launcher)

    def test_custom_launcher(self):
        from core.base_manager import BaseManager

        calls = []

        def fake_launcher(target, args):
            calls.append((target, args))

        mgr = BaseManager(thread_launcher=fake_launcher)
        self.assertEqual(mgr._thread_launcher, fake_launcher)


class TestMesaDriversJson(unittest.TestCase):
    """Tests for MESA_DRIVERS loaded from JSON."""

    def test_loads_all_variants(self):
        from core.mesa_manager import MESA_DRIVERS

        ids = {d["id"] for d in MESA_DRIVERS}
        self.assertEqual(ids, {"amber", "stable", "tkg-stable", "tkg-git"})

    def test_each_has_required_keys(self):
        from core.mesa_manager import MESA_DRIVERS

        for d in MESA_DRIVERS:
            for key in ("id", "name", "detect_package", "packages", "conflicts"):
                self.assertIn(key, d, f"Missing key '{key}' in {d['id']}")

    def test_stable_has_correct_packages(self):
        from core.mesa_manager import MESA_DRIVERS

        stable = next(d for d in MESA_DRIVERS if d["id"] == "stable")
        self.assertIn("mesa", stable["packages"])
        self.assertIn("lib32-mesa", stable["packages"])


class TestKernelInfoTypedDict(unittest.TestCase):
    """Tests for KernelInfo TypedDict structure."""

    def test_typeddict_fields(self):
        from core.kernel_manager import KernelInfo

        required = KernelInfo.__required_keys__
        optional = KernelInfo.__optional_keys__
        all_keys = required | optional
        for key in ("name", "version", "installed", "rt", "lts", "obsolete"):
            self.assertIn(key, all_keys, f"Missing field '{key}' in KernelInfo")


if __name__ == "__main__":
    unittest.main()
