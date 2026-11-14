#!/system/bin/sh
if [ "$KSU" = "true" ]; then
    ROOT_MNGR="KernelSU"
elif [ "$APATCH" = "true" ]; then
    ROOT_MNGR="APatch"
elif [ -n "$MAGISK_VER" ] || [ -d /data/adb/magisk ]; then
    ROOT_MNGR="Magisk"
else
    ROOT_MNGR="Root"
fi
ui_print " "
ui_print "  Oplus Camera — OnePlus 9 / 9 Pro"
# OnePlus 9 (lemonade) and 9 Pro (lemonadep): builds report the
# codename or the marketing name.
camera_device=
for prop in ro.product.vendor.device ro.product.device ro.build.product; do
    case "$(getprop "$prop")" in
        lemonade|lemonadep|OnePlus9|OnePlus9Pro) camera_device=$(getprop "$prop"); break ;;
    esac
done
[ -n "$camera_device" ] || abort "Expected a OnePlus 9 or a OnePlus 9 Pro."
case "$camera_device" in
    lemonadep|OnePlus9Pro) AOX_DEVICE=lemonadep ;;
    *) AOX_DEVICE=lemonade ;;
esac
CAMERA_SDK=$(getprop ro.build.version.sdk)
case "$CAMERA_SDK" in
    ''|*[!0-9]*) abort "Cannot determine Android SDK version." ;;
esac
[ "$CAMERA_SDK" -ge 36 ] || abort "Requires Android 16 / SDK 36 or newer."
case "$CAMERA_SDK" in
    36) ANDROID_LABEL="Android 16 (SDK 36)" ;;
    37) ANDROID_LABEL="Android 17 (SDK 37)" ;;
    *) ANDROID_LABEL="Android SDK $CAMERA_SDK (experimental)" ;;
esac
[ -x /system/bin/mkfs.erofs ] || [ -x /system/bin/mkfs.ext4 ] || abort "Missing filesystem tools (mkfs.erofs / mkfs.ext4)."
grep -qw overlay /proc/filesystems || abort "This kernel needs OverlayFS support."
MODVER=$(sed -n 's/^version=//p' "$MODPATH/module.prop" 2>/dev/null)
APPVER=$(cat "$MODPATH/aox/app-version.txt" 2>/dev/null)
ui_print "  app ${APPVER:-unknown} · module ${MODVER:-unknown} · $ROOT_MNGR"
ui_print " "
ui_print "> Checking compatibility"
ui_print "  device  $camera_device"
ui_print "  rom     $(getprop ro.build.display.id) · $ANDROID_LABEL"
ui_print "  mount   standalone OverlayFS (no Mountify)"
if [ -f "$MODPATH/ksu-visibility" ]; then
    set_perm "$MODPATH/ksu-visibility" 0 0 0700
    # Without the helper the boot scripts do nothing and the App Profile
    # switch is the user's to set; the message at the end says which it is.
    "$MODPATH/ksu-visibility" check >/dev/null 2>&1 || rm -f "$MODPATH/ksu-visibility"
fi
if [ -f "$MODPATH/aox.sh" ]; then
    ui_print " "
    ui_print "> Applying camera changes"
    # shellcheck source=module/aox.sh
    . "$MODPATH/aox.sh"
    if ! aox_install; then
        # The module directory is discarded on failure; keep the reasons.
        cp "$MODPATH/aox.log" /data/local/tmp/ooscamera-install.log 2>/dev/null
        abort "$(grep -E '^(fail|app) ' "$MODPATH/aox.log" | tail -n 1 | cut -c 7-) (log: /data/local/tmp/ooscamera-install.log)"
    fi
fi
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/post-fs-data.sh" 0 0 0755
set_perm "$MODPATH/action.sh" 0 0 0755
set_perm "$MODPATH/boot-completed.sh" 0 0 0755
set_perm "$MODPATH/mount-camera.sh" 0 0 0755
if [ -f "$MODPATH/ksu-visibility" ]; then
    set_perm "$MODPATH/ksu-visibility" 0 0 0700
    set_perm "$MODPATH/service.sh" 0 0 0755
    set_perm "$MODPATH/uninstall.sh" 0 0 0755
fi
set_perm_recursive "$MODPATH/system" 0 0 0755 0644 u:object_r:system_file:s0
if [ -f "$MODPATH/native-labels.txt" ]; then
    while IFS= read -r path; do
        # aox libraries this device does not need were removed above.
        [ -f "$MODPATH/$path" ] || continue
        case "$path" in
            system/vendor/odm/lib64/*.so|system/vendor/lib64/*.so|system/vendor/lib/*.so)
                chcon u:object_r:same_process_hal_file:s0 "$MODPATH/$path" ;;
        esac
    done < "$MODPATH/native-labels.txt"
fi
[ -f "$MODPATH/aox.sh" ] && aox_label
ui_print " "
ui_print "> Preparing camera image"
# shellcheck source=module/mount-camera.sh
. "$MODPATH/mount-camera.sh"
if ! camera_prepare_image; then
    # Never leave installer mounts or a partial replacement image behind.
    umount "$MODPATH/.camera-probe" 2>/dev/null
    umount "$MODPATH/.camera-image" 2>/dev/null
    rm -f "$MODPATH/camera.img.new"
    cp "$MODPATH/aox.log" /data/local/tmp/ooscamera-install.log 2>/dev/null
    abort "Camera filesystem preparation failed; installation cancelled."
fi
if [ "$(getprop sys.boot_completed)" = "1" ] && [ -x /system/bin/pm ]; then
    if pm path com.oplus.camera >/dev/null 2>&1; then
        ui_print " "
        ui_print "> Optimizing app (AOT)"
        pm compile -m speed --secondary-dex com.oplus.camera >/dev/null 2>&1 || true
        ui_print "  dex     speed compilation requested"
    fi
fi
ui_print " "
ui_print "  Installation complete — reboot to activate."
ui_print "  Open Oplus Camera and grant its permissions."
if [ -f "$MODPATH/ksu-visibility" ]; then
    ui_print "  Visibility automatic: camera and launcher get Umount modules OFF."
    ui_print "  If the camera still closes: App Profile → Oplus Camera → Umount modules OFF."
else
    ui_print "  This KernelSU has no usable app profile interface."
    ui_print "  App Profile → Oplus Camera → Custom → Umount modules OFF."
    ui_print "  Leave camera Superuser access OFF."
fi
