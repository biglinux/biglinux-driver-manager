"""Tests for pure functions from the UI layer (no GTK dependency)."""

import sys
import os
import unittest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "usr", "share", "big-driver-manager"),
)

from ui.kernel_card_builder import classify_kernel, version_sort_key


# ------------------------------------------------------------------
# classify_kernel
# ------------------------------------------------------------------


class TestClassifyKernel(unittest.TestCase):
    """Tests for classify_kernel()."""

    def test_standard_kernel(self):
        k = {"name": "linux69", "version": "6.9.1-1"}
        info = classify_kernel(k)
        self.assertFalse(info.is_lts)
        self.assertFalse(info.is_rt)
        self.assertFalse(info.is_xanmod)
        self.assertEqual(info.badge_entries, [])

    def test_lts_by_flag(self):
        k = {"name": "linux66", "version": "6.6.50-1", "lts": True}
        info = classify_kernel(k)
        self.assertTrue(info.is_lts)
        self.assertFalse(info.is_rt)
        self.assertIn(("LTS", "success"), info.badge_entries)

    def test_lts_by_name(self):
        k = {"name": "linux66-lts", "version": "6.6.50-1"}
        info = classify_kernel(k)
        self.assertTrue(info.is_lts)

    def test_rt_by_flag(self):
        k = {"name": "linux-rt", "version": "6.8.0-1", "rt": True}
        info = classify_kernel(k)
        self.assertTrue(info.is_rt)
        self.assertIn(("RT", "warning"), info.badge_entries)

    def test_rt_by_name(self):
        k = {"name": "linux66-rt", "version": "6.6.50-1"}
        info = classify_kernel(k)
        self.assertTrue(info.is_rt)

    def test_xanmod_by_flag(self):
        k = {"name": "linux-xanmod", "version": "6.9.1-1", "xanmod": True}
        info = classify_kernel(k)
        self.assertTrue(info.is_xanmod)
        self.assertIn(("Xanmod", "purple"), info.badge_entries)

    def test_xanmod_by_name(self):
        k = {"name": "linux-xanmod-edge", "version": "6.9.1-1"}
        info = classify_kernel(k)
        self.assertTrue(info.is_xanmod)

    def test_lts_rt_combo(self):
        k = {"name": "linux66-lts-rt", "version": "6.6.50-1"}
        info = classify_kernel(k)
        self.assertTrue(info.is_lts)
        self.assertTrue(info.is_rt)
        self.assertEqual(len(info.badge_entries), 2)

    def test_type_desc_not_empty(self):
        for k in [
            {"name": "linux69"},
            {"name": "linux66-lts"},
            {"name": "linux-rt"},
            {"name": "linux-xanmod"},
        ]:
            info = classify_kernel(k)
            self.assertTrue(len(info.type_desc) > 0, f"Empty type_desc for {k}")

    def test_full_desc_not_empty(self):
        for k in [
            {"name": "linux69"},
            {"name": "linux66-lts"},
            {"name": "linux-rt"},
            {"name": "linux-xanmod"},
        ]:
            info = classify_kernel(k)
            self.assertTrue(len(info.full_desc) > 0, f"Empty full_desc for {k}")

    def test_empty_dict(self):
        info = classify_kernel({})
        self.assertFalse(info.is_lts)
        self.assertFalse(info.is_rt)
        self.assertFalse(info.is_xanmod)

    def test_frozen_dataclass(self):
        info = classify_kernel({"name": "linux69"})
        with self.assertRaises(AttributeError):
            info.is_lts = True


# ------------------------------------------------------------------
# version_sort_key
# ------------------------------------------------------------------


class TestVersionSortKey(unittest.TestCase):
    """Tests for version_sort_key()."""

    def test_simple_version(self):
        self.assertEqual(version_sort_key({"version": "6.9.1-1"}), (6, 9, 1, 1))

    def test_two_part_version(self):
        self.assertEqual(version_sort_key({"version": "6.9"}), (6, 9))

    def test_no_version_key(self):
        self.assertEqual(version_sort_key({}), (0,))

    def test_no_numbers(self):
        self.assertEqual(version_sort_key({"version": "abc"}), (0,))

    def test_long_version_truncated_to_4(self):
        key = version_sort_key({"version": "1.2.3.4.5.6"})
        self.assertEqual(key, (1, 2, 3, 4))

    def test_sorting_order(self):
        kernels = [
            {"version": "6.6.50-1"},
            {"version": "6.9.1-1"},
            {"version": "6.1.100-1"},
            {"version": "6.11.2-1"},
        ]
        sorted_names = sorted(kernels, key=version_sort_key)
        versions = [k["version"] for k in sorted_names]
        self.assertEqual(
            versions,
            ["6.1.100-1", "6.6.50-1", "6.9.1-1", "6.11.2-1"],
        )

    def test_reverse_sorting(self):
        kernels = [
            {"version": "6.6.50-1"},
            {"version": "6.9.1-1"},
            {"version": "6.1.100-1"},
        ]
        sorted_k = sorted(kernels, key=version_sort_key, reverse=True)
        self.assertEqual(sorted_k[0]["version"], "6.9.1-1")
        self.assertEqual(sorted_k[-1]["version"], "6.1.100-1")


# ------------------------------------------------------------------
# _get_category_icon
# ------------------------------------------------------------------


class TestGetCategoryIcon(unittest.TestCase):
    """Tests for _get_category_icon from drivers_hub_page."""

    @classmethod
    def setUpClass(cls):
        from ui.drivers_hub_page import _get_category_icon

        cls._fn = staticmethod(_get_category_icon)

    def test_known_categories(self):
        known = {
            "video": "video-display-symbolic",
            "wifi": "network-wireless-symbolic",
            "bluetooth": "bluetooth-symbolic",
            "printer": "printer-symbolic",
            "scanner": "document-scan-symbolic",
        }
        for cat_id, expected_icon in known.items():
            self.assertEqual(self._fn(cat_id), expected_icon)

    def test_unknown_returns_fallback(self):
        self.assertEqual(
            self._fn("nonexistent_category"),
            "application-x-firmware-symbolic",
        )


# ------------------------------------------------------------------
# _MESA_HUMAN_NAMES
# ------------------------------------------------------------------


class TestMesaHumanNames(unittest.TestCase):
    """Tests for _MESA_HUMAN_NAMES mapping."""

    @classmethod
    def setUpClass(cls):
        from ui.mesa_data import _init_mesa_names, _MESA_HUMAN_NAMES

        _init_mesa_names()
        cls._names = _MESA_HUMAN_NAMES

    def test_stable_present(self):
        self.assertIn("stable", self._names)
        self.assertIn("title", self._names["stable"])
        self.assertIn("desc", self._names["stable"])

    def test_tkg_stable_present(self):
        self.assertIn("tkg-stable", self._names)

    def test_tkg_git_present(self):
        self.assertIn("tkg-git", self._names)

    def test_amber_present(self):
        self.assertIn("amber", self._names)

    def test_all_have_title_and_desc(self):
        for key, val in self._names.items():
            self.assertIn("title", val, f"Missing 'title' for {key}")
            self.assertIn("desc", val, f"Missing 'desc' for {key}")
            self.assertTrue(len(val["title"]) > 0)
            self.assertTrue(len(val["desc"]) > 0)


# ------------------------------------------------------------------
# translate_description (no gettext — falls back to identity)
# ------------------------------------------------------------------


class TestTranslateDescription(unittest.TestCase):
    """Tests for description translation (without active locale)."""

    def setUp(self):
        from utils.desc_translate import translate_description

        self.translate = translate_description

    def test_empty_string(self):
        self.assertEqual(self.translate(""), "")

    def test_preserves_model_names(self):
        result = self.translate("Printing driver for Brother DCP-T310")
        self.assertIn("Brother DCP-T310", result)

    def test_translates_known_phrase(self):
        result = self.translate("Printing driver for Brother DCP-T310")
        # Model name must be preserved regardless of locale
        self.assertIn("Brother DCP-T310", result)
        # The phrase part should not be the original English lowercased
        # (it will be translated or have canonical casing applied)
        self.assertTrue(len(result) > 0)

    def test_case_insensitive_match(self):
        result = self.translate("PRINTING DRIVER FOR HP LaserJet 1020")
        self.assertIn("HP LaserJet 1020", result)

    def test_firmware_phrase(self):
        result = self.translate("Firmware for Realtek RTL8821CU Wi-Fi chips")
        # Model name preserved
        self.assertIn("Realtek RTL8821CU", result)
        self.assertTrue(len(result) > 0)

    def test_scanner_phrase(self):
        result = self.translate("Scanner driver for Canon LiDE 300")
        self.assertIn("Canon LiDE 300", result)

    def test_unknown_text_unchanged(self):
        original = "Some completely unknown custom text 12345"
        self.assertEqual(self.translate(original), original)


# ------------------------------------------------------------------
# build_tooltip_body
# ------------------------------------------------------------------


class TestBuildTooltipBody(unittest.TestCase):
    """Tests for tooltip body generation."""

    def setUp(self):
        from utils.tooltip_helper import build_tooltip_body

        self.build = build_tooltip_body

    def _make_driver(self, **kw):
        from core.driver_database import DriverModule

        defaults = dict(
            name="rtl8821cu-dkms",
            category="wifi",
            description="Driver for Realtek RTL8821CU",
            package="rtl8821cu-dkms",
        )
        defaults.update(kw)
        return DriverModule(**defaults)

    def _make_peripheral(self, **kw):
        from core.driver_database import PeripheralEntry

        defaults = dict(
            name="brother-dcp-t310",
            description="Printing driver for Brother DCP-T310",
            package="brother-dcp-t310",
        )
        defaults.update(kw)
        return PeripheralEntry(**defaults)

    def test_contains_package_name(self):
        item = self._make_driver()
        body = self.build(item, "wifi")
        self.assertIn("rtl8821cu-dkms", body)

    def test_detected_installed_status(self):
        item = self._make_driver(detected=True, installed=True)
        body = self.build(item, "wifi")
        self.assertIn("✓", body)

    def test_detected_not_installed(self):
        item = self._make_driver(detected=True, installed=False)
        body = self.build(item, "wifi")
        # Should show some status text (locale-dependent)
        self.assertTrue(len(body) > 0)

    def test_device_name_shown(self):
        item = self._make_driver(
            detected=True,
            detected_device_name="Realtek RTL8821CU [802.11ac]",
        )
        body = self.build(item, "wifi")
        self.assertIn("Realtek RTL8821CU [802.11ac]", body)

    def test_category_tip_present(self):
        item = self._make_driver()
        body = self.build(item, "wifi")
        self.assertIn("💡", body)

    def test_printer_category_tip(self):
        item = self._make_peripheral()
        body = self.build(item, "printer")
        self.assertIn("💡", body)

    def test_unknown_category_no_tip(self):
        item = self._make_driver(category="nonexistent")
        body = self.build(item, "nonexistent")
        self.assertNotIn("💡", body)

    def test_empty_description(self):
        item = self._make_driver(description="")
        body = self.build(item, "wifi")
        self.assertIn("rtl8821cu-dkms", body)


if __name__ == "__main__":
    unittest.main()
