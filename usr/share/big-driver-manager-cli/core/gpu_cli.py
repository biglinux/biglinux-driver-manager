"""``big-driver-manager-cli gpu ...``: graphics drivers without mhwd.

detect   what display controllers, kernels and virtualization there are
plan     what ``install`` would do (no root needed)
install  install the drivers the machine needs: live session, installer, GUI
mode     hybrid | nvidia | integrated on an integrated + NVIDIA machine
status   recorded mode and hardware
boot     what runs before the display manager on every boot
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from core import gpu, gpu_mode
from core.privileged import is_root

LIVE_MARKER = Path("/livefs-pkgs.txt")
OFFLINE_PACMAN_CONFIG = Path("/opt/mhwd/pacman-mhwd.conf")
KERNEL_CMDLINE = Path("/proc/cmdline")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_NOT_ROOT = 77


def add_parser(verbs: argparse._SubParsersAction) -> None:
    parser = verbs.add_parser("gpu", help="graphics drivers (replaces mhwd)")
    actions = parser.add_subparsers(dest="gpu_action", required=True)

    def target_options(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--root", type=Path, help="target system (installer)")
        sub.add_argument(
            "--pmconfig",
            type=Path,
            help="pacman configuration, e.g. the live medium's offline repository",
        )

    def driver_options(sub: argparse.ArgumentParser) -> None:
        group = sub.add_mutually_exclusive_group()
        group.add_argument(
            "--free", action="store_true", help="open source drivers only"
        )
        group.add_argument(
            "--from-cmdline",
            action="store_true",
            help="driver=free|nonfree from the kernel command line (live media)",
        )

    detect = actions.add_parser("detect", help="show the hardware")
    detect.add_argument("--json", action="store_true")

    plan = actions.add_parser("plan", help="show what install would do")
    driver_options(plan)
    target_options(plan)
    plan.add_argument("--json", action="store_true")

    install = actions.add_parser(
        "install", help="install the drivers this machine needs"
    )
    driver_options(install)
    target_options(install)

    mode = actions.add_parser("mode", help="choose which GPU drives a hybrid machine")
    mode.add_argument("mode", choices=gpu_mode.MODES)
    mode.add_argument("--root", type=Path, help="target system (installer)")

    status = actions.add_parser("status", help="recorded GPU mode and hardware")
    status.add_argument("--json", action="store_true")

    actions.add_parser("boot", help="run by big-driver-manager-gpu.service")


# --------------------------------------------------------------------------


def _print(text: str) -> None:
    print(text, flush=True)


def _error(text: str) -> None:
    print(f"big-driver-manager-cli: {text}", file=sys.stderr, flush=True)


def _cmdline_args(path: Path = KERNEL_CMDLINE) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").split()
    except OSError:
        return []


def _cmdline_value(key: str, args: list[str]) -> str | None:
    values = [a.split("=", 1)[1] for a in args if a.startswith(key + "=")]
    return values[-1] if values else None


def _nonfree(args: argparse.Namespace) -> bool:
    if getattr(args, "free", False):
        return False
    if getattr(args, "from_cmdline", False):
        # mhwd-live's default: an absent driver= means nonfree
        return _cmdline_value("driver", _cmdline_args()) != "free"
    return True


def _target_root(args: argparse.Namespace) -> Path:
    return args.root if getattr(args, "root", None) else Path("/")


def _untrusted(path: Path) -> str | None:
    """Why ``path`` could be controlled by someone other than root, or None."""
    try:
        info = os.lstat(path)
    except OSError as error:
        return f"{path}: {error.strerror}"
    if stat.S_ISLNK(info.st_mode):
        return f"{path} is a symbolic link"
    if info.st_uid != 0:
        return f"{path} is not owned by root"
    if info.st_mode & 0o022:
        return f"{path} is writable by group or others"
    return None


# Paths of a target system whose owner decides what runs inside it: pacman
# --root runs install scriptlets and hooks chrooted there, as root.
_ROOT_SKELETON = ("", "etc", "usr", "usr/bin", "usr/lib")


def _refuse_redirection(args: argparse.Namespace) -> str | None:
    """--root and --pmconfig let pacman install, as root, from a configuration
    and into a tree chosen by the caller. They are honoured only when both are
    root's alone -- the installer's target, the live medium's /opt/mhwd --
    whoever asks (pkexec reaches here too, and so does the installer, which
    the live session starts through pkexec)."""
    root = getattr(args, "root", None)
    if root:
        for relative in _ROOT_SKELETON:
            reason = _untrusted(root / relative)
            if reason:
                return f"--root refused: {reason}"
    pmconfig = getattr(args, "pmconfig", None)
    if pmconfig:
        for path in (pmconfig, pmconfig.parent):
            reason = _untrusted(path)
            if reason:
                return f"--pmconfig refused: {reason}"
    return None


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("LC_")}
    env.update(LANG="C", LC_ALL="C")
    return env


def _build_plan(args: argparse.Namespace) -> gpu.GpuPlan:
    root = _target_root(args)
    pacman_root = root if root != Path("/") else None
    return gpu.build_plan(
        gpu.scan_pci(),
        gpu.installed_kernels(root),
        gpu.repo_packages(args.pmconfig, pacman_root),
        nonfree=_nonfree(args),
        virtualization=gpu.detect_virtualization(),
        chips=gpu.load_supported_gpus(),
        installed=gpu.installed_packages(pacman_root),
    )


def _describe_plan(plan: gpu.GpuPlan) -> None:
    for item in plan.gpus:
        primary = " (boot display)" if item["boot_vga"] else ""
        driver = item["driver"] or "no driver"
        _print(
            f"GPU {item['slot']}: {item['vendor_name']} "
            f"[{item['vendor']}:{item['device']}] {driver}{primary}"
        )
    _print(f"Kernels: {', '.join(plan.kernels) or 'none'}")
    if plan.virtualization:
        _print(f"Virtual machine: {plan.virtualization}")
    if plan.nvidia and plan.nvidia.branch:
        flavor = "open" if plan.nvidia.open_module else "proprietary"
        _print(f"NVIDIA driver: {plan.nvidia.branch} ({flavor} kernel module)")
    _print(f"Hybrid: {'yes' if plan.hybrid else 'no'}")
    _print(f"Install: {' '.join(plan.install) or 'nothing'}")
    if plan.unavailable:
        _print(f"Not in the repositories: {' '.join(plan.unavailable)}")
    for note in plan.notes:
        _print(f"Note: {note}")


def _run(cmd: list[str]) -> bool:
    _print("Command: " + " ".join(cmd))
    try:
        return subprocess.run(cmd, env=_env()).returncode == 0
    except OSError as error:
        _error(str(error))
        return False


def _install(args: argparse.Namespace) -> int:
    root = _target_root(args)
    plan = _build_plan(args)
    _describe_plan(plan)
    pacman_root = root if root != Path("/") else None
    if plan.install and not _run(
        gpu.pacman_install_command(plan.install, args.pmconfig, pacman_root)
    ):
        _error("installing the drivers failed")
        return EXIT_FAILED
    for path in gpu.write_files(plan.files, root):
        _print(f"Wrote {path}")
    if plan.services and not _run(gpu.enable_units_command(plan.services, root)):
        _error("enabling services failed")
        return EXIT_FAILED
    return EXIT_OK


def _apply_mode(mode: str, root: Path, live: bool) -> int:
    try:
        change = gpu_mode.apply_mode(mode, gpu.scan_pci(), root)
    except gpu_mode.GpuModeError as error:
        _error(str(error))
        return EXIT_USAGE
    for path in change.written:
        _print(f"Wrote /{path}")
    for path in change.removed:
        _print(f"Removed /{path}")
    if change.services:
        _run(gpu.enable_units_command(change.services, root))
    if change.needs_initramfs:
        # The live system boots an initramfs from the medium; another root is
        # the installer's job.
        if live or root != Path("/"):
            _print("Note: initramfs not rebuilt here")
        elif not _run(["mkinitcpio", "-P"]):
            _error("rebuilding the initramfs failed")
            return EXIT_FAILED
    for note in change.notes:
        _print(f"Note: {note}")
    _print(f"GPU mode: {change.mode}")
    return EXIT_OK


def requested_mode(cmdline: list[str]) -> str | None:
    """GPU mode asked for on the kernel command line of a live boot.

    ``bdm.gpu=hybrid|nvidia|integrated``; the older ``bignvidia=`` of the
    BigLinux live menu is understood too (1-8 integrated primary, 9-16 NVIDIA).
    """
    value = _cmdline_value("bdm.gpu", cmdline) or _cmdline_value("bignvidia", cmdline)
    if value in gpu_mode.MODES:
        return value
    if value and value.isdigit() and 1 <= int(value) <= 16:
        return "nvidia" if int(value) >= 9 else "hybrid"
    return None


def _boot() -> int:
    """Before the display manager: keep hybrid machines in their mode."""
    live = LIVE_MARKER.exists()
    devices = gpu.scan_pci()
    if live:
        # Live media: world-readable render nodes for the NVIDIA proprietary
        # driver (biglinux-livecd workaround, kept as it was).
        for node in Path("/dev/dri").glob("renderD*"):
            try:
                node.chmod(0o666)
            except OSError:
                pass
    if not gpu_mode.is_hybrid(devices):
        return EXIT_OK
    requested = requested_mode(_cmdline_args())
    if requested and live:
        return _apply_mode(requested, Path("/"), live)
    if gpu_mode.read_mode() is None:
        return _apply_mode("hybrid", Path("/"), live)
    return EXIT_OK


def run(args: argparse.Namespace) -> int:
    action = args.gpu_action
    if action == "detect":
        devices = gpu.display_devices(gpu.scan_pci())
        info = {
            "gpus": [{**d.__dict__, "vendor_name": d.vendor_name} for d in devices],
            "hybrid": gpu_mode.is_hybrid(devices),
            "kernels": gpu.installed_kernels(),
            "virtualization": gpu.detect_virtualization(),
        }
        _print(
            json.dumps(info, indent=2)
            if args.json
            else "\n".join(f"{k}: {v}" for k, v in info.items())
        )
        return EXIT_OK
    if action == "status":
        devices = gpu.scan_pci()
        info = {
            "mode": gpu_mode.read_mode(),
            "hybrid": gpu_mode.is_hybrid(devices),
            "nvidia": any(
                d.vendor == gpu.VENDOR_NVIDIA for d in gpu.display_devices(devices)
            ),
        }
        _print(
            json.dumps(info)
            if args.json
            else "\n".join(f"{k}={v}" for k, v in info.items())
        )
        return EXIT_OK

    refusal = _refuse_redirection(args)
    if refusal:
        _error(refusal)
        return EXIT_USAGE
    if action == "plan":
        plan = _build_plan(args)
        if args.json:
            _print(json.dumps(plan.to_dict(), indent=2))
        else:
            _describe_plan(plan)
        return EXIT_OK

    if not is_root():
        _error("must run as root (use pkexec)")
        return EXIT_NOT_ROOT
    if action == "install":
        return _install(args)
    if action == "mode":
        return _apply_mode(args.mode, _target_root(args), LIVE_MARKER.exists())
    if action == "boot":
        return _boot()
    return EXIT_USAGE
