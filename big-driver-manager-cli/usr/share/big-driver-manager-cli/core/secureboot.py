#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Secure Boot (BigLinux)

Secure Boot with the BigLinux key comes from one package, big-secureboot
(big-comm/big-kernel). Installing it enables it: it puts Fedora's shim and a
GRUB signed with the BigLinux key in the ESP, adds their boot entry and
the kexec and IOMMU settings Easy Anti-Cheat checks, and schedules the key,
which the user confirms once on the blue screen of the next boot
(MokManager). Booted with Secure Boot, linux-big locks itself down. Removing
the package takes all that out again. So enabling is installing, disabling is removing, both through
the command line's usual pacman verbs; nothing here needs root.

The state is read without root, too:

- UEFI: /sys/firmware/efi exists.
- Secure Boot on: the SecureBoot EFI variable, which any user may read.
- The key enrolled: not readable by a user (MokListRT is root's), but implied:
  with Secure Boot on, a system with big-secureboot only boots through its
  shim and GRUB once the key is enrolled.
"""

import os
from pathlib import Path

from core.base_manager import BaseManager

PACKAGE = "big-secureboot"
# The password the package sets for the blue screen (big-secureboot enable).
MOK_PASSWORD = "big"

_EFI_DIR = Path("/sys/firmware/efi")
_SECURE_BOOT_VAR = _EFI_DIR / "efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
_DB_VAR = _EFI_DIR / "efivars/db-d719b2cb-3d3a-4596-a3bc-dad00e67656f"
_EFIVARS = _EFI_DIR / "efivars"
# shim is signed with Microsoft's CAs for other systems. "Secured-core" PCs
# leave both out of db until "Allow Microsoft 3rd Party UEFI CA" is turned
# on in the firmware settings: shim would never start there.
_THIRD_PARTY_CAS = (b"Microsoft Corporation UEFI CA 2011", b"Microsoft UEFI CA 2023")
# Room the key and the request take in the firmware's variable storage,
# with margin (the same figure big-secureboot checks).
NVRAM_NEEDED = 8192

# States, in the order a user goes through them.
UNAVAILABLE = "unavailable"  # not BigCommunity, or not UEFI: nothing to show
NO_CA = "no_ca"  # the firmware does not accept shim: an option to turn on first
NO_SPACE = "no_space"  # no room in the firmware for the key
OFF = "off"  # can be enabled
PENDING = "pending"  # installed; key to confirm and/or Secure Boot to turn on
ACTIVE = "active"  # Secure Boot on with the BigLinux key: locked down


def secure_boot_enabled(var: Path = _SECURE_BOOT_VAR) -> bool:
    """The SecureBoot variable: 4 bytes of attributes, then 1 when on."""
    try:
        data = var.read_bytes()
    except OSError:
        return False
    return len(data) >= 5 and data[4] == 1


def firmware_trusts_shim(var: Path = _DB_VAR) -> bool:
    """db holds one of the CAs shim is signed with. No db (setup mode, or
    not readable) tells nothing yet, so it does not block."""
    try:
        data = var.read_bytes()
    except OSError:
        return True
    return any(ca in data for ca in _THIRD_PARTY_CAS)


def nvram_free(path: Path = _EFIVARS) -> int | None:
    """Free bytes in the firmware's variable storage, as efivarfs reports
    it; None when the kernel does not."""
    try:
        info = os.statvfs(path)
    except OSError:
        return None
    if not info.f_blocks:
        return None
    return info.f_bavail * info.f_frsize


def state(
    *,
    uefi: bool,
    available: bool,
    installed: bool,
    secure_boot: bool,
    trusts_shim: bool = True,
    free: int | None = None,
) -> str:
    """Where a machine is on the way to the anti-cheat boot."""
    if not uefi or not (available or installed):
        return UNAVAILABLE
    if not installed:
        if not trusts_shim:
            return NO_CA
        if free is not None and free < NVRAM_NEEDED:
            return NO_SPACE
        return OFF
    if not secure_boot:
        return PENDING
    return ACTIVE


class SecureBootManager(BaseManager):
    """Reads the state and installs or removes big-secureboot."""

    def __init__(self, package_manager, repo_packages, **kwargs) -> None:
        """*package_manager* answers is_package_installed(); *repo_packages*
        returns the names the repositories offer (fetch_repo_package_set)."""
        super().__init__(**kwargs)
        self._packages = package_manager
        self._repo_packages = repo_packages

    def current_state(self) -> str:
        return state(
            uefi=_EFI_DIR.is_dir(),
            available=PACKAGE in self._repo_packages(),
            installed=self._packages.is_package_installed(PACKAGE),
            secure_boot=secure_boot_enabled(_SECURE_BOOT_VAR),
            trusts_shim=firmware_trusts_shim(_DB_VAR),
            free=nvram_free(_EFIVARS),
        )

    def enable(self, operation_name: str, **callbacks) -> None:
        """Install big-secureboot; its install script enables it."""
        self.run_pacman_command(
            ["-S", "--noconfirm", "--needed", PACKAGE],
            operation_name=operation_name,
            **callbacks,
        )

    def disable(self, operation_name: str, **callbacks) -> None:
        """Remove big-secureboot alone: its dependencies (mokutil, efibootmgr)
        may serve something else."""
        self.run_pacman_command(
            ["-R", "--noconfirm", PACKAGE],
            operation_name=operation_name,
            **callbacks,
        )
