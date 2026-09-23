#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Driver Installer — installs and removes driver/firmware/peripheral packages.

For repo packages, runs pacman via pkexec with progress tracking.
For AUR packages, launches pamac-installer --build (BigLinux standard),
after installing the build prerequisites DKMS modules need.
"""

import subprocess
import shutil
import threading

from dataclasses import dataclass
from typing import Callable

from core.base_manager import BaseManager
from core.hardware_detect import fetch_installed_set
from core.logging_config import get_logger
from core.package_manager import fetch_repo_package_set
from utils.i18n import _

_logger = get_logger("DriverInstaller")

# Packages every DKMS build needs besides the headers of each kernel
_DKMS_BUILD_DEPS = ("dkms", "base-devel")


def _is_in_repo(package: str) -> bool:
    """Check if a package is available in the enabled pacman repositories."""
    return package in fetch_repo_package_set()


def missing_dkms_prerequisites(installed: set[str], available: set[str]) -> list[str]:
    """Return the repo packages still needed to build a DKMS module.

    Includes dkms, base-devel and the headers of every installed kernel,
    so the module is built for all of them — not only the running one.
    """
    needed = [pkg for pkg in _DKMS_BUILD_DEPS if pkg not in installed]
    for name in sorted(installed):
        headers = f"{name}-headers"
        if (
            name.startswith("linux")
            and not name.endswith("-headers")
            and headers in available
            and headers not in installed
        ):
            needed.append(headers)
    return [pkg for pkg in needed if pkg in available]


@dataclass(frozen=True)
class InstallPlan:
    """Describe how a package install will be executed."""

    package: str
    source: str  # "repo" or "aur"
    cancelable: bool
    initial_message: str


class DriverInstaller(BaseManager):
    """Install/remove driver packages with progress tracking."""

    def build_install_plan(self, package: str) -> InstallPlan:
        """Return the install mode so the UI can expose honest controls."""
        if _is_in_repo(package):
            return InstallPlan(
                package=package,
                source="repo",
                cancelable=True,
                initial_message=_("Please wait..."),
            )
        return InstallPlan(
            package=package,
            source="aur",
            cancelable=False,
            initial_message=_(
                "Continue the installation in the pamac window that was opened."
            ),
        )

    def install_package(
        self,
        package: str,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
        plan: InstallPlan | None = None,
    ) -> None:
        """Install a driver package in background thread."""
        _logger.info("Installing package: %s", package)
        self.last_error_hint = None

        resolved_plan = plan or self.build_install_plan(package)
        if resolved_plan.source == "repo":
            self.run_pacman_command(
                args=["-S", "--noconfirm", "--needed", package],
                progress_callback=progress_callback,
                output_callback=output_callback,
                complete_callback=complete_callback,
                operation_name=_("Installing {}").format(package),
            )
            return

        _logger.info("Package %s not in repos, using pamac-installer --build", package)

        def _launch(success: bool = True) -> None:
            if not success:
                if complete_callback:
                    complete_callback(False)
                return
            self._launch_pamac(
                package,
                build=True,
                progress_callback=progress_callback,
                output_callback=output_callback,
                complete_callback=complete_callback,
            )

        prereqs = []
        if "dkms" in package:
            prereqs = missing_dkms_prerequisites(
                fetch_installed_set(), fetch_repo_package_set()
            )
        if not prereqs:
            _launch()
            return

        _logger.info("Installing DKMS prerequisites first: %s", prereqs)
        self._output(
            output_callback,
            _("Installing build prerequisites: {}").format(", ".join(prereqs)),
        )
        self.run_pacman_command(
            args=["-S", "--noconfirm", "--needed", *prereqs],
            progress_callback=progress_callback,
            output_callback=output_callback,
            complete_callback=_launch,
            operation_name=_("Installing build prerequisites"),
        )

    def remove_package(
        self,
        package: str,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
    ) -> None:
        """Remove a driver package in background thread."""
        _logger.info("Removing package: %s", package)
        self.run_pacman_command(
            args=["-R", "--noconfirm", package],
            progress_callback=progress_callback,
            output_callback=output_callback,
            complete_callback=complete_callback,
            operation_name=_("Removing {}").format(package),
        )

    def _launch_pamac(
        self,
        package: str,
        build: bool = False,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
    ) -> None:
        """Launch pamac-installer for AUR packages, wait in background thread."""
        pamac = shutil.which("pamac-installer")
        if not pamac:
            msg = _("pamac-installer not found. Cannot install AUR package {}.")
            _logger.error(msg.format(package))
            self.last_error_hint = msg.format(package)
            if output_callback:
                output_callback(msg.format(package))
            if complete_callback:
                complete_callback(False)
            return

        cmd = [pamac, "--build", package] if build else [pamac, package]

        # Update progress dialog to inform user
        if progress_callback:
            progress_callback(
                0.0,
                _(
                    "Continue the installation in the pamac window that was opened. "
                    "This dialog is only monitoring the result."
                ),
            )

        def _wait() -> None:
            success = False
            try:
                # pamac-installer is a GUI: keep the user's locale (no
                # subprocess_env/LANG=C, which would show it in English).
                # Tracked so cancel_operation() can close the pamac window.
                self._current_process = subprocess.Popen(cmd)
                self._current_process.wait()
                success = self._current_process.returncode == 0
            except OSError as exc:
                _logger.error("Failed to launch pamac-installer: %s", exc)
                if output_callback:
                    output_callback(str(exc))
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Unexpected error waiting on pamac: %s", exc)
                if output_callback:
                    output_callback(str(exc))
            finally:
                self._current_process = None
                if complete_callback:
                    complete_callback(success)

        threading.Thread(target=_wait, daemon=True).start()
