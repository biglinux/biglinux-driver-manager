#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kernel Manager Application - Package Manager

This module provides a query-only interface to interact with pacman package
manager for listing and checking packages (installed and available in the
repositories). Actual install/remove operations are handled by
BaseManager._run_pacman_command.
"""

import os
import re
import subprocess
import threading
import time
from pathlib import Path

from core.subprocess_env import subprocess_env

_PACMAN_SYNC_DIR = Path("/var/lib/pacman/sync")
_PACMAN_LOG = Path("/var/log/pacman.log")
# Only the tail of pacman.log is scanned for the last database sync.
_PACMAN_LOG_TAIL_BYTES = 512 * 1024
_SYNC_LOG_RE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})[^\]]*\] \[PACMAN\] "
    r"synchronizing package lists",
    re.MULTILINE,
)

_repo_cache: set[str] | None = None
_repo_cache_lock = threading.Lock()


def fetch_repo_package_set(refresh: bool = False) -> set[str]:
    """Return the names of all packages available in the enabled repositories.

    Runs ``pacman -Slq`` once and caches the result for the process lifetime,
    so availability checks don't spawn one ``pacman -Si`` per package.
    Returns an empty set if pacman cannot be queried.
    """
    global _repo_cache
    with _repo_cache_lock:
        if _repo_cache is None or refresh:
            try:
                result = subprocess.run(
                    ["pacman", "-Slq"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=subprocess_env(),
                )
                _repo_cache = (
                    set(result.stdout.split()) if result.returncode == 0 else set()
                )
            except (subprocess.TimeoutExpired, OSError):
                _repo_cache = set()
        return _repo_cache


def last_sync_age_days(now: float | None = None) -> float | None:
    """Return how many days ago the pacman sync databases were refreshed.

    The db file mtimes alone are unreliable (pacman keeps them when the mirror
    has nothing new), so the newest of: sync dir/file mtimes and the last
    "synchronizing package lists" entry in pacman.log is used.
    Returns None when nothing can be determined.
    """
    stamps: list[float] = []
    try:
        stamps.append(_PACMAN_SYNC_DIR.stat().st_mtime)
        stamps.extend(p.stat().st_mtime for p in _PACMAN_SYNC_DIR.iterdir())
    except OSError:
        pass
    log_stamp = _last_sync_from_log()
    if log_stamp is not None:
        stamps.append(log_stamp)
    if not stamps:
        return None
    now = time.time() if now is None else now
    return max(0.0, (now - max(stamps)) / 86400)


def _last_sync_from_log() -> float | None:
    try:
        with _PACMAN_LOG.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - _PACMAN_LOG_TAIL_BYTES))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    matches = _SYNC_LOG_RE.findall(tail)
    if not matches:
        return None
    day, hour = matches[-1]
    try:
        return time.mktime(time.strptime(f"{day} {hour}", "%Y-%m-%d %H:%M"))
    except ValueError:
        return None


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
