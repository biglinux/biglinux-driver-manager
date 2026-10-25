#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Additional unit coverage for core and logging modules."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(__file__), "..", "usr", "share", "big-driver-manager-cli"
    ),
)


class TestBaseManagerExtra(unittest.TestCase):
    def test_run_pacman_command_uses_custom_thread_launcher(self):
        captured = []

        def launcher(target, args):
            captured.append((target.__name__, args))

        from core.base_manager import BaseManager

        mgr = BaseManager(thread_launcher=launcher)
        mgr.run_pacman_command(args=["-S", "mesa"], operation_name="Install")

        self.assertEqual(captured[0][0], "_execute_command_thread")
        self.assertEqual(captured[0][1][0], ["-S", "mesa"])
        self.assertEqual(captured[0][1][-1], "Install")

    def test_cancel_operation_kills_process_after_timeout(self):
        from core.base_manager import BaseManager

        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="pacman", timeout=2),
            None,
        ]

        mgr = BaseManager()
        mgr._current_process = process

        mgr.cancel_operation()

        self.assertTrue(mgr._cancelled)
        process.terminate.assert_called_once()
        process.kill.assert_called_once()

    def test_execute_command_thread_retries_on_locked_database(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        outputs = []
        progress = []
        completed = []

        def fake_attempt(_cmd, attempt, progress_callback, output_callback, _op):
            mgr._current_process = SimpleNamespace(returncode=0 if attempt else 1)
            if attempt == 0:
                mgr._last_output_lines = ["error: unable to lock database"]
                return False
            return True

        with (
            patch.object(mgr, "_run_single_attempt", side_effect=fake_attempt),
            patch("core.base_manager.time.sleep") as sleep_mock,
        ):
            mgr._execute_command_thread(
                ["-S", "--noconfirm", "--needed", "pkg"],
                lambda frac, text: progress.append((frac, text)),
                outputs.append,
                completed.append,
                "Installing pkg",
            )

        self.assertGreaterEqual(len(outputs), 3)
        self.assertEqual(completed, [True])
        sleep_mock.assert_called_once()

    def test_run_single_attempt_handles_spawn_exception(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        outputs = []
        progress = []

        with patch("core.base_manager.subprocess.Popen", side_effect=OSError("boom")):
            result = mgr._run_single_attempt(
                ["sudo", "pacman"],
                0,
                lambda frac, text: progress.append((frac, text)),
                outputs.append,
                "Install",
            )

        self.assertIsNone(result)
        self.assertTrue(any("boom" in line for line in outputs))
        self.assertTrue(any(item[1] and "boom" in item[1] for item in progress))

    def test_progress_parsing_and_error_recovery(self):
        from core.base_manager import BaseManager

        mgr = BaseManager()
        self.assertEqual(mgr._parse_download_progress("downloading foo 75%", 0.1), 0.4)
        self.assertEqual(mgr._parse_download_progress("downloading (3/4)", 0.1), 0.4)
        progress, text = mgr._parse_progress("checking dependencies", 0.0)
        self.assertEqual(progress, 0.2)
        self.assertTrue(text)

        outputs = []
        mgr._last_output_lines = ["target not found: nonexistent"]
        mgr._suggest_error_recovery(outputs.append)
        self.assertEqual(len(outputs), 1)
        self.assertIn("pac", outputs[0].lower())


class TestKernelManagerExtra(unittest.TestCase):
    def _make_manager(self):
        with patch("core.kernel_manager.get_logger"):
            from core.kernel_manager import KernelManager

            mgr = KernelManager()
            mgr._lts_versions = ["66", "612"]
            return mgr

    def test_get_running_kernel_package_matches_and_falls_back(self):
        mgr = self._make_manager()
        with (
            patch.object(
                mgr,
                "get_installed_kernels",
                return_value=[
                    {"name": "linux612", "version": "6.12.10-1"},
                    {"name": "linux66", "version": "6.6.70-1"},
                ],
            ),
            patch.object(mgr, "get_running_kernel", return_value="6.12.10-1-MANJARO"),
        ):
            self.assertEqual(mgr.get_running_kernel_package(), "linux612")

        with (
            patch.object(
                mgr,
                "get_installed_kernels",
                return_value=[{"name": "linux612", "version": "6.12.9-1"}],
            ),
            patch.object(mgr, "get_running_kernel", return_value="6.12.10-1-MANJARO"),
        ):
            self.assertEqual(mgr.get_running_kernel_package(), "linux612")

    @patch("subprocess.run")
    def test_search_kernel_packages_filters_and_parses_results(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "core/linux612 6.12.10-1\n"
                "extra/python 3.13.0-1\n"
                "core/linux612-headers 6.12.10-1\n"
            ),
        )
        mgr = self._make_manager()
        kernels = mgr._search_kernel_packages("linux")
        self.assertEqual(
            kernels,
            [{"name": "linux612", "version": "6.12.10-1", "repository": "core"}],
        )

    def test_get_kernel_modules_includes_headers_and_repo_filter(self):
        mgr = self._make_manager()
        mgr.package_manager = MagicMock()
        mgr.package_manager.get_installed_packages.return_value = [
            {"name": "linux612-headers"},
            {"name": "linux612-nvidia-550xx"},
            {"name": "mesa"},
        ]

        with (
            patch.object(mgr, "get_running_kernel_package", return_value="linux612"),
            patch.object(
                mgr,
                "_filter_existing_in_repos",
                return_value=["linux619-headers", "linux619-nvidia-550xx"],
            ),
        ):
            modules = mgr._get_kernel_modules("linux619")

        self.assertEqual(modules, ["linux619-headers", "linux619-nvidia-550xx"])

    def test_get_obsolete_kernels_skips_running_kernel(self):
        mgr = self._make_manager()
        with (
            patch.object(
                mgr,
                "get_installed_kernels",
                return_value=[
                    {"name": "linux66", "version": "6.6.70-1"},
                    {"name": "linux612", "version": "6.12.10-1"},
                ],
            ),
            patch.object(
                mgr,
                "get_available_kernels",
                return_value=[{"name": "linux612", "version": "6.12.10-1"}],
            ),
            patch.object(mgr, "get_running_kernel_package", return_value="linux612"),
        ):
            obsolete = mgr.get_obsolete_kernels()

        self.assertEqual(len(obsolete), 1)
        self.assertEqual(obsolete[0]["name"], "linux66")
        self.assertTrue(obsolete[0]["obsolete"])

    def test_install_and_remove_kernel_use_precomputed_packages(self):
        mgr = self._make_manager()
        with patch.object(mgr, "run_pacman_command") as run_cmd:
            mgr.install_kernel(
                {"name": "linux612"}, packages=["linux612", "linux612-headers"]
            )
            mgr.remove_kernel(
                {"name": "linux612"}, packages=["linux612", "linux612-headers"]
            )

        self.assertEqual(
            run_cmd.call_args_list[0].kwargs["args"],
            ["-S", "--noconfirm", "linux612", "linux612-headers"],
        )
        self.assertEqual(
            run_cmd.call_args_list[1].kwargs["args"],
            ["-R", "--noconfirm", "linux612", "linux612-headers"],
        )


class TestMesaManagerExtra(unittest.TestCase):
    def _make_manager(self):
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
                    "packages": ["mesa-tkg-stable"],
                    "detect_package": "mesa-tkg-stable",
                    "conflicts": ["mesa"],
                },
            ]
            return mgr

    def test_get_available_drivers_marks_active_from_installed_set(self):
        mgr = self._make_manager()
        drivers = mgr.get_available_drivers(installed_set={"mesa-tkg-stable"})
        active = {driver["id"]: driver["active"] for driver in drivers}
        self.assertFalse(active["stable"])
        self.assertTrue(active["tkg-stable"])

    def test_apply_driver_reports_missing_driver(self):
        mgr = self._make_manager()
        outputs = []
        completed = []
        mgr.apply_driver(
            "missing",
            output_callback=outputs.append,
            complete_callback=completed.append,
        )
        self.assertIn("missing", outputs[0])
        self.assertEqual(completed, [False])

    def test_apply_driver_runs_the_whole_switch_as_one_cli_request(self):
        # One pkexec request: the switch (download, replace, roll back) runs
        # as root in "mesa apply", never as separate remove/install steps.
        mgr = self._make_manager()
        captured = []
        with (
            patch.object(
                mgr, "run_cli_command", side_effect=lambda *a, **k: captured.append(a)
            ),
            patch.object(mgr, "run_pacman_command") as run_pacman,
        ):
            mgr.apply_driver("tkg-stable")
        self.assertEqual(captured[0][0], ["mesa", "apply", "tkg-stable", "--confirmed"])
        run_pacman.assert_not_called()

    def test_packages_available_parses_multiple_name_blocks(self):
        mgr = self._make_manager()
        fake_out = (
            "Repository    : extra\n"
            "Name           : mesa\n"
            "Version        : 25.0-1\n"
            "\n"
            "Repository    : extra\n"
            "Name           : vulkan-radeon\n"
            "Version        : 25.0-1\n"
        )
        result = MagicMock()
        result.stdout = fake_out
        result.returncode = 0
        with patch("core.mesa_manager.subprocess.run", return_value=result):
            found = mgr._packages_available(["mesa", "vulkan-radeon", "bogus"])
        self.assertEqual(found, {"mesa", "vulkan-radeon"})


class TestLoggingAndExceptions(unittest.TestCase):
    def test_setup_logging_warns_when_file_handler_fails(self):
        from core.constants import APP_NAME
        from core.logging_config import setup_logging

        with (
            patch("core.logging_config.os.makedirs"),
            patch(
                "core.logging_config.RotatingFileHandler",
                side_effect=OSError("no disk"),
            ),
        ):
            logger = setup_logging(console_output=True, file_output=True)

        self.assertEqual(logger.name, APP_NAME)
        self.assertTrue(logger.handlers)

    def test_init_app_logging_uses_debug_level(self):
        from core import logging_config

        with patch.object(logging_config, "setup_logging") as setup:
            logging_config.init_app_logging(debug=True)
            self.assertEqual(setup.call_args.kwargs["level"], logging.DEBUG)

    def test_custom_exceptions_build_human_messages(self):
        from core.exceptions import (
            InstallationError,
            PackageNotFoundError,
            PrivilegeError,
            RemovalError,
        )

        self.assertIn("mesa", str(PackageNotFoundError("mesa")))
        self.assertIn("exit code: 2", str(InstallationError("mesa", return_code=2)))
        self.assertIn("exit code: 3", str(RemovalError("mesa", return_code=3)))
        self.assertIn("remove", str(PrivilegeError("remove")))
