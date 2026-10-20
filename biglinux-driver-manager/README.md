<p align="center">
  <img src="usr/share/icons/hicolor/scalable/apps/big-driver-manager.svg" alt="Big Driver Manager" width="128" height="128">
</p>

<h1 align="center">Big Driver Manager</h1>

<p align="center">
  A modern graphical tool for managing Linux kernels and Mesa video drivers on Arch-based systems.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/GTK-4.0-4A86CF?logo=gtk&logoColor=white" alt="GTK 4.0">
  <img src="https://img.shields.io/badge/Adwaita-1.0-4A86CF" alt="Adwaita">
  <img src="https://img.shields.io/badge/Platform-Arch%20Linux-1793D1?logo=archlinux&logoColor=white" alt="Arch Linux">
  <img src="https://img.shields.io/badge/Translations-29%20languages-green" alt="29 Languages">
</p>

---

## Overview

**Big Driver Manager** is a GTK4/Adwaita desktop application designed for [BigLinux](https://www.biglinux.com.br/) and other Arch-based distributions. It provides an intuitive graphical interface for two critical system management tasks:

- **Kernel Management** — Install, remove, and switch between available Linux kernels with full visibility into version, type (LTS, RT, Xanmod), and current usage status.
- **Mesa Video Driver Management** — Switch between Mesa driver variants (Stable, Amber, TKG-Stable, TKG-Git) with automated conflict resolution and clear risk descriptions.

## Screenshots

> *Application uses system accent colors and follows GNOME/Adwaita design guidelines.*

## Features

### Kernel Management
- View all installed kernels with version details
- Identify the currently running kernel at a glance
- Browse and install available kernels from the repository
- Safely remove unused kernels with confirmation dialogs
- Badge indicators for **LTS**, **RT**, and **In Use** status

### Mesa Video Driver Management
- Switch between four Mesa driver variants:
  - **Stable** — Official Mesa release (Recommended)
  - **Amber** — Classic OpenGL for legacy hardware
  - **TKG-Stable** — Custom performance-patched build
  - **TKG-Git** — Bleeding-edge development version
- Automatic conflict resolution during driver switching
- Clear risk labels: *Recommended*, *Legacy*, *Performance*, *DEV*

### User Experience
- Modern GTK4/Adwaita interface with dark theme support
- System accent color integration on tab buttons
- Asynchronous data loading with spinner indicators
- Real-time terminal output during operations
- Progress tracking for install/remove operations
- Toast notifications for user feedback

### Internationalization
- Full translation support via GNU gettext
- **29 languages** included: Bulgarian, Czech, Danish, German, Greek, English, Spanish, Estonian, Finnish, French, Hebrew, Croatian, Hungarian, Icelandic, Italian, Japanese, Korean, Dutch, Norwegian, Polish, Portuguese, Brazilian Portuguese, Romanian, Russian, Slovak, Swedish, Turkish, Ukrainian, and Chinese

## Architecture

The interface only draws. Detection, the driver database and everything that
changes the system live in [big-driver-manager-cli](https://github.com/biglinux/big-driver-manager-cli),
which this package depends on: `core/` is imported from
`/usr/share/big-driver-manager-cli`, and every operation that needs root runs
as `pkexec big-driver-manager-cli <verb>`.

```
usr/share/big-driver-manager/
├── main.py                  # Application entry point
├── core_path.py             # Finds the core shipped by big-driver-manager-cli
├── ui/
│   ├── application.py       # Adw.Application subclass
│   ├── window.py            # Main window with tab navigation
│   ├── base_page.py         # Base page with shared UI patterns
│   ├── kernel_page.py       # Kernel management interface
│   ├── mesa_page.py         # Mesa driver management interface
│   └── progress_dialog.py   # Operation progress dialog
├── utils/
│   ├── i18n.py              # Internationalization setup
│   └── ui_constants.py      # Window and icon sizes
└── assets/
    ├── css/style.css        # Application stylesheet
    ├── icons/
    └── illustrations/
```

## Requirements

| Dependency | Version | Purpose |
|---|---|---|
| Python | ≥ 3.10 | Runtime |
| GTK | 4.0 | UI toolkit |
| libadwaita | ≥ 1.0 | Adwaita widgets and styling |
| big-driver-manager-cli | — | Hardware detection, driver database and every system change |

### Python Packages

- `PyGObject` — GObject Introspection bindings for GTK4 and Adwaita

## Installation

### From BigLinux Repository

```bash
sudo pacman -S big-driver-manager
```

### From Source

```bash
# Clone the repository
git clone https://github.com/communitybig/big-driver-manager.git
cd big-driver-manager

# Run directly (requires dependencies installed). The core comes from
# big-driver-manager-cli: installed, cloned next to this repository,
# or pointed at with BDM_CLI_DIR=/path/to/usr/share/big-driver-manager-cli
python usr/share/big-driver-manager/main.py
```

### Building the Package

```bash
cd ../pkgbuild
makepkg -si   # builds big-driver-manager-cli and the interface
```

## Usage

Launch from your application menu or via terminal:

```bash
big-driver-manager
```

> **Note:** Kernel and driver operations require administrator privileges. The application asks for them through `pkexec big-driver-manager-cli`, never for pacman itself.

## Translation

Translation files are located in the `locale/` directory. To contribute a new translation:

1. Copy the template file:
   ```bash
   cp locale/big-driver-manager.pot locale/<lang_code>.po
   ```
2. Translate the `msgstr` entries in the new `.po` file
3. Compile the translation:
   ```bash
   msgfmt locale/<lang_code>.po -o usr/share/locale/<lang_code>/LC_MESSAGES/big-driver-manager.mo
   ```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

## Credits

Developed by the [BigLinux Team](https://www.biglinux.com.br/) and the [Community Big](https://github.com/communitybig) contributors.

<p align="center">
  <sub>Made with ❤️ for the BigLinux community</sub>
</p>
