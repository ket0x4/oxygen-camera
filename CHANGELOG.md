# Changelog

## 2.3.8

- On Android 17 the crashing Hyperlapse EIS toggle is hidden with a new
  SDK-gated edit (`sdkge|37|…com.oplus.feature.hyper.lapse.support=0`).
  Time-Lapse keeps its full SAT zoom; Android 16 keeps the toggle.
- Docs reconciled with 2.3.7 reality: AI Highlight/Ultra Night Video is
  enabled with the 64-bit libs, aperture blur works through
  `VideoBlurTexturePreview`, and the tap-to-focus/zoom measurements are
  recorded.
- Documented the remaining non-fatal vendor-tag mismatch: the 7.x app probes
  Oplus tags the stock OP9 HAL does not define, while focus/exposure still use
  the Camera2 AF/AE keys.

## 2.3.7

- Installer output is now structured: a device/ROM/module banner, phase
  headers, and a per-category summary (app, libraries, configs, log path).
- `aox.log` has a version/date header, `## app` / `## libraries` /
  `## configs` sections, and a machine-readable `summary` line.
- The Action button prints an aligned diagnostics report instead of prose.
- README refreshed for 2.3.x: installation, in-place updates, 16 KB
  alignment, reproducible builds, CI and release channels.

## 2.3.6

- Tap-to-focus no longer rebuilds the whole Qualcomm SAT pipeline. Tapping the
  viewfinder now focuses immediately and keeps the preview at full frame rate
  instead of stalling for ~1.5 s on every tap.
- All 64-bit native libraries shipped by the module and inside the camera APK
  now declare 16 KB `PT_LOAD` alignment, and the APK's uncompressed `.so`
  entries are enforced at 16 KB offsets.
- The module supports in-place updates from KernelSU Next / APatch / Magisk
  through `updateJson`; the update manifest is published with every release.
- Aligned the `camera_unit_feature_config.protobuf` replacement hashes with
  the latest `LE2113_16.0.10.500(EX01)` firmware, so the feature configuration
  is applied on that build too.

## 2.3.5

- Added the missing camera algorithm libraries loaded by the 7.x APS/JNI
  layers (`libAncHumanSegFigureFusion`, `libAncHumanDoubleExposure`,
  `libRedeyeReduce`, `libTrafficMode`, `libPerfectColor`, `libalCFR`,
  `libaisd`, `libAncSegBaseSdk`, `libancbase_segbase`, `libCaptureBokeh`,
  `libBokehPre`, `libaiseg`, `libyuvwrapper`, `libapsyuv`, `libpngwrapper`,
  `libapspng`, `libFDClite`, `libarcsoft_long_exposure_*`).
- Shipped `libHeifWinBufExchg-jni.so` from the stock 16.0.10.500 image.

## 2.3.4

- Night Mode purple tint fixed by shipping the stock ArcSoft HVX DSP
  skeletons.

## 2.3.3

- Video aperture blur and computational SuperRAW (RAW+) verified.
