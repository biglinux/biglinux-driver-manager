"""core.gpu_mode, core.gpu_cli and the PRIME xrandr scripts."""

import argparse
import os
import stat
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core import gpu_cli, gpu_mode
from core.gpu import PciDevice

VGA = 0x030000
INTEL = PciDevice("0000:00:02.0", "8086", "a7a0", VGA, boot_vga=True)
NVIDIA = PciDevice("0000:01:00.0", "10de", "28a0", VGA)
HYBRID = [INTEL, NVIDIA]
SHARE = Path(__file__).resolve().parent.parent / "usr/share/big-driver-manager-cli"


def _with_display_managers(root: Path, *names: str) -> None:
    markers = {"lightdm": "etc/lightdm", "sddm": "usr/bin/sddm", "gdm": "usr/share/gdm"}
    for name in names:
        path = root / markers[name]
        if name == "sddm":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
        else:
            path.mkdir(parents=True, exist_ok=True)


class TestModes(unittest.TestCase):
    def test_nvidia_mode_writes_xorg_and_greeter_hooks_for_installed_dms(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            _with_display_managers(root, "lightdm")
            change = gpu_mode.apply_mode("nvidia", HYBRID, root)
            self.assertIn(gpu_mode.NVIDIA_PRIMARY_XORG, change.written)
            self.assertIn(gpu_mode.LIGHTDM_DROPIN, change.written)
            self.assertNotIn(gpu_mode.SDDM_DROPIN, change.written)  # no SDDM here
            self.assertIn(gpu_mode.SESSION_AUTOSTART, change.written)
            self.assertIn("0x00", (root / gpu_mode.MODE_MODPROBE).read_text())
            self.assertTrue(change.needs_initramfs)
            self.assertEqual(gpu_mode.read_mode(root), "nvidia")

    def test_back_to_hybrid_removes_every_override(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            _with_display_managers(root, "lightdm", "sddm", "gdm")
            gpu_mode.apply_mode("nvidia", HYBRID, root)
            change = gpu_mode.apply_mode("hybrid", HYBRID, root)
            self.assertEqual(change.written, [])
            for relative in (
                gpu_mode.MODE_MODPROBE,
                gpu_mode.NVIDIA_PRIMARY_XORG,
                gpu_mode.LIGHTDM_DROPIN,
                gpu_mode.SDDM_DROPIN,
                gpu_mode.SESSION_AUTOSTART,
                gpu_mode.GDM_GREETER_AUTOSTART,
            ):
                self.assertFalse((root / relative).exists(), relative)
            self.assertEqual(gpu_mode.read_mode(root), "hybrid")
            self.assertIn("switcheroo-control.service", change.services)

    def test_integrated_blacklists_and_blocks_every_nvidia_module(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            change = gpu_mode.apply_mode("integrated", HYBRID, root)
            text = (root / gpu_mode.MODE_MODPROBE).read_text()
            for module in ("nvidia", "nvidia_drm", "nvidia_modeset", "nvidia_uvm"):
                self.assertIn(f"install {module} /bin/false", text)
            self.assertEqual(change.services, [])

    def test_same_mode_twice_changes_nothing(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            gpu_mode.apply_mode("integrated", HYBRID, root)
            change = gpu_mode.apply_mode("integrated", HYBRID, root)
            self.assertEqual((change.written, change.removed), ([], []))
            self.assertFalse(change.needs_initramfs)

    def test_modes_need_a_hybrid_machine(self):
        with TemporaryDirectory() as t, self.assertRaises(gpu_mode.GpuModeError):
            gpu_mode.apply_mode("nvidia", [NVIDIA], Path(t))
        with TemporaryDirectory() as t, self.assertRaises(gpu_mode.GpuModeError):
            gpu_mode.apply_mode("turbo", HYBRID, Path(t))

    def test_reads_and_replaces_biglinux_gpu_manager_mode(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            legacy = root / gpu_mode.LEGACY_MODE_FILE
            legacy.parent.mkdir(parents=True)
            for value, expected in (
                ("1", "hybrid"),
                ("11", "nvidia"),
                ("integrated", "integrated"),
            ):
                legacy.write_text(value + "\n")
                self.assertEqual(gpu_mode.read_mode(root), expected)
            gpu_mode.apply_mode("hybrid", HYBRID, root)
            self.assertFalse(legacy.exists())


class TestCli(unittest.TestCase):
    def test_requested_mode_from_cmdline(self):
        cases = {
            ("bdm.gpu=integrated",): "integrated",
            ("bignvidia=3",): "hybrid",
            ("bignvidia=11",): "nvidia",
            ("bignvidia=nvidia",): "nvidia",
            ("bignvidia=99",): None,
            ("quiet",): None,
        }
        for args, expected in cases.items():
            with self.subTest(args=args):
                self.assertEqual(gpu_cli.requested_mode(list(args)), expected)

    def test_redirection_into_a_user_tree_is_refused(self):
        with TemporaryDirectory() as t:  # owned by the user running the tests
            for args in (
                argparse.Namespace(root=Path(t), pmconfig=None),
                argparse.Namespace(root=None, pmconfig=Path(t) / "pacman.conf"),
                argparse.Namespace(root=Path(t) / "missing", pmconfig=None),
            ):
                with self.subTest(args=args):
                    self.assertIsNotNone(gpu_cli._refuse_redirection(args))

    def test_redirection_to_root_owned_paths_is_accepted(self):
        def lstat(path):
            return os.stat_result((stat.S_IFDIR | 0o755, 0, 0, 0, 0, 0, 0, 0, 0, 0))

        args = argparse.Namespace(root=Path("/mnt"), pmconfig=Path("/opt/mhwd/x.conf"))
        with patch.object(gpu_cli.os, "lstat", side_effect=lstat):
            self.assertIsNone(gpu_cli._refuse_redirection(args))

    def test_group_writable_or_symlinked_paths_are_refused(self):
        modes = {"/mnt/usr": stat.S_IFDIR | 0o775, "/mnt/etc": stat.S_IFLNK | 0o777}

        def lstat(path):
            mode = modes.get(str(path), stat.S_IFDIR | 0o755)
            return os.stat_result((mode, 0, 0, 0, 0, 0, 0, 0, 0, 0))

        args = argparse.Namespace(root=Path("/mnt"), pmconfig=None)
        with patch.object(gpu_cli.os, "lstat", side_effect=lstat):
            reason = gpu_cli._refuse_redirection(args)
        self.assertIn("/mnt/etc", reason)

    def test_free_from_cmdline(self):
        args = argparse.Namespace(free=False, from_cmdline=True)
        with patch.object(gpu_cli, "_cmdline_args", return_value=["driver=free"]):
            self.assertFalse(gpu_cli._nonfree(args))
        with patch.object(gpu_cli, "_cmdline_args", return_value=["quiet"]):
            self.assertTrue(gpu_cli._nonfree(args))

    def test_check_names_only_what_a_kernel_still_lacks(self):
        from core import gpu

        plan = gpu.GpuPlan(
            kernels=["linux-big", "linux-xanmod"],
            install=[
                "nvidia-utils",
                "linux-big-nvidia-open",
                "linux-xanmod-nvidia-open",
                "nvidia-open-dkms",
                "linux-xanmod-headers",
                "nvidia-prime",
            ],
        )
        installed = {"nvidia-utils", "linux-big-nvidia-open", "nvidia-prime"}
        self.assertEqual(
            gpu_cli.kernel_packages_missing(plan, installed),
            ["linux-xanmod-nvidia-open", "nvidia-open-dkms", "linux-xanmod-headers"],
        )

    def test_check_is_silent_without_the_proprietary_driver(self):
        with (
            patch.object(gpu_cli.gpu, "installed_packages", return_value={"mesa"}),
            patch.object(gpu_cli.gpu, "build_plan") as build,
        ):
            self.assertEqual(gpu_cli._check(), 0)
        build.assert_not_called()

    def test_install_runs_pacman_then_files_then_units(self):
        from core import gpu

        plan = gpu.GpuPlan(
            install=["nvidia-utils"],
            services=["switcheroo-control.service"],
            files={gpu.NVIDIA_MODULES_LOAD: gpu.NVIDIA_MODULES_LOAD_TEXT},
        )
        with TemporaryDirectory() as t:
            args = argparse.Namespace(
                root=Path(t), pmconfig=Path("/opt/mhwd/pacman-mhwd.conf")
            )
            with (
                patch.object(gpu_cli, "_build_plan", return_value=plan),
                patch.object(gpu_cli.gpu, "installed_packages", return_value=set()),
                patch.object(gpu_cli.gpu, "installed_kernels", return_value=[]),
                patch.object(gpu_cli.subprocess, "run") as run,
            ):
                run.return_value.returncode = 0
                self.assertEqual(gpu_cli._install(args), 0)
            commands = [c.args[0] for c in run.call_args_list]
            self.assertEqual(commands[0][:2], ["pacman", "-S"])
            self.assertIn("--root", commands[0])
            self.assertEqual(commands[1][:3], ["systemctl", "--root", t])
            self.assertTrue((Path(t) / gpu.NVIDIA_MODULES_LOAD).is_file())

    def test_failed_pacman_stops_before_files(self):
        from core import gpu

        plan = gpu.GpuPlan(install=["x"], files={gpu.NVIDIA_MODULES_LOAD: "x"})
        with TemporaryDirectory() as t:
            args = argparse.Namespace(root=Path(t), pmconfig=None)
            with (
                patch.object(gpu_cli, "_build_plan", return_value=plan),
                patch.object(gpu_cli.gpu, "installed_packages", return_value=set()),
                patch.object(gpu_cli.gpu, "installed_kernels", return_value=[]),
                patch.object(gpu_cli.subprocess, "run") as run,
            ):
                run.return_value.returncode = 1
                self.assertEqual(gpu_cli._install(args), gpu_cli.EXIT_FAILED)
            self.assertFalse((Path(t) / gpu.NVIDIA_MODULES_LOAD).exists())


class TestBranchSwitching(unittest.TestCase):
    KERNELS = ["linux-big", "linux-xanmod"]

    def _plan(self, branch="580xx", install=None):
        from core import gpu

        choice = gpu.NvidiaChoice(branch=branch)
        return gpu.GpuPlan(
            nvidia=choice,
            kernels=self.KERNELS,
            install=install
            or [
                "nvidia-580xx-utils",
                "nvidia-580xx-settings",
                "linux-big-nvidia-580xx",
                "linux-xanmod-nvidia-580xx",
            ],
        )

    def test_another_branch_is_replaced(self):
        installed = {
            "nvidia-utils",
            "nvidia-settings",
            "lib32-nvidia-utils",
            "linux-big-nvidia-open",
            "linux-xanmod-nvidia-open",
            "linux-firmware-nvidia",  # not a module of any kernel
            "nvidia-prime",
            "mesa",
        }
        self.assertEqual(
            gpu_cli.packages_to_replace(self._plan(), installed, self.KERNELS),
            [
                "lib32-nvidia-utils",
                "linux-big-nvidia-open",
                "linux-xanmod-nvidia-open",
                "nvidia-settings",
                "nvidia-utils",
            ],
        )

    def test_other_module_flavour_of_the_same_branch_is_replaced(self):
        plan = self._plan(
            "current",
            ["nvidia-utils", "linux-big-nvidia-open", "linux-xanmod-nvidia-open"],
        )
        installed = {"nvidia-utils", "linux-big-nvidia", "linux-xanmod-nvidia"}
        self.assertEqual(
            gpu_cli.packages_to_replace(plan, installed, self.KERNELS),
            ["linux-big-nvidia", "linux-xanmod-nvidia"],
        )

    def test_nothing_replaced_when_already_right_or_on_free_drivers(self):
        from core import gpu

        plan = self._plan()
        self.assertEqual(
            gpu_cli.packages_to_replace(plan, set(plan.install), self.KERNELS), []
        )
        self.assertEqual(
            gpu_cli.packages_to_replace(gpu.GpuPlan(), {"nvidia-utils"}, self.KERNELS),
            [],
        )

    def _install(self, plan, installed, results):
        args = argparse.Namespace(root=None, pmconfig=None, nvidia_branch="580xx")
        with (
            patch.object(gpu_cli, "_build_plan", return_value=plan),
            patch.object(gpu_cli.gpu, "installed_packages", return_value=installed),
            patch.object(gpu_cli.gpu, "installed_kernels", return_value=self.KERNELS),
            patch.object(gpu_cli.subprocess, "run") as run,
        ):
            run.side_effect = [
                type("R", (), {"returncode": code})() for code in results
            ]
            code = gpu_cli._install(args)
        return code, [c.args[0] for c in run.call_args_list]

    def test_swap_removes_without_deps_then_installs(self):
        code, commands = self._install(self._plan(), {"nvidia-utils"}, [0, 0])
        self.assertEqual(code, 0)
        self.assertEqual(commands[0], ["pacman", "-Rdd", "--noconfirm", "nvidia-utils"])
        self.assertEqual(commands[1][:2], ["pacman", "-S"])

    def test_failed_install_restores_the_previous_driver(self):
        code, commands = self._install(self._plan(), {"nvidia-utils"}, [0, 1, 0])
        self.assertEqual(code, gpu_cli.EXIT_FAILED)
        self.assertEqual(commands[2][-1], "nvidia-utils")
        self.assertEqual(commands[2][:2], ["pacman", "-S"])

    def test_no_swap_when_the_new_driver_is_not_available(self):
        plan = self._plan()
        plan.unavailable = ["linux-xanmod-nvidia-580xx"]
        code, commands = self._install(plan, {"nvidia-utils"}, [])
        self.assertEqual(code, gpu_cli.EXIT_FAILED)
        self.assertEqual(commands, [])

    def test_remove_takes_prime_along_and_clears_the_mode(self):
        installed = {"nvidia-utils", "linux-big-nvidia-open", "nvidia-prime", "mesa"}
        with (
            patch.object(gpu_cli.gpu, "installed_packages", return_value=installed),
            patch.object(gpu_cli.gpu, "installed_kernels", return_value=["linux-big"]),
            patch.object(gpu_cli.gpu_mode, "clear_mode") as clear,
            patch.object(gpu_cli.subprocess, "run") as run,
        ):
            run.return_value.returncode = 0
            clear.return_value = gpu_mode.ModeChange(mode="none")
            code = gpu_cli._remove(argparse.Namespace())
        self.assertEqual(code, 0)
        self.assertEqual(
            run.call_args_list[0].args[0],
            [
                "pacman",
                "-Rns",
                "--noconfirm",
                "linux-big-nvidia-open",
                "nvidia-utils",
                "nvidia-prime",
            ],
        )
        clear.assert_called_once()

    def test_clear_mode_removes_every_mode_file(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            _with_display_managers(root, "lightdm")
            gpu_mode.apply_mode("nvidia", HYBRID, root)
            change = gpu_mode.clear_mode(root)
            self.assertTrue(change.needs_initramfs)
            self.assertIsNone(gpu_mode.read_mode(root))
            self.assertFalse((root / gpu_mode.LIGHTDM_DROPIN).exists())


class TestPrimeScripts(unittest.TestCase):
    PROVIDERS = (
        "Providers: number : 2\n"
        "Provider 0: id: 0x1b8 cap: 0x1, Source Output crtcs: 4 outputs: 1 "
        "associated providers: 0 name:NVIDIA-0\n"
        "Provider 1: id: 0x45 cap: 0xf, Source Output, Sink Output crtcs: 3 outputs: 2 "
        "associated providers: 0 name:Unknown AMD Radeon GPU @ pci:0000:05:00.0\n"
    )

    def _fake_bin(self, tmp: Path) -> Path:
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        xrandr = bin_dir / "xrandr"
        xrandr.write_text(
            "#!/bin/sh\n"
            f'echo "$*" >> "{tmp}/xrandr.log"\n'
            f'[ "$1" = --listproviders ] && cat "{tmp}/providers"\n'
            "exit 0\n"
        )
        xrandr.chmod(xrandr.stat().st_mode | stat.S_IEXEC)
        (tmp / "providers").write_text(self.PROVIDERS)
        return bin_dir

    def test_uses_provider_ids_not_names(self):
        with TemporaryDirectory() as t:
            tmp = Path(t)
            env = dict(
                os.environ,
                PATH=f"{self._fake_bin(tmp)}:{os.environ['PATH']}",
                XDG_SESSION_TYPE="x11",
            )
            subprocess.run(["sh", str(SHARE / "prime-xrandr.sh")], env=env, check=True)
            log = (tmp / "xrandr.log").read_text().splitlines()
        self.assertIn("--setprovideroutputsource 0x45 0x1b8", log)
        self.assertIn("--auto", log)

    def test_does_nothing_on_wayland(self):
        with TemporaryDirectory() as t:
            tmp = Path(t)
            env = dict(
                os.environ,
                PATH=f"{self._fake_bin(tmp)}:{os.environ['PATH']}",
                XDG_SESSION_TYPE="wayland",
            )
            subprocess.run(["sh", str(SHARE / "prime-xrandr.sh")], env=env, check=True)
            self.assertFalse((tmp / "xrandr.log").exists())

    def test_lightdm_wrapper_chains_the_previous_setup_script(self):
        with TemporaryDirectory() as t:
            tmp = Path(t)
            conf_d = tmp / "lightdm/lightdm.conf.d"
            conf_d.mkdir(parents=True)
            previous = tmp / "sync-wallpaper"
            previous.write_text(f'#!/bin/sh\necho ran > "{tmp}/previous.log"\n')
            previous.chmod(0o755)
            (conf_d / "99-comm-sync-wallpaper.conf").write_text(
                f"[Seat:*]\ndisplay-setup-script={previous}\n"
            )
            (conf_d / "zz-big-driver-manager-prime.conf").write_text(
                gpu_mode.LIGHTDM_DROPIN_TEXT
            )
            env = dict(
                os.environ,
                BDM_LIGHTDM_DIR=str(tmp / "lightdm"),
                BDM_PRIME_SCRIPT="true",
            )
            subprocess.run(
                ["sh", str(SHARE / "prime-xrandr-lightdm.sh")], env=env, check=True
            )
            self.assertEqual((tmp / "previous.log").read_text().strip(), "ran")


if __name__ == "__main__":
    unittest.main()
