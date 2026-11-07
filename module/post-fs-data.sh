#!/system/bin/sh
MODDIR=${0%/*}
# shellcheck source=module/mount-camera.sh
. "$MODDIR/mount-camera.sh"
camera_mount || exit 1
if [ -f "$MODDIR/aox.sh" ]; then
    # shellcheck source=module/aox.sh
    . "$MODDIR/aox.sh"
    aox_mount_media
fi
# Live Photo working directories. The ROM trees create them from
# /odm/etc/init/init.camera_process.rc, which init reads before modules mount.
for dir in /data/vendor/camera_process /data/vendor/camera_process/livephoto; do
    [ -d "$dir" ] && continue
    mkdir "$dir" && chown camera:camera "$dir" && chmod 0777 "$dir"
done
# A ROM without the aox policy leaves the store as vendor_data_file, which
# the app may not write. Use the type sepolicy.rule declares, else the camera
# data label.
chcon -R u:object_r:vendor_oplus_camera_process_file:s0 /data/vendor/camera_process 2>/dev/null ||
    chcon -R --reference=/data/vendor/camera /data/vendor/camera_process
RESETPROP=
for candidate in /data/adb/ksu/bin/resetprop /data/adb/magisk/resetprop /data/adb/ap/bin/resetprop resetprop /data/adb/ksud; do
    if command -v "$candidate" >/dev/null 2>&1; then
        RESETPROP="$candidate"
        break
    elif [ -x "$candidate" ]; then
        RESETPROP="$candidate"
        break
    fi
done

set_prop() {
    key=$1
    val=$2
    [ -n "$RESETPROP" ] || return 0
    if [ "$RESETPROP" = /data/adb/ksud ]; then
        "$RESETPROP" resetprop -n "$key" "$val" 2>/dev/null || true
    else
        "$RESETPROP" -n "$key" "$val" 2>/dev/null || true
    fi
}

append_camera() {
    key=$1
    current=$(getprop "$key")
    case ",$current," in
        *,com.oplus.camera,*) return ;;
    esac
    value=${current:+$current,}com.oplus.camera
    set_prop "$key" "$value"
}
append_camera persist.vendor.camera.privapp.list
append_camera persist.camera.privapp.list
# Preserve existing package entries. No persistent-property-store edits.
current=$(getprop vendor.camera.aux.packagelist)
[ -z "$current" ] || append_camera vendor.camera.aux.packagelist
set_prop persist.sys.oplus.anim_level 1
set_prop ro.com.google.lens.oem_camera_package com.oplus.camera
