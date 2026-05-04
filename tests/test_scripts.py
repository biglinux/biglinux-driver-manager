#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Regression tests for shell notification scripts."""

import getpass
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
UDEV_SCRIPT = REPO_ROOT / "usr/share/big-driver-manager/udev-notify.sh"
LOGIN_SCRIPT = REPO_ROOT / "usr/share/big-driver-manager/login-check-drivers.sh"
TEST_DIALOG_SCRIPT = REPO_ROOT / "usr/share/big-driver-manager/test-udev-dialog.sh"


class ScriptTestCase(unittest.TestCase):
    """Common helpers for running shell scripts with fake binaries."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory(dir=REPO_ROOT)
        self.base = Path(self.tmpdir.name)
        self.fakebin = self.base / "fakebin"
        self.fakebin.mkdir()
        self.runtime_dir = self.base / "runtime"
        self.dialog_log = self.base / "dialog.log"
        self.systemd_run_log = self.base / "systemd-run.log"
        self.user = getpass.getuser()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_executable(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _write_fake_bin(self, name: str, content: str) -> None:
        self._write_executable(self.fakebin / name, content)

    def _write_dialog_script(self) -> Path:
        path = self.base / "dialog.py"
        path.write_text(
            textwrap.dedent(
                """
                import os
                import pathlib
                import sys

                log_path = pathlib.Path(os.environ["BDM_DIALOG_LOG"])
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(" ".join(sys.argv[1:]) + "\\n")
                """
            ),
            encoding="utf-8",
        )
        return path

    def _script_env(self, **extra: str) -> dict[str, str]:
        env = os.environ.copy()
        env["PATH"] = f"{self.fakebin}:{env['PATH']}"
        env["USER"] = self.user
        env["BDM_DIALOG_LOG"] = str(self.dialog_log)
        env.update(extra)
        return env


class TestUdevNotifyScript(ScriptTestCase):
    """Tests for udev-notify.sh security and cooldown behavior."""

    def setUp(self):
        super().setUp()
        self.cache_file = self.base / "ids_cache.txt"
        self.cache_file.write_text(
            "1234:5678\tdevice-ids\ttest-driver\ttest-package\tTest driver\n",
            encoding="utf-8",
        )
        self.dialog_script = self._write_dialog_script()
        self._write_fake_bin(
            "pacman",
            "#!/bin/sh\nexit 1\n",
        )
        self._write_fake_bin(
            "loginctl",
            textwrap.dedent(
                f"""\
                #!/bin/sh
                if [ "$1" = "list-sessions" ]; then
                    printf '10 seat0\\n'
                    exit 0
                fi
                if [ "$1" = "show-session" ]; then
                    case "$4" in
                        Name) printf '%s\\n' '{self.user}' ;;
                        Type) printf 'wayland\\n' ;;
                        State) printf 'active\\n' ;;
                        Display) printf ':0\\n' ;;
                        WaylandDisplay) printf 'wayland-0\\n' ;;
                    esac
                    exit 0
                fi
                exit 1
                """
            ),
        )
        self._write_fake_bin(
            "systemd-run",
            textwrap.dedent(
                """\
                #!/bin/sh
                printf '%s\n' "$*" >> "$BDM_SYSTEMD_RUN_LOG"
                exit 0
                """
            ),
        )

    def test_runtime_dir_and_cooldown_are_enforced(self):
        env = self._script_env(
            BDM_CACHE_FILE=str(self.cache_file),
            BDM_DIALOG_SCRIPT=str(self.dialog_script),
            BDM_RUNTIME_DIR=str(self.runtime_dir),
            BDM_SYSTEMD_RUN_LOG=str(self.systemd_run_log),
            BDM_PACMAN_BIN=str(self.fakebin / "pacman"),
            BDM_LOGINCTL_BIN=str(self.fakebin / "loginctl"),
            BDM_SYSTEMD_RUN_BIN=str(self.fakebin / "systemd-run"),
            BDM_PYTHON_BIN=sys.executable,
        )

        subprocess.run(
            ["bash", str(UDEV_SCRIPT), "usb", "1234", "5678"],
            check=True,
            env=env,
            cwd=REPO_ROOT,
        )
        subprocess.run(
            ["bash", str(UDEV_SCRIPT), "usb", "1234", "5678"],
            check=True,
            env=env,
            cwd=REPO_ROOT,
        )

        self.assertTrue((self.runtime_dir / "notify-state").is_dir())
        log_lines = self.systemd_run_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(log_lines), 1)
        self.assertIn(str(self.dialog_script), log_lines[0])


class TestLoginCheckScript(ScriptTestCase):
    """Tests for login-check-drivers.sh session gating and blacklist logic."""

    def setUp(self):
        super().setUp()
        self.cache_file = self.base / "ids_cache.txt"
        self.cache_file.write_text(
            "1234:5678\tdevice-ids\ttest-driver\ttest-package\tTest driver\n",
            encoding="utf-8",
        )
        self.fw_cache_file = self.base / "firmware_cache.txt"
        self.fw_cache_file.write_text("", encoding="utf-8")
        self.dialog_script = self._write_dialog_script()
        self.blacklist_file = self.base / "ignored_devices.json"
        self.shown_file = self.base / "shown"
        self._write_fake_bin(
            "pacman",
            "#!/bin/sh\nexit 1\n",
        )
        self._write_fake_bin(
            "lspci",
            "#!/bin/sh\nprintf '00:02.0 0300: 1234:5678 (rev 01)\\n'\n",
        )
        self._write_fake_bin(
            "dmesg",
            "#!/bin/sh\nexit 0\n",
        )

    def test_blacklist_prevents_dialog(self):
        self.blacklist_file.write_text(json.dumps(["1234:5678"]), encoding="utf-8")
        env = self._script_env(
            BDM_CACHE_FILE=str(self.cache_file),
            BDM_DIALOG_SCRIPT=str(self.dialog_script),
            BDM_BLACKLIST_FILE=str(self.blacklist_file),
            BDM_SHOWN_FILE=str(self.shown_file),
            BDM_FW_CACHE_FILE=str(self.fw_cache_file),
            BDM_MAX_DIALOGS="1",
            BDM_PACMAN_BIN=str(self.fakebin / "pacman"),
            BDM_LSPCI_BIN=str(self.fakebin / "lspci"),
            BDM_DMESG_BIN=str(self.fakebin / "dmesg"),
            BDM_PYTHON_BIN=sys.executable,
        )

        subprocess.run(
            ["bash", str(LOGIN_SCRIPT)],
            check=True,
            env=env,
            cwd=REPO_ROOT,
        )
        time.sleep(0.2)

        self.assertFalse(self.dialog_log.exists())

    def test_shown_file_blocks_repeat_dialogs(self):
        env = self._script_env(
            BDM_CACHE_FILE=str(self.cache_file),
            BDM_DIALOG_SCRIPT=str(self.dialog_script),
            BDM_BLACKLIST_FILE=str(self.blacklist_file),
            BDM_SHOWN_FILE=str(self.shown_file),
            BDM_FW_CACHE_FILE=str(self.fw_cache_file),
            BDM_MAX_DIALOGS="1",
            BDM_PACMAN_BIN=str(self.fakebin / "pacman"),
            BDM_LSPCI_BIN=str(self.fakebin / "lspci"),
            BDM_DMESG_BIN=str(self.fakebin / "dmesg"),
            BDM_PYTHON_BIN=sys.executable,
        )

        subprocess.run(
            ["bash", str(LOGIN_SCRIPT)],
            check=True,
            env=env,
            cwd=REPO_ROOT,
        )
        time.sleep(0.3)
        subprocess.run(
            ["bash", str(LOGIN_SCRIPT)],
            check=True,
            env=env,
            cwd=REPO_ROOT,
        )
        time.sleep(0.3)

        lines = self.dialog_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(self.shown_file.exists())


class TestDialogTestScript(ScriptTestCase):
    """Tests for test-udev-dialog.sh device simulation helper."""

    def setUp(self):
        super().setUp()
        self.dialog_script = self._write_dialog_script()
        self.assets_dir = self.base / "assets"
        driver_dir = self.assets_dir / "device-ids" / "test-usb-driver"
        driver_dir.mkdir(parents=True)
        (driver_dir / "usb.ids").write_text("1234:5678\n", encoding="utf-8")
        (driver_dir / "pkg").write_text("test-package\n", encoding="utf-8")
        (driver_dir / "description").write_text("Test USB Driver\n", encoding="utf-8")
        firmware_dir = self.assets_dir / "firmware" / "test-firmware-package"
        firmware_dir.mkdir(parents=True)
        (firmware_dir / "description").write_text(
            "Test Firmware Package\n", encoding="utf-8"
        )

    def test_resolves_device_from_assets_and_launches_dialog(self):
        env = self._script_env(
            BDM_ASSETS_DIR=str(self.assets_dir),
            BDM_CACHE_FILE=str(self.base / "missing-cache.txt"),
            BDM_DIALOG_SCRIPT=str(self.dialog_script),
            BDM_PYTHON_BIN=sys.executable,
        )

        subprocess.run(
            ["bash", str(TEST_DIALOG_SCRIPT), "usb", "0x1234", "0x5678"],
            check=True,
            env=env,
            cwd=REPO_ROOT,
        )

        logged = self.dialog_log.read_text(encoding="utf-8").strip()
        self.assertEqual(
            logged,
            "usb 1234 5678 device-ids test-usb-driver test-package Test USB Driver",
        )

    def test_resolves_firmware_package_from_assets_and_launches_dialog(self):
        env = self._script_env(
            BDM_ASSETS_DIR=str(self.assets_dir),
            BDM_CACHE_FILE=str(self.base / "missing-cache.txt"),
            BDM_FW_CACHE_FILE=str(self.base / "missing-firmware-cache.txt"),
            BDM_DIALOG_SCRIPT=str(self.dialog_script),
            BDM_PYTHON_BIN=sys.executable,
        )

        subprocess.run(
            ["bash", str(TEST_DIALOG_SCRIPT), "firmware", "test-firmware-package"],
            check=True,
            env=env,
            cwd=REPO_ROOT,
        )

        logged = self.dialog_log.read_text(encoding="utf-8").strip()
        self.assertEqual(
            logged,
            "firmware 0000 0000 firmware test-firmware-package test-firmware-package Test Firmware Package",
        )


if __name__ == "__main__":
    unittest.main()
