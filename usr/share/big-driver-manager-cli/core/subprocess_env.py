"""Shared subprocess environment helper for deterministic command output."""

import os


def subprocess_env() -> dict[str, str]:
    """Return a subprocess environment with LC_* fully pinned to C.

    LC_ALL alone is insufficient when callers of this helper also set
    LC_MESSAGES, LC_NUMERIC, etc. in their own environment — those
    category-specific vars override LANG but not LC_ALL. Still, we
    clear every LC_* to keep pacman/mhwd output parseable even if the
    child process resets LC_ALL internally.
    """
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("LC_"):
            env[key] = "C"
    env["LANG"] = "C"
    env["LC_ALL"] = "C"
    return env
