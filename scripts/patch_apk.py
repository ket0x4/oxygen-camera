#!/usr/bin/env python3
"""Patch OplusCamera.apk to fix RAW capture, Log Video crash, Portrait freeze, and Front camera viewfinder.

Fixes applied:
1. classes.dex:
   - ApsService$CameraPictureCallbackImpl: Removes gates on j0.U(), j0.w(), j0.x0() so format 32
     RAW frames are forwarded directly to CaptureProcessor on OP9.
   - com.oplus.base.ocrscanner.oseesdk.a: In LogPreviewView popup show, handles null ListView (o)
     by falling back to RecyclerView (r) and null-checking before rotation; bypasses addGuideIcon
     which crashes on missing coui_popup_wrapper.

2. classes2.dex:
   - CameraEntry: In k(ILjava/lang/String;)I, routes back_dual and back_second_dual directly to
     Lab/r;->v() (Camera ID 12 / rear_sat) instead of falling back to non-existent Camera ID 100/101.
   - ab.r: Methods q() and w() redirected to invoke v() (rear_sat), preventing any query for ID 100.

3. classes3.dex:
   - ne.g (FaceSlenderTexturePreview): In canProcess()Z, checks mbInitEngineFinish (this.h) and
     OplusFaceBeautyPreviewHelper (this.g); if engine is not initialized or helper is null, returns
     false so the camera preview stream renders directly without blacking out the viewfinder.

4. classes6.dex:
   - dl.i (XPanViewManager): In a(), passes false to CameraConfig.getSizeConfigValue("com.oplus.xpan.wide.picturesize", false)
     so the 30mm Ultra-Wide / 45mm Wide camera switch bar is displayed and operational in XPan mode.

5. classes7.dex:
   - em.o0 (MasterCapMode): fg() delegates directly to super.fg().
   - em.v (HSProfessionalCapMode): Nj(J)Z checks this.N2 (raw frame flag) instead of waiting for
     null thumbnail this.L2; Oj(J)V falls back to CaptureProcessor.n if this.W2 <= 0.

6. classes33.dex:
   - jh.x: In onDismiss of LogPreviewView popup, null-checks coui_popup_wrapper and this.e before
     calling removeView to prevent NPE on dismiss.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import zipfile


def patch_smali_aps(text):
    marker_before = "if-ne v1, v3, :cond_168"
    marker_after = '"com.oplus.feature.professional.dng.encode.inAps"'
    idx1 = text.find(marker_before)
    if idx1 == -1:
        raise SystemExit("ApsService smali: marker_before not found")
    idx2 = text.find(marker_after, idx1)
    if idx2 == -1:
        raise SystemExit("ApsService smali: marker_after not found")

    idx_const = text.rfind("const-string v1, ", idx1, idx2)
    if idx_const == -1:
        raise SystemExit("ApsService smali: const-string v1 not found")

    new_snippet = "if-ne v1, v3, :cond_168\n\n    "
    return text[:idx1] + new_snippet + text[idx_const:]


def patch_smali_log_preview(text):
    # Fix 1: Null check on ListView / fallback to RecyclerView before rotation
    rot_marker = """    iget-object v1, p0, Lcom/oplus/camera/feature/logvideo/view/LogPreviewView;->a:Lcom/coui/appcompat/poplist/n;

    .line 102
    iget-object v1, v1, Lcom/coui/appcompat/poplist/n;->o:Landroid/widget/ListView;

    .line 103
    iget v2, v0, Lcom/oplus/camera/common/config/PopupWindowConfigs;->mPopupWindowRotation:I

    int-to-float v2, v2

    invoke-virtual {v1, v2}, Landroid/view/View;->setRotation(F)V"""

    new_rot = """    iget-object v1, p0, Lcom/oplus/camera/feature/logvideo/view/LogPreviewView;->a:Lcom/coui/appcompat/poplist/n;

    if-eqz v1, :cond_rot_skip

    iget-object v2, v1, Lcom/coui/appcompat/poplist/n;->o:Landroid/widget/ListView;

    if-nez v2, :cond_rot_use_o

    iget-object v2, v1, Lcom/coui/appcompat/poplist/n;->r:Lcom/coui/appcompat/poplist/COUITouchRecyclerView;

    :cond_rot_use_o
    if-eqz v2, :cond_rot_skip

    iget v1, v0, Lcom/oplus/camera/common/config/PopupWindowConfigs;->mPopupWindowRotation:I

    int-to-float v1, v1

    invoke-virtual {v2, v1}, Landroid/view/View;->setRotation(F)V

    :cond_rot_skip"""

    if rot_marker in text:
        text = text.replace(rot_marker, new_rot, 1)

    # Fix 2: Skip addGuideIcon while preserving register v1 as String for logPrint
    guide_marker = """    const-string v1, "LogPreviewView"

    if-nez v0, :cond_3eb"""

    new_guide = """    const-string v1, "LogPreviewView"

    goto :cond_3eb"""

    if guide_marker in text:
        text = text.replace(guide_marker, new_guide, 1)

    return text


def patch_smali_camera_entry(text):
    # Route back_dual directly to Lab/r;->v()
    idx_m = text.find(".method public final k(ILjava/lang/String;)I")
    if idx_m == -1:
        raise SystemExit("CameraEntry: method k not found")

    marker1 = "if-eqz p1, :cond_139"
    idx1 = text.find(marker1, idx_m)
    if idx1 == -1:
        raise SystemExit("CameraEntry: marker1 not found")
    idx_end1 = text.find(":cond_139", idx1 + len(marker1))
    if idx_end1 == -1:
        raise SystemExit("CameraEntry: :cond_139 not found")

    new_block1 = """if-eqz p1, :cond_139

    invoke-static {}, Lab/r;->v()I

    move-result p0

    return p0

    """
    text = text[:idx1] + new_block1 + text[idx_end1:]

    # Route back_second_dual directly to Lab/r;->v()
    marker2 = "if-eqz p1, :cond_151"
    idx2 = text.find(marker2, idx_m)
    if idx2 == -1:
        raise SystemExit("CameraEntry: marker2 not found")
    idx_end2 = text.find(":cond_151", idx2 + len(marker2))
    if idx_end2 == -1:
        raise SystemExit("CameraEntry: :cond_151 not found")

    new_block2 = """if-eqz p1, :cond_151

    invoke-static {}, Lab/r;->v()I

    move-result p0

    return p0

    """
    text = text[:idx2] + new_block2 + text[idx_end2:]
    return text


def patch_smali_ab_r(text):
    def replace_method(src, sig, new_body):
        idx = src.find(sig)
        if idx == -1:
            raise SystemExit(f"ab/r.smali: {sig} not found")
        idx_end = src.find(".end method", idx)
        if idx_end == -1:
            raise SystemExit(f"ab/r.smali: end of {sig} not found")
        return src[:idx] + new_body + src[idx_end + len(".end method"):]

    new_q = """.method public static q()I
    .registers 1

    invoke-static {}, Lab/r;->v()I

    move-result v0

    return v0
.end method"""

    new_w = """.method public static w()I
    .registers 1

    invoke-static {}, Lab/r;->v()I

    move-result v0

    return v0
.end method"""

    text = replace_method(text, ".method public static q()I", new_q)
    text = replace_method(text, ".method public static w()I", new_w)
    return text


def patch_smali_face_slender(text):
    marker = """    iget-boolean v0, p0, Lne/g;->i:Z

    .line 15
    .line 16
    if-nez v0, :cond_17

    .line 17
    .line 18
    const-string p0, "canProcess, texture is not inited"

    .line 19
    .line 20
    invoke-static {v1, p0}, Lza/a;->L(Ljava/lang/String;Ljava/lang/String;)V

    .line 21
    .line 22
    .line 23
    return v2"""

    replacement = """    iget-boolean v0, p0, Lne/g;->i:Z

    if-nez v0, :cond_check_engine

    const-string p0, "canProcess, texture is not inited"

    invoke-static {v1, p0}, Lza/a;->L(Ljava/lang/String;Ljava/lang/String;)V

    return v2

    :cond_check_engine
    iget-boolean v0, p0, Lne/g;->h:Z

    if-nez v0, :cond_check_helper

    const-string p0, "canProcess, engine is not inited"

    invoke-static {v1, p0}, Lza/a;->L(Ljava/lang/String;Ljava/lang/String;)V

    return v2

    :cond_check_helper
    iget-object v0, p0, Lne/g;->g:Lcom/oplus/ocs/camera/OplusFaceBeautyPreviewHelper;

    if-nez v0, :cond_check_ok

    const-string p0, "canProcess, helper is null"

    invoke-static {v1, p0}, Lza/a;->L(Ljava/lang/String;Ljava/lang/String;)V

    return v2

    :cond_check_ok"""

    if marker not in text:
        raise SystemExit("ne/g.smali: canProcess marker not found")
    return text.replace(marker, replacement, 1)


def patch_smali_o0(text):
    method_sig = ".method public fg(Lcom/oplus/camera/protocal/event/message/deviceProtocol/deviceControlRequest/EventMessageCaptureRequestStage;)V"
    idx = text.find(method_sig)
    if idx == -1:
        raise SystemExit("em/o0.smali: fg method not found")
    idx_end = text.find(".end method", idx)
    if idx_end == -1:
        raise SystemExit("em/o0.smali: end of fg method not found")
    new_fg = method_sig + """
    .registers 3

    invoke-super {p0, p1}, Lem/v;->fg(Lcom/oplus/camera/protocal/event/message/deviceProtocol/deviceControlRequest/EventMessageCaptureRequestStage;)V

    return-void
.end method"""
    return text[:idx] + new_fg + text[idx_end + len(".end method"):]


def patch_smali_v(text):
    idx_nj = text.find(".method public final Nj(J)Z")
    if idx_nj == -1:
        raise SystemExit("em/v.smali: Nj(J)Z method not found")
    idx_oj = text.find(".method public final Oj(J)V", idx_nj)
    if idx_oj == -1:
        raise SystemExit("em/v.smali: Oj(J)V method not found")

    new_nj = """.method public final Nj(J)Z
    .registers 5

    iget-object v0, p0, Lem/v;->I2:Ljava/lang/Object;

    monitor-enter v0

    :try_start_3
    iget-boolean v1, p0, Lem/v;->N2:Z

    if-nez v1, :cond_b

    monitor-exit v0

    const/4 p0, 0x0

    return p0

    :cond_b
    const/4 v1, 0x0

    iput-boolean v1, p0, Lem/v;->N2:Z

    monitor-exit v0
    :try_end_d
    .catchall {:try_start_3 .. :try_end_d} :catchall_12

    invoke-virtual {p0, p1, p2}, Lem/v;->Oj(J)V

    const/4 p0, 0x1

    return p0

    :catchall_12
    move-exception p1

    monitor-exit v0

    throw p1
.end method

"""
    text = text[:idx_nj] + new_nj + text[idx_oj:]

    marker_m = "invoke-virtual/range {v5 .. v15}, Lcom/oplus/camera/module/processor/captureprocessor/CaptureProcessor;->M(J[BIILjava/lang/String;ZZJ)Z"
    idx_m = text.find(marker_m)
    if idx_m != -1:
        fallback = """    const-wide/16 v1, 0x0

    cmp-long v1, v6, v1

    if-gtz v1, :cond_w2_ok

    iget-wide v6, v5, Lcom/oplus/camera/module/processor/captureprocessor/CaptureProcessor;->n:J

    :cond_w2_ok
    """
        text = text[:idx_m] + fallback + text[idx_m:]
    return text


def patch_smali_movie_mode(text):
    """Route MovieMode to use the standard, vendor-supported 0x800b operation mode instead of unmapped 0x80a3/0x80a4."""
    idx = text.find(".method public final K9()I")
    if idx == -1:
        raise SystemExit("om/g.smali: method K9()I not found")
    idx_end = text.find(".end method", idx)
    if idx_end == -1:
        raise SystemExit("om/g.smali: end of K9()I not found")
    new_method = """.method public final K9()I
    .registers 1

    const p0, 0x800b

    return p0
.end method"""
    return text[:idx] + new_method + text[idx_end + len(".end method"):]


def patch_smali_log_dismiss(text):
    marker = """    invoke-virtual {v0, v1}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    .line 72
    .line 73
    .line 74
    move-result-object v0

    .line 75
    check-cast v0, Landroid/widget/FrameLayout;

    .line 76
    .line 77
    iget-object v1, p0, Lcom/oplus/camera/feature/logvideo/view/LogPreviewView;->e:Landroid/widget/FrameLayout;

    .line 78
    .line 79
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->removeView(Landroid/view/View;)V"""

    replacement = """    invoke-virtual {v0, v1}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v0

    if-eqz v0, :cond_skip_remove

    check-cast v0, Landroid/widget/FrameLayout;

    iget-object v1, p0, Lcom/oplus/camera/feature/logvideo/view/LogPreviewView;->e:Landroid/widget/FrameLayout;

    if-eqz v1, :cond_skip_remove

    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->removeView(Landroid/view/View;)V

    :cond_skip_remove"""

    if marker not in text:
        raise SystemExit("jh/x.smali: dismiss marker not found")
    return text.replace(marker, replacement, 1)


def patch_smali_movie_presenter(text):
    """Prevent MoviePresenter from setting VIDEO_10BIT_ENABLE to 'on', which breaks SurfaceView preview buffer allocation."""
    method_sig = ".method public final L(Lcom/oplus/camera/sh;)V"
    m_idx = text.find(method_sig)
    if m_idx == -1:
        raise SystemExit("rh/d.smali: method L(Lcom/oplus/camera/sh;)V not found")
    m_end = text.find(".end method", m_idx)
    if m_end == -1:
        raise SystemExit("rh/d.smali: end of method L not found")
    method_text = text[m_idx:m_end]

    idx_10 = method_text.find("CameraParameter;->VIDEO_10BIT_ENABLE")
    if idx_10 == -1:
        raise SystemExit("rh/d.smali: VIDEO_10BIT_ENABLE not found in method L")
    lbl_idx = method_text.rfind(":cond_", 0, idx_10)
    colon_end = method_text.find("\n", lbl_idx)

    idx_bitrate = method_text.find("CameraParameter;->VIDEO_BITRATE", idx_10)
    if idx_bitrate == -1:
        raise SystemExit("rh/d.smali: VIDEO_BITRATE not found in method L")
    lbl_after = method_text.rfind(":cond_", 0, idx_bitrate)
    colon_end2 = method_text.find("\n", lbl_after)
    label_after = method_text[lbl_after:colon_end2].strip()

    new_method = method_text[:colon_end] + f"\n    goto {label_after}\n\n" + method_text[colon_end:]
    return text[:m_idx] + new_method + text[m_end:]


def patch_smali_xpan_view_manager(text):
    """Enable 30mm Ultra-Wide camera switch bar in XPan mode."""
    target = """    const-string v0, "com.oplus.xpan.wide.picturesize"

    .line 7
    .line 8
    invoke-static {}, Lab/r;->E()Z

    .line 9
    .line 10
    .line 11
    move-result v1

    .line 12
    invoke-static {v0, v1}, Lcom/oplus/camera/configure/CameraConfig;->getSizeConfigValue(Ljava/lang/String;Z)Landroid/util/Size;"""

    repl = """    const-string v0, "com.oplus.xpan.wide.picturesize"

    const/4 v1, 0x0

    invoke-static {v0, v1}, Lcom/oplus/camera/configure/CameraConfig;->getSizeConfigValue(Ljava/lang/String;Z)Landroid/util/Size;"""

    if target not in text:
        raise SystemExit("classes6.dex: expected XPanViewManager wide picture size check not found")
    text = text.replace(target, repl, 1)

    legacy_target = """    const-string v0, "com.oplus.xpan.legacy.ui.style"

    .line 19
    .line 20
    invoke-static {v0, v1, v1}, Lcom/oplus/camera/configure/CameraConfig;->d(Ljava/lang/String;ZZ)Z

    .line 21
    .line 22
    .line 23
    move-result v0

    .line 24
    iput-boolean v0, p0, Ldl/i;->m:Z"""

    legacy_repl = """    const/4 v0, 0x1

    iput-boolean v0, p0, Ldl/i;->m:Z"""

    if legacy_target not in text:
        raise SystemExit("classes6.dex: expected XPanViewManager legacy ui style check not found")
    return text.replace(legacy_target, legacy_repl, 1)


def patch_apk(source, target, baksmali, smali, zipalign):
    """Patch dex files inside source APK and write aligned target APK."""
    threads = str(min(4, os.cpu_count() or 1))
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = pathlib.Path(tmp_dir)

        dex_targets = ["classes.dex", "classes2.dex", "classes3.dex", "classes5.dex", "classes6.dex", "classes7.dex", "classes33.dex"]

        # Extract all needed dex files
        with zipfile.ZipFile(source) as z:
            for dex_name in dex_targets:
                z.extract(dex_name, tmp)

        # 1. Patch classes.dex
        subprocess.run(["java", "-jar", str(baksmali), "d", "-j", threads,
                        str(tmp / "classes.dex"), "-o", str(tmp / "smali_classes1")],
                       check=True)
        aps_path = tmp / "smali_classes1/com/oplus/camera/aps/service/ApsService$CameraPictureCallbackImpl.smali"
        if not aps_path.exists():
            raise SystemExit("classes.dex: ApsService$CameraPictureCallbackImpl.smali not found")
        aps_path.write_text(patch_smali_aps(aps_path.read_text()))

        log_path = tmp / "smali_classes1/com/oplus/base/ocrscanner/oseesdk/a.smali"
        if not log_path.exists():
            raise SystemExit("classes.dex: com/oplus/base/ocrscanner/oseesdk/a.smali not found")
        log_path.write_text(patch_smali_log_preview(log_path.read_text()))

        subprocess.run(["java", "-jar", str(smali), "a", "-j", threads,
                        str(tmp / "smali_classes1"), "-o", str(tmp / "classes.dex")],
                       check=True)

        # 2. Patch classes2.dex
        subprocess.run(["java", "-jar", str(baksmali), "d", "-j", threads,
                        str(tmp / "classes2.dex"), "-o", str(tmp / "smali_classes2")],
                       check=True)
        ce_path = tmp / "smali_classes2/com/oplus/camera/entry/CameraEntry.smali"
        if not ce_path.exists():
            raise SystemExit("classes2.dex: CameraEntry.smali not found")
        ce_path.write_text(patch_smali_camera_entry(ce_path.read_text()))

        abr_path = tmp / "smali_classes2/ab/r.smali"
        if not abr_path.exists():
            raise SystemExit("classes2.dex: ab/r.smali not found")
        abr_path.write_text(patch_smali_ab_r(abr_path.read_text()))

        subprocess.run(["java", "-jar", str(smali), "a", "-j", threads,
                        str(tmp / "smali_classes2"), "-o", str(tmp / "classes2.dex")],
                       check=True)

        # 3. Patch classes3.dex
        subprocess.run(["java", "-jar", str(baksmali), "d", "-j", threads,
                        str(tmp / "classes3.dex"), "-o", str(tmp / "smali_classes3")],
                       check=True)
        g_path = tmp / "smali_classes3/ne/g.smali"
        if not g_path.exists():
            raise SystemExit("classes3.dex: ne/g.smali not found")
        g_path.write_text(patch_smali_face_slender(g_path.read_text()))

        subprocess.run(["java", "-jar", str(smali), "a", "-j", threads,
                        str(tmp / "smali_classes3"), "-o", str(tmp / "classes3.dex")],
                       check=True)

        # 4. Patch classes5.dex
        subprocess.run(["java", "-jar", str(baksmali), "d", "-j", threads,
                        str(tmp / "classes5.dex"), "-o", str(tmp / "smali_classes5")],
                       check=True)
        rh_path = tmp / "smali_classes5/rh/d.smali"
        if not rh_path.exists():
            raise SystemExit("classes5.dex: rh/d.smali not found")
        rh_path.write_text(patch_smali_movie_presenter(rh_path.read_text()))

        subprocess.run(["java", "-jar", str(smali), "a", "-j", threads,
                        str(tmp / "smali_classes5"), "-o", str(tmp / "classes5.dex")],
                       check=True)

        # 5. Patch classes6.dex
        subprocess.run(["java", "-jar", str(baksmali), "d", "-j", threads,
                        str(tmp / "classes6.dex"), "-o", str(tmp / "smali_classes6")],
                       check=True)
        xpan_path = tmp / "smali_classes6/dl/i.smali"
        if not xpan_path.exists():
            raise SystemExit("classes6.dex: dl/i.smali not found")
        xpan_path.write_text(patch_smali_xpan_view_manager(xpan_path.read_text()))

        subprocess.run(["java", "-jar", str(smali), "a", "-j", threads,
                        str(tmp / "smali_classes6"), "-o", str(tmp / "classes6.dex")],
                       check=True)

        # 6. Patch classes7.dex
        subprocess.run(["java", "-jar", str(baksmali), "d", "-j", threads,
                        str(tmp / "classes7.dex"), "-o", str(tmp / "smali_classes7")],
                       check=True)
        v_path = tmp / "smali_classes7/em/v.smali"
        if not v_path.exists():
            raise SystemExit("classes7.dex: em/v.smali not found")
        v_path.write_text(patch_smali_v(v_path.read_text()))

        o0_path = tmp / "smali_classes7/em/o0.smali"
        if not o0_path.exists():
            raise SystemExit("classes7.dex: em/o0.smali not found")
        o0_path.write_text(patch_smali_o0(o0_path.read_text()))

        movie_path = tmp / "smali_classes7/om/g.smali"
        if not movie_path.exists():
            raise SystemExit("classes7.dex: om/g.smali not found")
        movie_path.write_text(patch_smali_movie_mode(movie_path.read_text()))

        subprocess.run(["java", "-jar", str(smali), "a", "-j", threads,
                        str(tmp / "smali_classes7"), "-o", str(tmp / "classes7.dex")],
                       check=True)

        # 6. Patch classes33.dex
        subprocess.run(["java", "-jar", str(baksmali), "d", "-j", threads,
                        str(tmp / "classes33.dex"), "-o", str(tmp / "smali_classes33")],
                       check=True)
        x_path = tmp / "smali_classes33/jh/x.smali"
        if not x_path.exists():
            raise SystemExit("classes33.dex: jh/x.smali not found")
        x_path.write_text(patch_smali_log_dismiss(x_path.read_text()))

        subprocess.run(["java", "-jar", str(smali), "a", "-j", threads,
                        str(tmp / "smali_classes33"), "-o", str(tmp / "classes33.dex")],
                       check=True)

        # Repackage into unaligned APK
        unaligned_apk = tmp / "unaligned.apk"
        patched_set = set(dex_targets)
        with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(unaligned_apk, "w") as zout:
            for item in zin.infolist():
                if item.filename in patched_set:
                    zout.writestr(item, (tmp / item.filename).read_bytes(), compress_type=zipfile.ZIP_STORED)
                else:
                    data = zin.read(item.filename)
                    zout.writestr(item, data, compress_type=item.compress_type)

        # Align uncompressed entries: 16KB alignment for .so (Android 15+ 16KB page agnostic)
        # falling back to 4KB if the host zipalign does not support -P 16.
        res = subprocess.run([str(zipalign), "-P", "16", "-f", "4", str(unaligned_apk), str(target)],
                             capture_output=True)
        if res.returncode != 0:
            subprocess.run([str(zipalign), "-p", "-f", "4", str(unaligned_apk), str(target)], check=True)


if __name__ == "__main__":
    patch_apk(*sys.argv[1:6])
