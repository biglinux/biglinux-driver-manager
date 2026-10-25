"""``big-drivers mesa ...``: switch between the Mesa variants.

list   the variants, the one in use marked
plan   what switching to a variant would do (no root needed)
apply  switch to a variant, as the interface does

The switch replaces the old variant in one pacman transaction (see
``core.mesa_manager``): nothing that depends on Mesa is ever removed.
"""

from __future__ import annotations

import argparse
import json
import subprocess

from core import kernel_cli, term
from core.i18n import _
from core.mesa_manager import ASK_REMOVE_CONFLICTS, MesaManager, MesaSwitchPlan
from core.privileged import is_root

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


def add_parser(verbs: argparse._SubParsersAction) -> None:
    parser = verbs.add_parser(
        "mesa",
        help=_("switch between the Mesa variants (stable, tkg, amber)"),
        description=_(
            "Switch the Mesa graphics stack between its variants. The old "
            "variant is replaced in a single transaction: nothing that "
            "depends on Mesa is removed."
        ),
    )
    actions = parser.add_subparsers(dest="mesa_action", metavar=_("ACTION"))

    listing = actions.add_parser("list", help=_("the variants, the one in use marked"))
    listing.add_argument("--json", action="store_true", help=_("JSON output"))

    plan = actions.add_parser("plan", help=_("show what switching would do"))
    plan.add_argument("variant", metavar=_("VARIANT"))
    plan.add_argument("--json", action="store_true", help=_("JSON output"))

    apply = actions.add_parser("apply", help=_("switch to a variant"))
    apply.add_argument("variant", metavar=_("VARIANT"))
    apply.add_argument(
        "-y", "--yes", action="store_true", help=_("do not ask for confirmation")
    )
    # The request was already shown and confirmed before pkexec.
    apply.add_argument("--confirmed", action="store_true", help=argparse.SUPPRESS)


# --------------------------------------------------------------------------


def _list(args: argparse.Namespace) -> int:
    manager = MesaManager()
    drivers = manager.get_available_drivers()
    if getattr(args, "json", False):
        print(json.dumps(drivers, indent=2))
        return EXIT_OK
    rows = [
        [
            "",
            term.style(_("Variant"), "bold", "underline"),
            term.style(_("Package"), "bold", "underline"),
            "",
        ]
    ]
    for driver in drivers:
        active = driver.get("active")
        rows.append(
            [
                term.bullet_on() if active else term.bullet_off(),
                term.style(driver["id"], "bold", "green") if active else driver["id"],
                term.dim(driver.get("detect_package", driver["packages"][0])),
                term.style(_("in use"), "bold", "green") if active else "",
            ]
        )
    print(term.table(rows))
    return EXIT_OK


def _describe(plan: MesaSwitchPlan) -> None:
    print(term.heading(_("Switch Mesa to {}").format(term.bold(plan.name))))
    sections = (
        (_("Install"), plan.install, "green"),
        (_("Replaced"), plan.replaced, "yellow"),
        (_("Removed first, put back if the switch fails"), plan.remove_first, "yellow"),
        (_("Skipped (no 32-bit Mesa installed)"), plan.skipped, "dim"),
    )
    for title, packages, color in sections:
        if packages:
            print("  " + term.bold(title + ":"))
            print("    " + " ".join(term.style(p, color) for p in packages))
    for problem in plan.problems:
        print("  " + term.fail(problem))
    print()


def _plan(args: argparse.Namespace) -> int:
    plan = MesaManager().plan_switch(args.variant)
    if args.json:
        print(json.dumps(plan.to_dict(), indent=2))
    else:
        _describe(plan)
    return EXIT_OK if plan.allowed else EXIT_FAILED


def _pacman(arguments: list[str]) -> bool:
    return kernel_cli._pacman(arguments) == 0


def _installed_as_dependency() -> set[str]:
    result = subprocess.run(
        ["pacman", "-Qqd"], capture_output=True, text=True, check=False
    )
    return set(result.stdout.split())


def _switch(plan: MesaSwitchPlan) -> int:
    ask = ["--ask", ASK_REMOVE_CONFLICTS]

    # Download first: a network failure must not happen half-way.
    if not _pacman(["-Sw", "--noconfirm", *ask, *plan.install]):
        kernel_cli._error(_("Downloading the packages failed. Nothing was changed."))
        return EXIT_FAILED

    as_dependency: set[str] = set()
    if plan.remove_first:
        as_dependency = _installed_as_dependency()
        # -dd: every package that needs these leaves in the same switch
        # (checked by the plan), the new variant takes their place.
        if not _pacman(["-Rdd", "--noconfirm", *plan.remove_first]):
            kernel_cli._error(
                _("Removing the old packages failed. Nothing was changed.")
            )
            return EXIT_FAILED

    # One transaction: pacman removes what the new packages conflict with and
    # refuses everything if a dependency would be left unsatisfied.
    if _pacman(["-S", "--noconfirm", "--needed", *ask, *plan.install]):
        return EXIT_OK

    kernel_cli._error(_("Installing {} failed.").format(plan.name))
    if plan.remove_first:
        print(term.step(_("Putting back the packages removed for the switch")))
        restored = _pacman(["-S", "--noconfirm", "--needed", *plan.remove_first])
        dependencies = [p for p in plan.remove_first if p in as_dependency]
        if restored and dependencies:
            _pacman(["-D", "--asdeps", *dependencies])
        if not restored:
            kernel_cli._error(
                _("Could not put back: {}. Install them again with pacman -S.").format(
                    " ".join(plan.remove_first)
                )
            )
    return EXIT_FAILED


def _apply(args: argparse.Namespace) -> int:
    manager = MesaManager()
    driver = manager.find_driver(args.variant)
    if driver is None:
        kernel_cli._error(_("Driver not found: {}").format(args.variant))
        print(
            "  "
            + term.dim(_("See the variants with: "))
            + term.style("big-drivers mesa list", "cyan")
        )
        return EXIT_USAGE

    plan = manager.plan_switch(args.variant)
    if not args.confirmed or not plan.allowed:
        _describe(plan)
    if not plan.allowed:
        kernel_cli._error(_("Nothing was changed."))
        return EXIT_FAILED
    if not args.confirmed:
        if not kernel_cli._confirm(_("Switch Mesa?"), True, args):
            print(term.info(_("Nothing was changed.")))
            return EXIT_FAILED
    if not is_root():
        return kernel_cli.elevate(["mesa", "apply", args.variant, "--confirmed"])

    if _switch(plan) != EXIT_OK:
        return EXIT_FAILED
    if manager._get_active_driver() != plan.driver_id:  # noqa: SLF001
        kernel_cli._error(
            _("{} is not the Mesa in use after the switch.").format(plan.name)
        )
        return EXIT_FAILED
    print()
    print(_("✅ {} driver applied successfully!").format(plan.name))
    print("  " + _("Restart the computer to use it."))
    return EXIT_OK


def run(args: argparse.Namespace) -> int:
    action = args.mesa_action or "list"
    if action == "list":
        return _list(args)
    if action == "plan":
        return _plan(args)
    if action == "apply":
        return _apply(args)
    return EXIT_USAGE
