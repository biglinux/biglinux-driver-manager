"""The black screen guard: nouveau when the display never comes up."""

import argparse
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core import gpu_cli, gpu_fallback
from core.gpu import PciDevice

VGA = 0x030000
ON_NVIDIA = [PciDevice("0000:01:00.0", "10de", "28a0", VGA, driver="nvidia")]
ON_NOUVEAU = [PciDevice("0000:01:00.0", "10de", "28a0", VGA, driver="nouveau")]


class TestHelpers(unittest.TestCase):
    def test_graphical_session(self):
        greeter = {
            "Type": "wayland",
            "Class": "greeter",
            "State": "online",
            "Remote": "no",
        }
        user = {"Type": "x11", "Class": "user", "State": "active", "Remote": "no"}
        tty = {"Type": "tty", "Class": "user", "State": "active", "Remote": "no"}
        ssh = {"Type": "x11", "Class": "user", "State": "active", "Remote": "yes"}
        self.assertTrue(gpu_fallback.graphical_session([tty, greeter]))
        self.assertTrue(gpu_fallback.graphical_session([user]))
        self.assertFalse(gpu_fallback.graphical_session([tty, ssh]))
        self.assertFalse(gpu_fallback.graphical_session([]))

    def test_nvidia_in_use(self):
        self.assertTrue(gpu_fallback.nvidia_in_use(ON_NVIDIA))
        self.assertFalse(gpu_fallback.nvidia_in_use(ON_NOUVEAU))

    def test_persist_and_clear(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            gpu_fallback.persist(root, "why")
            text = (root / gpu_fallback.PERSIST_MODPROBE).read_text()
            for module in gpu_fallback.NVIDIA_MODULES:
                self.assertIn(f"install {module} /bin/false", text)
            self.assertIn(
                "nouveau", (root / gpu_fallback.PERSIST_MODULES_LOAD).read_text()
            )
            self.assertEqual(gpu_fallback.persisted_reason(root), "why")
            self.assertEqual(len(gpu_fallback.clear_persisted(root)), 3)
            self.assertIsNone(gpu_fallback.persisted_reason(root))
            self.assertEqual(gpu_fallback.clear_persisted(root), [])


class TestDisplayFailed(unittest.TestCase):
    def _run(self, *, recorded=None, scans, live=False, fall_back=True):
        calls = []
        with TemporaryDirectory() as t:
            with (
                patch.object(gpu_fallback, "recorded", return_value=recorded),
                patch.object(gpu_cli.gpu, "scan_pci", side_effect=scans),
                patch.object(
                    gpu_cli, "LIVE_MARKER", Path(t) / ("live" if live else "x")
                ),
                patch.object(gpu_cli, "_fall_back", return_value=fall_back) as fb,
                patch.object(gpu_fallback, "persist", return_value=["p"]) as persist,
                patch.object(
                    gpu_cli, "_run", side_effect=lambda c: calls.append(c) or True
                ),
            ):
                if live:
                    (Path(t) / "live").touch()
                code = gpu_cli._display_failed()
        return code, calls, fb, persist

    def test_once_per_boot(self):
        code, calls, fb, _ = self._run(recorded="earlier", scans=[ON_NVIDIA])
        self.assertEqual((code, calls), (0, []))
        fb.assert_not_called()

    def test_not_the_nvidia_drivers_doing(self):
        code, calls, fb, _ = self._run(scans=[ON_NOUVEAU])
        self.assertEqual((code, calls), (0, []))
        fb.assert_not_called()

    def test_switched_now_restarts_the_display_manager_and_persists(self):
        code, calls, _, persist = self._run(scans=[ON_NVIDIA, ON_NOUVEAU])
        self.assertEqual(code, 0)
        self.assertIn(
            ["systemctl", "restart", "--no-block", "display-manager.service"], calls
        )
        self.assertIn(["mkinitcpio", "-P"], calls)
        persist.assert_called_once()

    def test_stuck_on_an_installed_system_persists_and_restarts_once(self):
        code, calls, _, persist = self._run(scans=[ON_NVIDIA, ON_NVIDIA])
        self.assertEqual(code, 0)
        persist.assert_called_once()
        self.assertEqual(calls[-1], ["systemctl", "reboot"])

    def test_stuck_in_the_live_session_never_reboots(self):
        code, calls, _, persist = self._run(scans=[ON_NVIDIA, ON_NVIDIA], live=True)
        self.assertEqual(code, gpu_cli.EXIT_FAILED)
        self.assertNotIn(["systemctl", "reboot"], calls)
        persist.assert_not_called()

    def test_live_switch_restarts_without_persisting(self):
        code, calls, _, persist = self._run(scans=[ON_NVIDIA, ON_NOUVEAU], live=True)
        self.assertEqual(code, 0)
        self.assertIn(
            ["systemctl", "restart", "--no-block", "display-manager.service"], calls
        )
        persist.assert_not_called()

    def test_nouveau_forbidden_stops_there(self):
        code, calls, _, persist = self._run(scans=[ON_NVIDIA], fall_back=False)
        self.assertEqual(code, gpu_cli.EXIT_FAILED)
        persist.assert_not_called()


class TestDisplayCheck(unittest.TestCase):
    def test_no_nvidia_driver_no_wait(self):
        with (
            patch.object(gpu_cli.gpu, "scan_pci", return_value=ON_NOUVEAU),
            patch.object(gpu_cli, "_logind_sessions") as sessions,
        ):
            self.assertEqual(gpu_cli._display_check(), 0)
        sessions.assert_not_called()

    def test_session_found(self):
        greeter = {
            "Type": "wayland",
            "Class": "greeter",
            "State": "online",
            "Remote": "no",
        }
        with (
            patch.object(gpu_cli.gpu, "scan_pci", return_value=ON_NVIDIA),
            patch.object(gpu_cli, "_logind_sessions", return_value=[greeter]),
            patch.object(gpu_cli, "_display_failed") as failed,
        ):
            self.assertEqual(gpu_cli._display_check(), 0)
        failed.assert_not_called()

    def test_nothing_appears_in_time(self):
        with (
            patch.object(gpu_cli.gpu, "scan_pci", return_value=ON_NVIDIA),
            patch.object(gpu_cli, "_logind_sessions", return_value=[]),
            patch.object(gpu_cli, "DISPLAY_TIMEOUT", 0.05),
            patch.object(gpu_cli, "DISPLAY_POLL", 0.01),
            patch.object(gpu_cli, "_display_failed", return_value=0) as failed,
        ):
            gpu_cli._display_check()
        self.assertIn("no login screen", failed.call_args.args[0])


class TestInstallClearsTheFallback(unittest.TestCase):
    def test_installing_nvidia_again_clears_the_persisted_fallback(self):
        from core import gpu

        plan = gpu.GpuPlan(
            install=["nvidia-utils"], nvidia=gpu.NvidiaChoice(branch="current")
        )
        with TemporaryDirectory() as t:
            root = Path(t)
            for relative in ("etc", "usr", "usr/bin", "usr/lib"):
                (root / relative).mkdir(parents=True, exist_ok=True)
            gpu_fallback.persist(root, "earlier")
            args = argparse.Namespace(root=root, pmconfig=None)
            with (
                patch.object(gpu_cli, "_build_plan", return_value=plan),
                patch.object(gpu_cli.gpu, "installed_packages", return_value=set()),
                patch.object(gpu_cli.gpu, "installed_kernels", return_value=[]),
                patch.object(gpu_cli.subprocess, "run") as run,
            ):
                run.return_value.returncode = 0
                self.assertEqual(gpu_cli._install(args), 0)
            self.assertIsNone(gpu_fallback.persisted_reason(root))


if __name__ == "__main__":
    unittest.main()
