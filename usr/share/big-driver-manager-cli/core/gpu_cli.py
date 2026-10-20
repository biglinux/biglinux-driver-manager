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
import fcntl
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

from core import gpu, gpu_fallback, gpu_mode, kernel_cli, term
from core.i18n import _
from core.privileged import is_root

LIVE_MARKER = Path("/livefs-pkgs.txt")
OFFLINE_PACMAN_CONFIG = Path("/opt/mhwd/pacman-mhwd.conf")
KERNEL_CMDLINE = Path("/proc/cmdline")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_NOT_ROOT = 77


def add_parser(verbs: argparse._SubParsersAction) -> None:
    parser = verbs.add_parser("gpu", help=_("graphics drivers (replaces mhwd)"))
    actions = parser.add_subparsers(dest="gpu_action", metavar=_("ACTION"))

    def target_options(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--root", type=Path, help=_("target system (installer)"))
        sub.add_argument(
            "--pmconfig",
            type=Path,
            help=_("pacman configuration, e.g. the live medium's offline repository"),
        )

    def driver_options(sub: argparse.ArgumentParser) -> None:
        group = sub.add_mutually_exclusive_group()
        group.add_argument(
            "--free", action="store_true", help=_("open source drivers only")
        )
        group.add_argument(
            "--from-cmdline",
            action="store_true",
            help=_("driver=free|nonfree from the kernel command line (live media)"),
        )

    detect = actions.add_parser("detect", help=_("show the hardware"))
    detect.add_argument("--json", action="store_true", help=_("JSON output"))

    plan = actions.add_parser("plan", help=_("show what install would do"))
    driver_options(plan)
    target_options(plan)
    plan.add_argument("--json", action="store_true", help=_("JSON output"))

    install = actions.add_parser(
        "install", help=_("install the drivers this machine needs")
    )
    driver_options(install)
    target_options(install)
    for sub in (plan, install):
        sub.add_argument(
            "--nvidia-branch",
            choices=list(gpu.BRANCHES),
            help=_("instead of the recommended NVIDIA driver (must drive the GPU)"),
        )

    actions.add_parser("remove", help=_("remove the NVIDIA proprietary driver"))

    mode = actions.add_parser(
        "mode", help=_("choose which GPU drives a hybrid machine")
    )
    mode.add_argument("mode", choices=gpu_mode.MODES)
    mode.add_argument("--root", type=Path, help=_("target system (installer)"))

    status = actions.add_parser("status", help=_("recorded GPU mode and hardware"))
    status.add_argument("--json", action="store_true", help=_("JSON output"))

    actions.add_parser("boot", help=_("run by big-driver-manager-gpu.service"))
    actions.add_parser(
        "check", help=_("warn about kernels without their NVIDIA module (pacman hook)")
    )
    actions.add_parser(
        "display-check",
        help=_("fall back to nouveau when no login screen appears (service)"),
    )
    actions.add_parser(
        "display-failed",
        help=_("fall back to nouveau after the display manager failed (OnFailure)"),
    )


# --------------------------------------------------------------------------


def _print(text: str) -> None:
    print(text, flush=True)


def _error(text: str) -> None:
    print(term.fail(text), file=sys.stderr, flush=True)


def _note(text: str) -> None:
    _print(term.warn(text))


def _done(text: str) -> None:
    _print(term.ok(text))


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
_ROOT_HOOK_DIRS = ("usr/share/libalpm/hooks", "etc/pacman.d/hooks")


def _untrusted_ancestor(path: Path) -> str | None:
    """A directory above ``path`` someone else could swap it out of: owned by
    another user, or writable by others without the sticky bit (/tmp, where
    the installer mounts its target, has it)."""
    for parent in Path(os.path.abspath(path)).parents:
        try:
            info = os.lstat(parent)
        except OSError as error:
            return f"{parent}: {error.strerror}"
        if info.st_uid != 0:
            return f"{parent} is not owned by root"
        if info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX:
            return f"{parent} is writable by group or others"
    return None


def _refuse_redirection(args: argparse.Namespace) -> str | None:
    """--root and --pmconfig let pacman install, as root, from a configuration
    and into a tree chosen by the caller. They are honoured only when both are
    root's alone -- the installer's target, the live medium's /opt/mhwd --
    whoever asks (pkexec reaches here too, and so does the installer, which
    the live session starts through pkexec)."""
    root = getattr(args, "root", None)
    if root:
        reason = _untrusted_ancestor(root)
        for relative in _ROOT_SKELETON:
            reason = reason or _untrusted(root / relative)
        for relative in _ROOT_HOOK_DIRS:
            if not reason and os.path.lexists(root / relative):
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


def _pacman_root(args: argparse.Namespace) -> Path | None:
    root = _target_root(args)
    return root if root != Path("/") else None


def _build_plan(
    args: argparse.Namespace,
    installed: set[str] | None = None,
    kernels: list[str] | None = None,
) -> gpu.GpuPlan:
    """Raises ValueError when --nvidia-branch does not drive the GPU."""
    pacman_root = _pacman_root(args)
    return gpu.build_plan(
        gpu.scan_pci(),
        kernels if kernels is not None else gpu.installed_kernels(_target_root(args)),
        gpu.repo_packages(args.pmconfig, pacman_root),
        nonfree=_nonfree(args),
        virtualization=gpu.detect_virtualization(),
        chips=gpu.load_supported_gpus(),
        installed=installed
        if installed is not None
        else gpu.installed_packages(pacman_root),
        nvidia_branch=getattr(args, "nvidia_branch", None),
    )


def installed_nvidia_packages(installed: set[str], kernels: list[str]) -> list[str]:
    """Every installed package of any NVIDIA branch."""
    names: set[str] = set()
    for branch in gpu.BRANCHES.values():
        names.update(gpu.branch_packages(branch, installed, kernels))
    return sorted(names)


def packages_to_replace(
    plan: gpu.GpuPlan, installed: set[str], kernels: list[str]
) -> list[str]:
    """NVIDIA packages installed now that the plan does not keep: another
    branch, or the other module flavour (open/proprietary) of the same one.
    They conflict with the plan's packages, and pacman --noconfirm answers
    no to removing a conflicting package, so they go first."""
    if not (plan.nvidia and plan.nvidia.branch):
        return []
    # What the plan wants, installed already or not (a lib32 package whose
    # multilib repository is gone is wanted, not something to remove).
    keep = set(plan.install) | set(plan.wanted)
    return [p for p in installed_nvidia_packages(installed, kernels) if p not in keep]


def essential_missing(plan: gpu.GpuPlan) -> list[str]:
    """NVIDIA packages the repositories lack and the driver cannot work
    without: its userspace, and a module (or DKMS and headers) per kernel."""
    if not (plan.nvidia and plan.nvidia.branch):
        return []
    branch = gpu.BRANCHES[plan.nvidia.branch]
    essential = {branch.utils[0], branch.dkms, branch.open_dkms}
    return [
        name
        for name in plan.unavailable
        if name in essential
        or any(name.startswith(kernel + "-") for kernel in plan.kernels)
    ]


_VENDOR_COLORS = {"nvidia": "green", "intel": "blue", "amd": "red"}


def device_name(slot: str) -> str:
    """The card's marketing name from lspci, or "" when lspci cannot tell."""
    try:
        output = subprocess.run(
            ["lspci", "-mm", "-s", slot],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""
    fields = output.split('"')
    # Slot "Class" "Vendor" "Device" ...: the quoted fields are 1, 3, 5
    return fields[5].strip() if len(fields) > 5 else ""


def _yes_no(value: bool) -> str:
    return term.style(_("yes"), "bold", "green") if value else term.dim(_("no"))


def _gpu_rows(gpus: list[dict]) -> list[list[str]]:
    rows = []
    for item in gpus:
        vendor = item["vendor_name"]
        name = device_name(item["slot"]) or f"[{item['vendor']}:{item['device']}]"
        driver = item["driver"]
        tags = []
        if item["boot_vga"]:
            tags.append(term.style(_("boot display"), "cyan"))
        rows.append(
            [
                term.dim(item["slot"]),
                term.style(
                    vendor.upper(), "bold", _VENDOR_COLORS.get(vendor, "magenta")
                ),
                name,
                term.style(driver, "bold", "green")
                if driver
                else term.style(_("no driver"), "bold", "red"),
                " ".join(tags),
            ]
        )
    return rows


def _describe_plan(plan: gpu.GpuPlan) -> None:
    _print(term.heading(_("Graphics")))
    _print(
        term.table(_gpu_rows(plan.gpus)) or "  " + term.dim(_("no display controller"))
    )
    _print("")
    _print(term.label(_("Kernels"), ", ".join(plan.kernels) or _("none")))
    if plan.virtualization:
        _print(term.label(_("Virtual machine"), plan.virtualization))
    if plan.nvidia and plan.nvidia.branch:
        flavor = (
            _("open kernel module")
            if plan.nvidia.open_module
            else _("proprietary kernel module")
        )
        _print(
            term.label(
                _("NVIDIA driver"),
                f"{term.style(plan.nvidia.branch, 'bold', 'green')} ({flavor})",
            )
        )
    _print(term.label(_("Hybrid"), _yes_no(plan.hybrid)))
    install = " ".join(term.bold(p) for p in plan.install)
    _print(term.label(_("Install"), install or term.dim(_("nothing"))))
    if plan.unavailable:
        _print(
            term.label(
                _("Not in the repositories"),
                term.style(" ".join(plan.unavailable), "yellow"),
            )
        )
    for note in plan.notes:
        _note(note)


def _run(cmd: list[str]) -> bool:
    _print(term.dim("$ " + " ".join(cmd)))
    try:
        return subprocess.run(cmd, env=_env()).returncode == 0
    except OSError as error:
        _error(str(error))
        return False


def _pacman_remove(
    packages: list[str], mode: str, args: argparse.Namespace
) -> list[str]:
    cmd = ["pacman", mode, "--noconfirm"]
    if getattr(args, "pmconfig", None):
        cmd += ["--config", str(args.pmconfig)]
    if _pacman_root(args):
        cmd += ["--root", str(_pacman_root(args))]
    return cmd + packages


def _sync_offline_repository(args: argparse.Namespace) -> bool:
    """The offline repository ships only mhwd.db.tar.gz next to its packages:
    pacman must sync it before it can list or install from it. The
    configuration names no other repository, so nothing else is refreshed."""
    if not getattr(args, "pmconfig", None):
        return True
    cmd = ["pacman", "-Sy", "--noconfirm", "--config", str(args.pmconfig)]
    if _pacman_root(args):
        cmd += ["--root", str(_pacman_root(args))]
    return _run(cmd)


def _integrated_mode(root: Path) -> bool:
    """NVIDIA is meant to stay off: recorded, or asked for on a live boot."""
    if gpu_mode.read_mode(root) == "integrated":
        return True
    return LIVE_MARKER.exists() and requested_mode(_cmdline_args()) == "integrated"


def _fall_back_if_driverless(reason: str) -> None:
    """After a failed install on the running system: only a card left with no
    driver at all needs nouveau; a working NVIDIA driver is left alone."""
    if gpu_fallback.driverless_nvidia(gpu.scan_pci()):
        _fall_back(reason)


def _install(args: argparse.Namespace) -> int:
    root = _target_root(args)
    pacman_root = _pacman_root(args)
    running = pacman_root is None
    if not _sync_offline_repository(args):
        _error(_("Reading the offline repository failed."))
        if running:
            _fall_back_if_driverless("the offline driver repository could not be read")
        return EXIT_FAILED
    installed = gpu.installed_packages(pacman_root)
    kernels = gpu.installed_kernels(root)
    try:
        plan = _build_plan(args, installed, kernels)
    except ValueError as error:
        _error(str(error))
        return EXIT_USAGE
    _describe_plan(plan)
    nvidia = bool(plan.nvidia and plan.nvidia.branch)

    # Nothing is touched when the driver cannot be complete: a userspace
    # without a module (or the reverse) is a black screen, not a driver.
    missing = essential_missing(plan)
    if missing:
        _error(
            _("NVIDIA driver packages missing from the repositories: {}").format(
                " ".join(missing)
            )
        )
        if running:
            _fall_back_if_driverless("the NVIDIA driver is not in the repositories")
        return EXIT_FAILED

    # Download first: the old branch only goes once the new one is at hand.
    if plan.install:
        download = gpu.pacman_install_command(plan.install, args.pmconfig, pacman_root)
        download[1] = "-Sw"
        if not _run(download):
            _error(_("Downloading the drivers failed."))
            if running and nvidia:
                _fall_back_if_driverless("the NVIDIA driver could not be downloaded")
            return EXIT_FAILED

    replaced = packages_to_replace(plan, installed, kernels)
    if replaced:
        _print(term.step(_("Replacing: {}").format(" ".join(replaced))))
        # -dd: the new branch provides nvidia-utils again right after.
        if not _run(_pacman_remove(replaced, "-Rdd", args)):
            _error(_("Removing the installed NVIDIA driver failed."))
            return EXIT_FAILED

    if plan.install and not _run(
        gpu.pacman_install_command(plan.install, args.pmconfig, pacman_root)
    ):
        _error(_("Installing the drivers failed."))
        if replaced:
            _print(
                term.step(
                    _("Restoring the previous NVIDIA driver from the package cache")
                )
            )
            _run(gpu.pacman_install_command(replaced, args.pmconfig, pacman_root))
        elif running and nvidia:
            _fall_back_if_driverless("the NVIDIA driver could not be installed")
        return EXIT_FAILED

    for path in gpu.write_files(plan.files, root):
        _print(term.info(_("Wrote {}").format(path)))
    if nvidia:
        _clear_persisted_fallback(root)

    # The running system (live session, GUI): load the new driver now, as
    # mhwd did, and make sure it took the card before anything else; another
    # root boots it later. A module that does not load now is not fatal: the
    # next boot loads it.
    if running and not _integrated_mode(root):
        for cmd in plan.load:
            # Unloading a module that is not loaded "fails" too: not news.
            if not _run(cmd) and "-r" not in cmd:
                _note(_("{} failed; it loads on the next boot").format(" ".join(cmd)))
        if nvidia:
            _verify_nvidia()

    # One unit at a time, and never fatal: a service missing from the
    # repositories must not cost the rest of the setup.
    for unit in plan.services:
        if not _run(gpu.enable_units_command([unit], root)):
            _note(_("{} could not be enabled").format(unit))
    _done(_("Graphics drivers ready."))
    return EXIT_OK


def _settle() -> None:
    try:
        subprocess.run(["udevadm", "settle", "--timeout=15"], timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _fall_back(reason: str) -> bool:
    """Give the NVIDIA card to nouveau (Mesa) instead of a black screen."""
    cmdline = _cmdline_args()
    if gpu_fallback.nouveau_forbidden(cmdline):
        _error(
            _(
                "{}, and module_blacklist= on the kernel command line forbids "
                "nouveau: no driver for the NVIDIA GPU this boot"
            ).format(reason)
        )
        return False
    _error(
        _("{}: falling back to nouveau, the open source NVIDIA driver").format(reason)
    )
    for cmd in gpu_fallback.fallback_commands(cmdline):
        _run(cmd)
    _settle()
    try:
        gpu_fallback.record(reason)
    except OSError:
        pass
    return True


def _verify_nvidia() -> bool:
    """True when every NVIDIA card has a driver; otherwise fall back."""
    _settle()
    broken = gpu_fallback.driverless_nvidia(gpu.scan_pci())
    if not broken:
        return True
    slots = ", ".join(d.slot for d in broken)
    _fall_back(f"the NVIDIA driver did not take the GPU ({slots})")
    return False


def _apply_mode(mode: str, root: Path, live: bool) -> int:
    try:
        change = gpu_mode.apply_mode(mode, gpu.scan_pci(), root)
    except gpu_mode.GpuModeError as error:
        _error(str(error))
        return EXIT_USAGE
    for path in change.written:
        _print(term.info(_("Wrote {}").format(f"/{path}")))
    for path in change.removed:
        _print(term.info(_("Removed {}").format(f"/{path}")))
    if change.services:
        _run(gpu.enable_units_command(change.services, root))
    if mode == "integrated" and root == Path("/"):
        # Already loaded this boot (the live session installs and loads the
        # driver first): unload now, the blacklist takes over from here.
        _run(["modprobe", "-r", *gpu_fallback.NVIDIA_MODULES])
    if change.needs_initramfs:
        # The live system boots an initramfs from the medium; another root is
        # the installer's job.
        if live or root != Path("/"):
            _note(_("The initramfs is not rebuilt here"))
        elif not _run(["mkinitcpio", "-P"]):
            _error(_("Rebuilding the initramfs failed."))
            return EXIT_FAILED
    for note in change.notes:
        _note(note)
    _done(_("GPU mode: {}").format(term.bold(change.mode)))
    return EXIT_OK


def _remove(args: argparse.Namespace) -> int:
    installed = gpu.installed_packages()
    packages = installed_nvidia_packages(installed, gpu.installed_kernels())
    if not packages:
        _print(term.info(_("The NVIDIA proprietary driver is not installed")))
        return EXIT_OK
    if "nvidia-prime" in installed:
        packages.append("nvidia-prime")  # depends on nvidia-utils
    if not _run(_pacman_remove(packages, "-Rns", args)):
        _error(_("Removing the NVIDIA driver failed."))
        return EXIT_FAILED
    files = [gpu.NVIDIA_MODULES_LOAD, gpu.NVIDIA_POWER_MODPROBE, gpu.NVIDIA_POWER_UDEV]
    for relative in files:
        target = Path("/") / relative
        if target.is_file():
            target.unlink()
            _print(term.info(_("Removed {}").format(target)))
    change = gpu_mode.clear_mode()
    for relative in change.removed:
        _print(term.info(_("Removed {}").format(f"/{relative}")))
    cleared = gpu_fallback.clear_persisted(Path("/"))
    for relative in cleared:
        _print(term.info(_("Removed {}").format(f"/{relative}")))
    if (change.needs_initramfs or cleared) and not LIVE_MARKER.exists():
        _run(["mkinitcpio", "-P"])
    _done(_("NVIDIA proprietary driver removed."))
    return EXIT_OK


def _clear_persisted_fallback(root: Path) -> None:
    """The NVIDIA driver was installed again: let it try at the next boot."""
    cleared = gpu_fallback.clear_persisted(root)
    for relative in cleared:
        _print(term.info(_("Removed {} (nouveau fallback)").format(root / relative)))
    if cleared and root == Path("/") and not LIVE_MARKER.exists():
        _run(["mkinitcpio", "-P"])


DISPLAY_TIMEOUT = 120  # seconds for a login screen or session to appear
DISPLAY_POLL = 5


def _logind_sessions() -> list[dict[str, str]]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["loginctl", *args], capture_output=True, text=True, timeout=10
            ).stdout
        except (OSError, subprocess.TimeoutExpired):
            return ""

    sessions = []
    for line in run("list-sessions", "--no-legend").splitlines():
        if not line.split():
            continue
        properties = run(
            "show-session",
            line.split()[0],
            "-p",
            "Type",
            "-p",
            "Class",
            "-p",
            "State",
            "-p",
            "Remote",
        )
        sessions.append(
            dict(item.split("=", 1) for item in properties.splitlines() if "=" in item)
        )
    return sessions


def _display_check() -> int:
    """After the display manager starts: when the proprietary driver drives an
    NVIDIA card and no login screen nor session shows up, treat it as the
    black screen it is."""
    if not gpu_fallback.nvidia_in_use(gpu.scan_pci()):
        return EXIT_OK
    deadline = time.monotonic() + DISPLAY_TIMEOUT
    while time.monotonic() < deadline:
        if gpu_fallback.graphical_session(_logind_sessions()):
            return EXIT_OK
        time.sleep(DISPLAY_POLL)
    return _display_failed(
        f"no login screen or session appeared within {DISPLAY_TIMEOUT} s"
    )


def _restart_display_manager() -> None:
    _run(["systemctl", "reset-failed", "display-manager.service"])
    _run(["systemctl", "restart", "--no-block", "display-manager.service"])


# A display manager failing later than this is not a boot that never showed
# a screen: the session was up, leave the driver alone.
DISPLAY_FAILURE_WINDOW = 600  # seconds of uptime
LOCK = Path("/run/big-driver-manager/display.lock")


def _uptime() -> float:
    try:
        return float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return 0.0


def _display_failed(cause: str = "the display manager failed") -> int:
    """The display did not come up while the proprietary driver drove the GPU:
    move to nouveau, once per boot. On an installed system the next boots
    use nouveau too, until the NVIDIA driver is installed again; when the
    NVIDIA modules cannot be unloaded now (the console holds nvidia_drm's
    framebuffer), that takes one restart -- never a second one."""
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    # display-check and display-failed may both fire: one at a time.
    with LOCK.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _display_failed_locked(cause)


def _display_failed_locked(cause: str) -> int:
    if gpu_fallback.recorded():
        return EXIT_OK  # already fell back this boot: never loop
    if _uptime() > DISPLAY_FAILURE_WINDOW:
        _note(
            _(
                "The display manager failed long after boot, not while the driver started"
            )
        )
        return EXIT_OK
    if not gpu_fallback.nvidia_in_use(gpu.scan_pci()):
        return EXIT_OK  # not the NVIDIA driver's doing
    live = LIVE_MARKER.exists()
    persisted_before = gpu_fallback.persisted_reason(Path("/"))
    reason = f"{cause} with the NVIDIA driver"
    if not _fall_back(reason):
        return EXIT_FAILED
    switched = not gpu_fallback.nvidia_in_use(gpu.scan_pci())
    if not live:
        for relative in gpu_fallback.persist(Path("/"), reason):
            _print(term.info(_("Wrote {}").format(f"/{relative}")))
    if switched:
        _restart_display_manager()
        if not live and not _run(["mkinitcpio", "-P"]):
            _error(
                _(
                    "Rebuilding the initramfs failed; the next boot may load NVIDIA again."
                )
            )
        return EXIT_OK
    if live:
        _error(
            _(
                "The NVIDIA modules could not be unloaded; restart and choose "
                "the boot entry without proprietary drivers."
            )
        )
        return EXIT_FAILED
    if persisted_before:
        # This boot already ran under the fallback and NVIDIA still came up
        # (its modules in the initramfs, a stale image): restarting again
        # would loop.
        _error(
            _(
                "NVIDIA still loads although the fallback blocks it; not restarting "
                "again. Rebuild the initramfs (mkinitcpio -P) or remove the NVIDIA "
                "driver from a text console."
            )
        )
        return EXIT_FAILED
    if not _run(["mkinitcpio", "-P"]):
        _error(
            _("Rebuilding the initramfs failed; not restarting into the same state.")
        )
        return EXIT_FAILED
    _print(term.step(_("Restarting once to start with nouveau")))
    _run(["systemctl", "reboot"])
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
    # The proprietary driver is installed and allowed: it must have taken the
    # card by now (modules-load.d, udev), or the display manager would start
    # on a card nobody drives.
    integrated = gpu_mode.read_mode() == "integrated"
    if gpu.installed_branch(gpu.installed_packages()) and not integrated:
        if gpu_fallback.driverless_nvidia(devices):
            _verify_nvidia()
            devices = gpu.scan_pci()
    if not gpu_mode.is_hybrid(devices):
        return EXIT_OK
    requested = requested_mode(_cmdline_args())
    if requested and live:
        return _apply_mode(requested, Path("/"), live)
    if gpu_mode.read_mode() is None:
        return _apply_mode("hybrid", Path("/"), live)
    return EXIT_OK


_NVIDIA_UTILS = ("nvidia-utils", "nvidia-580xx-utils", "nvidia-470xx-utils")


def kernel_packages_missing(plan: gpu.GpuPlan, installed: set[str]) -> list[str]:
    """Driver packages a kernel of the plan still lacks (module, DKMS, headers)."""
    return [
        name
        for name in plan.install
        if name not in installed
        and (
            name.endswith("-dkms")
            or any(name.startswith(kernel + "-") for kernel in plan.kernels)
        )
    ]


def _check() -> int:
    """After a kernel is installed: pacman cannot install from inside its own
    transaction, so say which package the new kernel still needs. Silent on
    machines without the NVIDIA proprietary driver. Never fails."""
    installed = gpu.installed_packages()
    if not any(name in installed for name in _NVIDIA_UTILS):
        return EXIT_OK
    plan = gpu.build_plan(
        gpu.scan_pci(),
        gpu.installed_kernels(),
        gpu.repo_packages(),
        chips=gpu.load_supported_gpus(),
        installed=installed,
    )
    missing = kernel_packages_missing(plan, installed)
    if missing:
        _note(
            _(
                "A kernel has no NVIDIA driver module yet; it would start "
                "without the NVIDIA driver."
            )
        )
        _print(
            "  "
            + _("Install it with: {}").format(
                term.style("big-drivers gpu install", "cyan")
            )
        )
        _print("  " + term.dim("(" + " ".join(missing) + ")"))
    return EXIT_OK


def N_(text: str) -> str:  # noqa: N802 - marks a string for xgettext only
    return text


_MODE_TEXT = {
    "hybrid": N_("the integrated GPU draws the screen, NVIDIA on demand (prime-run)"),
    "nvidia": N_("NVIDIA draws the screen (Xorg sessions)"),
    "integrated": N_("NVIDIA turned off"),
}


def _detect_info() -> dict:
    devices = gpu.display_devices(gpu.scan_pci())
    return {
        "gpus": [{**d.__dict__, "vendor_name": d.vendor_name} for d in devices],
        "hybrid": gpu_mode.is_hybrid(devices),
        "kernels": gpu.installed_kernels(),
        "virtualization": gpu.detect_virtualization(),
    }


def _show_detect(info: dict) -> None:
    _print(term.heading(_("Graphics")))
    _print(
        term.table(_gpu_rows(info["gpus"]))
        or "  " + term.dim(_("no display controller"))
    )
    _print("")
    _print(term.label(_("Hybrid"), _yes_no(info["hybrid"])))
    _print(term.label(_("Kernels"), ", ".join(info["kernels"]) or _("none")))
    if info["virtualization"]:
        _print(term.label(_("Virtual machine"), info["virtualization"]))


def _status_info() -> dict:
    devices = gpu.scan_pci()
    return {
        "mode": gpu_mode.read_mode(),
        "nvidia_fallback": gpu_fallback.recorded(),
        "nvidia_fallback_persisted": gpu_fallback.persisted_reason(Path("/")),
        "hybrid": gpu_mode.is_hybrid(devices),
        "nvidia": any(
            d.vendor == gpu.VENDOR_NVIDIA for d in gpu.display_devices(devices)
        ),
        "nvidia_driver": gpu.installed_branch(gpu.installed_packages()),
    }


def _show_status(info: dict) -> None:
    _print(term.heading(_("GPU status")))
    mode = info["mode"]
    if mode in _MODE_TEXT:
        shown = term.style(mode, "bold", "cyan") + term.dim(" - " + _(_MODE_TEXT[mode]))
    else:
        shown = term.dim(_("not set"))
    _print(term.label(_("Mode"), shown))
    _print(term.label(_("Hybrid"), _yes_no(info["hybrid"])))
    _print(term.label(_("NVIDIA GPU"), _yes_no(info["nvidia"])))
    branch = info["nvidia_driver"]
    _print(
        term.label(
            _("NVIDIA driver"),
            term.style(branch, "bold", "green")
            if branch
            else term.dim(_("not installed")),
        )
    )
    for reason in (info["nvidia_fallback"], info["nvidia_fallback_persisted"]):
        if reason:
            _note(_("Using nouveau instead of the NVIDIA driver: {}").format(reason))
            break


def run(args: argparse.Namespace) -> int:
    action = args.gpu_action or "detect"
    if action == "detect":
        info = _detect_info()
        if getattr(args, "json", False):
            _print(json.dumps(info, indent=2))
        else:
            _show_detect(info)
        return EXIT_OK
    if action == "status":
        info = _status_info()
        if args.json:
            _print(json.dumps(info))
        else:
            _show_status(info)
        return EXIT_OK

    if action == "check":
        return _check()
    if action in ("display-check", "display-failed") and not is_root():
        _error(_("This needs administrator rights."))
        return EXIT_NOT_ROOT
    if action == "display-check":
        return _display_check()
    if action == "display-failed":
        return _display_failed()

    refusal = _refuse_redirection(args)
    if refusal:
        _error(refusal)
        return EXIT_USAGE
    if action == "plan":
        try:
            plan = _build_plan(args)
        except ValueError as error:
            _error(str(error))
            return EXIT_USAGE
        if args.json:
            _print(json.dumps(plan.to_dict(), indent=2))
        else:
            _describe_plan(plan)
        return EXIT_OK

    if not is_root():
        if action == "boot":
            _error(_("This needs administrator rights."))
            return EXIT_NOT_ROOT
        return kernel_cli.elevate(getattr(args, "argv", None) or ["gpu", action])
    if action == "install":
        return _install(args)
    if action == "remove":
        return _remove(args)
    if action == "mode":
        return _apply_mode(args.mode, _target_root(args), LIVE_MARKER.exists())
    if action == "boot":
        return _boot()
    return EXIT_USAGE
