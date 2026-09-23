#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Kernel Manager

This module provides functionality for managing Linux kernels
including listing, installing, and removing kernels.
"""

import json
import os
import platform
import re
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request
from xml.etree import ElementTree
from typing import Callable, TypedDict

from core.base_manager import BaseManager
from core.package_manager import PackageManager
from core.constants import (
    KERNEL_PATTERNS,
    EXCLUDED_PATTERNS,
    KERNEL_ORG_FEED_URL,
    DEFAULT_LTS_VERSIONS,
    CACHYOS_PATTERNS,
)
from core.logging_config import get_logger


class KernelInfo(TypedDict, total=False):
    """Typed dictionary for kernel information."""

    name: str
    version: str
    installed: bool
    repository: str
    rt: bool
    lts: bool
    xanmod: bool
    cachyos: bool
    x64v: int
    obsolete: bool
    # "local": package not in the enabled repos (third-party/self-built);
    # "manual": kernel installed outside pacman (no package at all)
    source: str
    kver: str


def lts_cache_path() -> Path:
    """Where the last kernel.org LTS list is kept (respects XDG_CACHE_HOME)."""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(base) / "big-driver-manager" / "lts_versions.json"


# Every Arch/Manjaro kernel package installs /usr/lib/modules/<kver>/vmlinuz
# plus a "pkgbase" file holding the package name — a name-independent way to
# find kernels (e.g. linux72-comm), including self-compiled ones.
MODULES_DIR = Path("/usr/lib/modules")


def scan_module_kernels(base: Path = MODULES_DIR) -> list[dict[str, str | None]]:
    """Return ``{"kver", "pkgbase"}`` for every bootable kernel in *base*.

    Directories without a ``vmlinuz`` are leftovers (e.g. an old ``build``
    link) and are skipped. ``pkgbase`` is None for kernels not installed by
    a package.
    """
    kernels: list[dict[str, str | None]] = []
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return kernels
    for entry in entries:
        if not (entry / "vmlinuz").exists():
            continue
        try:
            pkgbase = (entry / "pkgbase").read_text(encoding="utf-8").strip() or None
        except OSError:
            pkgbase = None
        kernels.append({"kver": entry.name, "pkgbase": pkgbase})
    return kernels


class KernelManager(BaseManager):
    """Manager for handling Linux kernels."""

    def __init__(self, package_manager: PackageManager | None = None) -> None:
        """Initialize the kernel manager.

        Args:
            package_manager: Optional shared ``PackageManager`` instance.
                Defaults to ``PackageManager.get_default()`` so cache hits
                are shared across managers.
        """
        super().__init__()
        self._logger = get_logger("KernelManager")
        self.package_manager = package_manager or PackageManager.get_default()

        # Use patterns from constants
        self.kernel_patterns = KERNEL_PATTERNS
        self.excluded_patterns = EXCLUDED_PATTERNS
        self._modules_dir = MODULES_DIR
        self._lts_cache_file = lts_cache_path()

        # LTS versions - lazy loaded to avoid blocking startup
        self._lts_versions = None

    @property
    def lts_versions(self) -> list[str]:
        """Get LTS versions, fetching from kernel.org if not cached."""
        if self._lts_versions is None:
            self._lts_versions = self._get_lts_kernel_versions()
        return list(self._lts_versions)

    def get_running_kernel(self) -> str:
        """
        Get the currently running kernel version string.

        Returns:
            The running kernel release string (e.g. "6.12.10-1-MANJARO").
        """
        return platform.release()

    def get_running_kernel_package(self) -> str:
        """
        Get the package name of the currently running kernel.

        Returns:
            The package name of the running kernel, or empty string if not found.
        """
        running_version = self.get_running_kernel()

        # Exact answer: the running kernel's own pkgbase (or its release
        # string for a kernel installed outside pacman)
        for entry in scan_module_kernels(self._modules_dir):
            if entry["kver"] == running_version:
                return entry["pkgbase"] or running_version

        # Get installed kernels and match by version
        installed = self.get_installed_kernels()
        for kernel in installed:
            pkg_version = kernel.get("version", "")
            # The running kernel version often starts with the package version
            if pkg_version and running_version.startswith(pkg_version.split("-")[0]):
                return kernel["name"]

        # Fallback: try to determine from the release string
        # e.g. "6.12.10-1-MANJARO" -> look for linux612
        version_match = re.match(r"(\d+)\.(\d+)", running_version)
        if version_match:
            major = version_match.group(1)
            minor = version_match.group(2)
            possible_name = f"linux{major}{minor}"
            for kernel in installed:
                if kernel["name"] == possible_name:
                    return possible_name

        return ""

    def _get_lts_kernel_versions(self) -> list[str]:
        """
        Get a list of current LTS kernel versions from kernel.org.

        A successful result is cached on disk, so a machine that is offline
        (or behind a proxy/captive portal) keeps using the last known list
        instead of the hardcoded DEFAULT_LTS_VERSIONS, which ages with every
        new LTS release.

        Returns:
            List of LTS kernel versions as strings (e.g. "612" for 6.12).
        """
        lts_versions: list[str] = []
        try:
            req = Request(KERNEL_ORG_FEED_URL)
            with urlopen(req, timeout=5) as response:
                content = response.read()
                root = ElementTree.fromstring(content)
                for item in root.findall(".//item"):
                    title = item.find("title")
                    if title is not None and title.text and ": longterm" in title.text:
                        version_match = re.match(r"(\d+\.\d+).*: longterm", title.text)
                        if version_match:
                            version = version_match.group(1)
                            numeric_version = version.replace(".", "")
                            lts_versions.append(numeric_version)
        except (OSError, ValueError, ElementTree.ParseError) as e:
            self._logger.warning("Failed to get LTS kernel versions: %s", e)

        if lts_versions:
            self._logger.debug(f"Fetched LTS versions: {lts_versions}")
            self._save_lts_cache(lts_versions)
            return lts_versions

        # Feed unreachable or without longterm entries (e.g. a captive portal)
        cached = self._load_lts_cache()
        if cached:
            self._logger.info("Using cached LTS versions: %s", cached)
            return cached
        return DEFAULT_LTS_VERSIONS.copy()

    def _save_lts_cache(self, versions: list[str]) -> None:
        try:
            self._lts_cache_file.parent.mkdir(parents=True, exist_ok=True)
            self._lts_cache_file.write_text(json.dumps(versions), encoding="utf-8")
        except OSError as e:
            self._logger.debug("Cannot write LTS cache: %s", e)

    def _load_lts_cache(self) -> list[str]:
        try:
            data = json.loads(self._lts_cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if isinstance(data, list) and all(
            isinstance(v, str) and v.isdigit() for v in data
        ):
            return data
        return []

    def get_installed_kernels(self) -> list[KernelInfo]:
        """
        Get a list of installed kernels.

        Combines packages whose names match the known kernel patterns with
        whatever /usr/lib/modules reports, so kernels with unusual names
        (linux72-comm, self-built packages) and kernels installed without a
        package are listed too.

        Returns:
            List of installed kernels with their information.
        """
        installed_packages = self.package_manager.get_installed_packages()
        versions = {p["name"]: p["version"] for p in installed_packages}

        kernels: list[KernelInfo] = []
        seen: set[str] = set()
        for package in installed_packages:
            if self._is_kernel_package(package["name"]):
                kernel: KernelInfo = {
                    "name": package["name"],
                    "version": package["version"],
                    "installed": True,
                }
                self._add_kernel_flags(kernel)
                kernels.append(kernel)
                seen.add(package["name"])

        for entry in scan_module_kernels(self._modules_dir):
            pkgbase, kver = entry["pkgbase"], entry["kver"]
            if pkgbase:
                # A stale pkgbase of a removed package is not a kernel
                if pkgbase in seen or pkgbase not in versions:
                    continue
                kernel = {
                    "name": pkgbase,
                    "version": versions[pkgbase],
                    "installed": True,
                }
                seen.add(pkgbase)
            else:
                kernel = {
                    "name": kver,
                    "version": kver,
                    "installed": True,
                    "source": "manual",
                    "kver": kver,
                }
            self._add_kernel_flags(kernel)
            kernels.append(kernel)

        return kernels

    def get_available_kernels(self) -> list[KernelInfo]:
        """
        Get a list of available kernels from repositories.

        Returns:
            List of available kernels with their information.
        """
        # Single pacman query instead of one per pattern
        available_kernels = self._search_kernel_packages("linux")

        # Get installed kernels to mark them
        installed_kernels = self.get_installed_kernels()
        installed_names = [k["name"] for k in installed_kernels]

        # Filter out duplicates and excluded patterns
        filtered_kernels = []
        seen_kernels = set()

        for kernel in available_kernels:
            kernel_name = kernel["name"]

            if any(
                re.search(exclude, kernel_name) for exclude in self.excluded_patterns
            ):
                continue

            kernel_key = f"{kernel_name}-{kernel['version']}"
            if kernel_key in seen_kernels:
                continue

            seen_kernels.add(kernel_key)
            kernel["installed"] = kernel_name in installed_names
            self._add_kernel_flags(kernel)
            filtered_kernels.append(kernel)

        # Installed kernels the repos don't offer still belong on the page.
        # Official-looking names that left the repos are EOL ("obsolete",
        # handled by compute_obsolete_kernels); anything else is a
        # third-party/self-built package or a manual install.
        repo_names = {k["name"] for k in filtered_kernels}
        for kernel in installed_kernels:
            if kernel["name"] in repo_names:
                continue
            if kernel.get("source") != "manual":
                if self._is_kernel_package(kernel["name"]):
                    continue  # EOL official kernel -> obsolete alert
                kernel = {**kernel, "source": "local"}
            filtered_kernels.append(kernel)

        return sorted(filtered_kernels, key=lambda k: (k["name"], k["version"]))

    def _search_kernel_packages(self, pattern: str) -> list[KernelInfo]:
        """
        Search for kernel packages matching a pattern.

        Args:
            pattern: Regex pattern to search for.

        Returns:
            List of matching packages.
        """
        cmd = ["pacman", "-Ss", f"^{pattern}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            return []

        packages = []
        for line in result.stdout.strip().split("\n"):
            if not line or line.startswith(" "):
                continue

            match = re.match(r"([^\s]+)/([^\s]+)\s+([^\s]+)", line)
            if match:
                package_name = match.group(2)
                package_version = match.group(3)

                if self._is_kernel_package(package_name):
                    packages.append(
                        {
                            "name": package_name,
                            "version": package_version,
                            "repository": match.group(1),
                        }
                    )

        return packages

    def _is_kernel_package(self, package_name: str) -> bool:
        """
        Check if a package is a true kernel package (not a module).

        Args:
            package_name: Name of the package.

        Returns:
            True if it's a kernel package, False otherwise.
        """
        is_kernel = any(
            re.match(pattern, package_name) for pattern in self.kernel_patterns
        )
        is_excluded = any(
            re.search(exclude, package_name) for exclude in self.excluded_patterns
        )
        return is_kernel and not is_excluded

    def _add_kernel_flags(self, kernel: KernelInfo) -> None:
        """
        Add flags to identify kernel types (RT, LTS, etc.)

        Args:
            kernel: Kernel dictionary to update with flags.
        """
        kernel_name = kernel["name"]

        # RT flag
        if "-rt" in kernel_name:
            kernel["rt"] = True

        # LTS flag
        if "-lts" in kernel_name:
            kernel["lts"] = True
        elif "xanmod" not in kernel_name and re.match(r"^linux\d+$", kernel_name):
            version_match = re.match(r"^linux(\d+)$", kernel_name)
            if version_match and version_match.group(1) in self.lts_versions:
                kernel["lts"] = True

        # XanMod flag
        if "xanmod" in kernel_name:
            kernel["xanmod"] = True

        # CachyOS flag
        if any(re.match(p, kernel_name) for p in CACHYOS_PATTERNS):
            kernel["cachyos"] = True

        # Optimized build flags
        match = re.search(r"-x64v(\d)", kernel_name)
        if match:
            kernel["optimized"] = True
            kernel["opt_level"] = match.group(1)

    def get_modules_for_install(self, kernel_name: str) -> list[str]:
        """Public entry point: list module packages to install with *kernel_name*.

        Equivalent to :meth:`_get_kernel_modules`; exposed so UI code does
        not need to touch private helpers when building the install plan.
        """
        return self._get_kernel_modules(kernel_name)

    def get_modules_for_remove(self, kernel_name: str) -> list[str]:
        """Public entry point: list installed module packages of *kernel_name*.

        Equivalent to :meth:`_get_installed_kernel_modules`.
        """
        return self._get_installed_kernel_modules(kernel_name)

    def _get_kernel_modules(self, kernel_name: str) -> list[str]:
        """
        Detect modules installed on the running kernel and return equivalent
        module packages for the target kernel.

        This detects packages like nvidia, virtualbox-host-modules, headers, etc.
        that are installed for the current running kernel and maps them to the
        target kernel name, keeping the same version suffixes (e.g. nvidia-550xx).

        Args:
            kernel_name: Name of the target kernel (e.g. "linux619").

        Returns:
            List of module package names to install with the target kernel.
        """
        running_kernel = self.get_running_kernel_package()
        if not running_kernel:
            self._logger.warning(
                "Could not detect running kernel, falling back to headers only"
            )
            return [f"{kernel_name}-headers"]

        self._logger.info(f"Detecting modules from running kernel: {running_kernel}")

        # Get all installed packages that are modules of the running kernel
        installed = self.package_manager.get_installed_packages()
        modules = []

        for pkg in installed:
            pkg_name = pkg["name"]
            # Check if package is a module of the running kernel (e.g. linux618-headers, linux618-nvidia-550xx)
            if pkg_name.startswith(f"{running_kernel}-"):
                suffix = pkg_name[
                    len(running_kernel) :
                ]  # e.g., "-headers", "-nvidia-550xx"
                target_module = f"{kernel_name}{suffix}"
                modules.append(target_module)
                self._logger.debug(f"Detected module: {pkg_name} -> {target_module}")

        # Always ensure headers are included
        headers_pkg = f"{kernel_name}-headers"
        if headers_pkg not in modules:
            modules.insert(0, headers_pkg)

        # Verify which modules exist in the repositories (single query)
        verified_modules = self._filter_existing_in_repos(modules, kernel_name)

        if not verified_modules:
            # Only include headers if they actually exist in repos
            if self._package_available_in_repos(headers_pkg):
                verified_modules = [headers_pkg]
            else:
                self._logger.warning(
                    "No modules found in repos for %s (not even headers)", kernel_name
                )
                verified_modules = []

        self._logger.info(f"Modules to install for {kernel_name}: {verified_modules}")
        return verified_modules

    def _filter_existing_in_repos(
        self, packages: list[str], kernel_name: str
    ) -> list[str]:
        """Return only packages that exist in the repositories.

        Uses a single ``pacman -Ssq ^<kernel>-`` call to fetch all available
        modules for the target kernel, then filters the requested list.
        """
        if not packages:
            return []
        cmd = ["pacman", "-Ssq", f"^{kernel_name}-"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            # Kernel has no modules at all — only the base package may exist
            return []
        available = set(result.stdout.strip().splitlines())
        return [p for p in packages if p in available]

    def _package_available_in_repos(self, package_name: str) -> bool:
        """Check if a single package exists in the repositories."""
        cmd = ["pacman", "-Ssq", f"^{package_name}$"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return (
            result.returncode == 0
            and package_name in result.stdout.strip().splitlines()
        )

    @staticmethod
    def compute_obsolete_kernels(
        installed: list[KernelInfo],
        available: list[KernelInfo],
        running_pkg: str,
    ) -> list[KernelInfo]:
        """Return the subset of *installed* kernels no longer in *available*.

        Pure function — takes pre-fetched lists so callers that already have
        them (e.g. the main window) don't trigger duplicate pacman queries.
        The running kernel is never flagged as obsolete even if its package
        is missing from the repos (removing it would soft-brick the system).
        """
        available_names = {k["name"] for k in available}
        obsolete: list[KernelInfo] = []
        for kernel in installed:
            name = kernel["name"]
            if name == running_pkg:
                continue
            # Not from the repos is not the same as end-of-life: third-party
            # and manual kernels are listed with their origin instead.
            if kernel.get("source") in ("local", "manual"):
                continue
            if name not in available_names:
                kernel = {**kernel, "obsolete": True}
                obsolete.append(kernel)
        return obsolete

    def get_obsolete_kernels(self) -> list[KernelInfo]:
        """Return kernels that are installed but no longer available in repos.

        These are kernels that should be removed because their packages have
        been dropped from the repositories (e.g. EOL kernels).
        """
        installed = self.get_installed_kernels()
        available = self.get_available_kernels()
        running_pkg = self.get_running_kernel_package()
        obsolete = self.compute_obsolete_kernels(installed, available, running_pkg)
        self._logger.info("Obsolete kernels: %s", [k["name"] for k in obsolete])
        return obsolete

    def install_kernel(
        self,
        kernel: KernelInfo,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
        packages: list[str] | None = None,
    ) -> None:
        """
        Install a kernel and its associated modules.

        Args:
            kernel: The kernel to install (dict with at least "name").
            progress_callback: Callback function for progress updates.
            output_callback: Callback function for command output.
            complete_callback: Callback function for completion notification.
            packages: Pre-computed package list. When provided, skips module detection.
        """
        kernel_name = kernel["name"]
        if packages is None:
            modules = self._get_kernel_modules(kernel_name)
            packages = [kernel_name] + modules

        self._logger.info(f"Installing kernel: {kernel_name}")

        # Use base manager's run_pacman_command
        args = ["-S", "--noconfirm"] + packages
        self.run_pacman_command(
            args=args,
            progress_callback=progress_callback,
            output_callback=output_callback,
            complete_callback=complete_callback,
            operation_name=f"Installing {kernel_name}",
        )

    def _get_installed_kernel_modules(self, kernel_name: str) -> list[str]:
        """Return modules of *kernel_name* that are currently installed.

        Unlike ``_get_kernel_modules`` this does NOT verify packages against
        the repos (``pacman -Si``).  It simply lists installed packages whose
        name starts with ``<kernel_name>-``.  This is much faster and is the
        right approach for *remove* operations.
        """
        installed = self.package_manager.get_installed_packages()
        prefix = f"{kernel_name}-"
        return [p["name"] for p in installed if p["name"].startswith(prefix)]

    def remove_kernel(
        self,
        kernel: KernelInfo,
        progress_callback: Callable | None = None,
        output_callback: Callable | None = None,
        complete_callback: Callable | None = None,
        packages: list[str] | None = None,
    ) -> None:
        """
        Remove a kernel and its modules.

        Args:
            kernel: The kernel to remove (dict with at least "name").
            progress_callback: Callback function for progress updates.
            output_callback: Callback function for command output.
            complete_callback: Callback function for completion notification.
            packages: Pre-computed package list. When provided, skips module detection.
        """
        kernel_name = kernel["name"]
        if packages is None:
            modules = self._get_installed_kernel_modules(kernel_name)
            packages = [kernel_name] + modules

        if not packages:
            self._output(output_callback, "No packages to remove.")
            if complete_callback:
                complete_callback(True)
            return

        self._logger.info(f"Removing kernel: {kernel_name}")

        # Use base manager's run_pacman_command
        args = ["-R", "--noconfirm"] + packages
        self.run_pacman_command(
            args=args,
            progress_callback=progress_callback,
            output_callback=output_callback,
            complete_callback=complete_callback,
            operation_name=f"Removing {kernel_name}",
        )
