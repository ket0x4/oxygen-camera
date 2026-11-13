# Oplus Camera for OnePlus 9 / 9 Pro

[![Release](https://img.shields.io/github/v/release/ket0x4/oxygen-camera?color=blue&label=Latest%20Release)](https://github.com/ket0x4/oxygen-camera/releases/latest)
[![SELinux](https://img.shields.io/badge/SELinux-Enforcing-success)](https://github.com/ket0x4/oxygen-camera)
[![Android](https://img.shields.io/badge/Android-16%20%7C%2017-brightgreen)](https://github.com/ket0x4/oxygen-camera)
[![16 KB pages](https://img.shields.io/badge/16%20KB%20pages-ready-informational)](https://github.com/ket0x4/oxygen-camera)
[![License](https://img.shields.io/badge/License-GPL%20v3-orange)](LICENSE)

A standalone **KernelSU Next / APatch / Magisk** module that ports **OplusCamera 7.013.11** (ColorOS 16 / OxygenOS 16) to the OnePlus 9 (`lemonade`) and OnePlus 9 Pro (`lemonadep`) on **Android 16 or 17** with **SELinux enforcing**.

The module builds its own read-only **EROFS** (or `ext4`) camera image at install time, mounts it through OverlayFS before Android scans packages, and configures KernelSU App Profile visibility automatically. No Mountify or other metamodules are required.

## Highlights

- **Fast tap-to-focus** — tapping the viewfinder focuses immediately instead of rebuilding the Qualcomm SAT pipeline and stalling for ~1.5 s.
- **16 KB page-size ready** — every 64-bit `PT_LOAD` segment in the APK and payload is 16 KB aligned, and the APK's stored `.so` entries sit on 16 KB offsets.
- **In-place updates** — `updateJson` lets KernelSU Next, APatch and Magisk offer new releases from the module card.
- **Self-contained** — a pinned, SHA-256-verified source set (including the firmware-derived camera payload) builds the module reproducibly.
- **Diagnostics built in** — structured install logs and an Action button report for SELinux, image, Power HAL, daemon priority and ART state.

## Features

Verified on OnePlus 9 (`LE2111` / `LE2115`) with **SELinux enforcing** on crDroid 16 / 17. The 9 Pro (`lemonadep`) uses its dedicated sensor and HAL configurations from the same vendor tree.

| Mode / Feature | Status | Notes |
|---|---|---|
| **Photo** (0.6x Ultra-Wide, 1x Main, 2x, 5x) | Working | Full HDR, AI scene, filters, Hasselblad watermark, DCI-P3 wide color gamut |
| **Hi-Res 48MP / 50MP** | Working | Full-resolution Bayer remosaic (`IMX689` / `IMX766` / `IMX789`) |
| **10-bit Color (HEIC)** | Working | 10-bit `yuv420p10le` hardware HEIC encoding |
| **Portrait** (Rear 1x & 2x, Front) | Working | SAT Camera ID `12` dual-camera depth + OEM FaceBeauty |
| **Night Mode** (0.6x Ultra-Wide, 1x Main, 2x IZOOM) | Working | SuperNight v3 (`0x8019`), 48MP in-sensor zoom (`IZOOM`), stock ArcSoft HVX DSP skeletons (multi-frame merge, no purple tint) |
| **Master / Pro Mode** (JPEG, RAW & RAW+) | Working | Native 12-bit DNG RAW and computational 8-frame stacked SuperRAW (`RAW+`) with Hasselblad color calibration profile; unified format selector; 1-swipe access |
| **Video** (720p / 1080p / 4K @ 30/60fps) | Working | Real-time aperture blur (`f/1.4` - `f/16`), EIS, Live HDR, Dolby Vision HLG, 10-bit video, 60fps focus tracking, 4K30 LUT & director filters |
| **AI Highlight & Ultra Night Video** | Working | 64-bit ColorOS 16 AI night vision pipeline (`libnightvision.so` + `libfastov_dsp.so`) |
| **Ultra-Wide 4K @ 60fps Video** | Working | Full 4K 60fps on the Sony IMX766 Ultra-Wide with seamless multi-camera zoom |
| **Ultra Steady Pro (Super EIS)** | Working | Wide-angle Super EIS on the IMX766 at up to 4K 30fps (`operation_mode = 0x8028`) |
| **Video 8K** (24 / 30 fps) | Working | 2-stream 8K pipeline |
| **Film (Movie) & Log Video** | Working | Full manual controls, histogram, and Log recording |
| **Slo-mo** (1080p@240fps / 720p@480fps) | Working | HFR 8x (240fps) and 16x (480fps) slow motion |
| **XPan** (30mm Ultra-Wide & 45mm Main) | Working | Hasselblad 65:24 panoramic mode on both `30mm` (`IMX766`) and `45mm` (`IMX689`) lenses |
| **Long Exposure** (0.6x Ultra-Wide & 1x Main) | Working | Multi-second light trails and moving crowds on both Ultra-Wide and Main lenses |
| **Panorama** (Rear & Front Selfie) | Working | Wide stitched panoramas on rear multi-camera and front IMX471 with live guidance |
| **Time-Lapse & Dual-View** | Working | Full multi-lens SAT zoom (`0.6x`, `1x`, `2x`, `5x`) and multi-stream recording |

## Requirements

- OnePlus 9 (`lemonade`) or OnePlus 9 Pro (`lemonadep`).
- Android 16 (SDK 36) or 17 (SDK 37), SELinux enforcing.
- Kernel with OverlayFS and loop-device support.
- KernelSU Next, APatch or Magisk with module support.
- Roughly 300 MB free in `/data` for the camera image.

## Install

1. Download `OplusCamera-OP9-<version>.zip` from [Releases](https://github.com/ket0x4/oxygen-camera/releases/latest), or build it locally.
2. In your root manager, open **Modules → Install**, pick the ZIP, and reboot.
3. Open **Oplus Camera** and grant its runtime permissions.

The installer prints a compatibility report, applies the camera changes, and builds the camera image. Details are written to `aox.log`.

### Updates

`module.prop` declares:

```text
updateJson=https://github.com/ket0x4/oxygen-camera/releases/latest/download/update.json
```

KernelSU Next, APatch and Magisk read that manifest and offer the matching ZIP from the module card. The manifest, ZIP and `.sha256` are published with every release; `CHANGELOG.md` is linked as the changelog.

### App Profile visibility

- **Automatic:** `service.sh` runs `ksu-visibility`, which turns **Umount modules OFF** for `com.oplus.camera` and the default launcher without granting root, and restores both profiles when the module is removed.
- **Manual fallback:** **KernelSU Next → App Profile → Oplus Camera → Custom → Umount modules: OFF** (leave Root OFF).

### Action button

Tapping **Action** on the module card prints an aligned report covering SELinux, the camera image (EROFS/ext4 and size), Power HAL UAH state, camera daemon `nice` values and ART compilation state, applies any missing optimizations, and launches the camera.

## Diagnostics

| File | Purpose |
|---|---|
| `aox.log` | Version/date header, `## app` / `## libraries` / `## configs` sections, per-file decisions, and a `summary` line |
| `mount.log` | EROFS/ext4 loop mount and OverlayFS results for every target |
| `visibility.log` | KernelSU App Profile changes for the camera and launcher |

All logs live in `/data/adb/modules/ooscamera_op9/`. If installation fails, the installer copies `aox.log` to `/data/local/tmp/ooscamera-install.log`. A boot that never completes disables the module on the next boot automatically.

## Build from source

### Prerequisites

- **Python 3.10+**
- **Java 17+** (`java` in `PATH`, used for `baksmali` / `smali` and `apksigner`)
- **Android SDK Build-Tools** (`apksigner` and `zipalign` in `PATH`, or under `~/.local/share/android/sdk/build-tools/<ver>/`)
- **Clang & LLD** (`clang` and `ld.lld` in `PATH`, used for `liboplus-uah-client.so`)
- **Android NDK r27+** *(optional)* — only when rebuilding `native/ksu_visibility.c`

### Prepare the pinned sources

```bash
python3 scripts/prepare_aox.py --fixtures
```

This verifies every pinned tree file by SHA-256, restores the `aox-sources`
bundle (the camera APK and the firmware-derived `system_ext` payload that is
not in any public tree), and fetches the test fixtures and AOSP platform test
keys into `.cache/aox/`. `aox/manifest.json` records the exact revisions,
input hashes and bundle hash.

### Build

```bash
python3 scripts/build.py --update-tag v<version>
```

The build:

1. Patches `OplusCamera.apk` — RAW forwarding, portrait/front-camera fixes,
   the tap-to-focus preview stall, and 16 KB ELF alignment — then signs it with
   the AOSP platform test key.
2. Patches the camera SDK jar and the HAL/algorithm libraries.
3. Builds `liboplus-uah-client.so` and bundles `ksu-visibility`.
4. Raises every 64-bit payload `PT_LOAD` to 16 KB alignment and verifies it.
5. Writes `build/OplusCamera-OP9-<version>.zip`, `.sha256` and `update.json`.

`--update-tag` makes `update.json` point at the tag being released; without it
the manifest targets `releases/latest/download/<zip>`.

### Validate

```bash
python3 -m unittest discover -s tests -v
python3 scripts/audit_artifact.py build/OplusCamera-OP9.zip
python3 scripts/elf_align.py check build/module
```

The tests cover the installer decisions, config edit engine, mount planner,
UAH shim and visibility helper. The audit checks the payload allowlist and the
SHA-256 provenance manifest; `elf_align.py` checks 16 KB alignment.

### Release

Pushing to `main` or `cam4` runs `.github/workflows/build.yml`, which prepares
the sources, runs the tests, builds the module and publishes a release with the
ZIP, checksum and `update.json`. Releases can also be created manually:

```bash
gh release create v<version> \
  build/OplusCamera-OP9-<version>.zip \
  build/OplusCamera-OP9-<version>.zip.sha256 \
  build/update.json --latest
```

## Project layout

```text
aox/                 manifest, provenance helpers and pinned stock inputs
module/              installer, mount logic, aox.sh, action.sh and module.prop
native/              UAH Power HAL shim and ksu-visibility helper
scripts/             prepare, build, patch, audit and ELF alignment tools
tests/               host tests for installer, configs, mount and helpers
fwk/                 compatibility classes used when patching oplus-fwk.jar
docs/                feature tracker and engineering write-ups
.github/workflows/   CI build and release pipeline
```

## Documentation

- [docs/STATUS.md](docs/STATUS.md) — lens/sensor feature tracker with on-device verification records.
- [docs/PROBLEMS_AND_FIXES.md](docs/PROBLEMS_AND_FIXES.md) — root causes and the ARM64, Smali, SELinux, EROFS and performance fixes.
- [aox/README.md](aox/README.md) — `aox` architecture, the install-time edit engine and device rules.
- [CHANGELOG.md](CHANGELOG.md) — release notes.

## Credits

- **[varakumar01](https://github.com/varakumar01) / [varakumar02](https://github.com/varakumar02)** — OnePlus 9 / 9 Pro device and vendor camera trees, `android_hardware_oplus`, and `open_oplus_camera`.
- **Hecheng Yu ([dodge-camera-port/vendor_oplus_camera](https://github.com/dodge-camera-port/vendor_oplus_camera))** — original port layout and gallery receiver patch foundation.
- **Ben Gruver ([JesusFreke/smali](https://github.com/JesusFreke/smali))** — `smali` / `baksmali` DEX assembler and disassembler (BSD 3-Clause).
- **LineageOS, crDroid & AxionOS maintainers** — `sm8350` platform trees and `extract-utils` tooling.

## License

The scripts, patches and module files are licensed under the **[GNU General Public License v3.0](LICENSE)**.

- `native/ksu_visibility.c` and `tests/visibility_policy_device.c` are **GPL-2.0-only**.
- `native/uah-client/uah_client.c` is **Apache-2.0**.

Proprietary OEM camera binaries and libraries are not tracked in this repository and remain the property of their respective owners, except the small stock compatibility shims under `aox/stock/` that are required as build inputs.
