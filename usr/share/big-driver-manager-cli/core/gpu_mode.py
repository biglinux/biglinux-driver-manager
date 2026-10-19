"""Which GPU drives a hybrid (integrated + NVIDIA) machine.

hybrid      (default) the integrated GPU drives the screen; NVIDIA renders on
            demand (prime-run, switcheroo "launch on discrete GPU") and sleeps
            otherwise (RTD3, see core.gpu).
nvidia      NVIDIA stays awake and is the Xorg primary GPU. On a laptop the
            panel is wired to the integrated GPU, so its outputs must be told
            to show what NVIDIA renders (xrandr --setprovideroutputsource):
            done for the greeter (LightDM, SDDM, GDM) and for X11 sessions.
            Wayland sessions are not affected: the compositor already renders
            where it should.
integrated  the NVIDIA modules never load: best battery life.

Only the deviations from the hybrid baseline are written; switching back to
hybrid removes them. Ported from biglinux-gpu-manager (mhwd-biglinux), whose
mode file is still read so existing choices survive the move.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.gpu import VENDOR_NVIDIA, PciDevice, display_devices

MODES = ("hybrid", "nvidia", "integrated")

MODE_FILE = "etc/big-driver-manager/gpu-mode"
LEGACY_MODE_FILE = "etc/biglinux-gpu-mode"  # biglinux-gpu-manager
# zz-: sorts after the power options in core.gpu, so this one wins the merge
MODE_MODPROBE = "etc/modprobe.d/zz-big-driver-manager-gpu-mode.conf"
NVIDIA_PRIMARY_XORG = "etc/X11/xorg.conf.d/99-big-driver-manager-nvidia-primary.conf"
LIGHTDM_DROPIN = "etc/lightdm/lightdm.conf.d/zz-big-driver-manager-prime.conf"
SDDM_DROPIN = "etc/sddm.conf.d/zz-big-driver-manager-prime.conf"
SESSION_AUTOSTART = "etc/xdg/autostart/big-driver-manager-prime.desktop"
GDM_GREETER_AUTOSTART = (
    "usr/share/gdm/greeter/autostart/big-driver-manager-prime.desktop"
)

SHARE_DIR = "/usr/share/big-driver-manager-cli"
PRIME_SCRIPT = f"{SHARE_DIR}/prime-xrandr.sh"
PRIME_SCRIPT_LIGHTDM = f"{SHARE_DIR}/prime-xrandr-lightdm.sh"
PRIME_SCRIPT_SDDM = f"{SHARE_DIR}/prime-xrandr-sddm.sh"

_HEADER = "# Managed by big-driver-manager-cli (gpu mode {mode}). Do not edit.\n"

NVIDIA_MODE_MODPROBE_TEXT = (
    _HEADER.format(mode="nvidia")
    + 'options nvidia "NVreg_DynamicPowerManagement=0x00"\n'
)
INTEGRATED_MODE_MODPROBE_TEXT = _HEADER.format(mode="integrated") + "".join(
    f"blacklist {m}\ninstall {m} /bin/false\n"
    for m in ("nvidia", "nvidia_drm", "nvidia_modeset", "nvidia_uvm")
)
NVIDIA_PRIMARY_XORG_TEXT = (
    _HEADER.format(mode="nvidia")
    + """Section "OutputClass"
    Identifier "big-driver-manager-nvidia-primary"
    MatchDriver "nvidia-drm"
    Driver "nvidia"
    Option "AllowEmptyInitialConfiguration"
    Option "PrimaryGPU" "yes"
    ModulePath "/usr/lib/nvidia/xorg"
    ModulePath "/usr/lib/xorg/modules"
EndSection
"""
)
LIGHTDM_DROPIN_TEXT = (
    _HEADER.format(mode="nvidia")
    + f"[Seat:*]\ndisplay-setup-script={PRIME_SCRIPT_LIGHTDM}\n"
)
SDDM_DROPIN_TEXT = (
    _HEADER.format(mode="nvidia") + f"[X11]\nDisplayCommand={PRIME_SCRIPT_SDDM}\n"
)
AUTOSTART_TEXT = f"""\
[Desktop Entry]
# Managed by big-driver-manager-cli (gpu mode nvidia). Do not edit.
Type=Application
Name=NVIDIA PRIME display setup
Exec={PRIME_SCRIPT}
NoDisplay=true
X-GNOME-Autostart-Phase=DisplayServer
"""

# Files each mode owns. Everything listed under another mode is removed.
_MODE_FILES: dict[str, dict[str, str]] = {
    "hybrid": {},
    "nvidia": {
        MODE_MODPROBE: NVIDIA_MODE_MODPROBE_TEXT,
        NVIDIA_PRIMARY_XORG: NVIDIA_PRIMARY_XORG_TEXT,
        LIGHTDM_DROPIN: LIGHTDM_DROPIN_TEXT,
        SDDM_DROPIN: SDDM_DROPIN_TEXT,
        SESSION_AUTOSTART: AUTOSTART_TEXT,
        GDM_GREETER_AUTOSTART: AUTOSTART_TEXT,
    },
    "integrated": {MODE_MODPROBE: INTEGRATED_MODE_MODPROBE_TEXT},
}
_ALL_FILES = {path for files in _MODE_FILES.values() for path in files}
# Written only when that display manager is installed.
_DM_FILES = {
    LIGHTDM_DROPIN: "etc/lightdm",
    SDDM_DROPIN: "usr/bin/sddm",
    GDM_GREETER_AUTOSTART: "usr/share/gdm",
}
# Changes that only take effect from the initramfs on (modconf hook).
_INITRAMFS_FILES = {MODE_MODPROBE}


class GpuModeError(ValueError):
    pass


@dataclass
class ModeChange:
    mode: str
    written: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def needs_initramfs(self) -> bool:
        return any(path in _INITRAMFS_FILES for path in self.written + self.removed)


def is_hybrid(devices: list[PciDevice]) -> bool:
    display = display_devices(devices)
    return any(d.vendor == VENDOR_NVIDIA for d in display) and any(
        d.vendor != VENDOR_NVIDIA for d in display
    )


def read_mode(root: Path = Path("/")) -> str | None:
    """The recorded mode, or None. Understands biglinux-gpu-manager's file."""
    for relative in (MODE_FILE, LEGACY_MODE_FILE):
        try:
            value = (root / relative).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value in MODES:
            return value
        # biglinux-gpu-manager numeric modes: 1-8 iGPU primary, 9-16 NVIDIA
        if value.isdigit():
            return "nvidia" if 9 <= int(value) <= 16 else "hybrid"
    return None


def apply_mode(
    mode: str, devices: list[PciDevice], root: Path = Path("/")
) -> ModeChange:
    """Write the files for ``mode`` and remove those of the other modes."""
    if mode not in MODES:
        raise GpuModeError(f"unknown GPU mode: {mode} (use {', '.join(MODES)})")
    if not is_hybrid(devices):
        raise GpuModeError("GPU modes need an integrated GPU and an NVIDIA GPU")
    change = ModeChange(mode=mode)
    wanted = _MODE_FILES[mode]
    for relative in sorted(_ALL_FILES - set(wanted)):
        target = root / relative
        if target.is_file():
            target.unlink()
            change.removed.append(relative)
    for relative, content in wanted.items():
        marker = _DM_FILES.get(relative)
        if marker and not (root / marker).exists():
            continue
        target = root / relative
        if target.is_file() and target.read_text(encoding="utf-8") == content:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        change.written.append(relative)
    mode_file = root / MODE_FILE
    mode_file.parent.mkdir(parents=True, exist_ok=True)
    mode_file.write_text(mode + "\n", encoding="utf-8")
    legacy = root / LEGACY_MODE_FILE
    if legacy.is_file():
        legacy.unlink()
    if mode != "integrated":
        change.services.append("switcheroo-control.service")
    if mode == "nvidia":
        change.notes.append(
            "NVIDIA drives Xorg sessions after a restart; Wayland sessions keep "
            "the integrated GPU on the screen"
        )
    if change.needs_initramfs:
        change.notes.append("the initramfs must be rebuilt (mkinitcpio -P)")
    return change


def clear_mode(root: Path = Path("/")) -> ModeChange:
    """Remove every mode file: the NVIDIA driver is gone."""
    change = ModeChange(mode="none")
    for relative in sorted(_ALL_FILES | {MODE_FILE, LEGACY_MODE_FILE}):
        target = root / relative
        if target.is_file():
            target.unlink()
            change.removed.append(relative)
    return change
