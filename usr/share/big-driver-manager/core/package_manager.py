#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kernel Manager Application - Package Manager

This module provides a query-only interface to interact with pacman package
manager for listing and checking packages. Actual install/remove operations
are handled by BaseManager._run_pacman_command.
"""

import re
import subprocess
import threading


class PackageManager:
    """Interface for querying the pacman package manager."""

    def __init__(self) -> None:
        self._installed_cache: list[dict[str, str]] | None = None
        self._installed_names: set[str] | None = None
        self._cache_lock = threading.Lock()

    def invalidate_cache(self) -> None:
        """Clear the installed-packages cache (call after install/remove)."""
        with self._cache_lock:
            self._installed_cache = None
            self._installed_names = None

    def get_installed_packages(
        self, pattern: str | None = None
    ) -> list[dict[str, str]]:
        """
        Get a list of installed packages.

        Results are cached until ``invalidate_cache()`` is called.

        Args:
            pattern: Optional regex pattern to filter packages.

        Returns:
            list: List of installed packages.
        """
        with self._cache_lock:
            if self._installed_cache is None:
                cmd = ["pacman", "-Q"]
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)

                if result.returncode != 0:
                    return []

                packages = []
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        packages.append({"name": parts[0], "version": parts[1]})
                self._installed_cache = packages
                self._installed_names = {p["name"] for p in packages}

            if pattern:
                return [p for p in self._installed_cache if re.search(pattern, p["name"])]
            return list(self._installed_cache)

    def is_package_installed(self, package_name: str) -> bool:
        """
        Check if a package is installed.

        Uses the cached installed-packages list when available, falling back
        to a single ``pacman -Q`` lookup when the cache is unset.

        Args:
            package_name: Name of the package.

        Returns:
            bool: True if the package is installed, False otherwise.
        """
        with self._cache_lock:
            if self._installed_cache is not None:
                return package_name in self._installed_names
        cmd = ["pacman", "-Q", package_name]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode == 0
