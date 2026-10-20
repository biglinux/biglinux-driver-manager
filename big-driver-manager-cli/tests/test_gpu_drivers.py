"""core.gpu_drivers: the interface's view of video drivers, without mhwd."""

import unittest
from unittest.mock import patch

from core import gpu_drivers
from core.gpu import NvidiaChip, PciDevice
from core.gpu_drivers import GpuDriverManager, VideoDriver, list_video_drivers

VGA = 0x030000
INTEL = PciDevice("0000:00:02.0", "8086", "a7a0", VGA, boot_vga=True)
ADA = PciDevice("0000:01:00.0", "10de", "28a0", VGA)
PASCAL = PciDevice("0000:01:00.0", "10de", "1c03", VGA)
CHIPS = {
    "28a0": NvidiaChip(
        "28a0", "RTX 4060", None, frozenset({"kernelopen", "runtimepm"})
    ),
    "1c03": NvidiaChip("1c03", "GTX 1060", "580.xx", frozenset()),
}


def by_name(drivers):
    return {d.name: d for d in drivers}


class TestList(unittest.TestCase):
    def test_names_match_what_the_interface_knows(self):
        drivers = by_name(list_video_drivers([INTEL, ADA], CHIPS, set(), None))
        self.assertEqual(
            sorted(drivers),
            ["video-nvidia", "video-nvidia-470xx", "video-nvidia-580xx"],
        )
        self.assertTrue(
            all(d.is_nvidia and not d.free_driver for d in drivers.values())
        )

    def test_recommended_and_compatible_follow_nvidia_data(self):
        ada = by_name(list_video_drivers([INTEL, ADA], CHIPS, set(), None))
        self.assertTrue(ada["video-nvidia"].recommended)
        self.assertTrue(ada["video-nvidia-580xx"].compatible)
        self.assertFalse(ada["video-nvidia-470xx"].compatible)
        pascal = by_name(list_video_drivers([PASCAL], CHIPS, set(), None))
        self.assertTrue(pascal["video-nvidia-580xx"].recommended)
        self.assertFalse(pascal["video-nvidia"].compatible)

    def test_installed_and_version(self):
        drivers = by_name(
            list_video_drivers(
                [ADA],
                CHIPS,
                {"nvidia-580xx-utils"},
                None,
                {"nvidia-580xx-utils": "580.178.04"},
            )
        )
        self.assertTrue(drivers["video-nvidia-580xx"].installed)
        self.assertEqual(drivers["video-nvidia-580xx"].version, "580.178.04")
        self.assertFalse(drivers["video-nvidia"].installed)

    def test_no_nvidia_no_nvidia_entries(self):
        self.assertEqual(list_video_drivers([INTEL], CHIPS, set(), None), [])

    def test_virtual_machine_entry(self):
        drivers = list_video_drivers(
            [PciDevice("x", "80ee", "beef", VGA)],
            CHIPS,
            {"virtualbox-guest-utils"},
            "oracle",
        )
        [vm] = drivers
        self.assertEqual(vm.name, gpu_drivers.VM_DRIVER)
        self.assertTrue(vm.installed and vm.free_driver and not vm.is_nvidia)
        self.assertEqual(vm.packages, ("virtualbox-guest-utils",))


class TestActions(unittest.TestCase):
    def _args(self, method, driver):
        manager = GpuDriverManager()
        with patch.object(manager, "run_cli_command") as run:
            getattr(manager, method)(driver)
        return run.call_args.args[0]

    def test_install_and_switch_ask_for_the_branch(self):
        driver = VideoDriver(name="video-nvidia-580xx", branch="580xx")
        expected = ["gpu", "install", "--nvidia-branch", "580xx"]
        self.assertEqual(self._args("install_driver", driver), expected)
        self.assertEqual(self._args("switch_driver", driver), expected)

    def test_remove(self):
        self.assertEqual(
            self._args(
                "remove_driver", VideoDriver(name="video-nvidia", branch="current")
            ),
            ["gpu", "remove"],
        )
        vm = VideoDriver(name="video-virtualmachine", packages=("open-vm-tools",))
        self.assertEqual(
            self._args("remove_driver", vm),
            ["remove", "--recursive", "--", "open-vm-tools"],
        )

    def test_cli_runs_through_pkexec_with_progress_handling(self):
        manager = GpuDriverManager()
        launched = []
        manager._thread_launcher = lambda target, args: launched.append((target, args))
        with patch("core.privileged.is_root", return_value=False):
            manager.run_cli_command(["gpu", "remove"])
        target, args = launched[0]
        self.assertEqual(target.__name__, "_execute_command_thread")
        self.assertEqual(args[-1][0], "pkexec")
        self.assertEqual(args[-1][2:], ["gpu", "remove"])


if __name__ == "__main__":
    unittest.main()
