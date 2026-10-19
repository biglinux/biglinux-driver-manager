"""core.gpu: detection, NVIDIA driver choice and the install plan."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core import gpu
from core.gpu import NvidiaChip, PciDevice, build_plan, choose_nvidia

VGA = 0x030000
THREE_D = 0x030200

INTEL = PciDevice("0000:00:02.0", "8086", "a7a0", VGA, boot_vga=True, driver="i915")
AMD = PciDevice("0000:05:00.0", "1002", "1681", VGA, boot_vga=True, driver="amdgpu")
ADA = PciDevice("0000:01:00.0", "10de", "28a0", VGA)  # RTX 4060 Laptop
AMPERE_3D = PciDevice("0000:01:00.0", "10de", "25a2", THREE_D)  # RTX 3050 Mobile
PASCAL = PciDevice("0000:01:00.0", "10de", "1c03", VGA)  # GTX 1060
KEPLER = PciDevice("0000:01:00.0", "10de", "1004", VGA)  # GTX 780
FERMI = PciDevice("0000:01:00.0", "10de", "1082", VGA)  # GTX 560 Ti
UNKNOWN = PciDevice("0000:01:00.0", "10de", "ffff", VGA)
BROADCOM = PciDevice("0000:03:00.0", "14e4", "43b1", 0x028000)
AUDIO = PciDevice("0000:01:00.1", "10de", "22be", 0x040300)

CHIPS = {
    "28a0": NvidiaChip(
        "28a0", "RTX 4060 Laptop", None, frozenset({"kernelopen", "runtimepm"})
    ),
    "25a2": NvidiaChip(
        "25a2", "RTX 3050 Mobile", None, frozenset({"kernelopen", "runtimepm"})
    ),
    "1c03": NvidiaChip("1c03", "GTX 1060", "580.xx", frozenset({"runtimepm"})),
    "1004": NvidiaChip("1004", "GTX 780", "470.xx", frozenset()),
    "1082": NvidiaChip("1082", "GTX 560 Ti", "390.xx", frozenset()),
}

KERNELS = ["linux-big", "linux618"]


def repo(*extra):
    names = {
        "nvidia-utils",
        "nvidia-settings",
        "lib32-nvidia-utils",
        "nvidia-580xx-utils",
        "nvidia-580xx-settings",
        "lib32-nvidia-580xx-utils",
        "nvidia-470xx-utils",
        "nvidia-470xx-settings",
        "lib32-nvidia-470xx-utils",
        "nvidia-dkms",
        "nvidia-open-dkms",
        "nvidia-580xx-dkms",
        "nvidia-470xx-dkms",
        "nvidia-prime",
        "switcheroo-control",
        "broadcom-wl-dkms",
        "virtualbox-guest-utils",
        "open-vm-tools",
        "xf86-input-vmmouse",
        "qemu-guest-agent",
        "spice-vdagent",
        "linux618-headers",
        "linux-big-headers",
    }
    for kernel in KERNELS:
        for module in (
            "nvidia",
            "nvidia-open",
            "nvidia-580xx",
            "nvidia-580xx-open",
            "nvidia-470xx",
            "broadcom-wl",
        ):
            names.add(f"{kernel}-{module}")
    return names | set(extra)


def plan_for(devices, **kwargs):
    kwargs.setdefault("chips", CHIPS)
    kwargs.setdefault("broadcom_wl_ids", {"14e4:43b1"})
    return build_plan(
        devices, kwargs.pop("kernels", KERNELS), kwargs.pop("repo", repo()), **kwargs
    )


class TestNvidiaChoice(unittest.TestCase):
    def test_current_chip_takes_the_open_module(self):
        choice = choose_nvidia([ADA], CHIPS)
        self.assertEqual(
            (choice.branch, choice.open_module, choice.runtime_pm),
            ("current", True, True),
        )

    def test_3d_controller_class_counts(self):
        self.assertEqual(choose_nvidia([AMPERE_3D], CHIPS).branch, "current")

    def test_580_legacy_is_proprietary(self):
        choice = choose_nvidia([PASCAL], CHIPS)
        self.assertEqual((choice.branch, choice.open_module), ("580xx", False))

    def test_470_legacy(self):
        self.assertEqual(choose_nvidia([KEPLER], CHIPS).branch, "470xx")

    def test_390_and_older_have_no_driver(self):
        choice = choose_nvidia([FERMI], CHIPS)
        self.assertIsNone(choice.branch)
        self.assertEqual(len(choice.unsupported), 1)

    def test_unknown_chip_follows_nvidia_rule_current_open(self):
        choice = choose_nvidia([UNKNOWN], CHIPS)
        self.assertEqual((choice.branch, choice.open_module), ("current", True))

    def test_mixed_chips_take_the_oldest_branch_and_proprietary(self):
        second = PciDevice("0000:02:00.0", "10de", "28a0", VGA)
        choice = choose_nvidia([PASCAL, second], CHIPS)
        self.assertEqual((choice.branch, choice.open_module), ("580xx", False))

    def test_non_display_nvidia_functions_are_ignored(self):
        self.assertEqual(
            choose_nvidia([ADA, AUDIO], CHIPS).chips, ["RTX 4060 Laptop [10de:28a0]"]
        )


class TestBranchChoice(unittest.TestCase):
    def test_compatible_branches(self):
        self.assertEqual(choose_nvidia([ADA], CHIPS).compatible, ["current", "580xx"])
        self.assertEqual(choose_nvidia([PASCAL], CHIPS).compatible, ["580xx"])
        self.assertEqual(choose_nvidia([KEPLER], CHIPS).compatible, ["470xx"])
        self.assertEqual(choose_nvidia([PASCAL, ADA], CHIPS).compatible, ["580xx"])

    def test_forcing_580xx_on_a_current_chip_keeps_the_open_module(self):
        plan = plan_for([INTEL, ADA], nvidia_branch="580xx")
        self.assertEqual(plan.nvidia.branch, "580xx")
        self.assertIn("linux-big-nvidia-580xx-open", plan.install)
        self.assertIn("nvidia-580xx-utils", plan.install)
        self.assertNotIn("nvidia-utils", plan.install)

    def test_forcing_an_incompatible_branch_is_refused(self):
        with self.assertRaises(ValueError):
            plan_for([PASCAL], nvidia_branch="current")
        with self.assertRaises(ValueError):
            plan_for([INTEL], nvidia_branch="580xx")

    def test_branch_packages_by_kernel_pkgbase(self):
        installed = {
            "nvidia-utils",
            "linux-big-nvidia-open",
            "linux-xanmod-lts-nvidia",
            "linux-firmware-nvidia",
            "linux-big-nvidia-580xx",
        }
        current = gpu.BRANCHES["current"]
        self.assertEqual(
            gpu.branch_packages(current, installed, ["linux-big", "linux-xanmod-lts"]),
            ["linux-big-nvidia-open", "linux-xanmod-lts-nvidia", "nvidia-utils"],
        )
        self.assertEqual(gpu.installed_branch(installed), "current")
        self.assertIsNone(gpu.installed_branch({"mesa"}))


class TestPlan(unittest.TestCase):
    def test_intel_nvidia_laptop(self):
        plan = plan_for([INTEL, ADA, AUDIO])
        self.assertTrue(plan.hybrid)
        self.assertEqual(
            plan.install,
            [
                "nvidia-utils",
                "nvidia-settings",
                "lib32-nvidia-utils",
                "linux-big-nvidia-open",
                "linux618-nvidia-open",
                "nvidia-prime",
                "switcheroo-control",
            ],
        )
        self.assertIn("switcheroo-control.service", plan.services)
        self.assertIn(gpu.NVIDIA_POWER_UDEV, plan.files)
        self.assertIn(gpu.NVIDIA_POWER_MODPROBE, plan.files)
        self.assertIn(gpu.NVIDIA_MODULES_LOAD, plan.files)
        self.assertEqual(plan.unavailable, [])

    def test_amd_pascal_laptop(self):
        plan = plan_for([AMD, PASCAL])
        self.assertTrue(plan.hybrid)
        self.assertIn("linux-big-nvidia-580xx", plan.install)
        self.assertIn("nvidia-580xx-utils", plan.install)
        self.assertNotIn("nvidia-utils", plan.install)

    def test_desktop_nvidia_is_not_hybrid(self):
        plan = plan_for([ADA])
        self.assertFalse(plan.hybrid)
        self.assertNotIn("nvidia-prime", plan.install)
        self.assertNotIn(gpu.NVIDIA_POWER_UDEV, plan.files)
        self.assertIn(gpu.NVIDIA_MODULES_LOAD, plan.files)

    def test_no_runtime_pm_no_power_files(self):
        chips = dict(
            CHIPS, **{"28a0": NvidiaChip("28a0", "x", None, frozenset({"kernelopen"}))}
        )
        plan = plan_for([INTEL, ADA], chips=chips)
        self.assertNotIn(gpu.NVIDIA_POWER_UDEV, plan.files)

    def test_kepler_notes_no_wayland(self):
        plan = plan_for([KEPLER])
        self.assertIn("linux618-nvidia-470xx", plan.install)
        self.assertTrue(any("Wayland" in note for note in plan.notes))

    def test_fermi_keeps_nouveau(self):
        plan = plan_for([INTEL, FERMI])
        self.assertNotIn("nvidia-utils", plan.install)
        self.assertTrue(any("nouveau" in note for note in plan.notes))

    def test_kernel_without_module_package_falls_back_to_dkms(self):
        plan = plan_for([ADA], kernels=["linux-big", "linux72-comm"])
        self.assertIn("linux-big-nvidia-open", plan.install)
        self.assertIn("nvidia-open-dkms", plan.install)
        self.assertNotIn("linux72-comm-nvidia-open", plan.install)
        # linux72-comm-headers is not in this repo: reported, not installed
        self.assertIn("linux72-comm-headers", plan.unavailable)

    def test_xanmod_kernels_get_their_own_modules(self):
        kernels = ["linux-xanmod", "linux-xanmod-lts"]
        offline = repo(
            "linux-xanmod-nvidia-open",
            "linux-xanmod-lts-nvidia-open",
            "linux-xanmod-lts-nvidia-580xx",
        )
        plan = plan_for([INTEL, ADA], kernels=kernels, repo=offline)
        self.assertIn("linux-xanmod-nvidia-open", plan.install)
        self.assertIn("linux-xanmod-lts-nvidia-open", plan.install)
        self.assertNotIn("nvidia-open-dkms", plan.install)
        pascal = plan_for([PASCAL], kernels=["linux-xanmod-lts"], repo=offline)
        self.assertIn("linux-xanmod-lts-nvidia-580xx", pascal.install)

    def test_xanmod_without_module_package_builds_with_dkms(self):
        plan = plan_for(
            [ADA], kernels=["linux-xanmod"], repo=repo("linux-xanmod-headers")
        )
        self.assertIn("nvidia-open-dkms", plan.install)
        self.assertIn("linux-xanmod-headers", plan.install)

    def test_free_drivers_install_no_nvidia(self):
        plan = plan_for([INTEL, ADA], nonfree=False)
        self.assertEqual(plan.install, ["switcheroo-control"])
        self.assertEqual(plan.files, {})

    def test_lib32_only_when_multilib_is_enabled(self):
        plan = plan_for([ADA], repo=repo() - {"lib32-nvidia-utils"})
        self.assertNotIn("lib32-nvidia-utils", plan.install)
        self.assertNotIn("lib32-nvidia-utils", plan.unavailable)

    def test_installed_package_outside_the_repo_is_not_unavailable(self):
        offline = repo() - {"switcheroo-control"}
        plan = plan_for([INTEL, ADA], repo=offline, installed={"switcheroo-control"})
        self.assertNotIn("switcheroo-control", plan.install + plan.unavailable)

    def test_broadcom_wl_per_kernel(self):
        plan = plan_for([INTEL, BROADCOM])
        self.assertIn("linux-big-broadcom-wl", plan.install)
        self.assertIn("linux618-broadcom-wl", plan.install)
        self.assertNotIn(
            "broadcom-wl", " ".join(plan_for([INTEL, BROADCOM], nonfree=False).install)
        )

    def test_virtual_machines(self):
        cases = {
            "oracle": (["virtualbox-guest-utils"], ["vboxservice.service"]),
            "vmware": (["open-vm-tools", "xf86-input-vmmouse"], ["vmtoolsd.service"]),
            "kvm": (
                ["qemu-guest-agent", "spice-vdagent"],
                ["qemu-guest-agent.service", "spice-vdagentd.socket"],
            ),
        }
        for virt, (packages, units) in cases.items():
            with self.subTest(virt=virt):
                plan = plan_for(
                    [PciDevice("0000:00:02.0", "1af4", "1050", VGA)],
                    virtualization=virt,
                )
                self.assertEqual(plan.install, packages)
                self.assertEqual(plan.services, units)

    def test_plan_is_serializable(self):
        import json

        json.dumps(plan_for([INTEL, ADA]).to_dict())


class TestDetection(unittest.TestCase):
    def _device(
        self, base: Path, slot, vendor, device, klass, boot_vga=None, driver=None
    ):
        d = base / "bus/pci/devices" / slot
        d.mkdir(parents=True)
        (d / "vendor").write_text(f"0x{vendor}\n")
        (d / "device").write_text(f"0x{device}\n")
        (d / "class").write_text(f"0x{klass:06x}\n")
        if boot_vga is not None:
            (d / "boot_vga").write_text("1\n" if boot_vga else "0\n")
        if driver:
            target = base / "bus/pci/drivers" / driver
            target.mkdir(parents=True, exist_ok=True)
            os.symlink(target, d / "driver")

    def test_scan_pci_reads_sysfs(self):
        with TemporaryDirectory() as t:
            base = Path(t)
            self._device(base, "0000:00:02.0", "8086", "A7A0", VGA, True, "i915")
            self._device(base, "0000:01:00.0", "10DE", "28A0", THREE_D, False, "nvidia")
            self._device(base, "0000:00:1f.3", "8086", "51c8", 0x040380)
            devices = gpu.scan_pci(base)
        display = gpu.display_devices(devices)
        self.assertEqual([d.vendor_name for d in display], ["intel", "nvidia"])
        self.assertEqual(display[1].device, "28a0")
        self.assertEqual((display[0].boot_vga, display[0].driver), (True, "i915"))
        self.assertIsNone(devices[1].driver if not devices[1].is_display else None)

    def test_vendor_names_never_come_from_strings(self):
        # "NVIDIA Corporation" contains "ati": only the ID decides.
        self.assertEqual(ADA.vendor_name, "nvidia")
        self.assertEqual(PciDevice("x", "1af4", "1050", VGA).vendor_name, "virtual")

    def test_installed_kernels_from_pkgbase(self):
        with TemporaryDirectory() as t:
            modules = Path(t) / "usr/lib/modules"
            for kver, pkgbase in (
                ("7.2.11-2-big", "linux-big"),
                ("6.18.55-1-MANJARO", "linux618"),
                ("7.0.14-x64v3-xanmod1-1", "linux-xanmod"),
                ("6.18.37-x64v3-xanmod1-2-lts", "linux-xanmod-lts"),
                ("7.2.4-1-MANJARO-COMM", "linux72-comm"),
                ("old", None),
            ):
                (modules / kver).mkdir(parents=True)
                if pkgbase:
                    (modules / kver / "vmlinuz").write_text("")
                    (modules / kver / "pkgbase").write_text(pkgbase + "\n")
            self.assertEqual(
                sorted(gpu.installed_kernels(Path(t))),
                [
                    "linux-big",
                    "linux-xanmod",
                    "linux-xanmod-lts",
                    "linux618",
                    "linux72-comm",
                ],
            )

    def test_supported_gpus_json(self):
        with TemporaryDirectory() as t:
            path = Path(t) / "supported-gpus.json"
            path.write_text(
                '{"chips": ['
                '{"devid": "0x28A0", "name": "A", "features": ["kernelopen", "runtimepm"]},'
                '{"devid": "0x28A0", "subdevid": "0x1", "name": "A variant", "features": []},'
                '{"devid": "0x1C03", "name": "B", "legacybranch": "580.xx", "features": []}'
                "]}"
            )
            chips = gpu.load_supported_gpus(path)
        self.assertEqual(chips["28a0"].name, "A")  # first entry per device ID
        self.assertEqual(chips["1c03"].legacy_branch, "580.xx")
        self.assertEqual(gpu.load_supported_gpus(Path("/nonexistent")), {})

    @unittest.skipUnless(
        gpu.SUPPORTED_GPUS_JSON.exists(), "nvidia-driver-assistant not installed"
    )
    def test_real_nvidia_table(self):
        chips = gpu.load_supported_gpus()
        # GTX 1060 6GB (Pascal) -> 580.xx; GTX 780 (Kepler) -> 470.xx;
        # GTX 560 Ti (Fermi) -> none; RTX 4090 (Ada) -> current open
        self.assertEqual(
            choose_nvidia([PciDevice("x", "10de", "1c03", VGA)], chips).branch, "580xx"
        )
        self.assertEqual(
            choose_nvidia([PciDevice("x", "10de", "1004", VGA)], chips).branch, "470xx"
        )
        self.assertIsNone(
            choose_nvidia([PciDevice("x", "10de", "1082", VGA)], chips).branch
        )
        ada = choose_nvidia([PciDevice("x", "10de", "2684", VGA)], chips)
        self.assertEqual((ada.branch, ada.open_module), ("current", True))


class TestApplyHelpers(unittest.TestCase):
    def test_write_files_is_idempotent(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            files = {gpu.NVIDIA_MODULES_LOAD: gpu.NVIDIA_MODULES_LOAD_TEXT}
            self.assertEqual(len(gpu.write_files(files, root)), 1)
            self.assertEqual(gpu.write_files(files, root), [])
            self.assertEqual(
                (root / gpu.NVIDIA_MODULES_LOAD).read_text(),
                gpu.NVIDIA_MODULES_LOAD_TEXT,
            )

    def test_commands(self):
        self.assertEqual(
            gpu.pacman_install_command(
                ["a"], Path("/opt/mhwd/pacman-mhwd.conf"), Path("/mnt")
            ),
            [
                "pacman",
                "-S",
                "--noconfirm",
                "--needed",
                "--config",
                "/opt/mhwd/pacman-mhwd.conf",
                "--root",
                "/mnt",
                "a",
            ],
        )
        self.assertEqual(
            gpu.enable_units_command(["x.service"]),
            ["systemctl", "enable", "--now", "--no-block", "x.service"],
        )
        self.assertEqual(
            gpu.enable_units_command(["x.service"], Path("/mnt")),
            ["systemctl", "--root", "/mnt", "enable", "x.service"],
        )


if __name__ == "__main__":
    unittest.main()
