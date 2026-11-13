# Oplus Camera for OnePlus 9 / 9 Pro

[![Release](https://img.shields.io/github/v/release/ket0x4/oxygen-camera?color=blue&label=Latest%20Release)](https://github.com/ket0x4/oxygen-camera/releases/latest)
[![Android](https://img.shields.io/badge/Android-16%20%7C%2017-brightgreen)](https://github.com/ket0x4/oxygen-camera)
[![16 KB pages](https://img.shields.io/badge/16%20KB%20pages-ready-informational)](https://github.com/ket0x4/oxygen-camera)
[![License](https://img.shields.io/badge/License-GPL%20v3-orange)](LICENSE)

OplusCamera **7.013.11** (ColorOS 16) for the OnePlus 9 / 9 Pro on Android 16–17 custom ROMs. A standalone KernelSU Next / APatch / Magisk module that builds its own read-only EROFS camera image, mounts it through OverlayFS, and configures App Profile visibility automatically. No Mountify.

- Tap-to-focus without the SAT-pipeline stall
- 16 KB page-size aligned
- In-place updates through `updateJson`

## Features

| Area | Support |
|---|---|
| Photo | 0.6x / 1x / 2x / 5x, HDR, DCI-P3, Hasselblad watermark |
| Hi-Res | 48 MP / 50 MP remosaic |
| Portrait | Rear and front, SAT bokeh, FaceBeauty |
| Night | SuperNight v3, 2x IZOOM, ArcSoft HVX |
| Master | JPG, RAW, 8-frame SuperRAW (RAW+) |
| Video | 4K30/60, 8K, 10-bit, Dolby Vision, EIS, aperture blur, filters, 60 fps tracking |
| AI | Highlight video, Ultra Night Video |
| Extras | 10-bit HEIC, XPan, Long Exposure, Panorama, Time-Lapse, Dual-View, Slo-mo |

**Known limits:** front SuperNight is HAL-limited on the IMX471; Hyperlapse EIS is hidden on Android 17 (7.x SDK crash), while Time-Lapse keeps SAT zoom; wide SuperEIS at 4K is capped at 30 fps.

## Requirements

OnePlus 9 or 9 Pro · Android 16/17 · SELinux enforcing · OverlayFS kernel · ~300 MB free in `/data`.

## Install

1. Download `OplusCamera-OP9-<version>.zip` from [Releases](https://github.com/ket0x4/oxygen-camera/releases/latest).
2. Install it in KernelSU Next, APatch or Magisk, then reboot.
3. Open Oplus Camera and grant permissions.

Updates are offered from the module card. If the camera cannot see the module, set
**App Profile → Oplus Camera → Umount modules OFF**.

## Build

```bash
python3 scripts/prepare_aox.py --fixtures
python3 scripts/build.py --update-tag v<version>
python3 -m unittest discover -s tests
```

Needs Python 3.10+, Java 17+, Android build-tools, and clang/ld.lld. Pinned sources and
hashes live in [`aox/manifest.json`](aox/manifest.json); `prepare_aox.py` restores the
camera APK and firmware payload from the `aox-sources` release.

## Logs

`/data/adb/modules/ooscamera_op9/` holds `aox.log`, `mount.log` and `visibility.log`.
The module **Action** button prints live diagnostics and opens the camera.

## More

[Feature tracker](docs/STATUS.md) · [Root causes & fixes](docs/PROBLEMS_AND_FIXES.md) · [aox architecture](aox/README.md) · [Changelog](CHANGELOG.md)

## Credits

Built on the OnePlus 9 / 9 Pro camera trees by [varakumar02](https://github.com/varakumar02), `smali` / `baksmali` by [JesusFreke](https://github.com/JesusFreke/smali), and the LineageOS, crDroid and AxionOS SM8350 trees.

## License

GPL-3.0. `native/ksu_visibility.c` and `tests/visibility_policy_device.c` are GPL-2.0-only; `native/uah-client/uah_client.c` is Apache-2.0. Proprietary OEM binaries remain their owners' property, except the small build inputs under `aox/stock/`.
