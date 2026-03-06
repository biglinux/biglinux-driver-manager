# Driver Verification Report — big-driver-manager

Generated: 2026-03-01 (updated after AUR printer batch testing)
VM: Manjaro kernel 6.18.12-1 | Total: 961 drivers (659 original + 35 phase-1 + 267 phase-2 printers)

## Summary (original 659)

| Category | Total | Success | Failed | DKMS Fail | Conflict | Rate |
|----------|-------|---------|--------|-----------|----------|------|
| device-ids | 28 | 14 | 0 | 12 | 2 | 50% |
| firmware | 35 | 34 | 1 | 0 | 0 | 97% |
| scanner | 28 | 25 | 3 | 0 | 0 | 89% |
| printer | 568 | 514 | 54 | 0 | 0 | 90% |
| **TOTAL** | **659** | **587** | **58** | **12** | **2** | **89%** |

## New Drivers Added (35)

Discovered via AUR metadata search and tested on VM.

| Category | New | Success | Failed |
|----------|-----|---------|--------|
| device-ids | 12 | 11 | 1 (DKMS) |
| firmware | 7 | 7 | 0 |
| scanner | 4 | 4 | 0 |
| printer | 12 | 12 | 0 |
| **TOTAL** | **35** | **34** | **1** |

### New device-ids (12)
- `rtl8852cu` (pkg: rtl8852cu-dkms-morrownr-git) — 7 USB IDs — Network
- `rtl8188gu` (pkg: rtl8188gu-dkms-git) — compiled, no IDs — Network
- `r8126` (pkg: r8126-dkms) — 2 PCI IDs — Network
- `r8127` (pkg: r8127-dkms) — 2 PCI IDs — Network
- `rtl8189es` (pkg: rtl8189es-dkms-git) — 1 SDIO ID — Network
- `rtl8189fs` (pkg: rtl8189fs-dkms-git) — 1 SDIO ID — Network
- `rtl8852cu-lwfinger` (pkg: rtl8852cu-dkms-git) — compiled, no IDs — Network
- `rtw89bt` (pkg: rtw89bt-dkms-git) — DKMS fail — Bluetooth
- `rtl8851be-bt` (pkg: rtl8851be-bt-foxconn-dkms) — 17 USB IDs — Bluetooth
- `8852be` (pkg: 8852be-dkms-git) — compiled, no IDs — Network
- `rtl8xxxu` (pkg: rtl8xxxu-dkms-git) — 121 USB IDs — Network
- `mt76` (pkg: mt76-dkms-git) — no DKMS module — Network

### New firmware (7)
- `ast-firmware` — Aspeed VGA/IPMI firmware — storage
- `brcmfmac43456-firmware` — Broadcom brcmfmac43456 for RPi 400 — wifi
- `ipw2x00-firmware` — Intel ipw2100/ipw2200 Wi-Fi — wifi
- `rtl8761b-firmware` — Realtek RTL8761B Bluetooth — bluetooth
- `rtl8761bu-firmware` — Realtek RTL8761BU USB Bluetooth — bluetooth
- `rtl8812au-firmware` — Realtek RTL8812AU USB Wi-Fi — wifi
- `scarlett2-firmware` — Focusrite Scarlett USB audio — audio

### New scanners (4)
- `iscan-plugin-cx4400` — Epson Stylus CX4400
- `iscan-plugin-gt-f700` — Epson Perfection V350 Photo
- `iscan-plugin-gt-s80` — Epson Perfection 1640SU
- `iscan-plugin-gt-x830` — Epson Perfection V500

### New printers (12)
- `brother-cups-wrapper-common` — Common CUPS wrapper for Brother
- `kyocera-cups` — CUPS driver for Kyocera
- `epson-printer-utility` — Epson ink-level monitor
- `cnijfilter2-g3010` — Canon PIXMA G3010 series
- `brother-dcpt300` — Brother DCP-T300
- `brother-hll2445dw-lpr-bin` — Brother HL-L2445DW
- `brother-dcpt520w` — Brother DCP-T520W
- `brother-dcpj100` — Brother DCP-J100
- `brother-mfcj430w` — Brother MFC-J430W
- `brother-mfcl2700dw` — Brother MFC-L2700DW
- `brother-mfcj6510dw` — Brother MFC-J6510DW
- `brother-ql-cups` — Brother QL label printers

### Updated totals

| Category | Before | After Phase-1 | After Phase-2 |
|----------|--------|---------------|---------------|
| device-ids | 28 | 40 | 40 |
| firmware | 35 | 42 | 42 |
| scanner | 28 | 32 | 32 |
| printer | 568 | 580 | 847 |
| **TOTAL** | **659** | **694** | **961** |

## Phase-2: AUR Printer Batch Testing (267 new)

Searched AUR for all printer-related packages not already covered.
Filtered 375 candidates → 356 after removing duplicates and non-printers.

| Metric | Count |
|--------|-------|
| Tested | 356 |
| SUCCESS | 271 |
| FAILED | 85 |
| False positives removed | 4 (free42, flashprint, otf-dotrice, lexmark-network-scan) |
| **New printer assets created** | **267** |
| Success rate | 76% |

### USB ID assignment for new printers

| Type | Count |
|------|-------|
| Specific VID:PID (usb.ids) | 40 |
| Vendor-only (usb_vendors.ids) | 227 |
| No match | 0 |

PPD cross-reference: 10,188 PPD files scanned for IEEE 1284 DeviceID strings.
121 packages had PPD model info, 2 upgraded from vendor-only to specific VID:PID.

### Phase-2 failed installs (85)

#### Bixolon (6) — download URLs broken
- `bixolon-srp-150`, `bixolon-srp-270`, `bixolon-srp-275`, `bixolon-srp-275ii`, `bixolon-srp-275iii`, `bixolon-stp-103ii`

#### Brother (30)
- `brother-cups-wrapper-ac`, `brother-dcp-197c`, `brother-dcp7057-cups-bin`, `brother-dcp7190dw-printer`
- `brother-dcp-9020cdn`, `brother-dcp-9030cdn`, `brother-dcpb7500d`, `brother-dcpb7535dw-bin`
- `brother-dcpj105`, `brother-dcpl2535dw`, `brother-dcpl3560cdw-lpr-bin`, `brother-dcpt735dw`
- `brother-hl1208`, `brother-hl-l1230w`, `brother_hl-l2325dw-cups-bin`
- `brother-mfc-6490cw`, `brother-mfc7320-cups`, `brother-mfc8680dn-cups-bin`, `brother-mfc8680dn-lpr-bin`
- `brother-mfc-j2340dw`, `brother-mfcj430w-cups-bin`, `brother-mfcj430w-lpr-bin`
- `brother-mfc-l2400dw`, `brother-mfc-l2680w`

#### Canon cnijfilter (17) — obsolete i686 packages
- `cndrvcups-lb-bin`, `cnijfilter-e510`, `cnijfilter-ip100`, `cnijfilter-ip7200`
- `cnijfilter-mg2100`, `cnijfilter-mg2500series`, `cnijfilter-mg3100`, `cnijfilter-mg3200`
- `cnijfilter-mg4100`, `cnijfilter-mg5200`, `cnijfilter-mg5300`, `cnijfilter-mg6100`
- `cnijfilter-mg8100series`, `cnijfilter-mp495-x86_64`, `cnijfilter-mp560`, `cnijfilter-mp620`
- `cnijfilter-mp630`, `cnijfilter-mp640`, `cnijfilter-mx340`, `cnijfilter-mx520series`
- `cnijfilter-mx720series`, `cnijfilter-ts7450series`

#### Others (32)
- `cups-xerox-phaser-3160`, `dell-unified-printer-driver`, `epson-inkjet-printer-m105`
- `epson-pc-fax-bin`, `epson-tm-series-driver`, `hplip-lite`, `hplip-minimal`
- `icc-hp-x520`, `konica-minolta-bizhub-bhp-1250`, `kyocera-print-driver`
- `kyocera-taskalfa-1800-2200`, `kyocera_universal`, `lexmark-aey`
- `pantum-driver`, `pantum_driver`, `pnm2ppa`
- `samsung-m262x-m282x`, `samsung-m283x`, `samsung-ml1860series`, `samsung-ml-1915`
- `samsung-ml191x-series`, `samsung-ml2160`, `triumph-adler-printer-drivers`
- `xerox-phaser-3020`, `xerox-phaser-3040`, `xerox-phaser-3320`, `xerox-phaser-6000-6010`
- `xerox-phaser-6280`, `xerox-spl-driver`, `xerox-spl-driver-printer`
- `xerox-workcentre-6015`, `xerox-workcentre-6027`, `xerox-workcentre-6515`

## USB ID Enhancement for Peripherals

Enhanced automatic hardware detection by adding USB device IDs to printer and scanner assets.
Source: `/usr/share/hwdata/usb.ids` (Linux USB ID database, 2616 products across 12 printer/scanner vendors).

### Printers (847 total)

| Type | Count | Description |
|------|-------|-------------|
| `usb.ids` (specific VID:PID) | 231 | Exact USB vendor:product match from hwdata + PPD cross-ref |
| `usb_vendors.ids` (vendor only) | 615 | Vendor-only matching (brand detected from pkg name) |
| No match | 1 | ppd-toshiba-estudio5560c (no Toshiba USB vendor) |

USB VID:PID matches by vendor:
- Brother (04F9): ~120 printers with specific USB product IDs
- Canon (04A9): ~10 printers (PIXMA series)
- Kyocera (0482): ~5 printers (ECOSYS series)
- Brother QL labels: ~10 label printers with specific IDs
- Others: Epson, Samsung, HP, Ricoh via vendor-only matching

### Scanners (32 total)

| Type | Count | Description |
|------|-------|-------------|
| `usb_vendors.ids` (vendor only) | 31 | Vendor-only matching |
| No match | 1 | libsane-dsseries |

### Detection tiers (hardware_detect.py)
1. **Tier 1** — `usb.ids`: specific VID:PID → driver (most accurate, 189 printers)
2. **Tier 2** — `usb_vendors.ids`: vendor ID only → driver (390 printers, 31 scanners)
3. **Tier 3** — `_USB_VENDOR_BRANDS`: fallback brand keyword matching (unchanged)

## Device ID Changes (assets updated)

| Driver | Before → After | Changes |
|--------|--------------|---------|
| 8821ce/pci.ids | 3 → 4 | +1: 10EC:B821 |
| 8821cu/usb.ids | 10 → 14 | +4: 0BDA:8731, 0BDA:C80C, 7392:C811, 7392:D811 |
| r8152/usb.ids | 31 → 35 | +4: 045E:0C5E, 0B05:1976, 0BDA:8157, 0BDA:815A |
| rtl8821cu/usb.ids | 6 → 14 | +9/-1: updated to match current driver |
| rtl8851bu/usb.ids | 2 → 3 | +2: 3625:010B, 7392:E611 |

## DKMS Build Failures (kernel 6.18)

These drivers fail to compile on kernel 6.18 but may work on older LTS kernels.

- `rtl8723bu-dkms-git`
- `rtl8723ds-dkms-git`
- `rtl8723du-dkms-git`
- `rtl8812au-dkms-git`
- `rtl8821au-dkms-git`
- `r8101-dkms` ⚠️ OutOfDate 👤 orphan
- `8188eu-dkms` ⚠️ OutOfDate 👤 orphan
- `8188fu-kelebek333-dkms-git` 👤 orphan
- `rtl8761usb-dkms` ⚠️ OutOfDate
- `rtl8822bu-dkms`
- `rtl8852au-dkms-git`
- `rtl88x2ce-dkms-git`

## Failed Installs

### firmware (1)
- `mn88472-firmware`

### scanner (3)
- `iscan-for-epson-v500-photo`
- `iscan-plugin-perfection-v550`
- `kyocera-sane` [orphan]

### printer (54)
- `brother-dcp560cn`
- `brother-dcp7030`
- `brother-dcp7045n`
- `brother-dcpj125`
- `brother-dcpj525w`
- `brother-hl2030`
- `brother-hl2040`
- `brother-hl2140`
- `brother-hl2150n`
- `brother-hl2170w`
- `brother-hl5350dn-lpr-bin`
- `brother-mfc-210c`
- `brother-mfc-9335cdw`
- `brother-mfc-l8610cdw`
- `brother-mfc6490cw-cupswrapper`
- `brother-mfc7320-lpr`
- `brother-mfc7360n`
- `canon-pixma-ip1500`
- `canon-pixma-mg5200-complete` [orphan]
- `canon-pixma-mg6100-complete`
- `cnijfilter-common-mg5400` [orphan]
- `cnijfilter-ip110` [orphan]
- `cnijfilter-ip2800series` [orphan]
- `cnijfilter-ip4500` [orphan]
- `cnijfilter-mg3500series`
- `cnijfilter-mg4200`
- `cnijfilter-mg6200`
- `cnijfilter-mg6300`
- `cnijfilter-mg6400series`
- `cnijfilter-mp280`
- `cnijfilter-mp550` [orphan]
- `cnijfilter-mx470series`
- `cnijfilter-mx530series`
- `cnijfilter-mx880`
- `cnijfilter-mx920`
- `cups-xerox`
- `cups-xerox-phaser-3600`
- `cups-xerox-phaser-6500`
- `cups-xerox-workcentre-3025`
- `dell2150-cups-driver` [orphan]
- `dell2155-cups-driver`
- `konica-minolta-bizhub-bh423-series`
- `konica-minolta-bizhub-bhc360` [orphan]
- `konica-minolta-bizhub-c368-series`
- `kyocera-fs11001300d` [orphan]
- `lexmark_pro700` [orphan]
- `pantum-p1000-p2000-p3000-m5100-m5200-ppd-driver` [OutOfDate, orphan]
- `pantum-p2200-p2500-driver` [OutOfDate]
- `ppd-xerox-colorqube9300`
- `xerox-phaser-6020`
- `xerox-phaser-6022`
- `xerox-workcentre-3045b-3045ni`
- `xerox-workcentre-5135-5150`
- `xerox-workcentre-6505`

## OutOfDate AUR Packages (21)

- `r8101-dkms` — flagged 2025-11-24 — test: dkms_build_failed
- `8188eu-dkms` — flagged 2024-07-29 — test: dkms_build_failed
- `rtl8761usb-dkms` — flagged 2025-06-23 — test: dkms_build_failed
- `cura-binary-data-git` — flagged 2024-01-10 — test: success
- `sigrok-firmware-fx2lafw-git` — flagged 2024-01-29 — test: success
- `upd72020x-fw` — flagged 2025-09-23 — test: success
- `brother-dcp7055` — flagged 2025-12-18 — test: success
- `brother-dcp7055w-lpr-bin` — flagged 2025-12-18 — test: success
- `brother-dcpj140w` — flagged 2025-12-03 — test: success
- `brother-dcpj4110dw` — flagged 2024-10-23 — test: success
- `brother-hl2250dn` — flagged 2023-12-08 — test: success
- `brother-hl3150cdw` — flagged 2024-11-19 — test: success
- `brother-mfc-9130cw` — flagged 2020-04-22 — test: success
- `brother-mfc-l2713dw` — flagged 2023-01-10 — test: success
- `brother-ql1050` — flagged 2022-03-13 — test: success
- `brother-ql1060n` — flagged 2019-09-29 — test: success
- `canon-pixma-mg5500-complete` — flagged 2025-04-04 — test: success
- `cnijfilter-ip2700series` — flagged 2024-04-14 — test: success
- `pantum-p1000-p2000-p3000-m5100-m5200-ppd-driver` — flagged 2023-02-17 — test: failed
- `pantum-p2200-p2500-driver` — flagged 2024-06-11 — test: failed
- `xeroxprtdrv` — flagged 2020-01-18 — test: success

## Orphan Packages (42)

Packages without AUR maintainer. Higher risk of becoming broken.

- `broadcom-wl-dkms` (device-ids) — test: success
- `r8101-dkms` (device-ids) — test: dkms_build_failed
- `linux-latest-r8168` (device-ids) — test: conflict
- `8188eu-dkms` (device-ids) — test: dkms_build_failed
- `rtbth-dkms-git` (device-ids) — test: success
- `8188fu-kelebek333-dkms-git` (device-ids) — test: dkms_build_failed
- `bcm4350-firmware` (firmware) — test: success
- `crazycat-dvb-firmware` (firmware) — test: success
- `cura-binary-data-git` (firmware) — test: success
- `gpd-pocket-support-bcm4356-git` (firmware) — test: success
- `hauppauge-wintv-quadhd-firmware` (firmware) — test: success
- `isl3886usb-firmware` (firmware) — test: success
- `linux-firmware-broadcom` (firmware) — test: success
- `linux-firmware-marvell` (firmware) — test: success
- `sixfireusb-dkms` (firmware) — test: success
- `brother-dcp-9022cdw` (printer) — test: success
- `brother-dcpj785dw` (printer) — test: success
- `brother-hl-1112` (printer) — test: success
- `brother-hl3150cdw` (printer) — test: success
- `brother-hll6200dw` (printer) — test: success
- `brother-hll8360cdw-lpr-bin` (printer) — test: success
- `brother-mfc-l8650cdw` (printer) — test: success
- `brother-mfcj5330dw-cups-bin` (printer) — test: success
- `brother-mfcj5330dw-lpr-bin` (printer) — test: success
- `canon-pixma-mg5200-complete` (printer) — test: failed
- `canon-pixma-mg5500-complete` (printer) — test: success
- `cnijfilter-common` (printer) — test: success
- `cnijfilter-common-mg5400` (printer) — test: failed
- `cnijfilter-ip110` (printer) — test: failed
- `cnijfilter-ip2800series` (printer) — test: failed
- `cnijfilter-ip4500` (printer) — test: failed
- `cnijfilter-mp550` (printer) — test: failed
- `dell2150-cups-driver` (printer) — test: failed
- `konica-minolta-bizhub-bhc360` (printer) — test: failed
- `kyocera-fs11001300d` (printer) — test: failed
- `lexmark_pro700` (printer) — test: failed
- `pantum-p1000-p2000-p3000-m5100-m5200-ppd-driver` (printer) — test: failed
- `ricoh-sp3700-ppds` (printer) — test: success
- `ricoh-spc261-ppd` (printer) — test: success
- `ricoh-spc261sfnw-ppd` (printer) — test: success
- `xerox-workcentre-6515-6510` (printer) — test: success
- `kyocera-sane` (scanner) — test: failed