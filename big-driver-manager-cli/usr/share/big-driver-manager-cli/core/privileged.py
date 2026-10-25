"""The privileged boundary between the interface and the system.

Everything that changes the system runs as root through
``big-driver-manager-cli``. The interface never asks polkit for pacman itself:
it asks for one of a few verbs, and the command line accepts nothing else.

One table, ``_PACMAN_FORMS``, describes every pacman invocation the managers
make. ``pacman_to_cli`` turns one into the verb the interface sends through
pkexec, and ``cli_to_pacman`` turns the verb back into pacman arguments on the
root side, after validating it. Keeping both directions on the same table is
what stops them from drifting apart.
"""

import os
import re

CLI_BIN = os.environ.get("BDM_CLI_BIN", "/usr/bin/big-driver-manager-cli")
PKEXEC = "pkexec"
PACMAN = "/usr/bin/pacman"
MHWD = "/usr/bin/mhwd"

# Package names as pacman accepts them. A leading "-" or "." is refused so a
# name can never be read as an option.
_PACKAGE_RE = re.compile(r"^[A-Za-z0-9@_+][A-Za-z0-9@._+-]*$")
_MHWD_CONFIG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
MHWD_BUSES = ("pci", "usb")

# (verb, flags) -> pacman options. The package names follow the options.
_PACMAN_FORMS: dict[tuple[str, tuple[str, ...]], tuple[str, ...]] = {
    ("install", ()): ("-S", "--noconfirm", "--needed"),
    ("install", ("--reinstall",)): ("-S", "--noconfirm"),
    ("remove", ()): ("-R", "--noconfirm"),
    ("remove", ("--recursive",)): ("-Rns", "--noconfirm"),
    # No cascade (-Rc) form: with --noconfirm it removes everything that
    # depends on the packages, the whole desktop for mesa. Mesa variants
    # are switched by ``mesa apply``.
}


class PrivilegedRequestError(ValueError):
    """A request outside what the command line accepts."""


def validate_packages(packages: list[str]) -> list[str]:
    if not packages:
        raise PrivilegedRequestError("no packages given")
    for name in packages:
        if not _PACKAGE_RE.match(name):
            raise PrivilegedRequestError(f"invalid package name: {name!r}")
    return packages


def pacman_to_cli(args: list[str]) -> list[str]:
    """Verb for a pacman invocation the managers make, for pkexec."""
    # Longest first: a shorter form that is a prefix of a longer one must
    # not claim it.
    forms = sorted(_PACMAN_FORMS.items(), key=lambda item: -len(item[1]))
    for (verb, flags), options in forms:
        count = len(options)
        if tuple(args[:count]) == options:
            packages = validate_packages(list(args[count:]))
            return [verb, *flags, "--", *packages]
    raise PrivilegedRequestError(f"unsupported pacman invocation: {args!r}")


def cli_to_pacman(verb: str, flags: list[str], packages: list[str]) -> list[str]:
    """pacman arguments for a verb received on the root side."""
    options = _PACMAN_FORMS.get((verb, tuple(flags)))
    if options is None:
        raise PrivilegedRequestError(f"unsupported request: {verb} {' '.join(flags)}")
    return [*options, *validate_packages(packages)]


def mhwd_args(action: str, bus: str, config: str, force: bool = False) -> list[str]:
    """mhwd arguments for installing or removing one configuration."""
    if action not in ("install", "remove"):
        raise PrivilegedRequestError(f"invalid mhwd action: {action!r}")
    if bus not in MHWD_BUSES:
        raise PrivilegedRequestError(f"invalid bus: {bus!r}")
    if not _MHWD_CONFIG_RE.match(config):
        raise PrivilegedRequestError(f"invalid mhwd configuration: {config!r}")
    if force and action != "install":
        raise PrivilegedRequestError("--force only applies to install")
    args = ["-f"] if force else []
    return [*args, "-i" if action == "install" else "-r", bus, config]


def is_root() -> bool:
    return os.geteuid() == 0


def pacman_command(args: list[str]) -> list[str]:
    """The command to run for a pacman invocation from this process.

    Already root (the command line itself, the installer): pacman directly.
    Otherwise through pkexec and the command line, never pacman itself.
    Both accept the same forms: the request is validated either way.
    """
    verb = pacman_to_cli(args)
    if is_root():
        return [PACMAN, *args]
    return [PKEXEC, CLI_BIN, *verb]


def mhwd_command(action: str, bus: str, config: str, force: bool = False) -> list[str]:
    """The command to install or remove an mhwd configuration."""
    args = mhwd_args(action, bus, config, force)
    if is_root():
        return [MHWD, *args]
    verb = ["mhwd", action, bus, config]
    if force:
        verb.append("--force")
    return [PKEXEC, CLI_BIN, *verb]


def cli_command(args: list[str]) -> list[str]:
    """The command line itself (it validates its arguments): directly when
    already root, through pkexec otherwise."""
    if is_root():
        return [CLI_BIN, *args]
    return [PKEXEC, CLI_BIN, *args]
