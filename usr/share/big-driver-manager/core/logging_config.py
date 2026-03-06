#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Logging Configuration

This module provides a centralized logging configuration with
file rotation and console output support.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

from core.constants import LOG_DIR, LOG_FILE, APP_NAME


def setup_logging(
    level: int = logging.INFO,
    console_output: bool = True,
    file_output: bool = True,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> logging.Logger:
    """
    Configure and return the application logger.

    Args:
        level: Logging level (default: INFO)
        console_output: Whether to output to console
        file_output: Whether to output to file
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(level)

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    simple_formatter = logging.Formatter("%(levelname)s: %(message)s")

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)

    # File handler with rotation
    if file_output:
        try:
            # Ensure log directory exists
            os.makedirs(LOG_DIR, exist_ok=True)

            file_handler = RotatingFileHandler(
                LOG_FILE, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)  # Log everything to file
            file_handler.setFormatter(detailed_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # If we can't create file handler, just log to console
            if console_output:
                logger.warning(f"Could not create log file: {e}")

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Optional name for the logger (creates child logger)

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"{APP_NAME}.{name}")
    return logging.getLogger(APP_NAME)


# Convenience function to initialize logging at application start
def init_app_logging(debug: bool = False) -> logging.Logger:
    """
    Initialize application logging with sensible defaults.

    Args:
        debug: If True, set logging level to DEBUG

    Returns:
        Configured application logger
    """
    level = logging.DEBUG if debug else logging.INFO
    return setup_logging(level=level)
