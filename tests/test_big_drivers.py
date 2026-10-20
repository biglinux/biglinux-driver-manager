"""big-drivers: the kernel commands, terminal styling and the command line
around them (colour options, mhwd-kernel options, pkexec elevation)."""

import argparse
import importlib.machinery
import importlib.util
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from core import gpu_cli, kernel_cli, term
from core.kernel_manager import KernelInstallPlan

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "usr" / "bin" / "big-driver-manager-cli"


def _load_cli():
    loader = importlib.machinery.SourceFileLoader("bdm_cli_drivers", str(CLI))
    spec = importlib.util.spec_from_loader("bdm_cli_drivers", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


cli = _load_cli()


class FakeKernels:
    """KernelManager with a fixed machine: linux-big running, linux618
    installed, linux66 obsolete, linux612 available."""

    def __init__(self, plan=None):
        self.plan = plan
        self.installed = [
            {
                "name": "linux-big",
                "version": "7.2.11-1",
                "installed": True,
                "big": True,
            },
            {
                "name": "linux618",
                "version": "6.18.55-1",
                "installed": True,
                "lts": True,
            },
            {"name": "linux66", "version": "6.6.100-1", "installed": True},
            {
                "name": "6.9.0-custom",
                "version": "6.9.0-custom",
                "installed": True,
                "source": "manual",
            },
        ]
        self.available = [
            {"name": "linux-big", "version": "7.2.11-2", "repository": "community"},
            {"name": "linux612", "version": "6.12.112-1", "repository": "core"},
            {"name": "linux618", "version": "6.18.55-1", "repository": "core"},
            {"name": "6.9.0-custom", "version": "6.9.0-custom", "source": "manual"},
        ]

    def get_running_kernel_package(self):
        return "linux-big"

    def get_installed_kernels(self):
        return [dict(k) for k in self.installed]

    def get_available_kernels(self):
        return [dict(k) for k in self.available]

    def compute_obsolete_kernels(self, installed, available, running):
        from core.kernel_manager import KernelManager

        return KernelManager.compute_obsolete_kernels(installed, available, running)

    def get_obsolete_kernels(self):
        return self.compute_obsolete_kernels(
            self.installed, self.available, "linux-big"
        )

    def plan_kernel_install(self, name):
        return self.plan or KernelInstallPlan(
            name, [name, f"{name}-headers", f"{name}-nvidia"]
        )

    def get_modules_for_remove(self, name):
        return [f"{name}-headers", f"{name}-nvidia"]


def _args(**values):
    defaults = {"yes": False, "confirmed": False, "json": False, "installed": False}
    return argparse.Namespace(**{**defaults, **values})


def _run(function, args, manager, root=True, installed=frozenset(), stdin_tty=False):
    out, err = io.StringIO(), io.StringIO()
    with (
        patch.object(kernel_cli, "KernelManager", return_value=manager),
        patch.object(kernel_cli, "is_root", return_value=root),
        patch.object(kernel_cli.gpu, "installed_packages", return_value=set(installed)),
        patch.object(kernel_cli, "_pacman", return_value=0) as pacman,
        patch.object(kernel_cli, "elevate", return_value=0) as elevate,
        patch.object(kernel_cli.sys.stdin, "isatty", return_value=stdin_tty),
        redirect_stdout(out),
        redirect_stderr(err),
    ):
        code = function(args)
    return code, out.getvalue(), err.getvalue(), pacman, elevate


class TestKernelList(unittest.TestCase):
    def test_lists_repository_installed_and_obsolete_kernels(self):
        code, out, _err, _p, _e = _run(kernel_cli._list, _args(), FakeKernels())
        self.assertEqual(code, 0)
        for name in ("linux-big", "linux612", "linux618", "linux66", "6.9.0-custom"):
            self.assertIn(name, out)
        self.assertIn("big-drivers kernel remove linux66", out)
        self.assertNotIn("\033[", out)  # not a terminal: no colour

    def test_installed_version_and_the_newer_one(self):
        manager = FakeKernels()
        kernels, obsolete, running = kernel_cli.collect_kernels(manager, False)
        big = next(k for k in kernels if k["name"] == "linux-big")
        self.assertEqual(kernel_cli._version(big), "7.2.11-1 → 7.2.11-2")
        self.assertEqual([k["name"] for k in obsolete], ["linux66"])
        self.assertEqual(running, "linux-big")

    def test_installed_only(self):
        kernels, _obsolete, _running = kernel_cli.collect_kernels(FakeKernels(), True)
        self.assertEqual(
            sorted(k["name"] for k in kernels),
            ["6.9.0-custom", "linux-big", "linux618", "linux66"],
        )

    def test_json_for_other_programs(self):
        code, out, _err, _p, _e = _run(
            kernel_cli._list, _args(json=True, installed=True), FakeKernels()
        )
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["running_package"], "linux-big")
        by_name = {k["name"]: k for k in data["kernels"]}
        self.assertTrue(by_name["linux-big"]["running"])
        self.assertEqual(by_name["linux-big"]["version"], "7.2.11-1")
        self.assertEqual(by_name["linux-big"]["repository_version"], "7.2.11-2")
        self.assertTrue(by_name["linux66"]["obsolete"])
        self.assertTrue(all(k["installed"] for k in data["kernels"]))


class TestKernelInstall(unittest.TestCase):
    def test_installs_kernel_headers_and_modules(self):
        code, out, _err, pacman, _e = _run(
            kernel_cli._install, _args(name="linux612", yes=True), FakeKernels()
        )
        self.assertEqual(code, 0)
        pacman.assert_called_once_with(
            [
                "-S",
                "--noconfirm",
                "--needed",
                "linux612",
                "linux612-headers",
                "linux612-nvidia",
            ]
        )
        self.assertIn("linux612-nvidia", out)

    def test_only_what_is_missing(self):
        code, out, _err, pacman, _e = _run(
            kernel_cli._install,
            _args(name="linux618", yes=True),
            FakeKernels(),
            installed={"linux618", "linux618-headers", "linux618-nvidia"},
        )
        self.assertEqual(code, 0)
        pacman.assert_not_called()

    def test_blocked_plan_is_refused(self):
        plan = KernelInstallPlan("linux-big", ["linux-big"], "modules still publishing")
        code, _out, err, pacman, _e = _run(
            kernel_cli._install, _args(name="linux-big", yes=True), FakeKernels(plan)
        )
        self.assertEqual(code, 1)
        pacman.assert_not_called()

    def test_unknown_kernel(self):
        code, _out, err, pacman, _e = _run(
            kernel_cli._install, _args(name="linux99", yes=True), FakeKernels()
        )
        self.assertEqual(code, 1)
        self.assertIn("linux99", err)
        pacman.assert_not_called()

    def test_invalid_name_is_a_usage_error(self):
        code, _out, _err, pacman, _e = _run(
            kernel_cli._install, _args(name="--root=/tmp", yes=True), FakeKernels()
        )
        self.assertEqual(code, 2)
        pacman.assert_not_called()

    def test_without_terminal_or_yes_nothing_happens(self):
        code, _out, err, pacman, _e = _run(
            kernel_cli._install, _args(name="linux612"), FakeKernels()
        )
        self.assertEqual(code, 1)
        self.assertIn("--yes", err)
        pacman.assert_not_called()

    def test_not_root_asks_pkexec_after_confirming(self):
        code, _out, _err, pacman, elevate = _run(
            kernel_cli._install,
            _args(name="linux612", yes=True),
            FakeKernels(),
            root=False,
        )
        self.assertEqual(code, 0)
        pacman.assert_not_called()
        elevate.assert_called_once_with(
            ["kernel", "install", "linux612", "--confirmed"]
        )

    def test_answer_no_cancels(self):
        with patch("builtins.input", return_value="n"):
            code, _out, _err, pacman, _e = _run(
                kernel_cli._install,
                _args(name="linux612"),
                FakeKernels(),
                stdin_tty=True,
            )
        self.assertEqual(code, 1)
        pacman.assert_not_called()

    def test_enter_accepts_the_default_yes(self):
        with patch("builtins.input", return_value=""):
            code, _out, _err, pacman, _e = _run(
                kernel_cli._install,
                _args(name="linux612"),
                FakeKernels(),
                stdin_tty=True,
            )
        self.assertEqual(code, 0)
        pacman.assert_called_once()


class TestKernelRemove(unittest.TestCase):
    def test_removes_kernel_and_modules(self):
        code, _out, _err, pacman, _e = _run(
            kernel_cli._remove, _args(name="linux618", yes=True), FakeKernels()
        )
        self.assertEqual(code, 0)
        pacman.assert_called_once_with(
            ["-R", "--noconfirm", "linux618", "linux618-headers", "linux618-nvidia"]
        )

    def test_never_the_running_kernel(self):
        code, _out, err, pacman, _e = _run(
            kernel_cli._remove, _args(name="linux-big", yes=True), FakeKernels()
        )
        self.assertEqual(code, 1)
        pacman.assert_not_called()

    def test_never_the_only_kernel(self):
        manager = FakeKernels()
        manager.installed = [
            {"name": "linux618", "version": "6.18.55-1", "installed": True},
            {"name": "linux-big", "version": "7.2.11-1", "installed": True},
        ]
        manager.get_running_kernel_package = lambda: "6.9.0-custom"
        manager.installed.pop(1)
        code, _out, _err, pacman, _e = _run(
            kernel_cli._remove, _args(name="linux618", yes=True), manager
        )
        self.assertEqual(code, 1)
        pacman.assert_not_called()

    def test_not_a_manual_kernel(self):
        code, _out, _err, pacman, _e = _run(
            kernel_cli._remove, _args(name="6.9.0-custom", yes=True), FakeKernels()
        )
        self.assertEqual(code, 1)
        pacman.assert_not_called()

    def test_default_answer_is_no(self):
        with patch("builtins.input", return_value=""):
            code, _out, _err, pacman, _e = _run(
                kernel_cli._remove,
                _args(name="linux618"),
                FakeKernels(),
                stdin_tty=True,
            )
        self.assertEqual(code, 1)
        pacman.assert_not_called()


class TestCommandLine(unittest.TestCase):
    def test_mhwd_kernel_options(self):
        self.assertEqual(
            kernel_cli.from_mhwd_kernel(["-li"]), ["kernel", "list", "--installed"]
        )
        self.assertEqual(kernel_cli.from_mhwd_kernel(["-l"]), ["kernel", "list"])
        with redirect_stderr(io.StringIO()):
            self.assertEqual(
                kernel_cli.from_mhwd_kernel(["-i", "linux612", "rmc"]),
                ["kernel", "install", "linux612"],
            )
        self.assertEqual(
            kernel_cli.from_mhwd_kernel(["-r", "linux66"]),
            ["kernel", "remove", "linux66"],
        )
        self.assertEqual(kernel_cli.from_mhwd_kernel(["gpu"]), ["gpu"])

    def test_color_options_anywhere_before_double_dash(self):
        self.assertEqual(
            cli.color_option(["kernel", "list", "--no-color"]),
            ("never", ["kernel", "list"]),
        )
        self.assertEqual(
            cli.color_option(["--color=always", "gpu"]), ("always", ["gpu"])
        )
        self.assertEqual(
            cli.color_option(["install", "--", "--no-color"]),
            ("auto", ["install", "--", "--no-color"]),
        )

    def test_kernel_and_gpu_parse(self):
        parser = cli._parser()
        args = parser.parse_args(["kernel", "install", "linux612", "-y"])
        self.assertEqual(
            (args.verb, args.kernel_action, args.yes), ("kernel", "install", True)
        )
        args = parser.parse_args(["gpu"])
        self.assertIsNone(args.gpu_action)

    def test_package_verbs_elevate_with_the_same_request_when_not_root(self):
        with (
            patch.object(cli, "is_root", return_value=False),
            patch.object(cli.kernel_cli, "elevate", return_value=77) as elevate,
            patch.object(cli.os, "execve") as execve,
        ):
            code = cli.main(["install", "--", "linux612"])
        self.assertEqual(code, 77)
        elevate.assert_called_once_with(["install", "--", "linux612"])
        execve.assert_not_called()

    def test_elevate_needs_a_terminal(self):
        with (
            patch.object(kernel_cli.sys.stdin, "isatty", return_value=False),
            patch.object(kernel_cli.os, "execvp") as execvp,
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(kernel_cli.elevate(["gpu", "install"]), 77)
        execvp.assert_not_called()

    def test_elevate_runs_the_cli_through_pkexec(self):
        with (
            patch.object(kernel_cli.sys.stdin, "isatty", return_value=True),
            patch.object(kernel_cli.os, "execvp") as execvp,
            redirect_stdout(io.StringIO()),
        ):
            kernel_cli.elevate(["gpu", "install"])
        program, argv = execvp.call_args.args
        self.assertEqual(program, "pkexec")
        self.assertEqual(argv[1], kernel_cli.CLI_BIN)
        self.assertEqual(argv[3:], ["gpu", "install"])
        self.assertTrue(argv[2].startswith("--color="))

    def test_gpu_actions_that_change_the_system_elevate(self):
        args = argparse.Namespace(
            gpu_action="remove", argv=["gpu", "remove"], root=None, pmconfig=None
        )
        with (
            patch.object(gpu_cli, "is_root", return_value=False),
            patch.object(gpu_cli.kernel_cli, "elevate", return_value=77) as elevate,
        ):
            self.assertEqual(gpu_cli.run(args), 77)
        elevate.assert_called_once_with(["gpu", "remove"])


class TestTerm(unittest.TestCase):
    def tearDown(self):
        term.set_mode("auto")

    def test_plain_unless_asked(self):
        term.set_mode("never")
        self.assertEqual(term.style("x", "bold"), "x")
        term.set_mode("always")
        self.assertEqual(term.style("x", "bold", "red"), "\033[1;31mx\033[0m")

    def test_no_color_environment(self):
        stream = io.StringIO()
        stream.isatty = lambda: True
        with patch.dict(term.os.environ, {"NO_COLOR": "1"}):
            self.assertFalse(term.enabled(stream))
        with patch.dict(term.os.environ, {"NO_COLOR": "", "TERM": "xterm"}):
            self.assertTrue(term.enabled(stream))

    def test_width_ignores_escapes_and_counts_wide_characters(self):
        term.set_mode("always")
        self.assertEqual(term.width(term.bold("abc")), 3)
        self.assertEqual(term.width("内核"), 4)

    def test_table_aligns_styled_and_wide_cells(self):
        term.set_mode("always")
        first, second = term.table([[term.bold("a"), "x"], ["内核", "y"]]).splitlines()
        self.assertEqual(
            term.width(first[: first.index("x")]),
            term.width(second[: second.index("y")]),
        )


if __name__ == "__main__":
    unittest.main()


def _pot_msgids(path: Path) -> list[str]:
    """msgids of a .po/.pot file (the header's empty one excluded)."""
    import ast

    msgids, current, collecting = [], None, False
    for line in path.read_text(encoding="utf-8").splitlines() + [""]:
        if line.startswith("msgid "):
            current, collecting = ast.literal_eval(line[6:]), True
        elif collecting and line.startswith('"'):
            current += ast.literal_eval(line)
        else:
            if collecting and current:
                msgids.append(current)
            collecting = False
    return msgids


class TestTranslations(unittest.TestCase):
    LOCALE = REPO_ROOT / "locale"
    POT = LOCALE / "big-driver-manager-cli.pot"

    def test_big_drivers_is_the_same_program(self):
        link = REPO_ROOT / "usr" / "bin" / "big-drivers"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.readlink(), Path("big-driver-manager-cli"))

    def test_every_catalog_is_complete_compiled_and_keeps_placeholders(self):
        import gettext
        import re

        placeholder = re.compile(r"\{[a-z_]*\}|%\([a-z_]+\)[sr]|%s")
        msgids = _pot_msgids(self.POT)
        self.assertGreater(len(msgids), 100)
        catalogs = sorted(self.LOCALE.glob("*.po"))
        self.assertGreaterEqual(len(catalogs), 29)
        for po in catalogs:
            mo = (
                REPO_ROOT
                / "usr/share/locale"
                / po.stem
                / "LC_MESSAGES/big-driver-manager-cli.mo"
            )
            with self.subTest(language=po.stem), mo.open("rb") as handle:
                catalog = gettext.GNUTranslations(handle)._catalog
                missing = [m for m in msgids if not catalog.get(m)]
                self.assertEqual(missing, [], "untranslated or .mo not rebuilt")
                for msgid in msgids:
                    self.assertEqual(
                        sorted(placeholder.findall(catalog[msgid])),
                        sorted(placeholder.findall(msgid)),
                        msgid,
                    )

    def test_polkit_prompt_is_translated(self):
        policy = (
            REPO_ROOT
            / "usr/share/polkit-1/actions/br.com.biglinux.drivermanager.cli.policy"
        ).read_text(encoding="utf-8")
        for language in ("pt_BR", "de", "ja"):
            self.assertIn(f'<message xml:lang="{language}">', policy)
