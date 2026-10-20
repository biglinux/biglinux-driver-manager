"""Make the core, shipped by big-driver-manager-cli, importable.

The interface only draws; detection, the driver database and everything that
changes the system live in big-driver-manager-cli. Import this module before
anything from ``core``.
"""

import os
import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent


def _candidates() -> list[Path]:
    paths = []
    if os.environ.get("BDM_CLI_DIR"):
        paths.append(Path(os.environ["BDM_CLI_DIR"]))
    paths.append(Path("/usr/share/big-driver-manager-cli"))
    # Development: the two repositories cloned side by side.
    paths.append(
        _APP_DIR.parents[2].parent
        / "big-driver-manager-cli"
        / "usr"
        / "share"
        / "big-driver-manager-cli"
    )
    return paths


def core_dir() -> Path:
    for path in _candidates():
        if (path / "core").is_dir():
            return path
    raise ImportError("big-driver-manager-cli not found: install it or set BDM_CLI_DIR")


_dir = str(core_dir())
if _dir not in sys.path:
    sys.path.insert(0, _dir)
