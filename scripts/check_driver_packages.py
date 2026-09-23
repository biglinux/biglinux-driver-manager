#!/usr/bin/env python3
"""Report where each package in assets/device-ids comes from.

For every device-ids/*/pkg, checks the enabled pacman repositories
(``pacman -Si``) and, if absent there, the AUR RPC. Exits with status 1
when a package exists in neither, so renamed/removed packages are caught
before users hit "target not found".

Usage: scripts/check_driver_packages.py [--assets PATH]
"""

import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

_DEFAULT_ASSETS = (
    Path(__file__).resolve().parent.parent / "usr/share/big-driver-manager/assets"
)
_AUR_RPC = "https://aur.archlinux.org/rpc/v5/info"


def _in_repo(pkg: str) -> bool:
    return subprocess.run(["pacman", "-Si", pkg], capture_output=True).returncode == 0


def _in_aur(pkgs: list[str]) -> set[str]:
    if not pkgs:
        return set()
    query = urllib.parse.urlencode([("arg[]", p) for p in pkgs])
    with urllib.request.urlopen(f"{_AUR_RPC}?{query}", timeout=30) as resp:
        data = json.load(resp)
    return {r["Name"] for r in data.get("results", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--assets", type=Path, default=_DEFAULT_ASSETS)
    args = parser.parse_args()

    packages = {
        pkg_file.parent.name: pkg_file.read_text().strip()
        for pkg_file in sorted((args.assets / "device-ids").glob("*/pkg"))
    }
    not_in_repo = [p for p in packages.values() if not _in_repo(p)]
    aur = _in_aur(not_in_repo)

    missing = 0
    for module, pkg in packages.items():
        if pkg not in not_in_repo:
            source = "repo"
        elif pkg in aur:
            source = "AUR"
        else:
            source = "MISSING"
            missing += 1
        print(f"{source:8} {module:22} {pkg}")

    in_repo = len(packages) - len(not_in_repo)
    print(
        f"\n{in_repo} in repos, {len(aur)} AUR-only, {missing} missing "
        f"({len(packages)} total)"
    )
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
