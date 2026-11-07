#!/system/bin/sh
MODDIR=${0%/*}
mod_ver=$(sed -n 's/^version=//p' "$MODDIR/module.prop" 2>/dev/null)
app_ver=$(cat "$MODDIR/aox/app-version.txt" 2>/dev/null)
echo "=== Oplus Camera Port (${mod_ver:-unknown} / App ${app_ver:-unknown}) ==="
echo "SELinux: $(getenforce 2>/dev/null || echo unknown)"

if [ -f "$MODDIR/camera.img" ]; then
    img_size=$(du -sh "$MODDIR/camera.img" 2>/dev/null | awk '{print $1}')
    fs_type=$(awk '$2 == "/mnt/ooscamera" {print $3}' /proc/mounts 2>/dev/null)
    echo "Camera Image: ${img_size:-unknown} (${fs_type:-unmounted})"
fi

if [ -f /odm/lib64/liboplus-uah-client.so ]; then
    echo "Power HAL Boost (UAH): active"
else
    echo "Power HAL Boost (UAH): not installed"
fi

for proc in android.hardware.camera.provider@2.4-service_64 cameraserver; do
    pid=$(pidof "$proc" 2>/dev/null)
    if [ -n "$pid" ]; then
        renice -n -10 -p "$pid" 2>/dev/null || true
        ni=$(ps -o ni= -p "$pid" 2>/dev/null | tr -d ' ')
        echo "Daemon $proc (PID $pid): nice ${ni:-0}"
    fi
done

if dumpsys package com.oplus.camera 2>/dev/null | grep -q "status=speed"; then
    echo "ART DEX State: speed (AOT compiled)"
else
    echo "ART DEX State: optimizing (running pm compile -m speed)..."
    pm compile -m speed --secondary-dex com.oplus.camera >/dev/null 2>&1 || true
    echo "ART DEX State: speed compilation finished"
fi

echo "Launching OplusCamera..."
am start -n com.oplus.camera/com.oplus.camera.Camera >/dev/null 2>&1
