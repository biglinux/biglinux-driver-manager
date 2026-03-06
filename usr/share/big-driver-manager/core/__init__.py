"""Core functionality package for Big Driver Manager application."""

from core.constants import (
    APP_NAME,
    APP_ID,
    APP_VERSION,
    CONFIG_DIR,
    SETTINGS_FILE,
)
from core.exceptions import (
    KernelManagerError,
    PackageNotFoundError,
    InstallationError,
    RemovalError,
    PrivilegeError,
)
from core.base_manager import BaseManager
from core.logging_config import setup_logging, get_logger, init_app_logging

__all__ = [
    "APP_NAME",
    "APP_ID",
    "APP_VERSION",
    "CONFIG_DIR",
    "SETTINGS_FILE",
    "KernelManagerError",
    "PackageNotFoundError",
    "InstallationError",
    "RemovalError",
    "PrivilegeError",
    "BaseManager",
    "setup_logging",
    "get_logger",
    "init_app_logging",
]
