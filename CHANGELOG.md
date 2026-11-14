# Changelog

## 2.3.12

- Prepare the replacement camera image beside the module (`camera.img.new`)
  and rename it over `camera.img` only after the overlay probe succeeds. This
  keeps the current image intact if validation fails and avoids reformatting a
  live image when a manager runs `customize.sh` in place. KernelSU stages
  upgrades in `modules_update`, so the staged image is used on the next boot.

## 2.3.11

- Payload libraries are stripped of debug/unneeded sections when that makes
  them smaller: `libnightvision`, `libaisd`, `libimgClarityEvaluate` and
  `libSuperTextWrapper` lose 25 MiB uncompressed (~5.4 MiB of the ZIP). Their
  dynamic symbol tables are unchanged and the camera maps them normally.
- `liboplus-uah-client.so` and `ksu-visibility` now link with a 16 KB common
  page size, so their `PT_GNU_RELRO` ends align; the build and CI check both
  `p_align` and RELRO. Prebuilt vendor/APK libraries still carry their original
  4 KB RELRO layout (60 payload + 21 APK libs) and are reported as a known
  limit.
- CI publishes a release only when `module.prop` `versionCode` increases.
  Docs/CI-only pushes still build and upload an artifact, but leave the current
  release and static `update.json` untouched; a lower versionCode fails.

## 2.3.10

- Move the update manifest into the repository (`update.json` on `main`) and
  point `updateJson` at the static raw URL instead of the GitHub release
  redirect. The release workflow refreshes `update.json` after every build.

## 2.3.9

- Re-enable the 9 Pro tele camera gate: `com.oplus.feature.sat.tele.support=1`
  on `lemonadep` only. The 9 Pro HAL already reports SAT tele
  (`com.oplus.sat.tele.support=1`); the app switch bar was hiding it.
  Device validation on the 9 Pro is still pending.
- Tested the 4K60 wide SuperEIS flags on the OnePlus 9. Enabling
  `super.eis.wide.60fps.support` alone, and together with
  `video.eis.fps=60`, still makes the app fall back to 4K30 when Steady is
  enabled. The stock 30 fps cap is a real app/bandwidth limit, so the flags
  were not kept.

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
