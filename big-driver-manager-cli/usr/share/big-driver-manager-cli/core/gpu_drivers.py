"""Video drivers for the interface, decided by core.gpu instead of mhwd.

Offers the same surface the interface used from MhwdManager
(get_video_drivers, install/switch/remove_driver, can_install_nvidia,
cancel_operation), so the page that lists NVIDIA drivers only had to change
which manager it creates. Every action runs ``big-driver-manager-cli gpu ...``
through pkexec.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable

from core import gpu
from core.base_manager import BaseManager
from core.i18n import _
from core.logging_config import get_logger
from core.subprocess_env import subprocess_env

_logger = get_logger("GpuDriverManager")

VM_DRIVER = "video-virtualmachine"
_PRIORITY = {"current": 3, "580xx": 2, "470xx": 1}


def driver_name(branch: str) -> str:
    """Config-style name the interface already knows: video-nvidia, video-nvidia-580xx."""
    return f"video-{gpu.BRANCHES[branch].module}"


@dataclass
class VideoDriver:
    """One installable video driver, with the attributes MhwdDriver had."""

    name: str
    version: str = ""
    free_driver: bool = False
    bus_type: str = "PCI"
    info: str = ""
    priority: int = 0
    conflicts: str = ""
    installed: bool = False
    compatible: bool = False
    category: str = "video"
    recommended: bool = False
    branch: str | None = None  # NVIDIA branch, None for the VM guest tools
    packages: tuple[str, ...] = ()

    @property
    def is_nvidia(self) -> bool:
        return self.branch is not None

    @property
    def display_name(self) -> str:
        return self.name.replace("-", " ")


def _versions(packages: list[str]) -> dict[str, str]:
    """Repository version of each package, without the pkgrel."""
    try:
        output = subprocess.run(
            ["pacman", "-Si", *packages],
            capture_output=True,
            text=True,
            timeout=15,
            env=subprocess_env(),
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    versions, name = {}, ""
    for line in output.splitlines():
        key, _sep, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "Name":
            name = value
        elif key == "Version" and name and name not in versions:
            versions[name] = value.rsplit("-", 1)[0]
    return versions


def list_video_drivers(
    devices: list[gpu.PciDevice],
    chips: dict[str, gpu.NvidiaChip],
    installed: set[str],
    virtualization: str | None,
    versions: dict[str, str] | None = None,
) -> list[VideoDriver]:
    drivers: list[VideoDriver] = []
    has_nvidia = any(
        d.vendor == gpu.VENDOR_NVIDIA for d in gpu.display_devices(devices)
    )
    if has_nvidia:
        choice = gpu.choose_nvidia(devices, chips)
        versions = versions or {}
        for branch_name, branch in gpu.BRANCHES.items():
            utils = branch.utils[0]
            info = _("NVIDIA proprietary driver")
            if not branch.wayland:
                info = _("NVIDIA proprietary driver, X11 only")
            drivers.append(
                VideoDriver(
                    name=driver_name(branch_name),
                    version=versions.get(utils, ""),
                    info=info,
                    priority=_PRIORITY[branch_name],
                    installed=utils in installed,
                    compatible=branch_name in choice.compatible,
                    recommended=branch_name == choice.branch,
                    branch=branch_name,
                )
            )
    guests = gpu.VM_GUESTS.get(virtualization or "")
    if guests:
        packages = guests[0]
        drivers.append(
            VideoDriver(
                name=VM_DRIVER,
                free_driver=True,
                info=_("Virtual machine guest tools"),
                installed=all(p in installed for p in packages),
                compatible=True,
                recommended=True,
                packages=packages,
            )
        )
    return drivers


class GpuDriverManager(BaseManager):
    """Lists and changes video drivers through big-driver-manager-cli."""

    def __init__(self) -> None:
        super().__init__()
        self._logger = _logger

    def get_video_drivers(self) -> list[VideoDriver]:
        installed = gpu.installed_packages()
        return list_video_drivers(
            gpu.scan_pci(),
            gpu.load_supported_gpus(),
            installed,
            gpu.detect_virtualization(),
            _versions([b.utils[0] for b in gpu.BRANCHES.values()]),
        )

    def get_all_drivers(self) -> list[VideoDriver]:
        return self.get_video_drivers()

    def get_installed_drivers(self) -> list[VideoDriver]:
        return [d for d in self.get_video_drivers() if d.installed]

    def has_nvidia_installed(self) -> str | None:
        branch = gpu.installed_branch(gpu.installed_packages())
        return driver_name(branch) if branch else None

    def can_install_nvidia(self, name: str) -> tuple[bool, str]:
        """Kept for the interface. Switching branches is safe now (the old one
        is replaced in the same command), so only the remove-first rule of
        mhwd is kept for parity."""
        if "nvidia" not in name.lower():
            return True, ""
        existing = self.has_nvidia_installed()
        if existing and existing != name:
            return False, _("Remove the installed NVIDIA driver ({}) first.").format(
                existing
            )
        return True, ""

    def install_driver(
        self,
        driver: VideoDriver,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
    ) -> None:
        args = ["gpu", "install"]
        if driver.branch:
            args += ["--nvidia-branch", driver.branch]
        self.run_cli_command(
            args,
            progress_callback,
            output_callback,
            complete_callback,
            _("Installing {}").format(driver.display_name),
        )

    def switch_driver(
        self,
        driver: VideoDriver,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
    ) -> None:
        """Another NVIDIA branch: ``gpu install`` replaces the installed one."""
        self.install_driver(
            driver, progress_callback, output_callback, complete_callback
        )

    def remove_driver(
        self,
        driver: VideoDriver,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
    ) -> None:
        if driver.branch:
            args = ["gpu", "remove"]
        else:
            args = ["remove", "--recursive", "--", *driver.packages]
        self.run_cli_command(
            args,
            progress_callback,
            output_callback,
            complete_callback,
            _("Removing {}").format(driver.display_name),
        )
