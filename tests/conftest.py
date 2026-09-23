"""Safety net: no test may run a privileged or system-changing command.

This project drives pacman/mhwd/pamac through pkexec. A test whose mocks
miss (e.g. written against a different version of the code) would otherwise
run the real command — on 2026-09-23 that replaced a developer's mesa.

Two layers:
- Python: subprocess/os calls whose program is dangerous raise
  ``BlockedCommandError`` instead of running.
- Child processes (shell scripts under test): a directory of stub commands
  is put first on PATH. Stubs refuse dangerous invocations and pass
  harmless read-only queries (``pacman -Q``, ``-Si``…) to the real tool.

Blocked attempts are also appended to ``$BDM_BLOCKED_LOG`` so a test run
can be audited afterwards.
"""

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

import pytest

# Always refused, whatever the arguments
_ALWAYS_BLOCKED = frozenset(
    {
        "pkexec",
        "sudo",
        "doas",
        "su",
        "run0",
        "pamac",
        "pamac-installer",
        "systemd-run",
        "mkinitcpio",
        "grub-mkconfig",
        "update-grub",
        "reboot",
        "shutdown",
        "poweroff",
    }
)


class BlockedCommandError(RuntimeError):
    """Raised when a test tries to run a dangerous command for real."""


def _is_read_only(prog: str, args: list[str]) -> bool:
    """True for invocations that only query the system."""
    if prog == "pacman":
        op = args[0] if args else ""
        # -Q* queries; -S with only query modifiers (-Si, -Ss, -Sl, -Sp, -Sg)
        if op.startswith("-Q") or op in ("-T", "--version", "-V"):
            return True
        return (
            op.startswith("-S")
            and len(op) > 2
            and set(op[2:]) <= set("islpgq")
            and "--noconfirm" not in args
        )
    if prog == "mhwd":
        return bool(args) and all(a.startswith("-l") or a == "--pci" for a in args)
    if prog == "systemctl":
        return bool(args) and args[0] in ("status", "is-active", "is-enabled", "show")
    return True


def _check(cmd) -> None:
    if isinstance(cmd, (str, bytes)):
        text = cmd.decode() if isinstance(cmd, bytes) else cmd
        try:
            argv = shlex.split(text)
        except ValueError:
            argv = text.split()
    else:
        argv = [os.fspath(a) for a in cmd]
    if not argv:
        return
    prog = os.path.basename(argv[0])
    if prog in ("bash", "sh", "env") and len(argv) > 1:
        # "bash -c '...'" / "env X=1 pacman ..." — inspect the inner command
        inner = argv[2] if argv[1] == "-c" and len(argv) > 2 else None
        if inner is not None:
            for word in shlex.split(inner, posix=True) if inner else []:
                if os.path.basename(word) in _ALWAYS_BLOCKED:
                    _refuse(argv)
            return
        rest = [a for a in argv[1:] if "=" not in a or a.startswith("-")]
        if prog == "env" and rest:
            _check(rest)
        return
    if prog in _ALWAYS_BLOCKED or (
        prog in ("pacman", "mhwd", "systemctl") and not _is_read_only(prog, argv[1:])
    ):
        _refuse(argv)


def _refuse(argv) -> None:
    line = " ".join(argv)
    log = os.environ.get("BDM_BLOCKED_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    raise BlockedCommandError(f"test tried to run a system command: {line}")


_STUB = """#!/bin/sh
# Test stub installed by tests/conftest.py — see its docstring.
prog=$(basename "$0")
case "$prog" in
  pacman)
    case "$1" in
      -Q*|-T|-V|--version) exec {real_pacman} "$@" ;;
      -S[islpgq]*)
        case " $* " in *" --noconfirm "*) ;; *) exec {real_pacman} "$@" ;; esac ;;
    esac ;;
  mhwd)
    case "$1" in -l*) exec {real_mhwd} "$@" ;; esac ;;
  systemctl)
    case "$1" in status|is-active|is-enabled|show) exec {real_systemctl} "$@" ;; esac ;;
esac
echo "$prog $*" >> "${{BDM_BLOCKED_LOG:-/dev/null}}"
echo "blocked by tests/conftest.py: $prog $*" >&2
exit 126
"""


def _install_stubs(directory: Path) -> None:
    def real(name: str) -> str:
        for base in ("/usr/bin", "/usr/sbin", "/bin"):
            candidate = Path(base) / name
            if candidate.exists():
                return str(candidate)
        return "/bin/false"

    script = _STUB.format(
        real_pacman=real("pacman"),
        real_mhwd=real("mhwd"),
        real_systemctl=real("systemctl"),
    )
    for name in _ALWAYS_BLOCKED | {"pacman", "mhwd", "systemctl"}:
        stub = directory / name
        stub.write_text(script)
        stub.chmod(0o755)


@pytest.fixture(scope="session", autouse=True)
def _block_system_commands():
    """Install both safety layers for the whole test session."""
    stub_dir = Path(tempfile.mkdtemp(prefix="bdm-test-stubs-"))
    _install_stubs(stub_dir)
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{stub_dir}{os.pathsep}{old_path}"
    os.environ.setdefault("BDM_BLOCKED_LOG", str(stub_dir / "blocked.log"))
    # Caches written by the code under test (e.g. the LTS list) must not
    # land in the developer's real ~/.cache
    old_cache = os.environ.get("XDG_CACHE_HOME")
    os.environ["XDG_CACHE_HOME"] = str(stub_dir / "cache")

    originals = {
        "Popen_init": subprocess.Popen.__init__,
        "system": os.system,
    }

    def guarded_popen_init(self, args, *a, **kw):
        _check(args)
        return originals["Popen_init"](self, args, *a, **kw)

    def guarded_system(command):
        _check(command)
        return originals["system"](command)

    # subprocess.run/call/check_output all go through Popen.__init__
    subprocess.Popen.__init__ = guarded_popen_init
    os.system = guarded_system
    try:
        yield
    finally:
        subprocess.Popen.__init__ = originals["Popen_init"]
        os.system = originals["system"]
        os.environ["PATH"] = old_path
        if old_cache is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = old_cache
