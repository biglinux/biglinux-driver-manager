"""Regressions for the review of the GPU stack (2026-10-19)."""

import argparse
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core import gpu, gpu_cli, gpu_mode
from core.gpu import NvidiaChip, PciDevice, build_plan, choose_nvidia

VGA = 0x030000
INTEL = PciDevice("0000:00:02.0", "8086", "a7a0", VGA, boot_vga=True)
ADA = PciDevice("0000:01:00.0", "10de", "28a0", VGA)
PASCAL = PciDevice("0000:02:00.0", "10de", "1c03", VGA)
KEPLER = PciDevice("0000:03:00.0", "10de", "1004", VGA)
ASPEED = PciDevice("0000:05:00.0", "1a03", "2000", VGA, boot_vga=True)
CHIPS = {
    "28a0": NvidiaChip(
        "28a0", "RTX 4060", None, frozenset({"kernelopen", "runtimepm"})
    ),
    "1c03": NvidiaChip("1c03", "GTX 1060", "580.xx", frozenset()),
    "1004": NvidiaChip("1004", "GTX 780", "470.xx", frozenset()),
}
REPO = {
    "nvidia-utils",
    "nvidia-settings",
    "linux-big-nvidia-open",
    "nvidia-580xx-utils",
    "nvidia-580xx-settings",
    "linux-big-nvidia-580xx",
}
SHARE = Path(__file__).resolve().parent.parent / "usr/share/big-driver-manager-cli"


class TestChoice(unittest.TestCase):
    def test_without_nvidias_table_nothing_is_guessed(self):
        choice = choose_nvidia([PASCAL], {})
        self.assertIsNone(choice.branch)
        self.assertIn("supported-gpus.json missing", choice.unsupported[0])

    def test_chips_no_single_branch_drives_get_none(self):
        choice = choose_nvidia([ADA, KEPLER], CHIPS)
        self.assertIsNone(choice.branch)
        self.assertEqual(len(choice.unsupported), 2)

    def test_mixed_generations_use_the_branch_they_share(self):
        choice = choose_nvidia([ADA, PASCAL], CHIPS)
        self.assertEqual((choice.branch, choice.compatible), ("580xx", ["580xx"]))

    def test_a_bmc_vga_is_not_a_hybrid_machine(self):
        self.assertFalse(gpu_mode.is_hybrid([ASPEED, ADA]))
        self.assertFalse(
            build_plan([ASPEED, ADA], ["linux-big"], REPO, chips=CHIPS).hybrid
        )
        self.assertTrue(gpu_mode.is_hybrid([INTEL, ADA]))


class TestPlanBookkeeping(unittest.TestCase):
    def test_installed_lib32_is_kept_when_multilib_is_gone(self):
        plan = build_plan(
            [ADA], ["linux-big"], REPO, chips=CHIPS, installed={"lib32-nvidia-utils"}
        )
        self.assertIn("lib32-nvidia-utils", plan.wanted)
        self.assertNotIn("lib32-nvidia-utils", plan.install + plan.unavailable)
        installed = {"nvidia-utils", "lib32-nvidia-utils"}
        self.assertNotIn(
            "lib32-nvidia-utils",
            gpu_cli.packages_to_replace(plan, installed, ["linux-big"]),
        )

    def test_replacement_keeps_what_the_plan_wants(self):
        plan = gpu.GpuPlan(
            nvidia=gpu.NvidiaChoice(branch="current"),
            install=["nvidia-utils"],
            wanted=["nvidia-utils", "lib32-nvidia-utils"],
            kernels=["linux-big"],
        )
        installed = {"nvidia-utils", "lib32-nvidia-utils", "linux-big-nvidia"}
        self.assertEqual(
            gpu_cli.packages_to_replace(plan, installed, ["linux-big"]),
            ["linux-big-nvidia"],
        )

    def test_essential_missing(self):
        plan = build_plan([ADA], ["linux-big", "linux72-comm"], REPO, chips=CHIPS)
        # linux72-comm has no module package: DKMS and its headers are essential
        self.assertEqual(
            sorted(gpu_cli.essential_missing(plan)),
            ["linux72-comm-headers", "nvidia-open-dkms"],
        )
        self.assertEqual(
            gpu_cli.essential_missing(
                build_plan([ADA], ["linux-big"], REPO, chips=CHIPS)
            ),
            [],
        )


class TestInstallSafety(unittest.TestCase):
    def _install(self, plan, results, running=True):
        args = argparse.Namespace(root=None if running else Path("/mnt"), pmconfig=None)
        with (
            patch.object(gpu_cli, "_build_plan", return_value=plan),
            patch.object(gpu_cli, "_refuse_redirection", return_value=None),
            patch.object(gpu_cli.gpu, "installed_packages", return_value=set()),
            patch.object(gpu_cli.gpu, "installed_kernels", return_value=["linux-big"]),
            patch.object(gpu_cli.gpu, "write_files", return_value=[]),
            patch.object(gpu_cli, "_clear_persisted_fallback"),
            patch.object(gpu_cli, "_integrated_mode", return_value=False),
            patch.object(gpu_cli, "_verify_nvidia") as verify,
            patch.object(gpu_cli, "_fall_back_if_driverless") as fall_back,
            patch.object(gpu_cli.subprocess, "run") as run,
        ):
            run.side_effect = [type("R", (), {"returncode": c})() for c in results]
            code = gpu_cli._install(args)
        return code, [c.args[0] for c in run.call_args_list], verify, fall_back

    def test_missing_driver_packages_change_nothing(self):
        plan = gpu.GpuPlan(
            nvidia=gpu.NvidiaChoice(branch="current"),
            kernels=["linux-big"],
            unavailable=["linux-big-nvidia-open"],
        )
        code, commands, _, fall_back = self._install(plan, [])
        self.assertEqual((code, commands), (gpu_cli.EXIT_FAILED, []))
        fall_back.assert_called_once()

    def test_a_failing_service_does_not_skip_the_driver_check(self):
        plan = gpu.GpuPlan(
            nvidia=gpu.NvidiaChoice(branch="current"),
            install=["nvidia-utils"],
            load=[["modprobe", "nvidia_drm"]],
            services=["switcheroo-control.service", "spice-vdagentd.socket"],
        )
        # download, install, modprobe, enable (fails), enable (ok)
        code, commands, verify, _ = self._install(plan, [0, 0, 0, 1, 0])
        self.assertEqual(code, 0)
        verify.assert_called_once()
        self.assertEqual(commands[-1][-1], "spice-vdagentd.socket")

    def test_integrated_mode_neither_loads_nor_checks_nvidia(self):
        plan = gpu.GpuPlan(
            nvidia=gpu.NvidiaChoice(branch="current"),
            install=["nvidia-utils"],
            load=[["modprobe", "nvidia_drm"]],
        )
        with patch.object(gpu_cli, "_integrated_mode", return_value=True):
            args = argparse.Namespace(root=None, pmconfig=None)
            with (
                patch.object(gpu_cli, "_build_plan", return_value=plan),
                patch.object(gpu_cli.gpu, "installed_packages", return_value=set()),
                patch.object(gpu_cli.gpu, "installed_kernels", return_value=[]),
                patch.object(gpu_cli.gpu, "write_files", return_value=[]),
                patch.object(gpu_cli, "_clear_persisted_fallback"),
                patch.object(gpu_cli, "_verify_nvidia") as verify,
                patch.object(gpu_cli.subprocess, "run") as run,
            ):
                run.return_value.returncode = 0
                gpu_cli._install(args)
        verify.assert_not_called()
        self.assertNotIn(
            ["modprobe", "nvidia_drm"], [c.args[0] for c in run.call_args_list]
        )

    def test_applying_integrated_unloads_nvidia_now(self):
        with (
            patch.object(gpu_cli.gpu, "scan_pci", return_value=[INTEL, ADA]),
            patch.object(gpu_cli, "_run", return_value=True) as run,
            patch.object(gpu_cli.gpu_mode, "apply_mode") as apply_mode,
        ):
            apply_mode.return_value = gpu_mode.ModeChange(mode="integrated")
            gpu_cli._apply_mode("integrated", Path("/"), live=True)
        self.assertIn(
            [
                "modprobe",
                "-r",
                "nvidia_drm",
                "nvidia_uvm",
                "nvidia_modeset",
                "nvidia",
            ],
            [c.args[0] for c in run.call_args_list],
        )


class TestSddmChaining(unittest.TestCase):
    def test_runs_the_display_command_configured_before(self):
        with TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / "sddm.conf.d").mkdir()
            previous = tmp / "custom-xsetup"
            previous.write_text(f'#!/bin/sh\necho ran > "{tmp}/ran"\n')
            previous.chmod(0o755)
            (tmp / "sddm.conf").write_text(f"[X11]\nDisplayCommand={previous}\n")
            (tmp / "sddm.conf.d/zz-big-driver-manager-prime.conf").write_text(
                gpu_mode.SDDM_DROPIN_TEXT
            )
            env = dict(os.environ, BDM_SDDM_DIR=str(tmp), BDM_PRIME_SCRIPT="true")
            subprocess.run(
                ["sh", str(SHARE / "prime-xrandr-sddm.sh")], env=env, check=True
            )
            self.assertEqual((tmp / "ran").read_text().strip(), "ran")


class TestEnvironmentAsRoot(unittest.TestCase):
    def test_test_overrides_need_bdm_test(self):
        text = (SHARE / "core/gpu.py").read_text()
        self.assertIn('_TESTING = os.environ.get("BDM_TEST") == "1"', text)

    def test_code_and_locale_overrides_are_not_honoured_as_root(self):
        cli = (SHARE.parent.parent / "bin/big-driver-manager-cli").read_text()
        self.assertIn(
            'os.environ.get("BDM_CLI_DIR") if os.geteuid() != 0 else None', cli
        )
        self.assertIn("if os.geteuid() != 0:", (SHARE / "core/i18n.py").read_text())


if __name__ == "__main__":
    unittest.main()


class TestRootRedirection(unittest.TestCase):
    def _refusal(self, modes, owners=None, hooks=False):
        """modes/owners by absolute path; anything else: root, 0755 directory."""
        import stat as st

        owners = owners or {}

        def lstat(path):
            path = str(path)
            mode = modes.get(path, st.S_IFDIR | 0o755)
            return os.stat_result((mode, 0, 0, 0, owners.get(path, 0), 0, 0, 0, 0, 0))

        args = argparse.Namespace(
            root=Path("/run/media/user/stick/root"), pmconfig=None
        )
        with (
            patch.object(gpu_cli.os, "lstat", side_effect=lstat),
            patch.object(gpu_cli.os.path, "lexists", return_value=hooks),
        ):
            return gpu_cli._refuse_redirection(args)

    def test_a_user_owned_directory_above_the_target_is_refused(self):
        reason = self._refusal({}, owners={"/run/media/user": 1000})
        self.assertIn("/run/media/user is not owned by root", reason)

    def test_a_world_writable_sticky_directory_above_is_fine(self):
        import stat as st

        self.assertIsNone(
            self._refusal({"/run/media": st.S_IFDIR | st.S_ISVTX | 0o777})
        )

    def test_a_world_writable_directory_above_without_sticky_bit_is_refused(self):
        import stat as st

        reason = self._refusal({"/run/media": st.S_IFDIR | 0o777})
        self.assertIn("/run/media is writable", reason)

    def test_pacman_hook_directories_of_the_target_are_checked(self):
        import stat as st

        reason = self._refusal(
            {"/run/media/user/stick/root/etc/pacman.d/hooks": st.S_IFDIR | 0o777},
            hooks=True,
        )
        self.assertIn("pacman.d/hooks", reason)
