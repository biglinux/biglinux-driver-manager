# big-driver-manager-cli

The part of [Big Driver Manager](https://github.com/biglinux/biglinux-driver-manager)
that changes the system: hardware detection, the driver database and the
installation of drivers, kernels and Mesa. The graphical interface only draws
and asks this package to act.

---

## How the two packages fit together

```
biglinux-driver-manager      the GTK interface (ui/, utils/, icons, notifications)
        │  imports core/ from /usr/share/big-driver-manager-cli
        │  pkexec big-driver-manager-cli <verb>   for anything that needs root
        ▼
big-driver-manager-cli       core/, assets/ (device IDs, firmware, printers,
                             scanners, Mesa variants), the device-ID cache
```

The interface never asks polkit for pacman itself. It asks for one of the verbs
below, with its own polkit action (`br.com.biglinux.drivermanager.cli`), and the
command line refuses anything it does not know before running pacman or mhwd.
The live session and the installer, already root, use the same command.

## Usage

```bash
big-driver-manager-cli install [--reinstall | --overwrite-all] -- PACKAGE...
big-driver-manager-cli remove  [--recursive | --cascade]       -- PACKAGE...
big-driver-manager-cli mhwd install|remove pci|usb CONFIG [--force]
```

| Verb | pacman |
|---|---|
| `install` | `-S --noconfirm --needed` |
| `install --reinstall` | `-S --noconfirm` |
| `install --overwrite-all` | `-S --noconfirm --needed --overwrite '*'` (Mesa variant switch) |
| `remove` | `-R --noconfirm` |
| `remove --recursive` | `-Rns --noconfirm` |
| `remove --cascade` | `-Rnc --noconfirm` |

Exit codes: `2` invalid request, `77` not running as root.

## Development

The two repositories are expected side by side; the interface finds the core in
`../big-driver-manager-cli` (or `$BDM_CLI_DIR`, or the installed path).

```bash
python -m pytest
ruff check . && ruff format --check .
```

### Building and publishing

Build the package with [gitrepo](https://github.com/big-comm/gitrepo), choosing
**BigLinux** as the destination. To test locally:

```bash
cd pkgbuild && makepkg -si
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
