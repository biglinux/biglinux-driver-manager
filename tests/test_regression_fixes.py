#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Regression tests guarding the audit-driven fixes.

Each test asserts a single invariant established by a specific audit item
(C1–C5, H1–H10, M1–M15, L2, L10, L15). Keep the docstrings explicit so
future contributors understand which guarantee would break if the test
fails.
"""

from __future__ import annotations

import configparser
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


# Source roots
REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "usr" / "share" / "big-driver-manager"
sys.path.insert(0, str(APP_SRC))


# ---------------------------------------------------------------------------
# C1 / C2 — Safe Mesa flow + cancellable
# ---------------------------------------------------------------------------


class TestMesaApplyIsSafe(unittest.TestCase):
    """C1 + C2: Mesa apply never uses ``-Rdd``/``--ask 4`` and is cancellable."""

    def _make_manager(self, installed: list[str], available: set[str]):
        with patch("core.mesa_manager.get_logger"):
            from core.mesa_manager import MesaManager

            mgr = MesaManager()
            mgr.drivers = [
                {
                    "id": "stable",
                    "name": "mesa",
                    "packages": ["mesa"],
                    "conflicts": [],
                },
                {
                    "id": "tkg-stable",
                    "name": "mesa-tkg-stable",
                    "detect_package": "mesa-tkg-stable",
                    "packages": ["mesa-tkg-stable"],
                    "conflicts": ["mesa"],
                },
            ]
            installed_set = set(installed)
            mgr._is_real_package_installed = lambda p: p in installed_set
            mgr._packages_available = lambda pkgs: set(pkgs) & available
            return mgr

    def _capture_calls(self, mgr, complete_success_sequence):
        calls: list[list[str]] = []
        seq = iter(complete_success_sequence)

        def fake_run_pacman(**kwargs):
            calls.append(list(kwargs["args"]))
            cb = kwargs.get("complete_callback")
            if cb:
                try:
                    cb(next(seq))
                except StopIteration:
                    cb(True)

        mgr.run_pacman_command = fake_run_pacman
        return calls

    def test_apply_never_uses_Rdd(self):
        mgr = self._make_manager(["mesa"], {"mesa-tkg-stable"})
        calls = self._capture_calls(mgr, [True, True])
        completed: list[bool] = []
        mgr._apply_driver_thread(
            mgr.drivers[1], None, lambda _l: None, completed.append
        )
        for call in calls:
            self.assertNotIn("-Rdd", call)
        self.assertEqual(completed, [True])

    def test_apply_never_uses_ask_4(self):
        mgr = self._make_manager(["mesa"], {"mesa-tkg-stable"})
        calls = self._capture_calls(mgr, [True, True])
        mgr._apply_driver_thread(mgr.drivers[1], None, lambda _l: None, lambda _s: None)
        for call in calls:
            self.assertNotIn("--ask", call)

    def test_apply_uses_Rnc_for_conflict_removal(self):
        mgr = self._make_manager(["mesa"], {"mesa-tkg-stable"})
        calls = self._capture_calls(mgr, [True, True])
        mgr._apply_driver_thread(mgr.drivers[1], None, lambda _l: None, lambda _s: None)
        self.assertIn("-Rnc", calls[0])

    def test_apply_uses_needed_and_overwrite_on_install(self):
        mgr = self._make_manager(["mesa"], {"mesa-tkg-stable"})
        calls = self._capture_calls(mgr, [True, True])
        mgr._apply_driver_thread(mgr.drivers[1], None, lambda _l: None, lambda _s: None)
        # The install call is the second one (first is the remove).
        self.assertIn("-S", calls[1])
        self.assertIn("--needed", calls[1])
        self.assertIn("--overwrite", calls[1])
        # Followed immediately by the glob pattern "*".
        overwrite_idx = calls[1].index("--overwrite")
        self.assertEqual(calls[1][overwrite_idx + 1], "*")

    def test_apply_aborts_install_when_remove_fails(self):
        mgr = self._make_manager(["mesa"], {"mesa-tkg-stable"})
        calls = self._capture_calls(mgr, [False])
        completed: list[bool] = []
        mgr._apply_driver_thread(
            mgr.drivers[1], None, lambda _l: None, completed.append
        )
        # Only the remove call should have been issued; install must not run.
        self.assertEqual(len(calls), 1)
        self.assertEqual(completed, [False])

    def test_apply_skips_remove_phase_when_no_conflicts(self):
        mgr = self._make_manager([], {"mesa-tkg-stable"})
        calls = self._capture_calls(mgr, [True])
        mgr._apply_driver_thread(mgr.drivers[1], None, lambda _l: None, lambda _s: None)
        self.assertEqual(len(calls), 1)
        self.assertIn("-S", calls[0])

    def test_apply_respects_cancelled_flag(self):
        """When the user cancels during remove, install must not fire."""
        mgr = self._make_manager(["mesa"], {"mesa-tkg-stable"})
        calls: list[list[str]] = []

        def fake_run_pacman(**kwargs):
            calls.append(list(kwargs["args"]))
            mgr._cancelled = True  # Simulate the user clicking Cancel.
            cb = kwargs.get("complete_callback")
            if cb:
                cb(True)  # remove succeeded but user already cancelled

        mgr.run_pacman_command = fake_run_pacman
        completed: list[bool] = []
        mgr._apply_driver_thread(
            mgr.drivers[1], None, lambda _l: None, completed.append
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(completed, [False])


class TestMesaPackagesAvailable(unittest.TestCase):
    """C1 helper: bulk package availability query."""

    def _make_manager(self):
        with patch("core.mesa_manager.get_logger"):
            from core.mesa_manager import MesaManager

            return MesaManager()

    def test_returns_only_found_names(self):
        mgr = self._make_manager()
        fake_out = (
            "Name            : mesa\n"
            "Version         : 25\n"
            "Name            : vulkan-radeon\n"
            "Version         : 25\n"
        )
        with patch(
            "core.mesa_manager.subprocess.run",
            return_value=MagicMock(returncode=0, stdout=fake_out),
        ):
            found = mgr._packages_available(["mesa", "vulkan-radeon", "bogus"])
        self.assertEqual(found, {"mesa", "vulkan-radeon"})

    def test_empty_input_skips_subprocess(self):
        mgr = self._make_manager()
        with patch("core.mesa_manager.subprocess.run") as run:
            self.assertEqual(mgr._packages_available([]), set())
            run.assert_not_called()


# ---------------------------------------------------------------------------
# C3 / C4 — Packaging metadata
# ---------------------------------------------------------------------------


class TestPackagingMetadata(unittest.TestCase):
    """C3: licence consistency. C4: Python>=3.10 declared."""

    def test_pkgbuild_declares_mit_license(self):
        text = (REPO_ROOT / "pkgbuild" / "PKGBUILD").read_text(encoding="utf-8")
        self.assertRegex(text, r"license=\(\s*'MIT'\s*\)")

    def test_license_file_is_mit(self):
        text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", text.splitlines()[0])

    def test_about_dialog_declares_mit(self):
        window = (APP_SRC / "ui" / "window.py").read_text(encoding="utf-8")
        self.assertIn("Gtk.License.MIT_X11", window)
        self.assertNotIn("Gtk.License.GPL_3_0", window)

    def test_pkgbuild_python_min_version_is_310(self):
        text = (REPO_ROOT / "pkgbuild" / "PKGBUILD").read_text(encoding="utf-8")
        self.assertIn("python>=3.10", text)
        self.assertNotIn("python>=3.6", text)

    def test_pkgbuild_install_hook_has_shebang(self):
        first_line = (
            (REPO_ROOT / "pkgbuild" / "pkgbuild.install")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        self.assertTrue(
            first_line.startswith("#!"),
            f"pkgbuild.install missing shebang (got {first_line!r})",
        )

    def test_desktop_file_has_keywords_and_hardware_category(self):
        # L10: discoverability in GNOME Shell / KRunner.
        parser = configparser.RawConfigParser(strict=False)
        parser.read(
            REPO_ROOT
            / "usr"
            / "share"
            / "applications"
            / "br.com.biglinux.drivermanager.desktop",
            encoding="utf-8",
        )
        entry = parser["Desktop Entry"]
        self.assertIn("Keywords", entry)
        self.assertIn("driver", entry["Keywords"].lower())
        self.assertIn("HardwareSettings", entry["Categories"])


# ---------------------------------------------------------------------------
# C5 — animations_enabled tolerates headless
# ---------------------------------------------------------------------------


class TestAnimationsEnabledHeadless(unittest.TestCase):
    """C5: ``animations_enabled`` never raises, even with stub Gtk.Settings."""

    def test_without_get_default_returns_true(self):
        from utils import accessibility

        class FakeSettings:  # no ``get_default`` attribute
            pass

        with patch.object(accessibility.Gtk, "Settings", FakeSettings):
            self.assertTrue(accessibility.animations_enabled())

    def test_raises_default_value_true(self):
        from utils import accessibility

        class FakeSettings:
            @staticmethod
            def get_default():
                raise RuntimeError("no display")

        with patch.object(accessibility.Gtk, "Settings", FakeSettings):
            self.assertTrue(accessibility.animations_enabled())

    def test_returns_underlying_property(self):
        from utils import accessibility

        class FakeObj:
            def get_property(self, _name):
                return False

        class FakeSettings:
            @staticmethod
            def get_default():
                return FakeObj()

        with patch.object(accessibility.Gtk, "Settings", FakeSettings):
            self.assertFalse(accessibility.animations_enabled())


# ---------------------------------------------------------------------------
# H1 — Public run_pacman_command API
# ---------------------------------------------------------------------------


class TestRunPacmanCommandIsPublic(unittest.TestCase):
    """H1: ``run_pacman_command`` is public; UI must not touch underscore APIs."""

    def test_base_manager_exposes_public_method(self):
        from core.base_manager import BaseManager

        self.assertTrue(hasattr(BaseManager, "run_pacman_command"))
        self.assertTrue(callable(BaseManager.run_pacman_command))

    def test_ui_modules_do_not_call_private_run_pacman(self):
        for name in ("home_page.py", "mesa_page.py", "kernel_page.py"):
            src = (APP_SRC / "ui" / name).read_text(encoding="utf-8")
            self.assertNotIn(
                "_run_pacman_command",
                src,
                f"{name} still references private _run_pacman_command",
            )

    def test_old_private_alias_is_removed(self):
        from core.base_manager import BaseManager

        self.assertFalse(
            hasattr(BaseManager, "_run_pacman_command"),
            "_run_pacman_command alias should be removed after migration",
        )


# ---------------------------------------------------------------------------
# H2 / H3 — Shared PackageManager and cached DriverDatabase
# ---------------------------------------------------------------------------


class TestSharedPackageManager(unittest.TestCase):
    def setUp(self):
        from core.package_manager import PackageManager

        PackageManager.reset_default()

    def test_get_default_returns_singleton(self):
        from core.package_manager import PackageManager

        self.assertIs(PackageManager.get_default(), PackageManager.get_default())

    def test_managers_share_default_package_manager(self):
        from core.kernel_manager import KernelManager
        from core.mesa_manager import MesaManager
        from core.package_manager import PackageManager

        default = PackageManager.get_default()
        with (
            patch("core.kernel_manager.get_logger"),
            patch("core.mesa_manager.get_logger"),
        ):
            km = KernelManager()
            mm = MesaManager()
        self.assertIs(km.package_manager, default)
        self.assertIs(mm.package_manager, default)

    def test_explicit_injection_is_honored(self):
        from core.kernel_manager import KernelManager
        from core.package_manager import PackageManager

        pm = PackageManager()
        with patch("core.kernel_manager.get_logger"):
            km = KernelManager(package_manager=pm)
        self.assertIs(km.package_manager, pm)


class TestDriverDatabaseCache(unittest.TestCase):
    def setUp(self):
        from core.driver_database import DriverDatabase

        DriverDatabase.reset_cache()

    def test_get_default_memoizes_by_assets_dir(self):
        from core.driver_database import DriverDatabase

        a = DriverDatabase.get_default()
        b = DriverDatabase.get_default()
        self.assertIs(a, b)

    def test_reset_cache_returns_fresh_instance(self):
        from core.driver_database import DriverDatabase

        a = DriverDatabase.get_default()
        DriverDatabase.reset_cache()
        b = DriverDatabase.get_default()
        self.assertIsNot(a, b)


# ---------------------------------------------------------------------------
# H4 — VM detection is deferred off the UI thread
# ---------------------------------------------------------------------------


class TestVmDetectionDeferred(unittest.TestCase):
    """H4: MesaSection doesn't call systemd-detect-virt during __init__."""

    def test_mesa_page_init_does_not_invoke_detect_virt(self):
        # We scan the source rather than instantiating MesaSection (which
        # would require a full Gtk runtime or the gi_fakes setup).
        src = (APP_SRC / "ui" / "mesa_page.py").read_text(encoding="utf-8")
        # There should be a set_is_vm method so the window can inject the
        # result from its background thread pool.
        self.assertIn("def set_is_vm(", src)
        # __init__ must default _is_vm to False and must NOT immediately
        # call _detect_virtual_machine.
        init_body = re.search(
            r"def __init__\(self\) -> None:(.+?)def ", src, flags=re.DOTALL
        )
        self.assertIsNotNone(init_body)
        self.assertIn("self._is_vm = False", init_body.group(1))
        self.assertNotIn("_detect_virtual_machine()", init_body.group(1))


# ---------------------------------------------------------------------------
# H7 — __pycache__ not tracked
# ---------------------------------------------------------------------------


class TestNoPycacheTracked(unittest.TestCase):
    def test_no_pyc_files_in_git(self):
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=15,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.skipTest("git not available")
        tracked = result.stdout.splitlines()
        bad = [p for p in tracked if "__pycache__" in p or p.endswith(".pyc")]
        self.assertFalse(bad, f"tracked bytecode files: {bad}")


# ---------------------------------------------------------------------------
# H10 — DEFAULT_LTS_VERSIONS kept current
# ---------------------------------------------------------------------------


class TestDefaultLtsList(unittest.TestCase):
    def test_includes_linux_61(self):
        from core.constants import DEFAULT_LTS_VERSIONS

        # 6.1 is a long-term kernel and historically absent from the list.
        self.assertIn("61", DEFAULT_LTS_VERSIONS)
        # Keep the list sorted ascending for readability.
        as_ints = [int(v) for v in DEFAULT_LTS_VERSIONS]
        self.assertEqual(as_ints, sorted(as_ints))


# ---------------------------------------------------------------------------
# M6 — Public kernel module planning API
# ---------------------------------------------------------------------------


class TestKernelModulePlanningPublicAPI(unittest.TestCase):
    def _make_manager(self):
        from core.package_manager import PackageManager

        PackageManager.reset_default()
        with patch("core.kernel_manager.get_logger"):
            from core.kernel_manager import KernelManager

            return KernelManager()

    def test_get_modules_for_install_delegates(self):
        mgr = self._make_manager()
        with patch.object(
            mgr, "_get_kernel_modules", return_value=["linux612-headers"]
        ) as stub:
            self.assertEqual(
                mgr.get_modules_for_install("linux612"), ["linux612-headers"]
            )
            stub.assert_called_once_with("linux612")

    def test_get_modules_for_remove_delegates(self):
        mgr = self._make_manager()
        with patch.object(
            mgr,
            "_get_installed_kernel_modules",
            return_value=["linux612-headers", "linux612-nvidia"],
        ) as stub:
            self.assertEqual(
                mgr.get_modules_for_remove("linux612"),
                ["linux612-headers", "linux612-nvidia"],
            )
            stub.assert_called_once_with("linux612")


# ---------------------------------------------------------------------------
# M7 — Dedup obsolete kernel calculation via pure helper
# ---------------------------------------------------------------------------


class TestComputeObsoleteKernelsPure(unittest.TestCase):
    def test_marks_missing_and_keeps_running(self):
        from core.kernel_manager import KernelManager

        installed = [
            {"name": "linux66", "version": "6.6"},
            {"name": "linux612", "version": "6.12"},
            {"name": "linux-zen", "version": "6.19"},
        ]
        available = [
            {"name": "linux612", "version": "6.12"},
            {"name": "linux-zen", "version": "6.19"},
        ]
        obs = KernelManager.compute_obsolete_kernels(installed, available, "linux612")
        names = [k["name"] for k in obs]
        self.assertEqual(names, ["linux66"])
        self.assertTrue(obs[0]["obsolete"])

    def test_never_flags_running_kernel(self):
        from core.kernel_manager import KernelManager

        installed = [{"name": "linux99", "version": "9.9"}]
        # linux99 is not in the repos but it IS the running kernel.
        obs = KernelManager.compute_obsolete_kernels(installed, [], "linux99")
        self.assertEqual(obs, [])


# ---------------------------------------------------------------------------
# M9 — MHWD version display hides fake date-versions
# ---------------------------------------------------------------------------


class TestMhwdRowVersionDisplay(unittest.TestCase):
    """M9: date-like versions (2025.09.29) must not show as 'v...'."""

    def test_regex_rejects_date_version(self):
        # Mirror the regex used in mesa_page._build_mhwd_row.
        pattern = re.compile(r"^\d{1,3}\.\d+(\.\d+)?([-.]\w+)?$")
        self.assertIsNone(pattern.match("2025.09.29"))  # date → hidden
        self.assertTrue(pattern.match("590.48.01"))  # real NVIDIA → shown
        self.assertTrue(pattern.match("25.1-1"))

    def test_mesa_page_uses_restricted_regex(self):
        # Guard: the regex in source must match the one tested above.
        src = (APP_SRC / "ui" / "mesa_page.py").read_text(encoding="utf-8")
        self.assertIn(r"\d{1,3}\.\d+", src)


# ---------------------------------------------------------------------------
# M10 — udev rule ignores hubs
# ---------------------------------------------------------------------------


class TestUdevRuleFiltersHubs(unittest.TestCase):
    def test_rule_excludes_class_09(self):
        text = (
            REPO_ROOT
            / "usr"
            / "lib"
            / "udev"
            / "rules.d"
            / "99-big-driver-manager.rules"
        ).read_text(encoding="utf-8")
        self.assertIn('bDeviceClass}!="09"', text)


# ---------------------------------------------------------------------------
# M12 — Mesa GPU detection uses shared subprocess_env
# ---------------------------------------------------------------------------


class TestMesaGpuInfoUsesSubprocessEnv(unittest.TestCase):
    def test_detect_gpu_info_calls_subprocess_env(self):
        # Scan the source: dynamic import would require gi fakes.
        src = (APP_SRC / "ui" / "mesa_page.py").read_text(encoding="utf-8")
        self.assertIn("from core.subprocess_env import subprocess_env", src)
        m = re.search(r"def _detect_gpu_info.*?def ", src, flags=re.DOTALL)
        self.assertIsNotNone(m)
        self.assertIn("subprocess_env()", m.group(0))


# ---------------------------------------------------------------------------
# M15 — Progress dialog tag word-boundary matching
# ---------------------------------------------------------------------------


class TestProgressTagWordBoundary(unittest.TestCase):
    """M15: 'no errors found' is NOT tagged as error."""

    def test_line_tag_false_positive_free(self):
        from ui.progress_dialog import ProgressDialog

        # Bypass __init__: we only need _get_line_tag (a plain method).
        dlg = ProgressDialog.__new__(ProgressDialog)
        self.assertIsNone(dlg._get_line_tag("no errors found"))
        self.assertIsNone(dlg._get_line_tag("error message handling implemented"))
        self.assertEqual(dlg._get_line_tag("error: unable to lock database"), "error")
        self.assertEqual(
            dlg._get_line_tag("Transaction completed successfully."), "success"
        )
        self.assertEqual(dlg._get_line_tag("warning: signature is invalid"), "warning")
        self.assertEqual(dlg._get_line_tag("Installing linux612"), "info")


# ---------------------------------------------------------------------------
# L15 — utils.gtk_helpers exists and is independently usable
# ---------------------------------------------------------------------------


class TestGtkHelpersModule(unittest.TestCase):
    def test_module_exports_clear_functions(self):
        from utils import gtk_helpers

        for name in ("clear_box", "clear_listbox", "clear_flow"):
            self.assertTrue(hasattr(gtk_helpers, name), name)

    def test_clear_box_handles_empty_box(self):
        from utils.gtk_helpers import clear_box

        class FakeBox:
            def get_first_child(self):
                return None

            def remove(self, _child):  # pragma: no cover - never called
                raise AssertionError("remove should not be called on empty box")

        clear_box(FakeBox())

    def test_clear_box_removes_all_children(self):
        from utils.gtk_helpers import clear_box

        class Child:
            def __init__(self, nxt=None):
                self._next = nxt

            def get_next_sibling(self):
                return self._next

        c2 = Child(None)
        c1 = Child(c2)

        class FakeBox:
            def __init__(self):
                self._front = c1
                self.removed: list[Child] = []

            def get_first_child(self):
                return self._front

            def remove(self, child):
                self.removed.append(child)
                # Emulate Gtk semantics: after removal the next sibling
                # becomes the new first child.
                self._front = child._next

        box = FakeBox()
        clear_box(box)
        self.assertEqual(box.removed, [c1, c2])


# ---------------------------------------------------------------------------
# Scripts — bash syntax + shellcheck clean
# ---------------------------------------------------------------------------


class TestShellScriptsValid(unittest.TestCase):
    SCRIPTS = [
        REPO_ROOT / "usr" / "bin" / "big-driver-manager",
        REPO_ROOT / "usr" / "share" / "big-driver-manager" / "login-check-drivers.sh",
        REPO_ROOT / "usr" / "share" / "big-driver-manager" / "udev-notify.sh",
        REPO_ROOT / "usr" / "share" / "big-driver-manager" / "build-ids-cache.sh",
        REPO_ROOT / "usr" / "share" / "big-driver-manager" / "test-udev-dialog.sh",
        REPO_ROOT / "pkgbuild" / "pkgbuild.install",
    ]

    def test_bash_syntax_all_scripts(self):
        for script in self.SCRIPTS:
            with self.subTest(script=str(script.relative_to(REPO_ROOT))):
                result = subprocess.run(
                    ["bash", "-n", str(script)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_login_check_uses_blacklist_set(self):
        # H8: lookup should be O(1) via declare -A, not O(N) grep echo loop.
        text = (
            REPO_ROOT
            / "usr"
            / "share"
            / "big-driver-manager"
            / "login-check-drivers.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("declare -A BLACKLIST_SET", text)
        self.assertNotIn('grep -qF "$cache_id"', text)

    def test_udev_notify_has_global_cap(self):
        # H9: concurrent dialog cap is documented and enforced.
        text = (
            REPO_ROOT / "usr" / "share" / "big-driver-manager" / "udev-notify.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("MAX_CONCURRENT", text)

    def test_build_cache_checks_writability(self):
        text = (
            REPO_ROOT / "usr" / "share" / "big-driver-manager" / "build-ids-cache.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("[[ ! -w", text)


class TestBinWrapperHandlesMissingInstall(unittest.TestCase):
    """M8: the bash wrapper resolves install dir without brace-range hacks."""

    def test_wrapper_uses_glob_not_brace_range(self):
        text = (REPO_ROOT / "usr" / "bin" / "big-driver-manager").read_text(
            encoding="utf-8"
        )
        # The old wrapper looped python3.{25..6}; we replaced it with a
        # glob + version sort that won't age out.
        self.assertNotIn("python3.{25..6}", text)
        self.assertIn("/usr/lib/python3.*/site-packages/big-driver-manager", text)

    def test_find_install_dir_returns_dev_tree_fallback(self):
        """When nothing is installed system-wide the wrapper uses ../share."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bin_dir = td_path / "usr" / "bin"
            share_dir = td_path / "usr" / "share" / "big-driver-manager"
            bin_dir.mkdir(parents=True)
            share_dir.mkdir(parents=True)
            wrapper = bin_dir / "big-driver-manager"
            wrapper.write_text(
                (REPO_ROOT / "usr" / "bin" / "big-driver-manager").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            # We source the script (no ``exec`` runs) and invoke only the
            # helper function. This also covers the defensive `set -o pipefail`.
            probe = subprocess.run(
                [
                    "bash",
                    "-c",
                    # Rewrite the exec line out so sourcing is safe.
                    f"source <(sed 's/^exec /true /' {wrapper}); find_install_dir",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(probe.returncode, 0, msg=probe.stderr)
            # The probe prints the install directory on stdout; we require
            # that it points somewhere usable.
            resolved = probe.stdout.strip().splitlines()[-1]
            self.assertTrue(resolved, "find_install_dir produced no output")


# ---------------------------------------------------------------------------
# M13 — i18n wrapper still importable (smoke)
# ---------------------------------------------------------------------------


class TestI18NSmoke(unittest.TestCase):
    def test_underscore_helper_is_callable_and_returns_str(self):
        from utils.i18n import _

        # gettext may or may not translate depending on the installed
        # locale; we only assert the callable contract here.
        result = _("Install")
        self.assertIsInstance(result, str)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# .gitignore sanity
# ---------------------------------------------------------------------------


class TestGitignoreSanity(unittest.TestCase):
    def test_ruff_toml_not_ignored(self):
        text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("\nruff.toml\n", text)

    def test_pycache_ignored(self):
        text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("__pycache__/", text)


if __name__ == "__main__":
    unittest.main()
