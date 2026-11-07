#!/system/bin/sh
MODDIR=${0%/*}
# A clean boot allows another attempt next time; interrupted boots fail safe.
rm -f "$MODDIR/boot-pending"

# Boost Qualcomm Camera HAL provider and cameraserver to high priority (nice -10)
for proc in android.hardware.camera.provider@2.4-service_64 cameraserver; do
    pid=$(pidof "$proc" 2>/dev/null)
    if [ -n "$pid" ]; then
        renice -n -10 -p "$pid" 2>/dev/null || true
    fi
done

# Ensure OplusCamera DEX is AOT-compiled (speed) for instant launch & zero UI/capture stutter
(
    attempt=0
    while [ "$attempt" -lt 30 ]; do
        if pm path com.oplus.camera >/dev/null 2>&1; then
            break
        fi
        sleep 2
        attempt=$((attempt + 1))
    done

    if pm path com.oplus.camera >/dev/null 2>&1; then
        if ! dumpsys package com.oplus.camera 2>/dev/null | grep -q "status=speed"; then
            pm compile -m speed --secondary-dex com.oplus.camera >/dev/null 2>&1 || true
        fi
    fi
) &
