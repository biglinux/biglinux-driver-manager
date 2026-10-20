"""``big-drivers kernel ...``: kernels together with the modules they need.

list      kernels in the repositories, the installed ones marked
install   a kernel, its headers and the modules the running kernel uses
          (NVIDIA, Broadcom Wi-Fi, VirtualBox...), as the interface does
remove    a kernel and its modules, never the running one
obsolete  installed kernels that left the repositories

mhwd-kernel's options keep working: -l, -li, -i NAME, -r NAME.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys

from core import gpu, term
from core.i18n import _
from core.kernel_manager import KernelInfo, KernelManager
from core.privileged import (
    CLI_BIN,
    PACMAN,
    PKEXEC,
    PrivilegedRequestError,
    is_root,
    validate_packages,
)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_NOT_ROOT = 77

_NOT_FROM_REPOSITORIES = ("local", "manual")


def add_parser(verbs: argparse._SubParsersAction) -> None:
    parser = verbs.add_parser(
        "kernel",
        help=_("list, install and remove kernels with their modules"),
        description=_(
            "Install and remove kernels together with the modules the running "
            "kernel uses (NVIDIA, Broadcom Wi-Fi, VirtualBox...)."
        ),
    )
    actions = parser.add_subparsers(dest="kernel_action", metavar=_("ACTION"))

    listing = actions.add_parser(
        "list", help=_("kernels in the repositories, the installed ones marked")
    )
    listing.add_argument(
        "--installed", action="store_true", help=_("only the installed kernels")
    )
    listing.add_argument("--json", action="store_true", help=_("JSON output"))

    install = actions.add_parser(
        "install", help=_("install a kernel with its headers and modules")
    )
    remove = actions.add_parser("remove", help=_("remove a kernel and its modules"))
    for sub in (install, remove):
        sub.add_argument("name", metavar=_("KERNEL"))
        sub.add_argument(
            "-y", "--yes", action="store_true", help=_("do not ask for confirmation")
        )
        # The request was already shown and confirmed before pkexec.
        sub.add_argument("--confirmed", action="store_true", help=argparse.SUPPRESS)

    obsolete = actions.add_parser(
        "obsolete", help=_("installed kernels that left the repositories")
    )
    obsolete.add_argument("--json", action="store_true", help=_("JSON output"))


def from_mhwd_kernel(argv: list[str]) -> list[str]:
    """mhwd-kernel's options, for habit and old scripts."""
    if not argv:
        return argv
    first, rest = argv[0], argv[1:]
    if first in ("-l", "--list"):
        return ["kernel", "list", *rest]
    if first in ("-li", "--listinstalled"):
        return ["kernel", "list", "--installed", *rest]
    if first in ("-i", "--install"):
        if "rmc" in rest:
            print(
                term.warn(_("'rmc' is ignored: the running kernel is never removed.")),
                file=sys.stderr,
            )
        return ["kernel", "install", *(a for a in rest if a != "rmc")]
    if first in ("-r", "--remove"):
        return ["kernel", "remove", *rest]
    return argv


# --------------------------------------------------------------------------


def _error(text: str) -> None:
    print(term.fail(text), file=sys.stderr, flush=True)


def elevate(argv: list[str]) -> int:
    """Run the same request as root through pkexec: polkit asks for the
    password in the terminal. Without a terminal there is nobody to ask."""
    if not sys.stdin.isatty():
        _error(_("This needs administrator rights: run it with sudo or pkexec."))
        return EXIT_NOT_ROOT
    color = "always" if term.enabled() else "never"
    print(term.step(_("Administrator rights are needed; asking for the password...")))
    sys.stdout.flush()
    try:
        os.execvp(PKEXEC, [PKEXEC, CLI_BIN, f"--color={color}", *argv])
    except OSError as error:
        _error(str(error))
    return EXIT_NOT_ROOT


def _confirm(question: str, default: bool, args: argparse.Namespace) -> bool:
    if args.yes or args.confirmed:
        return True
    if not sys.stdin.isatty():
        _error(_("There is no terminal to confirm in: add --yes."))
        return False
    choices = _("[Y/n]") if default else _("[y/N]")
    prompt = f"{term.style('?', 'bold', 'magenta')} {term.bold(question)} {choices} "
    try:
        answer = input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    # Translators: the answer meaning "yes" at a [Y/n] prompt; only its first
    # letter is compared. English "y" is always accepted too.
    return answer[0] in {"y", _("y")[:1].lower()}


def _pacman(arguments: list[str]) -> int:
    """pacman with its output on the terminal, in the user's language
    there; plain English for logs and pipes."""
    cmd = [PACMAN, *arguments]
    if not term.enabled():
        cmd[1:1] = ["--color", "never"]
    env = dict(os.environ)
    if not sys.stdout.isatty():
        env = {k: v for k, v in env.items() if not k.startswith("LC_")}
        env.update(LANG="C", LC_ALL="C")
    print(term.dim("$ " + " ".join(cmd)), flush=True)
    try:
        return subprocess.run(cmd, env=env).returncode
    except OSError as error:
        _error(str(error))
        return EXIT_FAILED


# --------------------------------------------------------------------------
# list / obsolete
# --------------------------------------------------------------------------


def kernel_tags(kernel: KernelInfo, running: str) -> list[str]:
    tags = []
    if kernel["name"] == running:
        tags.append(term.style(_("running"), "bold", "green"))
    if kernel.get("big"):
        tags.append(term.style("Big", "bold", "magenta"))
    if kernel.get("lts"):
        tags.append(term.style("LTS", "cyan"))
    if kernel.get("rt"):
        tags.append(term.style(_("real-time"), "yellow"))
    if kernel.get("xanmod"):
        tags.append(term.style("XanMod", "blue"))
    if kernel.get("cachyos"):
        tags.append(term.style("CachyOS", "blue"))
    if kernel.get("opt_level"):
        tags.append(term.style(f"x86-64-v{kernel['opt_level']}", "blue"))
    if kernel.get("obsolete"):
        tags.append(term.style(_("left the repositories"), "bold", "red"))
    if kernel.get("source") == "local":
        tags.append(term.style(_("not from the repositories"), "yellow"))
    elif kernel.get("source") == "manual":
        tags.append(term.style(_("installed without a package"), "yellow"))
    return tags


def _version(kernel: KernelInfo) -> str:
    """The installed version, and the repository's when it is newer."""
    installed = kernel.get("installed_version")
    available = kernel.get("version", "")
    if installed and available and installed != available:
        return f"{installed} {term.style('→ ' + available, 'yellow')}"
    return installed or available


def kernel_rows(kernels: list[KernelInfo], running: str) -> list[list[str]]:
    with_repository = any(k.get("repository") for k in kernels)
    header = [_("Kernel"), _("Version")] + (
        [_("Repository")] if with_repository else []
    )
    rows = [["", *(term.style(h, "bold", "underline") for h in header), ""]]
    for kernel in kernels:
        name = kernel["name"]
        if name == running:
            shown = term.style(name, "bold", "green")
        elif kernel.get("installed"):
            shown = term.bold(name)
        else:
            shown = name
        row = [
            term.bullet_on() if kernel.get("installed") else term.bullet_off(),
            shown,
            _version(kernel),
        ]
        if with_repository:
            row.append(term.dim(kernel.get("repository", "")))
        row.append(term.dim(" · ").join(kernel_tags(kernel, running)))
        rows.append(row)
    return rows


def _json_kernels(kernels: list[KernelInfo], running: str) -> list[dict]:
    return [
        {
            **kernel,
            "version": kernel.get("installed_version") or kernel.get("version", ""),
            "repository_version": kernel.get("version", "")
            if kernel.get("repository")
            else "",
            "installed": bool(kernel.get("installed")),
            "running": kernel["name"] == running,
            "obsolete": bool(kernel.get("obsolete")),
        }
        for kernel in kernels
    ]


def collect_kernels(
    manager: KernelManager, installed_only: bool
) -> tuple[list[KernelInfo], list[KernelInfo], str]:
    """(kernels to show, obsolete ones, running kernel package).

    The repository list already holds the installed kernels it offers, plus
    third-party and hand-made ones; those that left the repositories are
    added back, marked obsolete.
    """
    running = manager.get_running_kernel_package()
    installed = manager.get_installed_kernels()
    available = manager.get_available_kernels()
    obsolete = manager.compute_obsolete_kernels(installed, available, running)
    versions = {k["name"]: k.get("version", "") for k in installed}
    names = {k["name"] for k in available}
    kernels = available + [k for k in obsolete if k["name"] not in names]
    shown = []
    for kernel in kernels:
        if kernel["name"] in versions:
            kernel = {
                **kernel,
                "installed": True,
                "installed_version": versions[kernel["name"]],
            }
        elif installed_only:
            continue
        shown.append(kernel)
    return sorted(shown, key=lambda k: k["name"]), obsolete, running


def _list(args: argparse.Namespace) -> int:
    manager = KernelManager()
    kernels, obsolete, running = collect_kernels(manager, args.installed)

    if args.json:
        print(
            json.dumps(
                {
                    "running": platform.release(),
                    "running_package": running,
                    "kernels": _json_kernels(kernels, running),
                },
                indent=2,
            )
        )
        return EXIT_OK

    title = _("Installed kernels") if args.installed else _("Kernels")
    print(term.heading(title))
    if kernels:
        print(term.table(kernel_rows(kernels, running)))
    else:
        print("  " + term.dim(_("No kernels found.")))
    print()
    print(
        term.label(_("Running"), f"{term.bold(running or '?')} ({platform.release()})")
    )
    if not args.installed:
        legend = f"{term.bullet_on()} {_('installed')}   {term.bullet_off()} {_('available')}"
        print(term.label(_("Legend"), legend))
    if obsolete:
        print()
        names = ", ".join(term.bold(k["name"]) for k in obsolete)
        print(term.warn(_("No longer in the repositories: {}").format(names)))
        print("  " + term.dim(_("They receive no updates; remove them with:")))
        for kernel in obsolete:
            print(
                "    "
                + term.style(f"big-drivers kernel remove {kernel['name']}", "cyan")
            )
    if not args.installed:
        print()
        print(
            term.dim(_("Install one with: "))
            + term.style("big-drivers kernel install " + _("KERNEL"), "cyan")
        )
    return EXIT_OK


def _obsolete(args: argparse.Namespace) -> int:
    manager = KernelManager()
    running = manager.get_running_kernel_package()
    obsolete = manager.get_obsolete_kernels()
    if args.json:
        print(json.dumps(_json_kernels(obsolete, running), indent=2))
        return EXIT_OK
    if not obsolete:
        print(
            term.ok(
                _("No obsolete kernels: every installed kernel is in the repositories.")
            )
        )
        return EXIT_OK
    print(term.heading(_("Kernels that left the repositories")))
    print(term.table(kernel_rows(obsolete, running)[1:]))
    print()
    print("  " + term.dim(_("They receive no updates; remove them with:")))
    for kernel in obsolete:
        print(
            "    " + term.style(f"big-drivers kernel remove {kernel['name']}", "cyan")
        )
    return EXIT_OK


# --------------------------------------------------------------------------
# install / remove
# --------------------------------------------------------------------------


def package_role(package: str, kernel: str) -> str:
    if package == kernel:
        return _("kernel")
    if package == f"{kernel}-headers":
        return _("headers, to build modules (DKMS)")
    return _("module the running kernel uses")


def _summary(title: str, kernel: KernelInfo, packages: list[str], running: str) -> None:
    print(term.heading(title))
    print(term.label(_("Kernel"), term.style(kernel["name"], "bold", "cyan")))
    if kernel.get("version"):
        print(term.label(_("Version"), kernel["version"]))
    if kernel.get("repository"):
        print(term.label(_("Repository"), kernel["repository"]))
    if running:
        print(term.label(_("Running"), running))
    print()
    print("  " + term.bold(_("Packages:")))
    rows = [
        [term.bullet_on(), term.bold(p), term.dim(package_role(p, kernel["name"]))]
        for p in packages
    ]
    print(term.table(rows, indent=4))
    print()


def _install(args: argparse.Namespace) -> int:
    name = args.name
    try:
        validate_packages([name])
    except PrivilegedRequestError as error:
        _error(str(error))
        return EXIT_USAGE
    manager = KernelManager()
    if not args.confirmed:
        print(
            term.step(
                _("Looking for {} in the repositories...").format(term.bold(name))
            ),
            flush=True,
        )
    available = {
        k["name"]: k
        for k in manager.get_available_kernels()
        if k.get("source") not in _NOT_FROM_REPOSITORIES
    }
    kernel = available.get(name)
    if kernel is None:
        _error(_("{} is not a kernel in the configured repositories.").format(name))
        print(
            "  "
            + term.dim(_("See the kernels you can install with: "))
            + term.style("big-drivers kernel list", "cyan")
        )
        return EXIT_FAILED

    plan = manager.plan_kernel_install(name)
    if not plan.allowed:
        _error(_("{} cannot be installed now.").format(name))
        for line in plan.blocked_reason.splitlines():
            print("  " + line)
        return EXIT_FAILED

    installed = gpu.installed_packages()
    packages = [p for p in dict.fromkeys(plan.packages) if p not in installed]
    if not packages:
        print(
            term.ok(
                _("{} is already installed, with all its modules.").format(
                    term.bold(name)
                )
            )
        )
        return EXIT_OK

    running = manager.get_running_kernel_package()
    if not args.confirmed:
        _summary(_("Install a kernel"), kernel, packages, running)
        if not _confirm(_("Install these packages?"), True, args):
            print(term.info(_("Nothing was changed.")))
            return EXIT_FAILED
    if not is_root():
        return elevate(["kernel", "install", name, "--confirmed"])

    code = _pacman(["-S", "--noconfirm", "--needed", *packages])
    print()
    if code != 0:
        _error(
            _("Installing {name} failed (pacman exit code {code}).").format(
                name=name, code=code
            )
        )
        return EXIT_FAILED
    print(term.ok(_("{} installed.").format(term.style(name, "bold", "green"))))
    print("  " + _("Restart to use it; the other kernels stay in the boot menu."))
    return EXIT_OK


def _remove(args: argparse.Namespace) -> int:
    name = args.name
    try:
        validate_packages([name])
    except PrivilegedRequestError as error:
        _error(str(error))
        return EXIT_USAGE
    manager = KernelManager()
    installed = {k["name"]: k for k in manager.get_installed_kernels()}
    kernel = installed.get(name)
    if kernel is None:
        _error(_("{} is not installed.").format(name))
        return EXIT_FAILED
    if kernel.get("source") == "manual":
        _error(
            _("{} was installed without a package; remove its files by hand.").format(
                name
            )
        )
        return EXIT_FAILED
    running = manager.get_running_kernel_package()
    if name == running:
        _error(
            _(
                "{} is the running kernel. Start the computer with another kernel to remove it."
            ).format(name)
        )
        return EXIT_FAILED
    others = [
        k
        for k in installed.values()
        if k["name"] != name and k.get("source") != "manual"
    ]
    if not others:
        _error(_("{} is the only installed kernel.").format(name))
        return EXIT_FAILED

    packages = list(dict.fromkeys([name, *manager.get_modules_for_remove(name)]))
    if not args.confirmed:
        _summary(_("Remove a kernel"), kernel, packages, running)
        if not _confirm(_("Remove these packages?"), False, args):
            print(term.info(_("Nothing was changed.")))
            return EXIT_FAILED
    if not is_root():
        return elevate(["kernel", "remove", name, "--confirmed"])

    code = _pacman(["-R", "--noconfirm", *packages])
    print()
    if code != 0:
        _error(
            _("Removing {name} failed (pacman exit code {code}).").format(
                name=name, code=code
            )
        )
        return EXIT_FAILED
    print(term.ok(_("{} removed.").format(term.bold(name))))
    return EXIT_OK


def run(args: argparse.Namespace) -> int:
    action = args.kernel_action or "list"
    if action == "list":
        if not hasattr(args, "installed"):  # plain "big-drivers kernel"
            args.installed, args.json = False, False
        return _list(args)
    if action == "obsolete":
        return _obsolete(args)
    if action == "install":
        return _install(args)
    if action == "remove":
        return _remove(args)
    return EXIT_USAGE
