"""Shared subprocess environment helper for deterministic command output."""

import os


def subprocess_env() -> dict[str, str]:
    """Return a subprocess environment with LANG=C for deterministic output."""
    env = os.environ.copy()
    env["LANG"] = "C"
    env["LC_ALL"] = "C"
    return env
