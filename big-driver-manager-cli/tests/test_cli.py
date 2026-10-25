"""usr/bin/big-driver-manager-cli: parsing, validation and what it executes."""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "usr" / "bin" / "big-driver-manager-cli"


def _load_cli():
    loader = importlib.machinery.SourceFileLoader("bdm_cli", str(CLI))
    spec = importlib.util.spec_from_loader("bdm_cli", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


cli = _load_cli()


class TestExecution(unittest.TestCase):
    def _run_as_root(self, argv):
        with (
            patch.object(cli, "is_root", return_value=True),
            patch.object(cli.os, "execve") as execve,
        ):
            code = cli.main(argv)
        return code, execve

    def test_install_executes_pacman_with_the_mapped_options(self):
        _, execve = self._run_as_root(
            ["install", "--", "linux-big", "linux-big-nvidia-open"]
        )
        path, argv, env = execve.call_args.args
        self.assertEqual(path, "/usr/bin/pacman")
        self.assertEqual(
            argv,
            [
                "/usr/bin/pacman",
                "-S",
                "--noconfirm",
                "--needed",
                "linux-big",
                "linux-big-nvidia-open",
            ],
        )
        # The interface parses pacman's English output for progress.
        self.assertEqual(env["LC_ALL"], "C")
        self.assertEqual(env["LANG"], "C")

    def test_each_mode(self):
        cases = {
            ("install", "--reinstall", "x"): ["-S", "--noconfirm", "x"],
            ("remove", "x"): ["-R", "--noconfirm", "x"],
            ("remove", "--recursive", "x"): ["-Rns", "--noconfirm", "x"],
        }
        for argv, expected in cases.items():
            with self.subTest(argv=argv):
                _, execve = self._run_as_root(list(argv))
                self.assertEqual(execve.call_args.args[1][1:], expected)

    def test_mhwd(self):
        _, execve = self._run_as_root(
            ["mhwd", "install", "pci", "video-nvidia", "--force"]
        )
        self.assertEqual(
            execve.call_args.args[1],
            ["/usr/bin/mhwd", "-f", "-i", "pci", "video-nvidia"],
        )

    def test_invalid_request_never_executes(self):
        code, execve = self._run_as_root(["install", "--", "--root=/mnt"])
        self.assertEqual(code, cli.EXIT_USAGE)
        execve.assert_not_called()

    def test_not_root_refuses_without_executing(self):
        with (
            patch.object(cli, "is_root", return_value=False),
            patch.object(cli.os, "execve") as execve,
        ):
            self.assertEqual(cli.main(["remove", "x"]), cli.EXIT_NOT_ROOT)
        execve.assert_not_called()

    def test_cascade_and_overwrite_are_gone(self):
        for argv in (
            ["remove", "--cascade", "mesa"],
            ["install", "--overwrite-all", "mesa"],
        ):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as raised:
                cli.main(argv)
            self.assertEqual(raised.exception.code, 2)


class TestAsProcess(unittest.TestCase):
    """The installed script, run the way pkexec runs it."""

    def _run(self, *args):
        env = dict(
            os.environ, BDM_CLI_DIR=str(REPO_ROOT / "usr/share/big-driver-manager-cli")
        )
        return subprocess.run(
            [sys.executable, "-I", str(CLI), *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_version(self):
        result = self._run("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip())

    def test_validation_happens_before_the_root_check(self):
        result = self._run("install", "--", "-x")
        self.assertEqual(result.returncode, cli.EXIT_USAGE)
        self.assertIn("invalid package name", result.stderr)

    @unittest.skipIf(os.geteuid() == 0, "needs an unprivileged user")
    def test_refuses_to_run_unprivileged(self):
        result = self._run("remove", "x")
        self.assertEqual(result.returncode, cli.EXIT_NOT_ROOT)


class TestPolkitPolicy(unittest.TestCase):
    def test_policy_points_at_the_installed_cli(self):
        policy = (
            REPO_ROOT
            / "usr/share/polkit-1/actions/br.com.biglinux.drivermanager.cli.policy"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '<annotate key="org.freedesktop.policykit.exec.path">'
            "/usr/bin/big-driver-manager-cli</annotate>",
            policy,
        )


if __name__ == "__main__":
    unittest.main()
