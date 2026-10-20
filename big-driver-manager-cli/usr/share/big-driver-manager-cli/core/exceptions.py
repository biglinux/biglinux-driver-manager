#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Custom Exceptions

This module defines custom exception classes for better error handling
throughout the application.
"""


class KernelManagerError(Exception):
    """Base exception for all Kernel Manager errors."""

    pass


class PackageNotFoundError(KernelManagerError):
    """Raised when a package cannot be found in repositories."""

    def __init__(self, package_name: str, message: str | None = None):
        self.package_name = package_name
        self.message = message or f"Package not found: {package_name}"
        super().__init__(self.message)


class InstallationError(KernelManagerError):
    """Raised when package installation fails."""

    def __init__(
        self,
        package_name: str,
        return_code: int | None = None,
        message: str | None = None,
    ):
        self.package_name = package_name
        self.return_code = return_code
        self.message = message or f"Failed to install package: {package_name}"
        if return_code is not None:
            self.message += f" (exit code: {return_code})"
        super().__init__(self.message)


class RemovalError(KernelManagerError):
    """Raised when package removal fails."""

    def __init__(
        self,
        package_name: str,
        return_code: int | None = None,
        message: str | None = None,
    ):
        self.package_name = package_name
        self.return_code = return_code
        self.message = message or f"Failed to remove package: {package_name}"
        if return_code is not None:
            self.message += f" (exit code: {return_code})"
        super().__init__(self.message)


class PrivilegeError(KernelManagerError):
    """Raised when elevated privileges are required but not available."""

    def __init__(self, operation: str | None = None, message: str | None = None):
        self.operation = operation
        self.message = message or "Elevated privileges required"
        if operation:
            self.message = f"Elevated privileges required for: {operation}"
        super().__init__(self.message)
