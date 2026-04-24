#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Driver Installer — installs and removes driver/firmware/peripheral packages.

For repo packages, runs pacman via pkexec with progress tracking.
For AUR packages, launches pamac-installer --build (BigLinux standard).
"""

import subprocess
import shutil

from dataclasses import dataclass
from typing import Callable

from core.base_manager import BaseManager
from core.logging_config import get_logger
from core.subprocess_env import subprocess_env
from utils.i18n import _

_logger = get_logger("DriverInstaller")


def _is_in_repo(package: str) -> bool:
    """Check if a package is available in pacman repositories."""
    try:
        result = subprocess.run(
            ["pacman", "-Si", package],
            capture_output=True,
            timeout=15,
            env=subprocess_env(),
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


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

        resolved_plan = plan or self.build_install_plan(package)
        if resolved_plan.source == "repo":
            self.run_pacman_command(
                args=["-S", "--noconfirm", "--needed", package],
                progress_callback=progress_callback,
                output_callback=output_callback,
                complete_callback=complete_callback,
                operation_name=_("Installing {}").format(package),
            )
        else:
            _logger.info(
                "Package %s not in repos, using pamac-installer --build", package
            )
            self._launch_pamac(
                package,
                build=True,
                progress_callback=progress_callback,
                output_callback=output_callback,
                complete_callback=complete_callback,
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

    @staticmethod
    def _launch_pamac(
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
                proc = subprocess.Popen(cmd, env=subprocess_env())
                proc.wait()
                success = proc.returncode == 0
            except OSError as exc:
                _logger.error("Failed to launch pamac-installer: %s", exc)
                if output_callback:
                    output_callback(str(exc))
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Unexpected error waiting on pamac: %s", exc)
                if output_callback:
                    output_callback(str(exc))
            finally:
                if complete_callback:
                    complete_callback(success)

        import threading

        threading.Thread(target=_wait, daemon=True).start()
