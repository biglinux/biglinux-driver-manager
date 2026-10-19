"""core.privileged: what the interface may ask root to do, and nothing else."""

import unittest
from unittest.mock import patch

from core import privileged
from core.privileged import (
    PrivilegedRequestError,
    cli_to_pacman,
    mhwd_args,
    mhwd_command,
    pacman_command,
    pacman_to_cli,
)

# Every pacman invocation the managers make today, as they make it.
MANAGER_FORMS = [
    (["-S", "--noconfirm", "--needed", "a", "b"], ["install", "--", "a", "b"]),
    (["-S", "--noconfirm", "linux-big"], ["install", "--reinstall", "--", "linux-big"]),
    (
        ["-S", "--noconfirm", "--needed", "--overwrite", "*", "mesa"],
        ["install", "--overwrite-all", "--", "mesa"],
    ),
    (["-R", "--noconfirm", "pkg"], ["remove", "--", "pkg"]),
    (["-Rns", "--noconfirm", "pkg"], ["remove", "--recursive", "--", "pkg"]),
    (["-Rnc", "--noconfirm", "pkg"], ["remove", "--cascade", "--", "pkg"]),
]


class TestPacmanForms(unittest.TestCase):
    def test_every_manager_form_maps_to_a_verb(self):
        for args, verb in MANAGER_FORMS:
            with self.subTest(args=args):
                self.assertEqual(pacman_to_cli(args), verb)

    def test_round_trip_gives_back_the_same_pacman_arguments(self):
        for args, verb in MANAGER_FORMS:
            with self.subTest(args=args):
                name, *rest = verb
                split = rest.index("--")
                self.assertEqual(
                    cli_to_pacman(name, rest[:split], rest[split + 1 :]), args
                )

    def test_overwrite_form_is_not_taken_for_a_package_list(self):
        # "-S --noconfirm --needed" is a prefix of the overwrite form.
        verb = pacman_to_cli(["-S", "--noconfirm", "--needed", "--overwrite", "*", "x"])
        self.assertEqual(verb[:2], ["install", "--overwrite-all"])

    def test_unknown_forms_are_refused(self):
        for args in (
            ["-Syu", "--noconfirm"],
            ["-U", "--noconfirm", "/tmp/evil.pkg.tar.zst"],
            ["-S", "--noconfirm", "--needed", "--root", "/mnt", "x"],
            ["-S", "x"],
            ["-Rdd", "--noconfirm", "glibc"],
        ):
            with self.subTest(args=args), self.assertRaises(PrivilegedRequestError):
                pacman_to_cli(args)

    def test_package_names_cannot_become_options(self):
        for name in ("-x", "--root=/", ".hidden", "a b", "a;b", "a/b", ""):
            with self.subTest(name=name), self.assertRaises(PrivilegedRequestError):
                cli_to_pacman("install", [], [name])

    def test_real_package_names_are_accepted(self):
        names = [
            "linux-big-nvidia-open",
            "lib32-mesa",
            "gtk+",
            "libc++",
            "python3.14",
            "r8168-dkms",
        ]
        self.assertEqual(cli_to_pacman("install", [], names)[-len(names) :], names)

    def test_no_packages_is_refused(self):
        with self.assertRaises(PrivilegedRequestError):
            cli_to_pacman("remove", [], [])

    def test_flag_combinations_outside_the_table_are_refused(self):
        with self.assertRaises(PrivilegedRequestError):
            cli_to_pacman("install", ["--recursive"], ["x"])
        with self.assertRaises(PrivilegedRequestError):
            cli_to_pacman("remove", ["--recursive", "--cascade"], ["x"])


class TestMhwd(unittest.TestCase):
    def test_arguments(self):
        self.assertEqual(
            mhwd_args("install", "pci", "video-nvidia"), ["-i", "pci", "video-nvidia"]
        )
        self.assertEqual(
            mhwd_args("install", "pci", "video-nvidia", force=True),
            ["-f", "-i", "pci", "video-nvidia"],
        )
        self.assertEqual(mhwd_args("remove", "usb", "x"), ["-r", "usb", "x"])

    def test_invalid_requests(self):
        for call in (
            lambda: mhwd_args("purge", "pci", "x"),
            lambda: mhwd_args("install", "isa", "x"),
            lambda: mhwd_args("install", "pci", "x;reboot"),
            lambda: mhwd_args("install", "pci", "-f"),
            lambda: mhwd_args("remove", "pci", "x", force=True),
        ):
            with self.assertRaises(PrivilegedRequestError):
                call()


class TestCommands(unittest.TestCase):
    def test_unprivileged_goes_through_pkexec_and_the_cli(self):
        with patch.object(privileged, "is_root", return_value=False):
            cmd = pacman_command(["-R", "--noconfirm", "x"])
            self.assertEqual(cmd[:2], ["pkexec", privileged.CLI_BIN])
            self.assertNotIn("pacman", cmd)
            self.assertEqual(
                mhwd_command("install", "pci", "video-nvidia", force=True),
                [
                    "pkexec",
                    privileged.CLI_BIN,
                    "mhwd",
                    "install",
                    "pci",
                    "video-nvidia",
                    "--force",
                ],
            )

    def test_root_runs_the_tools_directly(self):
        with patch.object(privileged, "is_root", return_value=True):
            self.assertEqual(
                pacman_command(["-R", "--noconfirm", "x"]),
                [privileged.PACMAN, "-R", "--noconfirm", "x"],
            )
            self.assertEqual(
                mhwd_command("remove", "pci", "x"), [privileged.MHWD, "-r", "pci", "x"]
            )

    def test_root_still_refuses_unknown_forms(self):
        with patch.object(privileged, "is_root", return_value=True):
            with self.assertRaises(PrivilegedRequestError):
                pacman_command(["-U", "/tmp/x.pkg.tar.zst"])


if __name__ == "__main__":
    unittest.main()
