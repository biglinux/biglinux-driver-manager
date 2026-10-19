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

## Graphics drivers (replaces mhwd and mhwd-biglinux)

```bash
big-driver-manager-cli gpu detect [--json]           # display controllers, kernels, VM
big-driver-manager-cli gpu plan   [--free] [--json]  # what install would do
big-driver-manager-cli gpu install [--free | --from-cmdline] [--root DIR] [--pmconfig FILE]
big-driver-manager-cli gpu mode hybrid|nvidia|integrated
big-driver-manager-cli gpu status [--json]
big-driver-manager-cli gpu check                  # pacman hook after a kernel install
```

What `install` decides, and from where:

| Question | Answer from |
|---|---|
| Which GPUs | `/sys/bus/pci/devices`, PCI class 0x03xx, by vendor ID |
| Which NVIDIA driver | NVIDIA's `supported-gpus.json` (nvidia-driver-assistant): no legacy branch → current driver with the open module; `580.xx` → `nvidia-580xx`; `470.xx` → `nvidia-470xx` (X11 only); older → nouveau. Several chips: the oldest branch, open module only if all support it |
| Which module package | every installed kernel's `pkgbase` → `<pkgbase>-nvidia[-open\|-580xx\|-470xx]`; a kernel without one gets the `-dkms` driver and its headers. linux-big, linux-xanmod, linux-xanmod-lts and linuxNN(-comm) need nothing special |
| Hybrid laptop | `nvidia-prime`, `switcheroo-control`; RTD3 power management when the chip supports it |
| Virtual machine | VirtualBox, VMware or QEMU/KVM guest tools and their services |
| Broadcom wl Wi-Fi | `<pkgbase>-broadcom-wl` per kernel |

`--root` and `--pmconfig` are for the live session and the installer. pacman
runs install scriptlets inside `--root`, as root, so both are honoured only when
they belong to root alone (the target and its `etc`, `usr`, `usr/bin`, `usr/lib`;
the configuration file and its directory: owned by root, not group/other
writable, not symbolic links) -- a tree or repository a user prepared is refused,
whoever runs the command.

GPU modes on an integrated + NVIDIA machine: `hybrid` (default: the integrated
GPU drives the screen, NVIDIA on demand and asleep otherwise), `nvidia` (NVIDIA
stays awake and is the Xorg primary GPU; the greeter of LightDM, SDDM or GDM and
X11 sessions get the xrandr PRIME setup, Wayland is unaffected), `integrated`
(NVIDIA modules never load). `biglinux-gpu-manager` is kept as a compatibility
command.

Services: `big-driver-manager-gpu.service` runs `gpu boot` before the display
manager; `big-driver-manager-live.service` installs the drivers on live media
from `/opt/mhwd/pacman-mhwd.conf`, honouring `driver=free|nonfree` and
`bdm.gpu=MODE` (or the older `bignvidia=`) on the kernel command line.

A pacman hook (`big-driver-manager-kernel.hook`) runs `gpu check` whenever a
kernel is installed or upgraded: on machines using the NVIDIA proprietary
driver it names the module package the new kernel still lacks (pacman cannot
install it from inside its own transaction).

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
