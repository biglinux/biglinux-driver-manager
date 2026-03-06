#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kernel Manager Application - Main Entry Point

This module serves as the entry point for the Kernel Manager application,
which allows users to manage and install different kernel versions and
Mesa drivers on Manjaro Linux.
"""

import signal
import sys

from ui.application import KernelManagerApplication


def main() -> int:
    """Main entry point for the application."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)

    app = KernelManagerApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
