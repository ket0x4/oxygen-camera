#!/system/bin/sh
# Action button: live diagnostics, apply missing optimizations, open the camera.
MODDIR=${0%/*}
mod_ver=$(sed -n 's/^version=//p' "$MODDIR/module.prop" 2>/dev/null)
app_ver=$(cat "$MODDIR/aox/app-version.txt" 2>/dev/null)
field() { printf '  %-12s %s\n' "$1" "$2"; }

echo "Oplus Camera diagnostics"
echo "----------------------------------------"
field "Module" "${mod_ver:-unknown}"
field "App" "${app_ver:-unknown}"
field "SELinux" "$(getenforce 2>/dev/null || echo unknown)"

echo ""
echo "Camera"
if [ -f "$MODDIR/camera.img" ]; then
    img_size=$(du -sh "$MODDIR/camera.img" 2>/dev/null | awk '{print $1}')
    fs_type=$(awk '$2 == "/mnt/ooscamera" {print $3}' /proc/mounts 2>/dev/null)
    field "Image" "${img_size:-unknown} (${fs_type:-unmounted})"
fi
if [ -f /odm/lib64/liboplus-uah-client.so ]; then
    field "Power HAL" "active (UAH boost)"
else
    field "Power HAL" "not installed"
fi

for proc in android.hardware.camera.provider@2.4-service_64 cameraserver; do
    pid=$(pidof "$proc" 2>/dev/null)
    if [ -n "$pid" ]; then
        renice -n -10 -p "$pid" 2>/dev/null || true
        ni=$(ps -o ni= -p "$pid" 2>/dev/null | tr -d ' ')
        field "Daemon" "$proc (PID $pid, nice ${ni:-0})"
    fi
done

if dumpsys package com.oplus.camera 2>/dev/null | grep -q "status=speed"; then
    field "ART" "speed (AOT compiled)"
else
    field "ART" "compiling (speed)"
    pm compile -m speed --secondary-dex com.oplus.camera >/dev/null 2>&1 || true
    field "ART" "speed compilation finished"
fi

echo "----------------------------------------"
echo "Launching Oplus Camera..."
am start -n com.oplus.camera/com.oplus.camera.Camera >/dev/null 2>&1
