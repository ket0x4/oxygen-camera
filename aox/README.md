# Architecture & Install-Time Patch Engine (`aox`)

This directory contains [manifest.json](manifest.json), which pins the upstream source repositories, file SHA-256 digests, ELF `DT_NEEDED` dependency lists, and install rules used by [scripts/build.py](../scripts/build.py) and [module/aox.sh](../module/aox.sh).

See [docs/PROBLEMS_AND_FIXES.md](../docs/PROBLEMS_AND_FIXES.md) for the detailed breakdown of every binary, bytecode, config, and SELinux fix.

---

## Upstream Sources

| Source | Repository | What is used |
|---|---|---|
| `camera` | `varakumar02/open_oplus_camera` | OplusCamera `7.013.11`, unit SDK jars, support wrapper, JNI libraries, permissions, `file_contexts` |
| `vendor` | `varakumar02/proprietary_vendor_oneplus_lemonade` | OnePlus 9 (`/odm/lib64`, `/vendor/lib64`, LUTs, models, `semco_imx689.bin`, configs) |
| `vendor_pro` | `varakumar02/proprietary_vendor_oneplus_lemonadep` | OnePlus 9 Pro per-device configs, protobuf, and `semco_imx789.bin` |
| `hardware` | `varakumar02/android_hardware_oplus` | `oplus-fwk` classes, UAH client interface, SELinux policy definitions |
| `device` / `common` | `varakumar02/android_device_oneplus_lemonade`, `sm8350-common` | Media profile encoder caps and platform definitions |

---

## How Install-Time Staging Works (`module/aox.sh`)

Every decision made during installation is logged to `/data/adb/modules/ooscamera_op9/aox.log`:

1. **Camera App & Paired Libraries (`group: app` / `pair`)**:
   - Installs `OplusCamera 7.013.11` into `/system_ext/priv-app/OplusCamera` (or replaces an older system copy in place).
   - Installs the paired `/odm/lib64` algorithm libraries (`libAlgoInterface.so`, `libAlgoProcess.so`, `libPreviewDecisionOld.so`, `libFilterWrapper.so`). If any `DT_NEEDED` dependency of a paired library is missing on the ROM, installation aborts cleanly rather than leaving a broken camera.
2. **Framework Compatibility (`oplus-fwk.jar`)**:
   - Inspects the ROM's `/system/framework/oplus-fwk.jar` for required markers (`fwk-markers.txt`, including `OplusHeifWriter` and `OplusGalleryLoadIconHelper`). Overlays the module's `oplus-fwk.jar` only when the ROM's copy lacks them.
3. **Conditional Fixes & Libraries (`group: fix` / `library`)**:
   - Shared libraries under `/odm/lib64` and `/vendor/lib64` are staged only if all of their `DT_NEEDED` dependencies exist on the device or in the module.
   - `replace` entries overwrite a device file only when the device file's SHA-256 matches a known stock/unpatched hash in `replace_sha256`.
4. **In-Place Config Edits (`module/aox/edits.txt`)**:
   - Rather than shipping static copies of device config files that might drift across ROM builds, `aox.sh` copies the phone's own config files (`oplus_camera_config`, `oplus_camera_aps_config`, `camera_unit_config`, `oplus_camera_algo_switch_config`, `CameraHWConfiguration.config`, `imx689`, `imx766`, `imx789`, `imx471`, `ov08a10`) and applies declarative rules (`tag|`, `ini|`, `zoommin|`, `modekey|`, `after|`, `block|`, `audiocap|`).
5. **Standalone EROFS / ext4 Image (`module/mount-camera.sh`)**:
   - Packs the tailored `$MODPATH/system` tree into a compressed read-only **EROFS** image (`mkfs.erofs -z lz4hc,level=9`, ~214 MB) with automatic fallback to `ext4` (`mkfs.ext4`), preserving all SELinux security contexts (`u:object_r:same_process_hal_file:s0`, `vendor_file`, `vendor_configs_file`, `system_file`).
   - At `post-fs-data` time, loop-mounts `camera.img` at `/mnt/ooscamera` and mounts read-only OverlayFS layers over only the directories present in the payload.

---

## Build-Time Patches

Applied automatically by `python3 scripts/build.py`:

- **[scripts/patch_apk.py](../scripts/patch_apk.py)** — Patches `OplusCamera.apk` for Master Mode 16-bit RAW DNG capture, Portrait SAT Camera ID `12` routing, Front Camera `FaceSlenderTexturePreview` safe fallback, XPan `30mm` Ultra-Wide lens switcher, and 16KB page alignment (`zipalign -P 16 -f 4`).
- **[scripts/patch_sdk.py](../scripts/patch_sdk.py)** — Patches `com.oplus.camera.unit.sdk.jar` to inject `com.oplus.packageName`, enable 10-bit HEIC reflection stubs, and normalize DNG `BlackLevel` (`64`) & `BaselineExposure` (`0.0 EV`).
- **[scripts/patch_hal.py](../scripts/patch_hal.py)** — Patches `/vendor/lib64/hw/camera.qcom.so` to expose `com.oplus.packageName` in `availableSessionKeys`.
- **[scripts/patch_algo.py](../scripts/patch_algo.py)** — Patches:
  - `libAlgoInterface.so`: SuperNight 10-bit black level (`64`) and unit AWB gain (`1.0f`) injection.
  - `libAlgoProcess.so`: 16-byte stride alignment (`ALIGN(width, 16)`) for 10-bit P010 buffers.
  - `libcamximageformatutils.so`: Bypasses `validateBufferSize` abort in Movie / Log video mode.
  - `com.qti.chi.override.so`: Forces `HALOutputBufferCombined = 0` in HFR slow-motion pipelines to prevent `cam-icp` buffer offset faults.
- **[native/uah-client/](../native/uah-client/)** — Builds `liboplus-uah-client.so` to forward camera launch, capture, and streaming hints to the Android Power HAL.
