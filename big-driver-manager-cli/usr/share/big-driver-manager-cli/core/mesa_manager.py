#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Mesa Manager

This module provides functionality for managing Mesa drivers
including listing, installing, and switching between different versions.

Switching variants never removes a package the desktop depends on: the new
variant is installed in a single pacman transaction that replaces the old
one (``--ask 4`` answers yes to removing the packages it conflicts with), so
everything that needs ``mesa`` is satisfied by the new package's provides.
pacman refuses the whole transaction, changing nothing, when it would leave
a dependency unsatisfied. Never use ``-Rc``/``--cascade`` here: removing
``mesa`` in cascade removes the whole desktop with it.
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from core.base_manager import BaseManager
from core.package_manager import PackageManager
from core.logging_config import get_logger
from core.subprocess_env import subprocess_env
from core.i18n import _

_logger = get_logger("MesaManager")

# pacman's --ask bit for "X and Y are in conflict. Remove Y?": answer yes.
ASK_REMOVE_CONFLICTS = "4"

_VERSION_RE = re.compile(r"[<>=].*$")


def _load_mesa_drivers() -> list[dict]:
    """Load Mesa driver definitions from external JSON data file.

    Failure to load leaves the Mesa page empty rather than crashing the
    whole app at import time — users can still manage kernels and other
    drivers while the JSON is inspected/repaired.
    """
    data_path = Path(__file__).resolve().parent.parent / "assets" / "mesa_drivers.json"
    try:
        with open(data_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        _logger.error("mesa_drivers.json not found at %s", data_path)
    except (OSError, json.JSONDecodeError) as exc:
        _logger.error("Failed to load mesa_drivers.json: %s", exc)
    return []


MESA_DRIVERS: list[dict] = _load_mesa_drivers()


def _is_lib32(package: str) -> bool:
    return package.startswith("lib32-")


def _bare_name(dependency: str) -> str:
    """``mesa=26.0-1`` -> ``mesa``: provides and conflicts carry versions."""
    return _VERSION_RE.sub("", dependency).strip()


def parse_pacman_info(output: str) -> dict[str, dict[str, list[str]]]:
    """Fields of ``pacman -Qi``/``-Si`` output (LANG=C), per package name.

    Only list fields are kept (``Provides``, ``Conflicts With``,
    ``Required By``...), split on whitespace; "None" is an empty list.
    A package listed by several repositories keeps its first block, the
    one pacman installs.
    """
    packages: dict[str, dict[str, list[str]]] = {}
    current: dict[str, list[str]] | None = None
    key = ""
    for line in output.splitlines():
        if not line.strip():
            current, key = None, ""
            continue
        if line[0].isspace():  # a wrapped value continues the last field
            if current is not None and key:
                current[key].extend(line.split())
            continue
        name, sep, value = line.partition(":")
        if not sep:
            continue
        key = name.strip()
        value = value.strip()
        if key == "Name":
            if value in packages:
                current, key = None, ""  # second repository: keep the first
                continue
            current = packages.setdefault(value, {})
            continue
        if current is not None:
            current[key] = [] if value == "None" else value.split()
    return packages


@dataclass
class MesaSwitchPlan:
    """What switching to a Mesa variant does, computed before anything runs.

    ``install``: the variant's packages, installed in one transaction.
    ``replaced``: installed packages that transaction replaces (the new
        packages conflict with them, so pacman removes them itself, and
        their provides keep every dependent satisfied).
    ``remove_first``: installed packages of the old variant the new one does
        not declare a conflict with but cannot live with (same files, or a
        dependency on the old ``mesa``). They are removed, without their
        dependency checks, right before the transaction, and put back if it
        fails.
    The plan is refused when a package that stays installed would lose a
    dependency (by name or provides) the new variant does not provide.
    ``problems``: why the switch cannot be done; nothing runs when set.
    """

    driver_id: str
    name: str
    install: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    remove_first: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return not self.problems and bool(self.install)

    def to_dict(self) -> dict:
        return {
            "driver": self.driver_id,
            "name": self.name,
            "allowed": self.allowed,
            "install": self.install,
            "replaced": self.replaced,
            "remove_first": self.remove_first,
            "skipped": self.skipped,
            "problems": self.problems,
        }


def plan_mesa_switch(
    driver: dict,
    installed: set[str],
    available: set[str],
    target_info: dict[str, dict[str, list[str]]],
    installed_info: dict[str, dict[str, list[str]]],
) -> MesaSwitchPlan:
    """Pure planning step of a Mesa variant switch (see ``MesaSwitchPlan``).

    Args:
        driver: entry of ``mesa_drivers.json``.
        installed: names of the installed packages (``pacman -Qq``).
        available: the driver's packages found in the repositories.
        target_info: ``pacman -Si`` fields of the available packages.
        installed_info: ``pacman -Qi`` fields of the installed packages.
    """
    plan = MesaSwitchPlan(
        driver_id=driver.get("id", ""), name=driver.get("name", driver.get("id", ""))
    )
    conflicts = [
        p for p in dict.fromkeys(driver.get("conflicts") or []) if p in installed
    ]
    has_lib32 = any(_is_lib32(p) for p in installed if p in conflicts or "mesa" in p)

    for package in dict.fromkeys(driver.get("packages") or []):
        if package in available:
            plan.install.append(package)
        elif _is_lib32(package) and not has_lib32:
            # No 32-bit Mesa here (or no multilib): nothing to keep in step.
            plan.skipped.append(package)
        else:
            plan.problems.append(
                _("{} is not in the configured repositories.").format(package)
            )
    if not plan.install:
        plan.problems.append(_("No packages available to install."))
    if plan.problems:
        return plan

    # What the new packages are, by name and by what they provide.
    new_names: set[str] = set()
    new_conflicts: set[str] = set()
    for package in plan.install:
        info = target_info.get(package, {})
        new_names.add(package)
        new_names.update(_bare_name(p) for p in info.get("Provides", []))
        new_conflicts.update(_bare_name(c) for c in info.get("Conflicts With", []))

    for package in conflicts:
        info = installed_info.get(package, {})
        old_names = {package, *(_bare_name(p) for p in info.get("Provides", []))}
        old_conflicts = {_bare_name(c) for c in info.get("Conflicts With", [])}
        if old_names & new_conflicts or old_conflicts & new_names:
            plan.replaced.append(package)
        else:
            plan.remove_first.append(package)

    # Refuse what would leave a package that stays without a dependency:
    # pacman would refuse the transaction anyway (after remove_first went
    # without dependency checks), and the user is better told why up front.
    leaving = set(plan.replaced) | set(plan.remove_first)
    leaving_names: set[str] = set()
    for package in leaving:
        leaving_names.add(package)
        info = installed_info.get(package, {})
        leaving_names.update(_bare_name(p) for p in info.get("Provides", []))
    still_there = set(new_names)
    for package in installed - leaving:
        still_there.add(package)
        info = installed_info.get(package, {})
        still_there.update(_bare_name(p) for p in info.get("Provides", []))
    broken: dict[str, list[str]] = {}
    for package in sorted(installed - leaving):
        for dependency in installed_info.get(package, {}).get("Depends On", []):
            name = _bare_name(dependency)
            if name in leaving_names and name not in still_there:
                broken.setdefault(name, []).append(package)
    for name, users in broken.items():
        plan.problems.append(
            _("{package} is needed by {users}, which would stop working.").format(
                package=name, users=", ".join(users)
            )
        )
    return plan


class MesaManager(BaseManager):
    """Manager for handling Mesa drivers."""

    def __init__(self, package_manager: PackageManager | None = None) -> None:
        """Initialize the Mesa manager.

        Args:
            package_manager: Optional shared ``PackageManager`` instance.
        """
        super().__init__()
        self._logger = get_logger("MesaManager")
        self.package_manager = package_manager or PackageManager.get_default()
        self.drivers = MESA_DRIVERS.copy()

    def get_available_drivers(
        self, installed_set: set[str] | None = None
    ) -> list[dict]:
        """
        Get a list of available Mesa drivers.

        Args:
            installed_set: Pre-fetched set of installed package names
                (from ``pacman -Qq``). Avoids subprocess calls.

        Returns:
            List of available Mesa drivers with their information.
        """
        active_driver = self._get_active_driver(installed_set)

        drivers = []
        for driver in self.drivers:
            driver_copy = driver.copy()
            driver_copy["active"] = driver_copy["id"] == active_driver
            drivers.append(driver_copy)

        return drivers

    def _get_active_driver(self, installed_set: set[str] | None = None) -> str:
        """
        Determine which Mesa driver is currently active.

        When *installed_set* (from ``pacman -Qq``) is provided, avoids
        per-package ``pacman -Qi`` calls.  ``pacman -Qq`` always returns
        real package names, so virtual provides cannot cause false positives.

        Returns:
            ID of the active driver, or "stable" if not determined.
        """
        if installed_set is not None:
            for driver in self.drivers:
                detect_pkg = driver.get("detect_package", driver["packages"][0])
                if detect_pkg in installed_set:
                    return driver["id"]
        else:
            for driver in self.drivers:
                detect_pkg = driver.get("detect_package", driver["packages"][0])
                if self._is_real_package_installed(detect_pkg):
                    return driver["id"]

        return "stable"

    def find_driver(self, driver_id: str) -> dict | None:
        """The ``mesa_drivers.json`` entry with this id."""
        return next((d for d in self.drivers if d.get("id") == driver_id), None)

    def plan_switch(self, driver_id: str) -> MesaSwitchPlan:
        """Plan switching to *driver_id*; read-only, needs no root."""
        driver = self.find_driver(driver_id)
        if driver is None:
            plan = MesaSwitchPlan(driver_id=driver_id, name=driver_id)
            plan.problems.append(_("Driver not found: {}").format(driver_id))
            return plan
        # Every installed package: what stays must keep its dependencies.
        installed_info = self._package_info(["-Qi"])
        targets = list(dict.fromkeys(driver.get("packages") or []))
        available = self._packages_available(targets)
        return plan_mesa_switch(
            driver,
            set(installed_info),
            available,
            self._package_info(["-Si", *[p for p in targets if p in available]]),
            installed_info,
        )

    def apply_driver(
        self,
        driver_id: str,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
    ) -> None:
        """
        Switch to a Mesa variant.

        The whole switch (download, replace, roll back on failure) runs as
        root in ``big-driver-manager-cli mesa apply``: one password prompt,
        and no half-done state left by a second prompt the user cancels.

        Args:
            driver_id: ID of the driver to apply.
            progress_callback: Callback function for progress updates.
            output_callback: Callback function for command output.
            complete_callback: Callback function for completion notification.
        """
        driver = self.find_driver(driver_id)
        if driver is None:
            self._logger.error(f"Driver not found: {driver_id}")
            self._output(output_callback, _("Driver not found: {}").format(driver_id))
            if complete_callback:
                complete_callback(False)
            return

        self._logger.info(f"Applying Mesa driver: {driver['name']}")
        self.run_cli_command(
            ["mesa", "apply", driver_id, "--confirmed"],
            progress_callback,
            output_callback,
            complete_callback,
            _("Installing {} driver").format(driver.get("name", driver_id)),
        )

    def _package_info(self, args: list[str]) -> dict[str, dict[str, list[str]]]:
        """``pacman -Qi``/``-Si`` fields: of the packages in *args*, or of
        every installed package for a bare ``-Qi``."""
        if args == ["-Si"]:
            return {}
        result = subprocess.run(
            ["pacman", *args],
            capture_output=True,
            text=True,
            check=False,
            env=subprocess_env(),
        )
        return parse_pacman_info(result.stdout)

    def _is_real_package_installed(self, package_name: str) -> bool:
        """
        Check if a package is installed by its exact name, not virtual provides.

        pacman -Q resolves virtual provides (e.g. mesa-tkg-stable provides mesa),
        which causes false positives. This method uses pacman -Qi and verifies
        the Name field matches exactly.

        LANG=C is forced so the "Name" field label is always in English,
        regardless of the user's desktop locale.

        Args:
            package_name: Exact package name to check.

        Returns:
            True if the package is installed with that exact name.
        """
        cmd = ["pacman", "-Qi", package_name]
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, env=subprocess_env()
        )
        if result.returncode != 0:
            return False
        # Verify the Name field matches exactly
        for line in result.stdout.splitlines():
            if line.startswith("Name"):
                actual_name = line.split(":", 1)[1].strip()
                return actual_name == package_name
        return False

    def _package_available(self, package_name: str) -> bool:
        """Check if a single package is available in the repositories."""
        return package_name in self._packages_available([package_name])

    def _packages_available(self, package_names: list[str]) -> set[str]:
        """Return the subset of package names that exist in the repositories.

        Uses a single ``pacman -Si`` invocation for all packages: pacman
        returns a non-zero exit status if any are missing but still prints
        "Name : <pkg>" blocks for every package it DID find, so parsing
        those blocks is reliable.
        """
        if not package_names:
            return set()
        cmd = ["pacman", "-Si", *package_names]
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, env=subprocess_env()
        )
        found: set[str] = set()
        for line in result.stdout.splitlines():
            if line.startswith("Name") and ":" in line:
                name = line.split(":", 1)[1].strip()
                if name:
                    found.add(name)
        return found
