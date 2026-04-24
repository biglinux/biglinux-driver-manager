#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Mesa Manager

This module provides functionality for managing Mesa drivers
including listing, installing, and switching between different versions.
"""

import json
import subprocess
import threading
from pathlib import Path
from typing import Callable

from core.base_manager import BaseManager
from core.package_manager import PackageManager
from core.logging_config import get_logger
from core.subprocess_env import subprocess_env
from utils.i18n import _

_logger = get_logger("MesaManager")


# Phase weights for progress reporting when applying a driver.
_PHASE_CHECK = 0.1
_PHASE_RESOLVE = 0.2
_PHASE_REMOVE_CONFLICTS = 0.35
_PHASE_INSTALL = 0.5
_PHASE_DONE = 1.0


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

    def apply_driver(
        self,
        driver_id: str,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
    ) -> None:
        """
        Apply a Mesa driver configuration.

        Args:
            driver_id: ID of the driver to apply.
            progress_callback: Callback function for progress updates.
            output_callback: Callback function for command output.
            complete_callback: Callback function for completion notification.
        """
        # Find the driver by ID
        selected_driver = None
        for driver in self.drivers:
            if driver["id"] == driver_id:
                selected_driver = driver
                break

        if not selected_driver:
            self._logger.error(f"Driver not found: {driver_id}")
            self._output(output_callback, _("Driver not found: {}").format(driver_id))
            if complete_callback:
                complete_callback(False)
            return

        self._logger.info(f"Applying Mesa driver: {selected_driver['name']}")

        # Start thread for applying driver
        threading.Thread(
            target=self._apply_driver_thread,
            args=(
                selected_driver,
                progress_callback,
                output_callback,
                complete_callback,
            ),
            daemon=True,
        ).start()

    def _apply_driver_thread(
        self,
        driver: dict,
        progress_callback: Callable | None,
        output_callback: Callable | None,
        complete_callback: Callable | None,
    ) -> None:
        """
        Thread function for applying a driver.

        Strategy (safe, atomic-ish):
          1. Resolve installed conflicts and available target packages.
          2. Remove conflicting packages with ``pacman -Rnc --noconfirm``
             (respects dependencies; recursively removes unneeded deps).
          3. Install the new Mesa variant with ``pacman -S --noconfirm
             --needed --overwrite '*'`` to handle file conflicts with the
             old variant that may have been carried over.

        Both pacman calls go through the standard ``run_pacman_command``
        path so they populate ``self._current_process`` and honour the
        user cancel button.

        Args:
            driver: The driver configuration to apply.
            progress_callback: Callback function for progress updates.
            output_callback: Callback function for command output.
            complete_callback: Callback function for completion notification.
        """
        self._cancelled = False
        name = driver.get("name", driver.get("id", "mesa"))
        self._progress(
            progress_callback, _PHASE_CHECK, _("Applying {} driver...").format(name)
        )
        self._output(
            output_callback,
            _("Starting {} driver installation...").format(name),
        )

        try:
            plan = self._plan_driver_apply(driver, output_callback, progress_callback)
        except Exception as exc:
            self._logger.error("Error planning driver apply: %s", exc)
            self._progress(progress_callback, 0.0, _("Error: {}").format(str(exc)))
            self._output(output_callback, _("❌ Error: {}").format(str(exc)))
            if complete_callback:
                complete_callback(False)
            return

        if plan is None:
            if complete_callback:
                complete_callback(False)
            return

        packages_to_install, installed_conflicts = plan

        # Step A: remove conflicts (if any), then install. Either step can
        # be cancelled by the user; we short-circuit on failure.
        def _after_remove(success: bool) -> None:
            if self._cancelled or not success:
                self._progress(
                    progress_callback,
                    0.0,
                    _("Failed to remove conflicting packages."),
                )
                if complete_callback:
                    complete_callback(False)
                return
            self._install_driver_packages(
                name,
                packages_to_install,
                progress_callback,
                output_callback,
                complete_callback,
            )

        if installed_conflicts:
            self._output(
                output_callback,
                _("Removing conflicts: {}").format(", ".join(installed_conflicts)),
            )
            self._progress(
                progress_callback,
                _PHASE_REMOVE_CONFLICTS,
                _("Removing conflicting packages..."),
            )
            # -Rnc: recursively remove unneeded deps, skip config backups.
            # This is safer than -Rdd which forces through dependency
            # violations and can corrupt the system.
            self.run_pacman_command(
                args=["-Rnc", "--noconfirm", *installed_conflicts],
                progress_callback=progress_callback,
                output_callback=output_callback,
                complete_callback=_after_remove,
                operation_name=_("Removing conflicting packages"),
            )
        else:
            self._install_driver_packages(
                name,
                packages_to_install,
                progress_callback,
                output_callback,
                complete_callback,
            )

    def _plan_driver_apply(
        self,
        driver: dict,
        output_callback: Callable | None,
        progress_callback: Callable | None,
    ) -> tuple[list[str], list[str]] | None:
        """Compute the (install, remove) plan for applying a Mesa variant.

        Returns ``None`` (and notifies the UI) when there is nothing to
        install, which is treated as a failure.
        """
        self._progress(
            progress_callback,
            _PHASE_RESOLVE,
            _("Checking for conflicting packages..."),
        )
        installed_conflicts = [
            pkg
            for pkg in driver.get("conflicts") or []
            if self._is_real_package_installed(pkg)
        ]

        self._progress(
            progress_callback,
            _PHASE_RESOLVE + 0.05,
            _("Checking {} packages...").format(driver.get("name", "")),
        )
        # Batch availability check for target packages.
        target = list(driver.get("packages") or [])
        if not target:
            self._output(output_callback, _("❌ No packages available to install."))
            return None
        available_set = self._packages_available(target)
        packages_to_install = [p for p in target if p in available_set]
        for skipped in (p for p in target if p not in available_set):
            self._output(
                output_callback,
                _("⚠️ Package {} not available, skipping...").format(skipped),
            )

        if not packages_to_install:
            self._output(output_callback, _("❌ No packages available to install."))
            return None

        return packages_to_install, installed_conflicts

    def _install_driver_packages(
        self,
        driver_name: str,
        packages: list[str],
        progress_callback: Callable | None,
        output_callback: Callable | None,
        complete_callback: Callable | None,
    ) -> None:
        """Install the packages for a Mesa variant through the safe path."""
        if self._cancelled:
            if complete_callback:
                complete_callback(False)
            return

        self._output(
            output_callback,
            _("Installing: {}").format(", ".join(packages)),
        )
        self._progress(
            progress_callback,
            _PHASE_INSTALL,
            _("Installing {} driver...").format(driver_name),
        )

        # --needed avoids reinstalls, --overwrite '*' handles file-level
        # conflicts that can remain from the previous variant even after
        # package removal (some Mesa builds ship the same file paths with
        # different ownership). We deliberately do NOT pass --ask 4.
        args = [
            "-S",
            "--noconfirm",
            "--needed",
            "--overwrite",
            "*",
            *packages,
        ]

        def _after_install(success: bool) -> None:
            if success and not self._cancelled:
                self._progress(
                    progress_callback,
                    _PHASE_DONE,
                    _("Driver applied successfully!"),
                )
                self._output(
                    output_callback,
                    _("✅ {} driver applied successfully!").format(driver_name),
                )
            if complete_callback:
                complete_callback(success and not self._cancelled)

        self.run_pacman_command(
            args=args,
            progress_callback=progress_callback,
            output_callback=output_callback,
            complete_callback=_after_install,
            operation_name=_("Installing {} driver").format(driver_name),
        )

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
