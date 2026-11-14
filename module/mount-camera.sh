#!/system/bin/sh
# Camera-only read-only overlays. Sourced by the installer and boot script.
# Uses KernelSU's bundled BusyBox; no metamodule or writable system partition.
camera_mounts() {
    # Only directories this payload actually carries: a build without
    # device-collected libraries has no vendor/lib64, for example.
    while read -r relative target; do
        [ -d "$1/$relative" ] && echo "$relative $target"
    done <<'EOF'
etc/sysconfig /system/etc/sysconfig
framework /system/framework
priv-app /system/priv-app
product/priv-app /product/priv-app
system_ext/etc/default-permissions /system_ext/etc/default-permissions
system_ext/etc/permissions /system_ext/etc/permissions
system_ext/framework /system_ext/framework
system_ext/lib64 /system_ext/lib64
system_ext/priv-app /system_ext/priv-app
vendor/lib /vendor/lib
vendor/lib64 /vendor/lib64
vendor/odm/etc/camera /odm/etc/camera
vendor/odm/lib/rfsa/adsp /odm/lib/rfsa/adsp
vendor/odm/lib64 /odm/lib64
EOF
}

camera_fail() {
    echo "Camera filesystem: $*"
    return 1
}

camera_prepare_image() {
    image="$MODPATH/camera.img"
    new_image="$MODPATH/camera.img.new"
    stage="$MODPATH/.camera-image"
    rm -f "$new_image"

    # Build beside the target image. Some managers run customize.sh against
    # the installed module while its image is still loop-mounted; never
    # reformat an image in place. The new file is renamed over camera.img
    # after validation and is used on the next boot.
    # Prefer compressed EROFS when supported: ~60% smaller, faster reads, direct creation without rw loop.
    if [ -x /system/bin/mkfs.erofs ] && grep -qw erofs /proc/filesystems; then
        echo "Building compressed EROFS camera image..."
        if /system/bin/mkfs.erofs -z lz4hc,level=9 -L OOSCamera "$new_image" "$MODPATH/system" >/dev/null 2>&1; then
            chmod 0600 "$new_image"
            chcon u:object_r:ksu_file:s0 "$new_image" 2>/dev/null || true
            mkdir -p "$stage" || return 1
            if mount -t erofs -o loop,ro,nodev,nosuid,noatime "$new_image" "$stage"; then
                camera_image_ok=1
                mkdir -p "$MODPATH/.camera-probe" || camera_image_ok=0
                while read -r relative target; do
                    [ -d "$target" ] || { camera_fail "this ROM has no $target"; camera_image_ok=0; break; }
                    if mount -t overlay -o "ro,lowerdir=$stage/$relative:$target" overlay "$MODPATH/.camera-probe" 2>/dev/null ||
                       mount -t overlay -o "ro,lowerdir=$stage/$relative:$target" KSU "$MODPATH/.camera-probe"; then
                        umount "$MODPATH/.camera-probe" || { camera_image_ok=0; break; }
                    else
                        camera_fail "overlay over $target was rejected by this kernel"
                        camera_image_ok=0
                        break
                    fi
                done <<EOF
$(camera_mounts "$stage")
EOF
                sync
                umount "$stage" || return 1
                rmdir "$stage" "$MODPATH/.camera-probe" 2>/dev/null || true
                if [ "$camera_image_ok" = 1 ]; then
                    mv "$new_image" "$image" || return 1
                    chmod 0600 "$image"
                    chcon u:object_r:ksu_file:s0 "$image" 2>/dev/null || true
                    rm -rf "$MODPATH/system"
                    return 0
                fi
            fi
            umount "$MODPATH/.camera-probe" 2>/dev/null || true
            umount "$stage" 2>/dev/null || true
            rm -f "$new_image"
            rmdir "$stage" "$MODPATH/.camera-probe" 2>/dev/null || true
        fi
    fi

    # Fallback to ext4 if EROFS is unavailable or probe failed.
    payload_kib=$(du -sk "$MODPATH/system" | awk '{print $1}')
    image_kib=$(( (payload_kib + 131072 + 65535) / 65536 * 65536 ))
    free_kib=$(df -Pk "$MODPATH" | tail -n 1 | awk '{print $4}')
    if [ "$free_kib" -lt "$((image_kib + 65536))" ]; then
        echo 'Insufficient free storage to prepare the camera filesystem.'
        return 1
    fi
    dd if=/dev/zero of="$new_image" bs=1024 count=0 seek="$image_kib" 2>/dev/null || { camera_fail "cannot create the image"; return 1; }
    /system/bin/mkfs.ext4 -q -O ^has_journal -m 0 -L OOSCamera "$new_image" || { camera_fail "mkfs.ext4 failed"; return 1; }
    chmod 0600 "$new_image"
    chcon u:object_r:ksu_file:s0 "$new_image" 2>/dev/null || true
    mkdir -p "$stage" || return 1
    mount -t ext4 -o loop,rw,nodev,nosuid,noatime "$new_image" "$stage" || { camera_fail "cannot loop-mount the image"; return 1; }
    camera_image_ok=1
    cp -aL "$MODPATH/system/." "$stage/" || { camera_fail "copying the payload failed"; camera_image_ok=0; }
    # BusyBox cp does not reliably preserve security.selinux on this device.
    while IFS= read -r source; do
        relative=${source#"$MODPATH/system"}
        chcon --reference="$source" "$stage$relative" 2>/dev/null || true
    done <<EOF
$(find -L "$MODPATH/system")
EOF
    # Validate each overlay against the current kernel before accepting install.
    mkdir -p "$MODPATH/.camera-probe" || camera_image_ok=0
    while read -r relative target; do
        [ -d "$target" ] || { camera_fail "this ROM has no $target"; camera_image_ok=0; break; }
        if mount -t overlay -o "ro,lowerdir=$stage/$relative:$target" overlay "$MODPATH/.camera-probe" 2>/dev/null ||
           mount -t overlay -o "ro,lowerdir=$stage/$relative:$target" KSU "$MODPATH/.camera-probe"; then
            umount "$MODPATH/.camera-probe" || { camera_image_ok=0; break; }
        else
            camera_fail "overlay over $target was rejected by this kernel"
            camera_image_ok=0
            break
        fi
    done <<EOF
$(camera_mounts "$stage")
EOF
    sync
    umount "$stage" || return 1
    rmdir "$stage" "$MODPATH/.camera-probe" || return 1
    [ "$camera_image_ok" = 1 ] || return 1
    mv "$new_image" "$image" || return 1
    chmod 0600 "$image"
    chcon u:object_r:ksu_file:s0 "$image" 2>/dev/null || true
    # The image now owns the payload: avoid storing a second unpacked copy.
    rm -rf "$MODPATH/system"
}

camera_mount() {
    [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || return 1
    [ ! -f /dev/ooscamera-mounted ] || return 0
    : > "$MODDIR/mount.log"
    if [ -f "$MODDIR/boot-pending" ]; then
        echo 'Previous boot did not complete; camera module disabled for recovery.' >> "$MODDIR/mount.log"
        touch "$MODDIR/disable"
        return 1
    fi
    touch "$MODDIR/boot-pending" || return 1
    stage=/mnt/ooscamera
    camera_mounted=
    mkdir -p "$stage" || return 1
    # Loop access selinux label
    chcon u:object_r:ksu_file:s0 "$MODDIR/camera.img" 2>/dev/null || true
    if ! mount -t erofs -o loop,ro,nodev,nosuid,noatime "$MODDIR/camera.img" "$stage" >> "$MODDIR/mount.log" 2>&1 &&
       ! mount -t ext4 -o loop,ro,nodev,nosuid,noatime "$MODDIR/camera.img" "$stage" >> "$MODDIR/mount.log" 2>&1 &&
       ! mount -o loop,ro,nodev,nosuid,noatime "$MODDIR/camera.img" "$stage" >> "$MODDIR/mount.log" 2>&1; then
        echo 'Cannot mount camera image; no camera overlays applied.' >> "$MODDIR/mount.log"
        touch "$MODDIR/disable"
        return 1
    fi
    camera_mount_ok=1
    while read -r relative target; do
        if [ -d "$stage/$relative" ] && [ -d "$target" ] &&
            { mount -t overlay -o "ro,lowerdir=$stage/$relative:$target" overlay "$target" >> "$MODDIR/mount.log" 2>&1 ||
              mount -t overlay -o "ro,lowerdir=$stage/$relative:$target" KSU "$target" >> "$MODDIR/mount.log" 2>&1; }; then
            camera_mounted="$target $camera_mounted"
            echo "Mounted $target" >> "$MODDIR/mount.log"
        else
            camera_mount_ok=0
            echo "Failed $target; rolling back camera overlays." >> "$MODDIR/mount.log"
            break
        fi
    done <<EOF
$(camera_mounts "$stage")
EOF
    if [ "$camera_mount_ok" != 1 ]; then
        for target in $camera_mounted; do
            umount "$target" >> "$MODDIR/mount.log" 2>&1
        done
        umount "$stage" >> "$MODDIR/mount.log" 2>&1
        touch "$MODDIR/disable"
        return 1
    fi
    touch /dev/ooscamera-mounted
    echo 'Camera overlays ready.' >> "$MODDIR/mount.log"
}
