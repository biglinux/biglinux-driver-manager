"""build-ids-cache.sh: the device-ID cache the udev notifier reads."""

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_CACHE = (
    REPO_ROOT / "usr" / "share" / "big-driver-manager-cli" / "build-ids-cache.sh"
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestBuildIdsCache(unittest.TestCase):
    """The cache builder must produce deterministic TSV output."""

    def test_builds_cache_from_assets_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            assets = tmp / "assets"
            # Minimal fixture: one device-ids driver, one peripheral.
            _write(assets / "device-ids" / "rtl8xxxu" / "pkg", "rtl8xxxu-dkms\n")
            _write(
                assets / "device-ids" / "rtl8xxxu" / "description",
                "WiFi driver for Realtek RTL8xxx\n",
            )
            _write(
                assets / "device-ids" / "rtl8xxxu" / "usb.ids",
                "0bda:8178\n0bda:b82c  # another\n",
            )
            _write(
                assets / "printer" / "brother-mfc-l" / "description",
                "Brother mono laser\n",
            )
            _write(assets / "printer" / "brother-mfc-l" / "usb.ids", "04f9:0042\n")
            _write(
                assets / "firmware" / "alsa-sof-firmware" / "description",
                "Intel Sound Open Firmware\n",
            )
            _write(
                assets / "firmware" / "alsa-sof-firmware" / "alsa-sof-firmware",
                "/usr/lib/firmware/intel/sof/example.ri\n",
            )

            # Redirect /var/cache target to tmp.
            modified = tmp / "build.sh"
            src = BUILD_CACHE.read_text(encoding="utf-8")
            src = src.replace(
                '"/var/cache/big-driver-manager"',
                f'"{tmp / "cache"}"',
            )
            modified.write_text(src, encoding="utf-8")
            modified.chmod(0o755)

            result = subprocess.run(
                ["bash", str(modified), str(assets)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            ids_cache = (tmp / "cache" / "ids_cache.txt").read_text(encoding="utf-8")
            fw_cache = (tmp / "cache" / "firmware_cache.txt").read_text(
                encoding="utf-8"
            )

            # Device-ids entries are upper-cased VID:DID, tab-separated.
            self.assertIn("0BDA:8178\tdevice-ids\trtl8xxxu\trtl8xxxu-dkms\t", ids_cache)
            self.assertIn(
                "04F9:0042\tprinter\tbrother-mfc-l\tbrother-mfc-l\t", ids_cache
            )
            # Firmware cache uses path-relative-to /usr/lib/firmware/.
            self.assertIn("intel/sof/example.ri\talsa-sof-firmware\t", fw_cache)

    def test_checks_writability(self):
        self.assertIn("[[ ! -w", BUILD_CACHE.read_text(encoding="utf-8"))

    def test_default_assets_are_the_cli_ones(self):
        self.assertIn(
            "/usr/share/big-driver-manager-cli/assets",
            BUILD_CACHE.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
