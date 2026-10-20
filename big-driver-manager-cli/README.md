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

## big-drivers, from the terminal

`big-drivers` is the same program under a name meant for people
(`big-driver-manager` opens the graphical interface):

```bash
big-drivers kernel list                 # kernels in the repositories, installed ones marked
big-drivers kernel list --installed [--json]
big-drivers kernel install linux-big    # + headers + the modules the running kernel uses
big-drivers kernel remove linux612      # + its modules; never the running kernel
big-drivers kernel obsolete             # installed kernels that left the repositories
big-drivers gpu                         # graphics cards and their drivers
big-drivers gpu install                 # the drivers this machine needs
```

- `kernel install` does what the interface does: the kernel, its headers and,
  for every module package of the running kernel (NVIDIA, Broadcom Wi-Fi,
  VirtualBox...), the same module for the new kernel. linux-big is not offered
  while a module the machine needs is missing for it, or still being published.
- It shows what it will do and asks first (`-y`/`--yes` skips the question;
  without a terminal it does nothing unless given `--yes`).
- Not root: it asks for the password through pkexec (polkit), in the terminal.
- mhwd-kernel's options keep working: `big-drivers -li`, `-l`, `-i NAME`,
  `-r NAME`.
- Colours and emphasis only on a terminal: pipes, the interface and the journal
  get plain text. `--no-color`, `--color=never|always` or `NO_COLOR=1` change it.
- Messages, help and the polkit prompt are translated (`locale/*.po`, domain
  `big-driver-manager-cli`). After changing a message, run
  `scripts/update-translations.sh`: it refreshes the template, merges the
  catalogs, compiles the `.mo` files and the polkit policy's translations.

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
big-driver-manager-cli gpu install [--free | --from-cmdline] [--nvidia-branch current|580xx|470xx]
                                   [--root DIR] [--pmconfig FILE]
big-driver-manager-cli gpu remove                 # the NVIDIA proprietary driver
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

Choosing another NVIDIA branch (or the other module flavour) replaces the
installed one: its packages are removed without dependency checks -- the new
branch provides `nvidia-utils` again in the next step -- only after every new
package was found in the repositories, and restored from the cache if the
installation fails.

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

While mhwd is still installed (BigLinux media keep mhwd-live and the mhwdcfg
installer job), `big-driver-manager-mhwd-compat.hook` keeps patching mhwd's
kernel list for linux-big and linux-xanmod, as mhwd-biglinux did, and
`big-driver-manager-live.service` stays out of the way of mhwd-live.

If the proprietary driver does not come up -- its install failed in the live
session, or the module loaded but left an NVIDIA card without a driver -- the
NVIDIA modules are unloaded and nouveau (Mesa's NVIDIA driver) is loaded before
the display manager starts, instead of a black screen. This runs after `gpu
install` on the running system and in `gpu boot` on every boot; the reason is
kept in `/run/big-driver-manager/nvidia-fallback` and shown by `gpu status`.
It needs nouveau to be loadable: `modprobe.blacklist=nouveau` (and modprobe.d)
allow an explicit load, `module_blacklist=nouveau` does not.

The driver can also take the card and the display still never come up (the
compositor or the greeter fails with it). Two guards cover that, both only
when the proprietary driver drives an NVIDIA card and at most once per boot:
`big-driver-manager-display-check.service` waits up to 2 minutes after the
display manager for a login screen or session in logind, and drop-ins add
`OnFailure=big-driver-manager-display-failed.service` to GDM, SDDM and LightDM.
Either moves the card to nouveau and restarts the display manager. On an
installed system the next boots use nouveau too (modprobe.d blocks the NVIDIA
modules, modules-load.d loads nouveau, the reason is in
`/var/lib/big-driver-manager/nvidia-fallback`) until the NVIDIA driver is
installed, switched or removed again; when the NVIDIA modules cannot be
unloaded right away (the console holds nvidia_drm's framebuffer) the system
restarts once. In the live session nothing persists and it never restarts.

A pacman hook (`big-driver-manager-kernel.hook`) runs `gpu check` whenever a
kernel is installed or upgraded: on machines using the NVIDIA proprietary
driver it names the module package the new kernel still lacks (pacman cannot
install it from inside its own transaction).

## Development

This directory and the interface's (`../biglinux-driver-manager`) share one
repository and one PKGBUILD; the interface finds the core here (or in
`$BDM_CLI_DIR`, or the installed path).

```bash
python -m pytest
ruff check . && ruff format --check .
```

End to end against the real pacman, in a throwaway container (never on a real
system -- it installs and removes packages):

```bash
docker run --rm -v "$PWD":/src:ro \
    -v /usr/share/nvidia-driver-assistant/supported-gpus:/nvda:ro \
    manjarolinux/base:latest bash /src/tests/e2e/gpu-flow.sh
```

### Building and publishing

Build the package with [gitrepo](https://github.com/big-comm/gitrepo), choosing
**BigLinux** as the destination. To test locally:

```bash
cd ../pkgbuild && makepkg -si   # builds both packages
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
