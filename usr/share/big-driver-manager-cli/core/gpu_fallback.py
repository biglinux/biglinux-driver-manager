"""Fall back to nouveau, Mesa's NVIDIA driver, when the proprietary one fails.

When the proprietary driver does not come up -- the package failed to
install in the live session, or the module loads but leaves the card without
a driver (GSP firmware failure, unsupported chip, broken build) -- the
display manager starts on a card nobody drives: a black screen. Before the
display manager, the NVIDIA modules are unloaded and nouveau loaded instead.
Nothing is uninstalled: the failure may be this boot's only.

nouveau can only come back if the kernel command line does not forbid it:
``module_blacklist=nouveau`` refuses every load, ``modprobe.blacklist=`` and
modprobe.d's ``blacklist`` only the automatic one, so an explicit
``modprobe nouveau`` still works.
"""

from __future__ import annotations

from pathlib import Path

from core.gpu import VENDOR_NVIDIA, PciDevice, display_devices

MARKER = Path("/run/big-driver-manager/nvidia-fallback")
NVIDIA_MODULES = ("nvidia_drm", "nvidia_uvm", "nvidia_modeset", "nvidia")


def driverless_nvidia(devices: list[PciDevice]) -> list[PciDevice]:
    """NVIDIA display controllers with no driver at all.

    A card on nouveau is not a failure: the proprietary driver was installed
    on a running system and takes over at the next boot.
    """
    return [
        d
        for d in display_devices(devices)
        if d.vendor == VENDOR_NVIDIA and d.driver is None
    ]


def _values(cmdline: list[str], key: str) -> list[str]:
    values: list[str] = []
    for argument in cmdline:
        if argument.startswith(key + "="):
            values += argument.split("=", 1)[1].split(",")
    return values


def nouveau_forbidden(cmdline: list[str]) -> bool:
    """module_blacklist=...nouveau... : the kernel refuses even an explicit load."""
    return "nouveau" in _values(cmdline, "module_blacklist")


def fallback_commands(cmdline: list[str]) -> list[list[str]]:
    """Unload the NVIDIA modules, then load nouveau with modesetting.

    nouveau.modeset=0 on the command line (BigLinux's menu) leaves nouveau
    loaded without KMS: it is reloaded with modeset=1, the option given to
    modprobe winning over the command line's.
    """
    commands = [["modprobe", "-r", *NVIDIA_MODULES]]
    if "nouveau.modeset=0" in cmdline:
        commands.append(["modprobe", "-r", "nouveau"])
        commands.append(["modprobe", "nouveau", "modeset=1"])
    else:
        commands.append(["modprobe", "nouveau"])
    return commands


def record(reason: str, marker: Path | None = None) -> None:
    """Leave the reason where the interface (and support) can find it."""
    marker = marker or MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(reason + "\n", encoding="utf-8")


def recorded(marker: Path | None = None) -> str | None:
    marker = marker or MARKER
    try:
        return marker.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None
