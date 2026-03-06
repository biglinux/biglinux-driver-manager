#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MHWD Manager — lists, installs and removes hardware drivers via MHWD.

Handles video drivers (NVIDIA, AMD, Intel) and network drivers.
Prevents installing multiple conflicting NVIDIA driver versions.
"""

import re
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Callable

from core.base_manager import BaseManager
from core.logging_config import get_logger
from core.subprocess_env import subprocess_env
from utils.i18n import _

_logger = get_logger("MhwdManager")


@dataclass
class MhwdDriver:
    """A MHWD driver configuration."""

    name: str
    version: str
    free_driver: bool
    bus_type: str  # "PCI" or "USB"
    info: str = ""
    priority: int = 0
    conflicts: str = ""
    installed: bool = False
    compatible: bool = False
    category: str = ""  # "video", "network"

    @property
    def is_nvidia(self) -> bool:
        return "nvidia" in self.name.lower()

    @property
    def display_name(self) -> str:
        """Human-friendly name (e.g. 'video nvidia 570xx' from 'video-nvidia-570xx')."""
        return self.name.replace("-", " ")


@dataclass
class MhwdDevice:
    """A hardware device detected by MHWD."""

    bus_id: str  # e.g. "0000:01:00.0"
    class_id: str  # e.g. "0300"
    vendor_device: str  # e.g. "10de:2182"
    description: str
    installed_configs: list[MhwdDriver] = field(default_factory=list)
    available_configs: list[MhwdDriver] = field(default_factory=list)


class MhwdManager(BaseManager):
    """Manages hardware drivers via the MHWD utility."""

    def __init__(self) -> None:
        super().__init__()
        self._logger = _logger

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run(args: list[str], timeout: int = 10) -> str:
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=subprocess_env(),
            )
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            _logger.warning("Command %s failed: %s", args, exc)
            return ""

    # ------------------------------------------------------------------
    # List all / compatible / installed configs
    # ------------------------------------------------------------------

    def get_all_drivers(self) -> list[MhwdDriver]:
        """Return every MHWD driver config (installed or not)."""
        output = self._run(["mhwd", "-la"])
        return self._parse_driver_list(output)

    def get_compatible_drivers(self) -> list[MhwdDriver]:
        """Return drivers compatible with detected hardware."""
        output = self._run(["mhwd", "-l"])
        return self._parse_driver_list(output, compatible=True)

    def get_installed_drivers(self) -> list[MhwdDriver]:
        """Return currently installed MHWD configs."""
        output = self._run(["mhwd", "-li"])
        drivers = self._parse_driver_list(output)
        for d in drivers:
            d.installed = True
        return drivers

    def get_detailed_devices(self) -> list[MhwdDevice]:
        """Parse `mhwd -l -d` for per-device installed/available breakdown."""
        output = self._run(["mhwd", "-l", "-d"])
        return self._parse_detailed(output)

    # ------------------------------------------------------------------
    # Enriched driver list (merge all + compatible + installed)
    # ------------------------------------------------------------------

    def get_enriched_drivers(self) -> list[MhwdDriver]:
        """Return all video/network drivers with installed and compatible flags.

        The three ``mhwd`` queries are executed in parallel to cut wall-time
        from ~3s to ~1s.
        """
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=3) as pool:
            fut_all = pool.submit(self.get_all_drivers)
            fut_compat = pool.submit(self.get_compatible_drivers)
            fut_inst = pool.submit(self.get_installed_drivers)

            all_drivers = fut_all.result()
            compatible_names = {d.name for d in fut_compat.result()}
            installed_names = {d.name for d in fut_inst.result()}

        for d in all_drivers:
            d.compatible = d.name in compatible_names
            d.installed = d.name in installed_names

        self._resolve_nvidia_versions(all_drivers)
        return all_drivers

    @staticmethod
    def _resolve_nvidia_versions(drivers: list[MhwdDriver]) -> None:
        """Replace MHWD date-versions with real package versions for NVIDIA."""
        nvidia_drivers = [d for d in drivers if d.is_nvidia]
        if not nvidia_drivers:
            return

        # Map config name → pacman package name
        # video-nvidia → nvidia-utils, video-nvidia-570xx → nvidia-570xx-utils
        pkg_map: dict[str, MhwdDriver] = {}
        for d in nvidia_drivers:
            suffix = d.name.replace("video-", "", 1)  # "nvidia" or "nvidia-570xx"
            pkg_map[f"{suffix}-utils"] = d

        # Single pacman query for all packages
        try:
            result = subprocess.run(
                ["pacman", "-Si", *pkg_map.keys()],
                capture_output=True,
                text=True,
                timeout=10,
                env=subprocess_env(),
            )
            output = result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return

        # Parse "Name : nvidia-utils" and "Version : 590.48.01-3" blocks
        current_pkg = ""
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Name") and ":" in line:
                current_pkg = line.split(":", 1)[1].strip()
            elif line.startswith("Version") and ":" in line and current_pkg:
                raw_ver = line.split(":", 1)[1].strip()
                # Strip trailing -N packaging revision
                ver = raw_ver.rsplit("-", 1)[0] if "-" in raw_ver else raw_ver
                drv = pkg_map.get(current_pkg)
                if drv:
                    drv.version = ver
                current_pkg = ""

    def get_network_drivers(self) -> list[MhwdDriver]:
        """Return only network MHWD drivers with enriched flags."""
        return [d for d in self.get_enriched_drivers() if d.category == "network"]

    def get_video_drivers(self) -> list[MhwdDriver]:
        """Return only video MHWD drivers with enriched flags."""
        return [d for d in self.get_enriched_drivers() if d.category == "video"]

    # ------------------------------------------------------------------
    # NVIDIA conflict check
    # ------------------------------------------------------------------

    def has_nvidia_installed(self) -> str | None:
        """Return the name of an installed NVIDIA driver, or None."""
        for d in self.get_installed_drivers():
            if d.is_nvidia:
                return d.name
        return None

    def can_install_nvidia(self, driver_name: str) -> tuple[bool, str]:
        """Check if a NVIDIA driver can be installed.

        Returns (allowed, reason).
        """
        if "nvidia" not in driver_name.lower():
            return True, ""
        existing = self.has_nvidia_installed()
        if existing and existing != driver_name:
            return False, _("Remove the installed NVIDIA driver ({}) first.").format(
                existing
            )
        return True, ""

    # ------------------------------------------------------------------
    # Install / Remove via MHWD (background thread + callbacks)
    # ------------------------------------------------------------------

    def install_driver(
        self,
        driver: MhwdDriver,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
    ) -> None:
        """Install a MHWD driver config in a background thread."""
        allowed, reason = self.can_install_nvidia(driver.name)
        if not allowed:
            if output_callback:
                output_callback(reason)
            if complete_callback:
                complete_callback(False)
            return

        self._logger.info("Installing MHWD config: %s", driver.name)
        self._run_mhwd_command(
            "i",
            driver.bus_type.lower(),
            driver.name,
            progress_callback,
            output_callback,
            complete_callback,
        )

    def remove_driver(
        self,
        driver: MhwdDriver,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
    ) -> None:
        """Remove a MHWD driver config in a background thread."""
        self._logger.info("Removing MHWD config: %s", driver.name)
        self._run_mhwd_command(
            "r",
            driver.bus_type.lower(),
            driver.name,
            progress_callback,
            output_callback,
            complete_callback,
        )

    def switch_driver(
        self,
        driver: MhwdDriver,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
    ) -> None:
        """Switch to a different MHWD driver (force-install replaces conflicts)."""
        self._logger.info("Switching to MHWD config: %s", driver.name)
        self._run_mhwd_command(
            "i",
            driver.bus_type.lower(),
            driver.name,
            progress_callback,
            output_callback,
            complete_callback,
            force=True,
        )

    # ------------------------------------------------------------------
    # Internal: run mhwd in a thread
    # ------------------------------------------------------------------

    def _run_mhwd_command(
        self,
        action: str,
        bus: str,
        config_name: str,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
        force: bool = False,
    ) -> None:
        force_flag = " -f" if force else ""
        operation = f"mhwd{force_flag} -{action} {bus} {config_name}"
        self._logger.info("Running: %s", operation)

        def _worker() -> None:
            self._cancelled = False
            cmd = [self.sudo_command, "mhwd"]
            if force:
                cmd.append("-f")
            cmd.extend([f"-{action}", bus, config_name])
            if output_callback:
                output_callback(_("Command: {}").format(" ".join(cmd)))
            if progress_callback:
                progress_callback(0.1, _("Starting {}...").format(operation))

            try:
                self._current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=subprocess_env(),
                )
                if self._current_process.stdout:
                    for line in self._current_process.stdout:
                        if self._cancelled:
                            break
                        stripped = line.rstrip()
                        if stripped and output_callback:
                            output_callback(stripped)
                    self._current_process.wait()

                success = self._current_process.returncode == 0 and not self._cancelled
                if progress_callback:
                    progress_callback(
                        1.0 if success else 0.0,
                        _("Completed") if success else _("Failed"),
                    )
                if complete_callback:
                    complete_callback(success)
            except Exception as exc:
                self._logger.error("MHWD command failed: %s", exc)
                if output_callback:
                    output_callback(str(exc))
                if complete_callback:
                    complete_callback(False)
            finally:
                self._current_process = None

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_driver_list(output: str, compatible: bool = False) -> list[MhwdDriver]:
        """Parse the tabular output of mhwd -l / -la / -li."""
        drivers: list[MhwdDriver] = []
        # Lines look like:
        #     video-nvidia            2025.09.29               false            PCI
        pattern = re.compile(r"^\s*([\w-]+)\s+([\d.]+)\s+(true|false)\s+(PCI|USB)\s*$")
        for line in output.splitlines():
            m = pattern.match(line)
            if not m:
                continue
            name = m.group(1)
            category = "video" if name.startswith("video-") else "network"
            drivers.append(
                MhwdDriver(
                    name=name,
                    version=m.group(2),
                    free_driver=m.group(3) == "true",
                    bus_type=m.group(4),
                    compatible=compatible,
                    category=category,
                )
            )
        return drivers

    # Compiled patterns for _parse_detailed
    _DEV_RE = re.compile(r">\s*PCI Device:\s+(\S+)\s+\(([0-9a-fA-F:]+)\)\s*(.*)")
    _NAME_RE = re.compile(r"^\s+NAME:\s+(.+)")
    _VER_RE = re.compile(r"^\s+VERSION:\s+(.+)")
    _INFO_RE = re.compile(r"^\s+INFO:\s+(.+)")
    _PRIO_RE = re.compile(r"^\s+PRIORITY:\s+(\d+)")
    _FREE_RE = re.compile(r"^\s+FREEDRIVER:\s+(true|false)")
    _CONF_RE = re.compile(r"^\s+CONFLICTS:\s+(.*)")

    @staticmethod
    def _build_mhwd_driver(temp: dict, section: str) -> MhwdDriver | None:
        """Build an MhwdDriver from accumulated field dict, or None."""
        name = temp.get("name")
        if not name:
            return None
        return MhwdDriver(
            name=name,
            version=temp.get("version", ""),
            free_driver=temp.get("free", True),
            bus_type="PCI",
            info=temp.get("info", ""),
            priority=temp.get("priority", 0),
            conflicts=temp.get("conflicts", ""),
            installed=section == "installed",
            compatible=True,
            category="video" if name.startswith("video-") else "network",
        )

    @staticmethod
    def _parse_detailed(output: str) -> list[MhwdDevice]:
        """Parse `mhwd -l -d` output into per-device structures."""
        devices: list[MhwdDevice] = []
        current_device: MhwdDevice | None = None
        section = ""
        temp: dict = {}

        def _flush() -> None:
            nonlocal current_device
            drv = MhwdManager._build_mhwd_driver(temp, section)
            if drv and current_device is not None:
                if section == "installed":
                    current_device.installed_configs.append(drv)
                else:
                    current_device.available_configs.append(drv)
            temp.clear()

        for line in output.splitlines():
            dm = MhwdManager._DEV_RE.search(line)
            if dm:
                _flush()
                dev_path = dm.group(1)
                ids = dm.group(2)
                parts = ids.split(":")
                bus_id = dev_path.rsplit("/", 1)[-1] if "/" in dev_path else ""
                current_device = MhwdDevice(
                    bus_id=bus_id,
                    class_id=parts[0] if len(parts) > 0 else "",
                    vendor_device=":".join(parts[1:]) if len(parts) > 1 else "",
                    description=dm.group(3).strip(),
                )
                devices.append(current_device)
                section = ""
                continue

            if (
                current_device is not None
                and not current_device.description
                and section == ""
                and line.strip()
                and not line.strip().startswith(">")
                and not line.startswith("---")
            ):
                current_device.description = line.strip()
                continue

            if "> INSTALLED:" in line:
                _flush()
                section = "installed"
                continue
            if "> AVAILABLE:" in line:
                _flush()
                section = "available"
                continue

            m = MhwdManager._NAME_RE.match(line)
            if m:
                _flush()
                temp["name"] = m.group(1).strip()
                continue
            m = MhwdManager._VER_RE.match(line)
            if m:
                temp["version"] = m.group(1).strip()
                continue
            m = MhwdManager._INFO_RE.match(line)
            if m:
                temp["info"] = m.group(1).strip()
                continue
            m = MhwdManager._PRIO_RE.match(line)
            if m:
                temp["priority"] = int(m.group(1))
                continue
            m = MhwdManager._FREE_RE.match(line)
            if m:
                temp["free"] = m.group(1) == "true"
                continue
            m = MhwdManager._CONF_RE.match(line)
            if m:
                temp["conflicts"] = m.group(1).strip()
                continue

        _flush()
        return devices
