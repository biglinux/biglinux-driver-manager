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


def _load_mesa_drivers() -> list[dict]:
    """Load Mesa driver definitions from external JSON data file."""
    data_path = Path(__file__).resolve().parent.parent / "assets" / "mesa_drivers.json"
    with open(data_path, encoding="utf-8") as f:
        return json.load(f)


MESA_DRIVERS: list[dict] = _load_mesa_drivers()


class MesaManager(BaseManager):
    """Manager for handling Mesa drivers."""

    def __init__(self):
        """Initialize the Mesa manager."""
        super().__init__()
        self._logger = get_logger("MesaManager")
        self.package_manager = PackageManager()
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

        Args:
            driver: The driver configuration to apply.
            progress_callback: Callback function for progress updates.
            output_callback: Callback function for command output.
            complete_callback: Callback function for completion notification.
        """
        self._progress(
            progress_callback, 0.1, _("Applying {} driver...").format(driver["name"])
        )
        self._output(
            output_callback,
            _("Starting {} driver installation...").format(driver["name"]),
        )

        try:
            # Step 1: Check for conflicting packages
            installed_conflicts = []
            if driver["conflicts"]:
                self._progress(
                    progress_callback, 0.2, _("Checking for conflicting packages...")
                )

                installed_conflicts = [
                    conflict
                    for conflict in driver["conflicts"]
                    if self._is_real_package_installed(conflict)
                ]

                if installed_conflicts:
                    self._output(
                        output_callback,
                        _("Removing conflicts: {}").format(
                            ", ".join(installed_conflicts)
                        ),
                    )

            # Step 2: Check available packages to install
            self._progress(
                progress_callback,
                0.3,
                _("Checking {} packages...").format(driver["name"]),
            )

            packages_to_install = []
            for pkg in driver["packages"]:
                if self._package_available(pkg):
                    packages_to_install.append(pkg)
                else:
                    self._output(
                        output_callback,
                        _("⚠️ Package {} not available, skipping...").format(pkg),
                    )

            if not packages_to_install:
                self._output(output_callback, _("❌ No packages available to install."))
                if complete_callback:
                    complete_callback(False)
                return

            self._output(
                output_callback,
                _("Installing: {}").format(", ".join(packages_to_install)),
            )

            # Step 3: Remove conflicting packages (if any)
            if installed_conflicts:
                self._progress(
                    progress_callback, 0.35, _("Removing conflicting packages...")
                )
                ok = self._run_pacman_subprocess(
                    [self.sudo_command, "pacman", "-Rdd", "--noconfirm"]
                    + installed_conflicts,
                    0.35,
                    progress_callback,
                    output_callback,
                )
                if not ok:
                    self._progress(
                        progress_callback,
                        0.0,
                        _("Failed to remove conflicting packages."),
                    )
                    if complete_callback:
                        complete_callback(False)
                    return

            # Step 4: Install the new driver packages
            self._progress(
                progress_callback,
                0.5,
                _("Installing {} driver...").format(driver["name"]),
            )
            ok = self._run_pacman_subprocess(
                [self.sudo_command, "pacman", "-S", "--noconfirm", "--ask", "4"]
                + packages_to_install,
                0.5,
                progress_callback,
                output_callback,
            )
            if not ok:
                self._progress(progress_callback, 0.0, _("Failed to apply driver."))
                if complete_callback:
                    complete_callback(False)
                return

            # Success
            self._progress(progress_callback, 1.0, _("Driver applied successfully!"))
            self._output(
                output_callback,
                _("✅ {} driver applied successfully!").format(driver["name"]),
            )

            if complete_callback:
                complete_callback(True)

        except Exception as e:
            self._logger.error(f"Error applying driver: {e}")
            self._progress(progress_callback, 0.0, _("Error: {}").format(str(e)))
            self._output(output_callback, _("❌ Error: {}").format(str(e)))
            if complete_callback:
                complete_callback(False)

    def _run_pacman_subprocess(
        self,
        cmd: list[str],
        initial_progress: float,
        progress_callback: Callable | None,
        output_callback: Callable | None,
    ) -> bool:
        """Run a pacman command, stream output, and return success."""
        env = subprocess_env()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            env=env,
        )
        progress = initial_progress
        if process.stdout:
            for line in iter(process.stdout.readline, ""):
                line = line.strip()
                if line:
                    self._output(output_callback, line)
                    progress, _status = self._parse_progress(line, progress)
                    self._progress(progress_callback, progress, _status)
        process.wait()
        if process.returncode != 0:
            self._output(
                output_callback,
                _("❌ Operation failed (exit code: {})").format(process.returncode),
            )
            return False
        return True

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
        """
        Check if a package is available in the repositories.

        Args:
            package_name: Name of the package to check.

        Returns:
            True if the package exists in repos, False otherwise.
        """
        cmd = ["pacman", "-Si", package_name]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode == 0
