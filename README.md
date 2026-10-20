# Big Driver Manager

Drivers, kernels and Mesa for BigLinux and BigCommunity. One repository, one
PKGBUILD, two packages:

| Directory | Package | What it is |
|---|---|---|
| [`big-driver-manager-cli/`](big-driver-manager-cli/README.md) | `big-driver-manager-cli` | The command line (`big-drivers`) and the core: hardware detection, graphics drivers, kernels with their modules. Runs in the live session, the installer and at boot; no graphical dependencies. |
| [`biglinux-driver-manager/`](biglinux-driver-manager/README.md) | `biglinux-driver-manager` | The GTK interface. It imports the core from `big-driver-manager-cli`. |

`pkgbuild/PKGBUILD` builds both at once (`pkgbase=biglinux-driver-manager`),
so the interface and the core it imports always ship the same version.

## Development

```bash
(cd big-driver-manager-cli && python -m pytest)
(cd biglinux-driver-manager && python -m pytest)   # finds the core in ../big-driver-manager-cli
ruff check . && ruff format --check .
```
