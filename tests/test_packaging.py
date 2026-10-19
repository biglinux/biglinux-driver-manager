"""Units, hooks and the mhwd compatibility kept while mhwd is still around."""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "usr/lib/systemd/system"
HOOKS = ROOT / "usr/share/libalpm/hooks"
COMPAT = ROOT / "usr/share/libalpm/scripts/big-driver-manager-mhwd-compat"


class TestUnits(unittest.TestCase):
    def test_live_service_leaves_mhwd_media_to_mhwd_live(self):
        unit = (UNITS / "big-driver-manager-live.service").read_text()
        self.assertIn("ConditionPathExists=/livefs-pkgs.txt", unit)
        self.assertIn("ConditionPathExists=!/usr/bin/mhwd", unit)
        self.assertIn("--from-cmdline --pmconfig /opt/mhwd/pacman-mhwd.conf", unit)
        self.assertIn(
            "BindReadOnlyPaths=-/usr/lib/biglinux-livecd/shims/mkinitcpio", unit
        )

    def test_gpu_service_runs_before_the_display_manager(self):
        unit = (UNITS / "big-driver-manager-gpu.service").read_text()
        self.assertIn("Before=display-manager.service", unit)
        self.assertIn("ExecStart=/usr/bin/big-driver-manager-cli gpu boot", unit)


class TestHooks(unittest.TestCase):
    def test_kernel_hook_checks_every_kernel_install(self):
        hook = (HOOKS / "big-driver-manager-kernel.hook").read_text()
        self.assertIn("Target = usr/lib/modules/*/pkgbase", hook)
        self.assertIn("Exec = /usr/bin/big-driver-manager-cli gpu check", hook)

    def test_mhwd_compat_follows_mhwd_upgrades(self):
        hook = (HOOKS / "big-driver-manager-mhwd-compat.hook").read_text()
        for target in ("mhwd", "mhwd-db", "big-driver-manager-cli"):
            self.assertIn(f"Target = {target}\n", hook)

    def test_mhwd_compat_teaches_linux_big_and_xanmod(self):
        text = COMPAT.read_text()
        self.assertIn("^linux-big$", text)
        self.assertIn("^linux-xanmod$|^linux-xanmod-lts$", text)
        subprocess.run(["bash", "-n", str(COMPAT)], check=True)

    def test_mhwd_compat_does_nothing_without_mhwd(self):
        self.assertIn(
            "[[ -f /var/lib/mhwd/scripts/mhwd ]] || exit 0", COMPAT.read_text()
        )


if __name__ == "__main__":
    unittest.main()
