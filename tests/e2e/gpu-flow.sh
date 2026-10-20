#!/bin/bash
# End-to-end test of 'big-driver-manager-cli gpu' against the real pacman, in a
# throwaway Manjaro container. Fake packages with the real names (and the real
# conflict shapes) are served from an offline repository laid out like the
# live medium's /opt/mhwd; a fake sysfs describes an Intel + NVIDIA RTX 4060
# laptop. Covers install, branch switch, refusal, GPU modes, remove, boot,
# installing into a --root target and refusing a user-prepared one.
#
#   docker run --rm -v "$PWD":/src:ro \
#       -v /usr/share/nvidia-driver-assistant/supported-gpus:/nvda:ro \
#       manjarolinux/base:latest bash /src/tests/e2e/gpu-flow.sh
#
# NEVER run it on a real system: it installs and removes packages as root.
[ -e /.dockerenv ] || [ -e /run/.containerenv ] || { echo "containers only" >&2; exit 1; }
set -uo pipefail
ok() { echo "OK   $*"; }
bad() { echo "FAIL $*"; FAILED=1; for l in /tmp/[0-9].log; do [ $l -nt /tmp/.mark ] && { echo "--- $l"; tail -8 $l; }; done; }
FAILED=0
check() { if eval "$1"; then ok "$2"; else bad "$2"; fi; touch /tmp/.mark; }
touch /tmp/.mark

pacman -Syu --noconfirm --needed python pciutils usbutils fakeroot >/dev/null 2>&1 || { echo "deps failed"; exit 2; }
export BDM_CLI_DIR=/src/usr/share/big-driver-manager-cli
export BDM_SUPPORTED_GPUS=/nvda/supported-gpus.json
export BDM_SYS_ROOT=/tmp/sys BDM_TEST=1
CLI="python3 /src/usr/bin/big-driver-manager-cli"

# fake sysfs: Intel iGPU + NVIDIA RTX 4060 Laptop (Ada: current driver, open module)
mkdev() { d=/tmp/sys/bus/pci/devices/$1; mkdir -p $d; echo 0x$2 >$d/vendor; echo 0x$3 >$d/device; echo 0x$4 >$d/class; }
mkdev 0000:00:02.0 8086 a7a0 030000; echo 1 >/tmp/sys/bus/pci/devices/0000:00:02.0/boot_vga
mkdev 0000:01:00.0 10de 28a0 030000
# fake installed kernel
mkdir -p /usr/lib/modules/7.2.11-2-big && touch /usr/lib/modules/7.2.11-2-big/vmlinuz && echo linux-big >/usr/lib/modules/7.2.11-2-big/pkgbase
printf '#!/bin/sh\necho "[stub] mkinitcpio $*"\n' >/usr/bin/mkinitcpio; chmod +x /usr/bin/mkinitcpio

# offline repository with fake packages (real names, real conflict shapes)
printf '[Unit]\nDescription=fake\n[Service]\nExecStart=/bin/true\n[Install]\nWantedBy=graphical.target\n' >/tmp/unit; chmod 644 /tmp/unit
useradd -m b; mkdir -p /opt/mhwd/pkg /build; chown b /build
mkpkg() { # name provides conflicts depends files...
    local n=$1 p=$2 c=$3 d=$4; shift 4
    mkdir -p /build/$n; cat >/build/$n/PKGBUILD <<EOF
pkgname=$n; pkgver=1; pkgrel=1; arch=(any); options=(!strip !debug)
provides=($p); conflicts=($c); depends=($d)
package() { for f in $*; do install -Dm644 /tmp/unit "\$pkgdir/\$f"; done; }
EOF
    chown -R b /build/$n; su b -c "cd /build/$n && PKGEXT=.pkg.tar makepkg -fd >/dev/null 2>&1" && cp /build/$n/*.pkg.tar /opt/mhwd/pkg/
}
mkpkg nvidia-utils "nvidia-utils=615" "" "" usr/lib/libnvidia-fake.so
mkpkg nvidia-settings "" "" "nvidia-utils" usr/bin/nvidia-settings
mkpkg linux-big-nvidia-open "NVIDIA-MODULE" "" "" usr/lib/modules/7.2.11-2-big/extramodules/nvidia.ko
mkpkg nvidia-580xx-utils "nvidia-utils=580" "" "" usr/lib/libnvidia-fake.so
mkpkg nvidia-580xx-settings "nvidia-settings=580" "nvidia-settings" "nvidia-utils" usr/bin/nvidia-settings
mkpkg linux-big-nvidia-580xx-open "NVIDIA-MODULE" "" "" usr/lib/modules/7.2.11-2-big/extramodules/nvidia.ko
mkpkg nvidia-prime "" "" "nvidia-utils" usr/bin/prime-run
mkpkg switcheroo-control "" "" "" usr/lib/systemd/system/switcheroo-control.service
repo-add -q /opt/mhwd/pkg/mhwd.db.tar.gz /opt/mhwd/pkg/*.pkg.tar
printf '[options]\nArchitecture = auto\nSigLevel = Never\n[mhwd]\nServer = file:///opt/mhwd/pkg\n' >/opt/mhwd/pacman-mhwd.conf
PM="--pmconfig /opt/mhwd/pacman-mhwd.conf"

echo "== 1. install (recommended: current, open module)"
$CLI gpu install $PM >/tmp/1.log 2>&1; check '[ $? -eq 0 ]' "install exit 0"
check 'pacman -Q nvidia-utils linux-big-nvidia-open nvidia-settings nvidia-prime switcheroo-control >/dev/null' "current open + prime + switcheroo installed"
check '[ -f /etc/modules-load.d/big-driver-manager-nvidia.conf ]' "modules-load file written"
check '[ -f /etc/udev/rules.d/80-big-driver-manager-nvidia-power.rules ] && [ -f /etc/modprobe.d/big-driver-manager-nvidia-power.conf ]' "RTD3 files written (Ada has runtimepm)"
check '[ -e /etc/systemd/system/graphical.target.wants/switcheroo-control.service ]' "switcheroo enabled"
check '[ -f /var/lib/pacman/sync/mhwd.db ]' "offline repository synced"
check 'grep -q "^Command: modprobe nvidia_drm" /tmp/1.log' "driver loaded right after install (live session)"
# The fake card never gets a driver here: exactly the black-screen case.
check 'grep -q "falling back to nouveau" /tmp/1.log && grep -q "^Command: modprobe nouveau" /tmp/1.log' "driverless NVIDIA card falls back to nouveau"
check 'grep -q "did not take the GPU" /run/big-driver-manager/nvidia-fallback' "fallback reason recorded"
check '$CLI gpu status --json | grep -q "did not take the GPU"' "status shows the fallback"
cat /tmp/1.log | grep -E '^(NVIDIA driver|Install|Hybrid)'

echo "== 2. switch to 580xx (file conflicts with the installed branch)"
$CLI gpu install --nvidia-branch 580xx $PM >/tmp/2.log 2>&1; check '[ $? -eq 0 ]' "switch exit 0"
check 'pacman -Q nvidia-580xx-utils nvidia-580xx-settings linux-big-nvidia-580xx-open >/dev/null' "580xx installed (open module: Ada supports it)"
check '! pacman -Qq | grep -qxE "nvidia-utils|linux-big-nvidia-open|nvidia-settings"' "current branch removed (exact names)"
check 'pacman -Q nvidia-prime >/dev/null && pacman -T nvidia-utils >/dev/null' "nvidia-prime kept, its nvidia-utils dependency satisfied"
grep -E '^Replacing' /tmp/2.log

echo "== 3. refused branch"
$CLI gpu install --nvidia-branch 470xx $PM >/tmp/3.log 2>&1; check '[ $? -eq 2 ]' "470xx refused for Ada (exit 2)"
check 'pacman -Q nvidia-580xx-utils >/dev/null' "nothing touched after refusal"

echo "== 4. modes"
mkdir -p /etc/lightdm
$CLI gpu mode nvidia >/tmp/4.log 2>&1; check '[ $? -eq 0 ]' "mode nvidia"
check 'grep -q 0x00 /etc/modprobe.d/zz-big-driver-manager-gpu-mode.conf && [ -f /etc/X11/xorg.conf.d/99-big-driver-manager-nvidia-primary.conf ] && [ -f /etc/lightdm/lightdm.conf.d/zz-big-driver-manager-prime.conf ]' "nvidia mode files (modprobe, Xorg, LightDM)"
check 'grep -q "stub. mkinitcpio -P" /tmp/4.log' "initramfs rebuilt"
$CLI gpu mode hybrid >/dev/null 2>&1; check '[ ! -e /etc/X11/xorg.conf.d/99-big-driver-manager-nvidia-primary.conf ] && [ ! -e /etc/lightdm/lightdm.conf.d/zz-big-driver-manager-prime.conf ]' "hybrid removes the overrides"
check '$CLI gpu status --json | python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(not (d[\"mode\"]==\"hybrid\" and d[\"hybrid\"]))"' "status reports hybrid"

echo "== 5. remove"
$CLI gpu remove >/tmp/5.log 2>&1; check '[ $? -eq 0 ]' "remove exit 0"
check '! pacman -Q nvidia-580xx-utils >/dev/null 2>&1 && ! pacman -Q linux-big-nvidia-580xx-open >/dev/null 2>&1 && ! pacman -Q nvidia-prime >/dev/null 2>&1' "driver and prime removed"
check '[ ! -e /etc/modules-load.d/big-driver-manager-nvidia.conf ] && [ ! -e /etc/big-driver-manager/gpu-mode ]' "driver files and mode cleared"
check 'pacman -Q switcheroo-control >/dev/null' "switcheroo kept"

echo "== 6. boot on a fresh hybrid machine records hybrid"
$CLI gpu boot >/dev/null 2>&1; check '[ "$(cat /etc/big-driver-manager/gpu-mode)" = hybrid ]' "boot applied hybrid"

echo "== 7. installer: --root into a target"
T=/mnt/target; mkdir -p $T/etc $T/usr/bin $T/usr/lib/modules/7.2.11-2-big $T/var/lib/pacman; touch $T/usr/lib/modules/7.2.11-2-big/vmlinuz; echo linux-big >$T/usr/lib/modules/7.2.11-2-big/pkgbase
$CLI gpu install --root $T $PM >/tmp/7.log 2>&1; check '[ $? -eq 0 ]' "install into target exit 0"
check 'pacman -Q --root $T nvidia-utils linux-big-nvidia-open >/dev/null' "drivers installed in the target"
check '[ -f $T/etc/modules-load.d/big-driver-manager-nvidia.conf ]' "files written in the target"
check '! pacman -Q linux-big-nvidia-open >/dev/null 2>&1' "live system untouched"
check '! grep -q "Command: modprobe" /tmp/7.log' "no modprobe for another root (installer)"

echo "== 8. a user-prepared --root is refused"
U=/tmp/usertree; mkdir -p $U/etc $U/usr/bin $U/usr/lib $U/var/lib/pacman; chown -R b $U
$CLI gpu install --root $U $PM >/tmp/8.log 2>&1; check '[ $? -eq 2 ] && grep -q "not owned by root" /tmp/8.log' "refused: not owned by root"
check '[ -z "$(ls -A $U/var/lib/pacman)" ]' "nothing installed there"

echo "== free boot installs no NVIDIA driver"
echo "driver=free" >/tmp/cmdline
$CLI gpu plan --free $PM | grep -E '^Install'

[ $FAILED -eq 0 ] && echo "ALL PASSED" || { echo "SOME FAILED"; exit 1; }
