"""Graphics driver selection, without mhwd.

Three questions decide what a machine needs:

* Which display controllers it has -- read from sysfs (PCI class 0x03xx),
  matched by vendor ID, never by the vendor names lspci prints.
* Which NVIDIA driver each NVIDIA chip takes -- from NVIDIA's own
  supported-gpus.json (shipped by nvidia-driver-assistant): the legacy branch
  a chip belongs to, whether it runs the open kernel module, whether it
  supports runtime power management.
* Which kernels are installed -- from the ``pkgbase`` file every kernel package
  puts in /usr/lib/modules/<version>/, so linux-big, linuxNN-comm and any other
  kernel get their module package (``<pkgbase>-nvidia-open``...) with no list
  of kernel names to keep up to date.

``build_plan`` combines the three into the packages, services and
configuration files to install; ``apply_plan`` carries it out as root.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.kernel_manager import scan_module_kernels
from core.logging_config import get_logger

_logger = get_logger("Gpu")

VENDOR_NVIDIA = "10de"
VENDOR_INTEL = "8086"
VENDOR_AMD = "1002"
_VENDOR_NAMES = {VENDOR_NVIDIA: "nvidia", VENDOR_INTEL: "intel", VENDOR_AMD: "amd"}
# Virtual GPUs: QEMU/virtio, Red Hat QXL, VirtualBox, VMware, Cirrus
_VIRTUAL_VENDORS = frozenset({"1af4", "1b36", "80ee", "15ad", "1013"})

SUPPORTED_GPUS_JSON = Path(
    os.environ.get(
        "BDM_SUPPORTED_GPUS",
        "/usr/share/nvidia-driver-assistant/supported-gpus/supported-gpus.json",
    )
)
BROADCOM_WL_IDS = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "device-ids"
    / "broadcom-wl"
    / "pci.ids"
)

# Files this module owns on the target system.
NVIDIA_MODULES_LOAD = "etc/modules-load.d/big-driver-manager-nvidia.conf"
NVIDIA_POWER_MODPROBE = "etc/modprobe.d/big-driver-manager-nvidia-power.conf"
NVIDIA_POWER_UDEV = "etc/udev/rules.d/80-big-driver-manager-nvidia-power.rules"

# NVIDIA README, "PCI-Express Runtime D3 (RTD3) Power Management": let the
# dGPU sleep when idle, and drop the USB/UCSI functions some cards expose,
# which would otherwise keep it awake.
NVIDIA_POWER_UDEV_RULES = """\
# Managed by big-driver-manager-cli. Do not edit.
# Remove NVIDIA USB xHCI Host Controller and USB Type-C UCSI functions, if present
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x0c0330", ATTR{remove}="1"
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x0c8000", ATTR{remove}="1"
# Enable runtime PM for NVIDIA VGA/3D controllers on driver bind, disable on unbind
ACTION=="bind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030000", TEST=="power/control", ATTR{power/control}="auto"
ACTION=="bind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", TEST=="power/control", ATTR{power/control}="auto"
ACTION=="unbind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030000", TEST=="power/control", ATTR{power/control}="on"
ACTION=="unbind", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", TEST=="power/control", ATTR{power/control}="on"
"""
NVIDIA_POWER_MODPROBE_TEXT = (
    "# Managed by big-driver-manager-cli. Do not edit.\n"
    'options nvidia "NVreg_DynamicPowerManagement=0x02"\n'
)
# Load nvidia_drm early, so the compositor or Xorg finds it on first start.
NVIDIA_MODULES_LOAD_TEXT = (
    "# Managed by big-driver-manager-cli. Do not edit.\nnvidia_drm\n"
)


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PciDevice:
    slot: str
    vendor: str  # lowercase hex, no 0x
    device: str
    pci_class: int
    boot_vga: bool = False
    driver: str | None = None

    @property
    def is_display(self) -> bool:
        return self.pci_class >> 16 == 0x03

    @property
    def vendor_name(self) -> str:
        if self.vendor in _VENDOR_NAMES:
            return _VENDOR_NAMES[self.vendor]
        return "virtual" if self.vendor in _VIRTUAL_VENDORS else "other"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _hex(value: str) -> str:
    return value.lower().removeprefix("0x")


def scan_pci(sys_root: Path = Path("/sys")) -> list[PciDevice]:
    devices = []
    base = sys_root / "bus" / "pci" / "devices"
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return devices
    for entry in entries:
        try:
            pci_class = int(_read(entry / "class") or "0", 16)
        except ValueError:
            continue
        driver_link = entry / "driver"
        driver = (
            os.path.basename(os.readlink(driver_link))
            if driver_link.is_symlink()
            else None
        )
        devices.append(
            PciDevice(
                slot=entry.name,
                vendor=_hex(_read(entry / "vendor")),
                device=_hex(_read(entry / "device")),
                pci_class=pci_class,
                boot_vga=_read(entry / "boot_vga") == "1",
                driver=driver,
            )
        )
    return devices


def display_devices(devices: list[PciDevice]) -> list[PciDevice]:
    return [d for d in devices if d.is_display]


def detect_virtualization() -> str | None:
    """systemd-detect-virt's answer for a VM ("oracle", "vmware", "kvm"...)."""
    try:
        result = subprocess.run(
            ["systemd-detect-virt", "--vm"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    answer = result.stdout.strip()
    return answer if result.returncode == 0 and answer and answer != "none" else None


def installed_kernels(root: Path = Path("/")) -> list[str]:
    """pkgbase of every installed kernel package, e.g. ["linux-big", "linux618"]."""
    names = []
    for kernel in scan_module_kernels(root / "usr" / "lib" / "modules"):
        if kernel["pkgbase"] and kernel["pkgbase"] not in names:
            names.append(kernel["pkgbase"])
    return names


# --------------------------------------------------------------------------
# NVIDIA driver choice
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class NvidiaChip:
    devid: str
    name: str
    legacy_branch: str | None
    features: frozenset[str]


@dataclass(frozen=True)
class DriverBranch:
    name: str
    utils: tuple[str, ...]
    lib32: tuple[str, ...]
    module: str
    open_module: str | None
    dkms: str
    open_dkms: str | None
    wayland: bool


# Oldest last: when chips disagree, the oldest branch any of them needs wins,
# because a newer driver dropped those chips while the older one still drives
# the newer chips.
BRANCHES: dict[str, DriverBranch] = {
    "current": DriverBranch(
        "current",
        ("nvidia-utils", "nvidia-settings"),
        ("lib32-nvidia-utils",),
        "nvidia",
        "nvidia-open",
        "nvidia-dkms",
        "nvidia-open-dkms",
        True,
    ),
    "580xx": DriverBranch(
        "580xx",
        ("nvidia-580xx-utils", "nvidia-580xx-settings"),
        ("lib32-nvidia-580xx-utils",),
        "nvidia-580xx",
        "nvidia-580xx-open",
        "nvidia-580xx-dkms",
        "nvidia-580xx-open-dkms",
        True,
    ),
    "470xx": DriverBranch(
        "470xx",
        ("nvidia-470xx-utils", "nvidia-470xx-settings"),
        ("lib32-nvidia-470xx-utils",),
        "nvidia-470xx",
        None,
        "nvidia-470xx-dkms",
        None,
        # 470 has no GBM: GNOME and Plasma fall back to their X11 session.
        False,
    ),
}
_BRANCH_ORDER = list(BRANCHES)


def load_supported_gpus(path: Path = SUPPORTED_GPUS_JSON) -> dict[str, NvidiaChip]:
    """Chips by device ID (lowercase, no 0x) from NVIDIA's supported-gpus.json."""
    try:
        chips = json.loads(path.read_text(encoding="utf-8"))["chips"]
    except (OSError, ValueError, KeyError) as error:
        _logger.warning("Cannot read %s: %s", path, error)
        return {}
    table: dict[str, NvidiaChip] = {}
    for chip in chips:
        devid = _hex(chip.get("devid", ""))
        if not devid or devid in table:
            continue
        table[devid] = NvidiaChip(
            devid=devid,
            name=chip.get("name", ""),
            legacy_branch=chip.get("legacybranch") or None,
            features=frozenset(f.lower() for f in chip.get("features", [])),
        )
    return table


@dataclass
class NvidiaChoice:
    branch: str | None  # key of BRANCHES; None when no chip has a usable driver
    open_module: bool = False
    runtime_pm: bool = False
    chips: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


def _chip_branch(chip: NvidiaChip | None) -> tuple[str | None, bool, bool]:
    """(branch, open module, runtime PM) for one chip."""
    if chip is None:
        # Newer than the table: NVIDIA's rule is the current open driver.
        return "current", True, True
    runtime_pm = "runtimepm" in chip.features
    if not chip.legacy_branch:
        return "current", "kernelopen" in chip.features, runtime_pm
    major = chip.legacy_branch.split(".")[0]
    if major == "580":
        return "580xx", "kernelopen" in chip.features, runtime_pm
    if major == "470":
        return "470xx", False, runtime_pm
    return None, False, False


def choose_nvidia(
    devices: list[PciDevice], chips: dict[str, NvidiaChip]
) -> NvidiaChoice:
    choice = NvidiaChoice(branch=None)
    branches, open_flags, pm_flags = [], [], []
    for device in devices:
        if device.vendor != VENDOR_NVIDIA or not device.is_display:
            continue
        chip = chips.get(device.device)
        label = f"{chip.name if chip else 'NVIDIA'} [10de:{device.device}]"
        branch, open_module, runtime_pm = _chip_branch(chip)
        if branch is None:
            choice.unsupported.append(label)
            continue
        choice.chips.append(label)
        branches.append(branch)
        open_flags.append(open_module)
        pm_flags.append(runtime_pm)
    if branches:
        choice.branch = max(branches, key=_BRANCH_ORDER.index)
        has_open = BRANCHES[choice.branch].open_module is not None
        choice.open_module = has_open and all(open_flags)
        choice.runtime_pm = all(pm_flags)
    return choice


# --------------------------------------------------------------------------
# Plan
# --------------------------------------------------------------------------


@dataclass
class GpuPlan:
    gpus: list[dict] = field(default_factory=list)
    hybrid: bool = False
    nonfree: bool = True
    nvidia: NvidiaChoice | None = None
    virtualization: str | None = None
    kernels: list[str] = field(default_factory=list)
    install: list[str] = field(default_factory=list)
    unavailable: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# systemd-detect-virt answer -> guest packages and the units they need
_VM_GUESTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "oracle": (("virtualbox-guest-utils",), ("vboxservice.service",)),
    "vmware": (("open-vm-tools", "xf86-input-vmmouse"), ("vmtoolsd.service",)),
    "kvm": (
        ("qemu-guest-agent", "spice-vdagent"),
        ("qemu-guest-agent.service", "spice-vdagentd.socket"),
    ),
    "qemu": (
        ("qemu-guest-agent", "spice-vdagent"),
        ("qemu-guest-agent.service", "spice-vdagentd.socket"),
    ),
}


def _load_broadcom_wl_ids(path: Path = BROADCOM_WL_IDS) -> set[str]:
    ids = set()
    for line in _read(path).splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" in line:
            vendor, device = line.split(":", 1)
            ids.add(f"{_hex(vendor)}:{_hex(device)}")
    return ids


def _kernel_module_packages(
    kernels: list[str], module: str, dkms: str, repo: set[str], plan: GpuPlan
) -> list[str]:
    """``<kernel>-<module>`` for each kernel, DKMS for kernels the repo lacks."""
    packages, missing = [], []
    for kernel in kernels:
        name = f"{kernel}-{module}"
        if name in repo:
            packages.append(name)
        else:
            missing.append(kernel)
    if missing:
        packages.append(dkms)
        packages.extend(f"{kernel}-headers" for kernel in missing)
        plan.notes.append(
            f"no {module} package for {', '.join(missing)}: building it with {dkms}"
        )
    return packages


def build_plan(
    devices: list[PciDevice],
    kernels: list[str],
    repo: set[str],
    *,
    nonfree: bool = True,
    virtualization: str | None = None,
    chips: dict[str, NvidiaChip] | None = None,
    broadcom_wl_ids: set[str] | None = None,
    installed: set[str] | None = None,
) -> GpuPlan:
    """Everything the machine needs, as packages, units and files.

    ``repo`` is the set of package names the configured repositories offer
    (``pacman -Slq``); a wanted package outside it is reported, not installed,
    unless it is already in ``installed``.
    """
    display = display_devices(devices)
    nvidia = [d for d in display if d.vendor == VENDOR_NVIDIA]
    others = [d for d in display if d.vendor != VENDOR_NVIDIA]
    plan = GpuPlan(
        gpus=[{**asdict(d), "vendor_name": d.vendor_name} for d in display],
        hybrid=bool(nvidia) and bool(others),
        nonfree=nonfree,
        virtualization=virtualization,
        kernels=list(kernels),
    )
    wanted: list[str] = []

    if nvidia and nonfree:
        choice = choose_nvidia(devices, chips if chips is not None else {})
        plan.nvidia = choice
        for label in choice.unsupported:
            plan.notes.append(f"{label}: no supported NVIDIA driver, keeping nouveau")
        if choice.branch:
            branch = BRANCHES[choice.branch]
            wanted += branch.utils
            if all(name in repo for name in branch.lib32):
                wanted += branch.lib32
            if choice.open_module:
                module, dkms = branch.open_module, branch.open_dkms
            else:
                module, dkms = branch.module, branch.dkms
            wanted += _kernel_module_packages(kernels, module, dkms, repo, plan)
            plan.files[NVIDIA_MODULES_LOAD] = NVIDIA_MODULES_LOAD_TEXT
            if not branch.wayland:
                plan.notes.append(
                    f"NVIDIA {branch.name} has no Wayland support: use an X11 session"
                )
            if plan.hybrid:
                wanted += ["nvidia-prime", "switcheroo-control"]
                plan.services.append("switcheroo-control.service")
                if choice.runtime_pm:
                    plan.files[NVIDIA_POWER_UDEV] = NVIDIA_POWER_UDEV_RULES
                    plan.files[NVIDIA_POWER_MODPROBE] = NVIDIA_POWER_MODPROBE_TEXT
    elif plan.hybrid:
        # Two GPUs on free drivers: still offer "launch on the other GPU".
        wanted.append("switcheroo-control")
        plan.services.append("switcheroo-control.service")

    if nonfree:
        wl_ids = (
            broadcom_wl_ids if broadcom_wl_ids is not None else _load_broadcom_wl_ids()
        )
        if any(f"{d.vendor}:{d.device}" in wl_ids for d in devices):
            wanted += _kernel_module_packages(
                kernels, "broadcom-wl", "broadcom-wl-dkms", repo, plan
            )

    if virtualization in _VM_GUESTS:
        packages, units = _VM_GUESTS[virtualization]
        wanted += packages
        plan.services += units

    installed = installed or set()
    for name in dict.fromkeys(wanted):
        if name in repo:
            plan.install.append(name)
        elif name not in installed:
            plan.unavailable.append(name)
    return plan


# --------------------------------------------------------------------------
# Applying a plan
# --------------------------------------------------------------------------


def repo_packages(
    pacman_config: Path | None = None, root: Path | None = None
) -> set[str]:
    """Names the configured repositories offer (``pacman -Slq``)."""
    cmd = ["pacman", "-Slq"]
    if pacman_config:
        cmd += ["--config", str(pacman_config)]
    if root:
        cmd += ["--root", str(root)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        _logger.warning("pacman -Slq failed: %s", error)
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def installed_packages(root: Path | None = None) -> set[str]:
    cmd = ["pacman", "-Qq"] + (["--root", str(root)] if root else [])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return set(result.stdout.split())


def write_files(files: dict[str, str], root: Path = Path("/")) -> list[Path]:
    written = []
    for relative, content in files.items():
        target = root / relative
        if target.is_file() and target.read_text(encoding="utf-8") == content:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written


def pacman_install_command(
    packages: list[str], pacman_config: Path | None = None, root: Path | None = None
) -> list[str]:
    cmd = ["pacman", "-S", "--noconfirm", "--needed"]
    if pacman_config:
        cmd += ["--config", str(pacman_config)]
    if root:
        cmd += ["--root", str(root)]
    return cmd + list(packages)


def enable_units_command(units: list[str], root: Path | None = None) -> list[str]:
    """Enable units; on the running system also start them, without waiting
    (this runs during boot, before the display manager)."""
    if root and root != Path("/"):
        return ["systemctl", "--root", str(root), "enable", *units]
    return ["systemctl", "enable", "--now", "--no-block", *units]
