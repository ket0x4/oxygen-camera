#!/usr/bin/env python3
"""Package OplusCamera and the aox camera changes as a KernelSU Next module."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import elf_align
import patch_algo
import patch_apk
import patch_hal
import patch_sdk

ROOT = pathlib.Path(__file__).resolve().parents[1]
AOX_MANIFEST = ROOT / "aox/manifest.json"
REPOSITORY = "ket0x4/oxygen-camera"
CAMERA_APK = "system_ext/priv-app/OplusCamera/OplusCamera.apk"
FWK_JAR = "system/framework/oplus-fwk.jar"
FWK_EXTRA = [b"Lcom/oplus/os/WaveformEffect$Builder;", b"Lcom/oplus/os/LinearmotorVibrator;",
             b"Lcom/oplus/util/OplusTypeCastingHelper;"]
UAH_CLIENT_PATH = "odm/lib64/liboplus-uah-client.so"
UAH_CLIENT_MARKER = b"ooscamera-aox-uah-client"
UAH_CLIENT_SYMBOLS = [
    "UahEventAcquireWrapper", "UahRelease", "UahReleaseWapper", "setRelatedSysInfo", "uahInit",
    "UahNotifyWapper", "UahNotify", "UahEventAcquire", "UahEventAcquireOneWay", "UahResAcquire",
    "UahPlatformResAcquire", "UahResStateRequest", "UahMutiResStateRequest", "UahGetHistory",
    "UahGetPowerConsis", "UahGetPMStatus", "Uah_fetch_dataset", "uahRuleCtl", "UahResourceInfo",
]


def elf_needed(data):
    """DT_NEEDED names of an ELF64 little-endian AArch64 shared library."""
    if data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise SystemExit("Expected an ELF64 little-endian AArch64 library")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phsize, phnum = struct.unpack_from("<HH", data, 54)
    headers = [struct.unpack_from("<IIQQQQQQ", data, phoff + i * phsize) for i in range(phnum)]
    dynamic = next(h for h in headers if h[0] == 2)
    entries = []
    for offset in range(dynamic[2], dynamic[2] + dynamic[5], 16):
        tag, value = struct.unpack_from("<qQ", data, offset)
        if tag == 0:
            break
        entries.append((tag, value))
    straddr = next(value for tag, value in entries if tag == 5)
    segment = next(h for h in headers if h[0] == 1 and h[3] <= straddr < h[3] + h[5])
    stroff = segment[2] + straddr - segment[3]
    return [data[stroff + value:data.index(b"\0", stroff + value)].decode()
            for tag, value in entries if tag == 1]


def find_tool(name):
    found = shutil.which(name)
    if found:
        return found
    sdk_root = pathlib.Path.home() / ".local/share/android/sdk/build-tools"
    if sdk_root.exists():
        for version_dir in sorted(sdk_root.iterdir(), reverse=True):
            candidate = version_dir / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return name


def aox_target(stage, path):
    """Module payload path of a device path."""
    parts = pathlib.PurePosixPath(path).parts
    if ".." in parts or parts[0] not in ("odm", "vendor", "system", "system_ext"):
        raise SystemExit(f"Invalid aox path: {path}")
    if parts[0] == "odm":  # /odm is staged under the vendor tree
        return stage / "system/vendor" / path
    return stage / path if parts[0] == "system" else stage / "system" / path


def check_apk_alignment(path):
    """The app maps its libraries straight from the APK: stored .so entries
    must start on a 16 KB boundary and be 16 KB aligned inside the ELF,
    other stored entries on 4 bytes."""
    with zipfile.ZipFile(path) as archive, path.open("rb") as handle:
        if archive.testzip():
            raise SystemExit("Camera APK contains a damaged ZIP entry")
        for entry in archive.infolist():
            if entry.compress_type != zipfile.ZIP_STORED:
                continue
            handle.seek(entry.header_offset + 26)
            name, extra = struct.unpack("<HH", handle.read(4))
            offset = entry.header_offset + 30 + name + extra
            if entry.filename.endswith(".so"):
                if offset % 16384:
                    raise SystemExit(f"Camera APK entry is not 16 KB aligned: {entry.filename}")
                value = elf_align.alignment(archive.read(entry.filename))
                if value is not None and value < elf_align.ALIGN_16K:
                    raise SystemExit(
                        f"Camera APK library is not 16 KB aligned: {entry.filename} (0x{value:x})")
            elif offset % 4:
                raise SystemExit(f"Camera APK entry is not aligned: {entry.filename}")


def sign_apk(source, target, keys, apksigner):
    """Sign with the public AOSP platform test key (v2/v3 only, so no ZIP
    entry moves and the alignment checked above is kept)."""
    check_apk_alignment(source)
    subprocess.run([apksigner, "sign", "--key", str(keys / "platform.pk8"),
                    "--cert", str(keys / "platform.x509.pem"), "--min-sdk-version", "30",
                    "--v1-signing-enabled", "false", "--v2-signing-enabled", "true",
                    "--v3-signing-enabled", "true", "--out", str(target), str(source)], check=True)
    idsig = target.with_name(target.name + ".idsig")
    idsig.unlink(missing_ok=True)
    subprocess.run([apksigner, "verify", "--min-sdk-version", "30", str(target)], check=True)
    check_apk_alignment(target)


def stage_aox(stage, cache, uah_client, apksigner="apksigner", zipalign="zipalign"):
    """Stage the camera app, the aox libraries and the on-device edit data.

    The app set is copied as is and listed in aox/app.txt, so the installer
    can drop it when the ROM already ships this camera. Everything else goes
    through aox/files.txt: customize.sh decides on the device which of those
    files apply. Files the module already provides (libraries collected from
    the device) are left untouched.
    """
    manifest = json.loads(AOX_MANIFEST.read_text())
    source = json.loads((cache / "source.json").read_text())
    if source.get("sources") != manifest["sources"]:
        raise SystemExit("aox cache was prepared for different revisions; run prepare_aox.py")
    data_dir = stage / "aox"
    shutil.copytree(ROOT / "module/aox", data_dir)
    lines, labels, app, staged, provided = [], [], [], {}, []
    for entry in manifest["files"]:
        path, device = entry["path"], entry.get("device", "")
        local = cache / device / path
        if hashlib.sha256(local.read_bytes()).hexdigest() != entry["sha256"]:
            raise SystemExit(f"aox checksum mismatch: {path}")
        target = aox_target(stage, path)
        relative = str(target.relative_to(stage))
        digest = entry["sha256"]
        if entry["group"] == "app":
            target.parent.mkdir(parents=True, exist_ok=True)
            if entry["kind"] == "apk":
                if entry.get("patch") == "raw-capture":
                    with tempfile.NamedTemporaryFile(suffix=".apk") as patched:
                        patch_apk.patch_apk(local, pathlib.Path(patched.name),
                                           cache / "inputs/baksmali.jar", cache / "inputs/smali.jar", zipalign)
                        sign_apk(pathlib.Path(patched.name), target, cache / "keys", apksigner)
                else:
                    sign_apk(local, target, cache / "keys", apksigner)
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
            elif entry.get("patch") == "client-package":
                patch_sdk.patch_jar(local, target, cache / "inputs/baksmali.jar", cache / "inputs/smali.jar")
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
            else:
                data = local.read_bytes()
                if entry["kind"] == "library":
                    data = elf_align.align(data)
                    digest = hashlib.sha256(data).hexdigest()
                target.write_bytes(data)
            app.append(relative)
        else:
            # Libraries collected from the device win, except over the ones
            # the app is paired with.
            if target.exists() and not device and entry["group"] != "pair":
                provided.append(path)
                continue
            # A per-device file waits under variants/ until the installer
            # knows which phone this is.
            if device:
                target = data_dir / "variants" / device / path
            target.parent.mkdir(parents=True, exist_ok=True)
            data = local.read_bytes()
            if entry.get("patch") == "session-key":
                data = patch_hal.patch(data)
                digest = hashlib.sha256(data).hexdigest()
            elif entry.get("patch") == "night-blacklevel":
                data = patch_algo.patch_interface(data)
                digest = hashlib.sha256(data).hexdigest()
            elif entry.get("patch") == "p010-scanline":
                data = patch_algo.patch_process(data)
                digest = hashlib.sha256(data).hexdigest()
            elif entry.get("patch") == "validate-buffersize":
                data = patch_algo.patch_imageformatutils(data)
                digest = hashlib.sha256(data).hexdigest()
            elif entry.get("patch") == "chi-override":
                data = patch_algo.patch_chi_override(data)
                digest = hashlib.sha256(data).hexdigest()
            if entry["kind"] == "library":
                data = elf_align.align(data)
                digest = hashlib.sha256(data).hexdigest()
            target.write_bytes(data)
            lines.append("|".join([path, entry["install"], digest,
                                   ",".join(entry.get("replace_sha256", [])),
                                   ",".join(entry.get("needed", [])), device]))
        staged[(device + ":" if device else "") + path] = digest
        if entry["kind"] == "library" and path.startswith(("odm/", "vendor/")):
            labels.append(relative)
    if uah_client:
        data = elf_align.align(uah_client.read_bytes())
        needed = elf_needed(data)
        if UAH_CLIENT_MARKER not in data or not set(needed) <= {"libc.so", "libdl.so"}:
            raise SystemExit("Unexpected liboplus-uah-client build; use native/uah-client/build.sh")
        if any(symbol.encode() + b"\0" not in data for symbol in UAH_CLIENT_SYMBOLS):
            raise SystemExit("liboplus-uah-client is missing a stock entry point")
        target = aox_target(stage, UAH_CLIENT_PATH)
        if target.exists():
            provided.append(UAH_CLIENT_PATH)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            staged[UAH_CLIENT_PATH] = digest
            lines.append("|".join([UAH_CLIENT_PATH, "uah", digest, "", ",".join(needed), ""]))
            labels.append(str(target.relative_to(stage)))

    # Permissions: the camera's own grants and its two SDK libraries.
    permissions = stage / "system/system_ext/etc/permissions/ooscamera-op9.xml"
    permissions.parent.mkdir(parents=True, exist_ok=True)
    doc = ET.parse(cache / "inputs/privapp-permissions-oplus.xml")
    for node in list(doc.getroot()):
        if node.tag == "privapp-permissions" and node.get("package") != "com.oplus.camera":
            doc.getroot().remove(node)
    # Expose the wrapper through an app library dependency, rather than adding
    # an OEM JAR to the device's global boot classpath.
    ET.SubElement(doc.getroot(), "library", {
        "name": "org.ooscamera.compat", "file": "/system/framework/oplus-support-wrapper.jar"})
    for node in doc.getroot().findall("library"):
        if node.get("name", "").startswith("com.oplus.camera.unit.sdk"):
            node.set("dependency", "org.ooscamera.compat")
    ET.indent(doc)
    doc.write(permissions, encoding="utf-8", xml_declaration=True)
    sysconfig = stage / "system/etc/sysconfig/ooscamera-hidden-api.xml"
    sysconfig.parent.mkdir(parents=True, exist_ok=True)
    sysconfig.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<config><hidden-api-whitelisted-app package="com.oplus.camera"/></config>\n')
    app += [str(permissions.relative_to(stage)), str(sysconfig.relative_to(stage))]

    # The boot jar the 5.x app needs; the installer keeps it only when the
    # ROM's own oplus-fwk.jar lacks the classes listed in fwk-markers.txt.
    framework = cache / "inputs/oplus-fwk.jar"
    if framework.exists():
        with zipfile.ZipFile(framework) as archive:
            dex = b"".join(archive.read(name) for name in archive.namelist()
                           if re.fullmatch(r"classes\d*\.dex", name))
        if any(marker.encode() not in dex for marker in manifest["fwk_markers"]):
            raise SystemExit("oplus-fwk.jar input lacks the classes the camera needs")
        # AxionOS has these in frameworks/base; other ROMs get them from fwk/.
        if any(name not in dex for name in FWK_EXTRA):
            raise SystemExit("oplus-fwk.jar input lacks the fwk/ classes")
        (stage / FWK_JAR).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(framework, stage / FWK_JAR)
        staged[FWK_JAR] = hashlib.sha256(framework.read_bytes()).hexdigest()

    (data_dir / "files.txt").write_text(
        "# path|rule|sha256|replace sha256s|needed|device (generated by build.py)\n"
        + "".join(line + "\n" for line in lines))
    (data_dir / "app.txt").write_text("".join(path + "\n" for path in app))
    (data_dir / "app-version.txt").write_text(manifest["app_version"] + "\n")
    (data_dir / "fwk-markers.txt").write_text("".join(m + "\n" for m in manifest["fwk_markers"]))
    with (stage / "native-labels.txt").open("a") as handle:
        handle.write("".join(label + "\n" for label in labels))
    for name in ("aox.sh", "sepolicy.rule"):
        shutil.copyfile(ROOT / "module" / name, stage / name)
    (stage / "aox-source.json").write_text(json.dumps({
        "branch": manifest["branch"], "app_version": manifest["app_version"],
        "sources": manifest["sources"], "files": staged, "module_provided": provided,
        "apk_signing": "public AOSP platform test key",
        "edits": "aox/edits.txt, applied on the device at install time"}, indent=2) + "\n")


def update_metadata(version, version_code, zip_name, tag=None):
    if tag:
        zip_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/{zip_name}"
    else:
        zip_url = f"https://github.com/{REPOSITORY}/releases/latest/download/{zip_name}"
    return {
        "version": version,
        "versionCode": version_code,
        "zipUrl": zip_url,
        "changelog": f"https://raw.githubusercontent.com/{REPOSITORY}/main/CHANGELOG.md",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=pathlib.Path, default=ROOT / "build")
    parser.add_argument("--candidate-version", help="Explicit prerelease version for an unvalidated test module")
    parser.add_argument("--update-tag", help="GitHub release tag used for the update.json zipUrl")
    parser.add_argument("--update-url", help="updateJson= URL to write into the staged module.prop")
    parser.add_argument("--visibility-cache", type=pathlib.Path,
                        help="App profile helper from prepare_visibility.py")
    parser.add_argument("--camera-config", type=pathlib.Path, help="Device camera configuration override")
    parser.add_argument("--aox-cache", type=pathlib.Path, default=ROOT / ".cache/aox",
                        help="Files fetched by prepare_aox.py")
    parser.add_argument("--uah-client", type=pathlib.Path,
                        help="liboplus-uah-client.so from native/uah-client/build.sh")
    parser.add_argument("--apksigner", default=find_tool("apksigner"),
                        help="apksigner from Android SDK Build Tools")
    parser.add_argument("--zipalign", default=find_tool("zipalign"),
                        help="zipalign from Android SDK Build Tools")
    args = parser.parse_args()
    if args.uah_client is None:
        default_uah = args.aox_cache / "liboplus-uah-client.so"
        if not default_uah.exists() and shutil.which("clang") and shutil.which("ld.lld"):
            default_uah.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["sh", str(ROOT / "native/uah-client/build.sh"), str(default_uah)], check=True)
        if default_uah.exists():
            args.uah_client = default_uah
    if args.visibility_cache is None:
        for candidate in (ROOT / "build/visibility", args.aox_cache / "visibility"):
            if (candidate / "source.json").exists() and (candidate / "ksu-visibility").exists():
                args.visibility_cache = candidate
                break
    if args.candidate_version and not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*-[A-Za-z0-9.-]+", args.candidate_version):
        raise SystemExit("Candidate version must include a prerelease suffix")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stage = output_dir / "module"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    if args.camera_config:
        json.loads(args.camera_config.read_text())
        target = stage / "system/vendor/odm/etc/camera/config/oplus_camera_config"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.camera_config, target)

    # After every other payload: anything the module already ships wins.
    stage_aox(stage, args.aox_cache, args.uah_client, args.apksigner, args.zipalign)

    for name in ["module.prop", "customize.sh", "post-fs-data.sh", "action.sh",
                 "mount-camera.sh", "boot-completed.sh", "skip_mount"]:
        shutil.copyfile(ROOT / "module" / name, stage / name)
    if args.visibility_cache:
        from prepare_visibility import PROFILE_VERSIONS
        visibility = json.loads((args.visibility_cache / "source.json").read_text())
        helper = (args.visibility_cache / "ksu-visibility").read_bytes()
        if (visibility.get("profile_versions") != PROFILE_VERSIONS or
                visibility.get("binary_sha256") != hashlib.sha256(helper).hexdigest() or
                visibility.get("source_sha256") != hashlib.sha256((ROOT / "native/ksu_visibility.c").read_bytes()).hexdigest()):
            raise SystemExit("Visibility helper source or payload mismatch")
        (stage / "ksu-visibility").write_bytes(helper)
        (stage / "visibility-source.json").write_text(json.dumps(visibility, indent=2) + "\n")
        for name in ("service.sh", "uninstall.sh", "visibility.sh"):
            shutil.copyfile(ROOT / "module" / name, stage / name)
    if args.update_url:
        prop = stage / "module.prop"
        prop.write_text(re.sub(r"(?m)^updateJson=.*$", "updateJson=" + args.update_url, prop.read_text()))
    bad = elf_align.check_tree(stage)
    if bad:
        raise SystemExit(f"{len(bad)} staged libraries are still below 16 KB alignment")
    total = sum(1 for path in stage.rglob("*.so")
                if elf_align.alignment(path.read_bytes()) is not None)
    print(f"16 KB aligned {total} staged ELF64 libraries")
    if args.candidate_version:
        prop = stage / "module.prop"
        text = re.sub(r"(?m)^version=.*$", "version=" + args.candidate_version, prop.read_text())
        text = re.sub(r"(?m)^name=(.*)$", r"name=\1 — TEST BUILD", text)
        text = re.sub(r"(?m)^description=.*$",
                      "description=Unvalidated compatibility candidate; device tests pending.", text)
        prop.write_text(text)
    manifest = {"sources": json.loads(AOX_MANIFEST.read_text())["sources"],
                "status": "experimental; device validation required", "files": {}}
    for path in sorted(stage.rglob("*")):
        if path.is_file():
            manifest["files"][str(path.relative_to(stage))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (stage / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    properties = dict(line.split("=", 1) for line in (stage / "module.prop").read_text().splitlines()
                      if "=" in line and not line.startswith("#"))
    version = properties["version"]
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?:-[A-Za-z0-9.-]+)?", version):
        raise SystemExit("Module version is not suitable for an artifact filename")
    output = output_dir / f"OplusCamera-OP9-{version}.zip"
    temporary = output.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                # Fixed ZIP epoch: do not publish the local build date or time.
                info = zipfile.ZipInfo(str(path.relative_to(stage)), (1980, 1, 1, 0, 0, 0))
                info.external_attr = (0o100755 if path.suffix == ".sh" else 0o100644) << 16
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    temporary.replace(output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n")
    # Preserve the existing local install/audit entry point.
    latest = output_dir / "OplusCamera-OP9.zip"
    latest.unlink(missing_ok=True)
    latest.symlink_to(output.name)
    latest.with_suffix(".zip.sha256").write_text(f"{digest}  {latest.name}\n")
    update = update_metadata(version, int(properties["versionCode"]), output.name, args.update_tag)
    (output_dir / "update.json").write_text(json.dumps(update, indent=2) + "\n")
    print(f"{output}: {output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
