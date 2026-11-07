# Oplus Camera for OnePlus 9 / 9 Pro

A standalone **KernelSU Next** (and APatch / Magisk) module that ports **OplusCamera 7.013.11** (ColorOS 16 / OxygenOS 16) to the OnePlus 9 (`lemonade`) and OnePlus 9 Pro (`lemonadep`) running any **Android 16 or 17** custom ROM with **SELinux Enforcing**.

No third-party metamodules (Mountify, OverlayFS managers, etc.) are required—the module builds its own compressed read-only **EROFS** (or `ext4`) image at install time, mounts it via OverlayFS before Android scans packages, and automatically configures KernelSU App Profile visibility.

---

## Features & Compatibility

Verified on OnePlus 9 (`LE2111` / `LE2115`), **SELinux Enforcing**, crDroid 16 / 17 (Android 16 & 17). The 9 Pro (`lemonadep`) uses its dedicated sensor/HAL configurations from the same vendor tree.

| Mode / Feature | Status | Notes |
|---|---|---|
| **Photo** (0.6x Ultra-Wide, 1x Main, 2x, 5x) | Working | Full HDR, AI scene, filters, Hasselblad watermark, DCI-P3 wide color gamut |
| **Hi-Res 48MP / 50MP** | Working | Full-resolution Bayer remosaic (`IMX689` / `IMX766` / `IMX789`) |
| **10-bit Color (HEIC)** | Working | 10-bit `yuv420p10le` hardware HEIC encoding |
| **Portrait** (Rear 1x & 2x, Front) | Working | SAT Camera ID `12` dual-camera depth + OEM FaceBeauty |
| **Night Mode** (0.6x Ultra-Wide, 1x Main, 2x IZOOM) | Working | SuperNight v3 (`0x8019`), 48MP in-sensor zoom (`IZOOM`), calibrated 10-bit black level (`64`) |
| **Master / Pro Mode** (JPEG & 12-bit RAW) | Working | Native 12-bit DNG RAW capture with Hasselblad color calibration profile; 1-swipe access on bottom carousel |
| **Video** (720p / 1080p / 4K @ 30/60fps) | Working | EIS, Live HDR, Dolby Vision HLG, 10-bit video, 60fps focus tracking, 4K30 LUT & director filters |
| **Ultra-Wide 4K @ 60fps Video** | Working | Unlocked full 4K 60fps on Sony IMX766 Ultra-Wide with seamless multi-camera zoom |
| **Ultra Steady Pro (Super EIS)** | Working | Wide-angle Super EIS stabilization on the IMX766 at up to 4K 30fps (`operation_mode = 0x8028`) |
| **Video 8K** (24 / 30 fps) | Working | 2-stream 8K pipeline |
| **Film (Movie) & Log Video** | Working | Full manual controls, histogram, and Log recording |
| **Slo-mo** (1080p@240fps / 720p@480fps) | Working | HFR 8x (240fps) and 16x (480fps) slow-motion |
| **XPan** (30mm Ultra-Wide & 45mm Main) | Working | Hasselblad 65:24 panoramic mode on both `30mm` (`IMX766`) and `45mm` (`IMX689`) lenses |
| **Long Exposure** (0.6x Ultra-Wide & 1x Main) | Working | Multi-second light trails and moving crowds on both Ultra-Wide and Main lenses |
| **Panorama** (Rear & Front Selfie) | Working | Wide stitched panoramas on rear multi-camera and front IMX471 with live stitching guidance |
| **Time-Lapse & Dual-View** | Working | Full multi-lens SAT zoom (`0.6x`, `1x`, `2x`, `5x`) and multi-stream recording |

---

## Installation

1. Download `OplusCamera-OP9-<version>.zip` from [Releases](../../releases) (or build it locally).
2. Open **KernelSU Next Manager** → **Modules** → **Install**, select the ZIP, and **Reboot**.
3. Open **Oplus Camera** and grant its runtime permissions.

### App Profile Visibility & Diagnostics
- **Automatic Visibility**: After boot, `service.sh` (`ksu-visibility`) automatically turns **Umount modules OFF** for `com.oplus.camera` and your default launcher (without granting root), and restores both profiles if the module is disabled or removed.
- **Manual Fallback**: If your KernelSU build does not expose the profile ioctl interface, open **KernelSU Next → App Profile → Oplus Camera → Custom → Umount modules: OFF** (keep Root OFF).
- **Action Button**: Tapping **Action** on the module card in KernelSU Next prints live diagnostics (`SELinux`, `camera.img` EROFS/ext4 size, Power HAL UAH status, camera daemon `nice` priority, ART `speed` compilation status), applies any missing optimizations, and launches the camera.

### Safety Checks & Logs
- The installer verifies that the device is `lemonade` or `lemonadep` running Android 16+ (SDK 36+) with kernel OverlayFS support.
- If a boot ever fails to complete, `post-fs-data.sh` automatically disables the module on the next boot.
- Logs are stored in `/data/adb/modules/ooscamera_op9/`:
  - `aox.log` — per-file installer and config edit decisions
  - `mount.log` — EROFS/ext4 loop mount and OverlayFS status
  - `visibility.log` — KernelSU App Profile configuration log

---

## Building from Source

### 1. Prerequisites
- **Python 3.10+**
- **Java 17+** (`java` in `PATH`, used to run `baksmali` / `smali` and `apksigner`)
- **Android SDK Build-Tools** (`apksigner` and `zipalign` in `PATH` or `~/.local/share/android/sdk/build-tools/<ver>/`)
- **Clang & LLD** (`clang` and `ld.lld` in `PATH`, used to compile `liboplus-uah-client.so`)
- **Android NDK r27+** *(optional)* — only needed if recompiling `native/ksu_visibility.c` from scratch (`ANDROID_NDK_HOME`).

### 2. Fetch Pinned Sources & Prepare Cache
```bash
python3 scripts/prepare_aox.py --fixtures
```
This downloads and verifies (by SHA-256) the pinned inputs, configs, test fixtures, and AOSP platform test signing keys into `.cache/aox/`.
*(Note: If regenerating blobs from an OxygenOS / ColorOS firmware dump, run `extract-files.py` from `open_oplus_camera` first to populate `.cache/aox/`.)*

### 3. Build the Module ZIP
```bash
python3 scripts/build.py
```
`build.py` automatically:
1. Patches `OplusCamera.apk` ([scripts/patch_apk.py](scripts/patch_apk.py)), 16KB-page-aligns native `.so` libraries, and signs with the AOSP platform test key.
2. Patches `com.oplus.camera.unit.sdk.jar` ([scripts/patch_sdk.py](scripts/patch_sdk.py)) for client package injection, 10-bit HEIC, and DNG `BlackLevel` / `BaselineExposure` normalization.
3. Patches `camera.qcom.so` ([scripts/patch_hal.py](scripts/patch_hal.py)) and `/odm/lib64` algorithm/override libraries ([scripts/patch_algo.py](scripts/patch_algo.py)).
4. Builds `liboplus-uah-client.so` ([native/uah-client/build.sh](native/uah-client/build.sh)) and bundles `ksu-visibility`.
5. Outputs `build/OplusCamera-OP9-<version>.zip` and its `.sha256` checksum.

### 4. Run Tests & Audit Artifact
```bash
# Run unit tests (installer logic, config edits, mount planner, UAH shim, visibility helper)
python3 -m unittest discover -s tests -v

# Audit the built ZIP against payload allowlist and SHA-256 provenance
python3 scripts/audit_artifact.py build/OplusCamera-OP9.zip
```

---

## Documentation

- **[docs/STATUS.md](docs/STATUS.md)** — Comprehensive lens and sensor feature enhancement tracker with live hardware verification records and CamX usecase details.
- **[docs/PROBLEMS_AND_FIXES.md](docs/PROBLEMS_AND_FIXES.md)** — Complete engineering write-up of all 18 root causes, ARM64 binary patches, Smali bytecode patches, SELinux rules, EROFS compression, and ART/HAL performance optimizations.
- **[aox/README.md](aox/README.md)** — Overview of the `aox` architecture, install-time config engine (`module/aox/edits.txt`), and device compatibility rules.

---

## Credits

- **[varakumar01](https://github.com/varakumar01) / [varakumar02](https://github.com/varakumar02)** — OnePlus 9 / 9 Pro (`lemonade` / `lemonadep`) device/vendor camera trees, `android_hardware_oplus`, and `open_oplus_camera`.
- **Hecheng Yu ([dodge-camera-port/vendor_oplus_camera](https://github.com/dodge-camera-port/vendor_oplus_camera))** — Original camera port layout and gallery receiver patch foundation.
- **Ben Gruver ([JesusFreke/smali](https://github.com/JesusFreke/smali))** — `smali` / `baksmali` DEX assembler and disassembler (BSD 3-Clause).
- **LineageOS, crDroid & AxionOS Maintainers** — `sm8350` platform trees and `extract-utils` tooling.

---

## License

The scripts, patches, and module files in this repository are licensed under the **[GNU General Public License v3.0](LICENSE)**.
- `native/ksu_visibility.c` and `tests/visibility_policy_device.c` are licensed under **GPL-2.0-only**.
- `native/uah-client/uah_client.c` is licensed under **Apache-2.0**.

Proprietary OEM camera binaries and libraries are not tracked in this repository and remain the property of their respective owners.
