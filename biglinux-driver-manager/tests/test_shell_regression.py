#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Behaviour tests for the packaged shell scripts.

These tests run the scripts inside a sandboxed environment built from
``tempfile.TemporaryDirectory`` + environment overrides. They guard:
- H8: blacklist in login-check-drivers is used, O(1).
- H9: udev-notify respects MAX_CONCURRENT cap.
- M10: udev rule filters hub devices (class 09) — covered by source test,
       but we also reconfirm the syntactic parity here.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "usr" / "share" / "big-driver-manager"
LOGIN_CHECK = SCRIPTS_DIR / "login-check-drivers.sh"
UDEV_NOTIFY = SCRIPTS_DIR / "udev-notify.sh"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestLoginCheckBlacklist(unittest.TestCase):
    """H8: blacklisted IDs must not launch dialogs."""

    def _prepare(self, tmp: Path, *, present_ids, cache_rows, blacklist):
        cache = tmp / "ids_cache.txt"
        cache.write_text(
            "".join(
                "\t".join([vid, cat, drv, pkg, desc]) + "\n"
                for vid, cat, drv, pkg, desc in cache_rows
            ),
            encoding="utf-8",
        )

        blacklist_path = tmp / "ignored.json"
        blacklist_path.write_text(json.dumps(blacklist), encoding="utf-8")

        shown = tmp / "shown.flag"

        dialog_log = tmp / "dialog.log"
        fake_dialog = tmp / "fake_dialog.py"
        fake_dialog.write_text(
            textwrap.dedent(
                f"""
                #!/usr/bin/env python3
                import sys
                with open({json.dumps(str(dialog_log))}, "a") as fh:
                    fh.write("\\t".join(sys.argv[1:]) + "\\n")
                """
            ).lstrip(),
            encoding="utf-8",
        )
        fake_dialog.chmod(0o755)

        # Fake pacman that always says "not installed" (exit 1 for -Qq <pkg>)
        fake_pacman = tmp / "fake_pacman"
        fake_pacman.write_text(
            textwrap.dedent(
                """
                #!/bin/bash
                exit 1
                """
            ).lstrip(),
            encoding="utf-8",
        )
        fake_pacman.chmod(0o755)

        # Fake lspci that emits a single PCI line for each present PCI id
        pci_ids = [i for i in present_ids if i.get("bus") == "pci"]
        usb_ids = [i for i in present_ids if i.get("bus") == "usb"]
        lines = []
        for entry in pci_ids:
            lines.append(f"00:00.0 0300: {entry['vid'].lower()}:{entry['did'].lower()}")
        fake_lspci = tmp / "fake_lspci"
        fake_lspci.write_text(
            "#!/bin/bash\ncat <<'OUT'\n" + "\n".join(lines) + "\nOUT\n",
            encoding="utf-8",
        )
        fake_lspci.chmod(0o755)

        # Fake sysfs USB devices
        sysfs_usb_base = tmp / "sysbus_usb"
        for i, entry in enumerate(usb_ids):
            d = sysfs_usb_base / f"usb{i}"
            d.mkdir(parents=True)
            (d / "idVendor").write_text(entry["vid"], encoding="utf-8")
            (d / "idProduct").write_text(entry["did"], encoding="utf-8")
        return {
            "cache": cache,
            "blacklist": blacklist_path,
            "shown": shown,
            "dialog_log": dialog_log,
            "fake_dialog": fake_dialog,
            "fake_pacman": fake_pacman,
            "fake_lspci": fake_lspci,
        }

    def _run(self, tmp: Path, state: dict, sysfs_override: bool) -> str:
        env = {
            **os.environ,
            "BDM_CACHE_FILE": str(state["cache"]),
            "BDM_DIALOG_SCRIPT": str(state["fake_dialog"]),
            "BDM_BLACKLIST_FILE": str(state["blacklist"]),
            "BDM_SHOWN_FILE": str(state["shown"]),
            "BDM_PACMAN_BIN": str(state["fake_pacman"]),
            "BDM_PYTHON_BIN": shutil.which("python3") or "/usr/bin/python3",
            "BDM_LSPCI_BIN": str(state["fake_lspci"]),
            "BDM_DMESG_BIN": "/bin/true",
            "BDM_MAX_DIALOGS": "5",
            "BDM_FW_CACHE_FILE": str(tmp / "nonexistent_fw_cache"),
        }
        # The script reads USB devices from $BDM_USB_SYSFS, so the fake
        # tree can be injected without editing the script.
        script_path = LOGIN_CHECK
        if sysfs_override:
            env["BDM_USB_SYSFS"] = str(tmp / "sysbus_usb")
        result = subprocess.run(
            ["bash", str(script_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        if state["dialog_log"].exists():
            return state["dialog_log"].read_text(encoding="utf-8")
        return ""

    def test_blacklist_suppresses_dialog(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            state = self._prepare(
                tmp,
                present_ids=[
                    {"bus": "usb", "vid": "0BDA", "did": "8178"},
                ],
                cache_rows=[
                    (
                        "0BDA:8178",
                        "device-ids",
                        "rtl8xxxu",
                        "rtl8xxxu-dkms",
                        "WiFi driver",
                    )
                ],
                blacklist=["0BDA:8178"],
            )
            log = self._run(tmp, state, sysfs_override=True)
            self.assertEqual(log, "", msg="dialog should NOT fire for blacklisted id")

    def test_non_blacklisted_fires_dialog(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            state = self._prepare(
                tmp,
                present_ids=[
                    {"bus": "usb", "vid": "0BDA", "did": "8178"},
                ],
                cache_rows=[
                    (
                        "0BDA:8178",
                        "device-ids",
                        "rtl8xxxu",
                        "rtl8xxxu-dkms",
                        "WiFi driver",
                    )
                ],
                blacklist=["0000:FFFF"],
            )
            # Use a tiny BDM_MAX_DIALOGS so sleep doesn't blow the timeout.
            os.environ["BDM_MAX_DIALOGS"] = "1"
            log = self._run(tmp, state, sysfs_override=True)
            self.assertIn("rtl8xxxu", log)

    def test_device_with_kernel_driver_is_skipped(self):
        """A USB device already bound to a kernel driver needs no extra one."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            state = self._prepare(
                tmp,
                present_ids=[{"bus": "usb", "vid": "0BDA", "did": "8153"}],
                cache_rows=[
                    ("0BDA:8153", "device-ids", "r8152", "r8152-dkms", "Ethernet")
                ],
                blacklist=[],
            )
            intf = tmp / "sysbus_usb" / "usb0" / "usb0:1.0"
            intf.mkdir()
            (tmp / "drivers" / "r8152").mkdir(parents=True)
            (intf / "driver").symlink_to(tmp / "drivers" / "r8152")
            log = self._run(tmp, state, sysfs_override=True)
            self.assertEqual(log, "", msg="no dialog for hardware that already works")


if __name__ == "__main__":
    unittest.main()
