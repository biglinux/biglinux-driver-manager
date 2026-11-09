"""core.secureboot: the Secure Boot state, read without root, and the two
operations, which go through the command line's usual pacman verbs."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import secureboot
from core.privileged import pacman_to_cli
from core.secureboot import (
    ACTIVE,
    OFF,
    PACKAGE,
    PENDING,
    UNAVAILABLE,
    SecureBootManager,
    secure_boot_enabled,
    state,
)


def _state(**overrides):
    values = dict(uefi=True, available=True, installed=False, secure_boot=False)
    values.update(overrides)
    return state(**values)


class TestState(unittest.TestCase):
    def test_hidden_without_uefi(self):
        self.assertEqual(_state(uefi=False, installed=True), UNAVAILABLE)

    def test_hidden_where_the_package_does_not_exist(self):
        self.assertEqual(_state(available=False), UNAVAILABLE)

    def test_installed_counts_even_if_no_repository_has_it(self):
        self.assertEqual(_state(available=False, installed=True), PENDING)

    def test_the_way_to_the_anti_cheat_boot(self):
        self.assertEqual(_state(), OFF)
        self.assertEqual(_state(installed=True), PENDING)
        self.assertEqual(_state(installed=True, secure_boot=True), ACTIVE)

    def test_secure_boot_alone_is_not_ours(self):
        # Secure Boot on with another distribution's chain: still to enable.
        self.assertEqual(_state(secure_boot=True), OFF)


class TestReading(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def file(self, name, data):
        path = self.dir / name
        path.write_bytes(data)
        return path

    def test_secure_boot_variable(self):
        attributes = b"\x06\x00\x00\x00"
        self.assertTrue(secure_boot_enabled(self.file("on", attributes + b"\x01")))
        self.assertFalse(secure_boot_enabled(self.file("off", attributes + b"\x00")))
        self.assertFalse(secure_boot_enabled(self.file("short", b"\x06")))
        self.assertFalse(secure_boot_enabled(self.dir / "missing"))


class _Installed:
    def __init__(self, names):
        self.names = names

    def is_package_installed(self, name):
        return name in self.names


class TestManager(unittest.TestCase):
    def manager(self, installed=(), repo=(PACKAGE,)):
        calls = []
        manager = SecureBootManager(
            _Installed(set(installed)),
            lambda: set(repo),
            thread_launcher=lambda target, args: calls.append(args[0]),
        )
        return manager, calls

    def test_enable_installs_and_disable_removes_only_the_package(self):
        manager, calls = self.manager()
        manager.enable("Enabling")
        manager.disable("Disabling")
        self.assertEqual(calls[0], ["-S", "--noconfirm", "--needed", PACKAGE])
        self.assertEqual(calls[1], ["-R", "--noconfirm", PACKAGE])

    def test_both_are_requests_the_command_line_accepts(self):
        manager, calls = self.manager()
        manager.enable("Enabling")
        manager.disable("Disabling")
        for args in calls:
            with self.subTest(args=args):
                self.assertEqual(pacman_to_cli(args)[-1], PACKAGE)

    def test_current_state_reads_the_machine(self):
        manager, _calls = self.manager(installed={PACKAGE})
        root = Path(tempfile.mkdtemp())
        variable = root / "SecureBoot"
        variable.write_bytes(b"\x06\x00\x00\x00\x01")
        with (
            patch.object(secureboot, "_EFI_DIR", root),
            patch.object(secureboot, "_SECURE_BOOT_VAR", variable),
        ):
            self.assertEqual(manager.current_state(), ACTIVE)
            variable.write_bytes(b"\x06\x00\x00\x00\x00")
            self.assertEqual(manager.current_state(), PENDING)
        with patch.object(secureboot, "_EFI_DIR", root / "missing"):
            self.assertEqual(manager.current_state(), UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
