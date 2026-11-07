#!/usr/bin/env python3
"""Make the camera unit SDK tell the HAL which app opened the session,
and fix RAW capture and HEIC processing.

1. Camera2Impl.createNewSession() builds the session parameters from its preview
   request. A call is added just before that request is built, setting the
   vendor tag com.oplus.packageName to this app's package. patch_hal.py makes
   the HAL accept the tag as a session key.

2. ConsumerImpl onHalPictureImageArrived / onPictureMetaArrived / processRawImage:
   Remove !isSupportMasterMode() guard so that RAW captures in Master mode
   create and save valid DNG files in-app using DngCreator rather than getting
   lost in APS. In processRawImage, invoke mProducerInterface.onFinishAddFrame()
   so ProducerImpl unlocks the shutter and clears mbTakingPicture.

3. ApsProcessor initAPS:
   Set mbHeicProcessInApp = true for standard picture sizes (enabling 10-bit
   HEIC in-app encoding) and mbHeicProcessInApp = false for high picture sizes
   (48 MP / 50 MP) so high-resolution captures are encoded in APS rather than
   failing in-app.

    python scripts/patch_sdk.py in.jar out.jar baksmali.jar smali.jar
"""
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import zipfile

CLASS = "Lcom/oplus/ocs/camera/producer/device/Camera2Impl;"
PROXY = "Lcom/oplus/ocs/camera/metadata/parameter/CaptureRequestBuilderProxy;"
HELPER = f"""
.method private static setClientPackage({PROXY})V
    .registers 4

    new-instance v0, Landroid/hardware/camera2/CaptureRequest$Key;

    const-string v1, "com.oplus.packageName"

    const-class v2, [B

    invoke-direct {{v0, v1, v2}}, Landroid/hardware/camera2/CaptureRequest$Key;-><init>(Ljava/lang/String;Ljava/lang/Class;)V

    const-string v1, "com.oplus.camera\\u0000"

    invoke-virtual {{v1}}, Ljava/lang/String;->getBytes()[B

    move-result-object v1

    invoke-virtual {{p0, v0, v1}}, {PROXY}->setParameter(Landroid/hardware/camera2/CaptureRequest$Key;Ljava/lang/Object;)Z

    return-void
.end method
"""


def patch_smali(text):
    build = re.compile(
        r"    invoke-virtual \{(\w+)\}, " + re.escape(PROXY) + r"->build\(\)Landroid/hardware/camera2/CaptureRequest;\n\n"
        r"    move-result-object \w+\n\n"
        r"    invoke-virtual \{\w+, \w+\}, Landroid/hardware/camera2/params/SessionConfiguration;->"
        r"setSessionParameters\(Landroid/hardware/camera2/CaptureRequest;\)V\n")
    sites = build.findall(text)
    if len(sites) != 1 or "setClientPackage(" in text:
        raise SystemExit(f"Camera2Impl: expected one session parameter site, found {len(sites)}")
    call = f"    invoke-static {{{sites[0]}}}, {CLASS}->setClientPackage({PROXY})V\n\n"
    return build.sub(lambda match: call + match.group(0), text).rstrip("\n") + "\n" + HELPER


def patch_consumer(text):
    target1 = """    invoke-static {}, Lcom/oplus/ocs/camera/producer/info/CameraConfigHelper;->isSupportVibeRawSensorDngInAps()Z

    move-result v1

    if-nez v1, :cond_52

    .line 1072
    invoke-static {}, Lcom/oplus/ocs/camera/producer/info/CameraConfigHelper;->isSupportMasterMode()Z

    move-result v1

    if-nez v1, :cond_52"""

    repl1 = """    invoke-static {}, Lcom/oplus/ocs/camera/producer/info/CameraConfigHelper;->isSupportVibeRawSensorDngInAps()Z

    move-result v1

    if-nez v1, :cond_52"""

    target2 = """    invoke-static {}, Lcom/oplus/ocs/camera/producer/info/CameraConfigHelper;->isSupportVibeRawSensorDngInAps()Z

    move-result v0

    if-nez v0, :cond_54

    .line 1220
    invoke-static {}, Lcom/oplus/ocs/camera/producer/info/CameraConfigHelper;->isSupportMasterMode()Z

    move-result v0

    if-nez v0, :cond_54"""

    repl2 = """    invoke-static {}, Lcom/oplus/ocs/camera/producer/info/CameraConfigHelper;->isSupportVibeRawSensorDngInAps()Z

    move-result v0

    if-nez v0, :cond_54"""

    if target1 not in text or target2 not in text:
        raise SystemExit("ConsumerImpl: expected isSupportMasterMode sites for RAW capture not found")
    text = text.replace(target1, repl1).replace(target2, repl2)

    raw_finish_target = """    :cond_1d
    iput-object v0, p0, Lcom/oplus/ocs/camera/consumer/ConsumerImpl;->mRawCaptureResult:Landroid/hardware/camera2/CaptureResult;

    :cond_1f
    return-void"""

    raw_finish_repl = """    :cond_1d
    iput-object v0, p0, Lcom/oplus/ocs/camera/consumer/ConsumerImpl;->mRawCaptureResult:Landroid/hardware/camera2/CaptureResult;

    iget-object p1, p0, Lcom/oplus/ocs/camera/consumer/ConsumerImpl;->mProducerInterface:Lcom/oplus/ocs/camera/ProducerConsumerInterfaceContract$ProducerInterface;

    if-eqz p1, :cond_1f

    invoke-interface {p1}, Lcom/oplus/ocs/camera/ProducerConsumerInterfaceContract$ProducerInterface;->onFinishAddFrame()V

    :cond_1f
    return-void"""

    if raw_finish_target not in text:
        raise SystemExit("ConsumerImpl: expected processRawImage finish site not found")
    return text.replace(raw_finish_target, raw_finish_repl)


def patch_aps_processor(text):
    marker = "iput-boolean v2, v3, Lcom/oplus/ocs/camera/consumer/apsAdapter/adapter/ApsInitParameter;->mbHeicProcessInApp:Z"
    idx_end = text.find(marker)
    if idx_end == -1:
        raise SystemExit("ApsProcessor: expected mbHeicProcessInApp site not found")
    idx_start = text.rfind("if-nez v2, :cond_a0", 0, idx_end)
    if idx_start == -1:
        raise SystemExit("ApsProcessor: expected if-nez v2, :cond_a0 branch site not found")

    new_branch = """if-nez v2, :cond_a0

    const/4 v2, 0x1

    goto :goto_a1

    :cond_a0
    const/4 v2, 0x0

    :goto_a1
    """
    return text[:idx_start] + new_branch + text[idx_end:]


def patch_characteristics_wrapper(text):
    target = """.method public get(Landroid/hardware/camera2/CameraCharacteristics$Key;)Ljava/lang/Object;
    .registers 7
    .param p1    # Landroid/hardware/camera2/CameraCharacteristics$Key;
        .annotation build Landroidx/annotation/NonNull;
        .end annotation
    .end param
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "<T:",
            "Ljava/lang/Object;",
            ">(",
            "Landroid/hardware/camera2/CameraCharacteristics$Key<",
            "TT;>;)TT;"
        }
    .end annotation

    .line 493
    iget-object v0, p0, Lcom/oplus/ocs/camera/producer/info/CameraCharacteristicsWrapper;->mCachedValues:Ljava/util/Map;"""

    repl = """.method public get(Landroid/hardware/camera2/CameraCharacteristics$Key;)Ljava/lang/Object;
    .registers 7
    .param p1    # Landroid/hardware/camera2/CameraCharacteristics$Key;
        .annotation build Landroidx/annotation/NonNull;
        .end annotation
    .end param
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "<T:",
            "Ljava/lang/Object;",
            ">(",
            "Landroid/hardware/camera2/CameraCharacteristics$Key<",
            "TT;>;)TT;"
        }
    .end annotation

    invoke-virtual {p1}, Landroid/hardware/camera2/CameraCharacteristics$Key;->getName()Ljava/lang/String;

    move-result-object v0

    const-string v1, "android.lens.facing"

    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v1

    if-eqz v1, :cond_wrap_orient

    iget-object v0, p0, Lcom/oplus/ocs/camera/producer/info/CameraCharacteristicsWrapper;->mCameraId:Ljava/lang/String;

    const-string v1, "1"

    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v0

    if-eqz v0, :cond_wrap_facing_back

    const/4 v0, 0x0

    invoke-static {v0}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v0

    return-object v0

    :cond_wrap_facing_back
    const/4 v0, 0x1

    invoke-static {v0}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v0

    return-object v0

    :cond_wrap_orient
    const-string v1, "android.sensor.orientation"

    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v0

    if-eqz v0, :cond_wrap_orig

    iget-object v0, p0, Lcom/oplus/ocs/camera/producer/info/CameraCharacteristicsWrapper;->mCameraId:Ljava/lang/String;

    const-string v1, "1"

    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v0

    if-eqz v0, :cond_wrap_orient_back

    const/16 v0, 0x10e

    invoke-static {v0}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v0

    return-object v0

    :cond_wrap_orient_back
    const/16 v0, 0x5a

    invoke-static {v0}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v0

    return-object v0

    :cond_wrap_orig
    iget-object v0, p0, Lcom/oplus/ocs/camera/producer/info/CameraCharacteristicsWrapper;->mCachedValues:Ljava/util/Map;"""
    if target not in text:
        raise SystemExit("CameraCharacteristicsWrapper: expected get() site not found")
    return text.replace(target, repl)


def patch_device_info(text):
    target = """.method public get(Landroid/hardware/camera2/CameraCharacteristics$Key;)Ljava/lang/Object;
    .registers 2
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "<T:",
            "Ljava/lang/Object;",
            ">(",
            "Landroid/hardware/camera2/CameraCharacteristics$Key<",
            "TT;>;)TT;"
        }
    .end annotation

    .line 334
    iget-object p0, p0, Lcom/oplus/ocs/camera/producer/info/CameraDeviceInfoImpl;->mCameraCharacteristicsWrapper:Lcom/oplus/ocs/camera/producer/info/CameraCharacteristicsWrapper;

    invoke-virtual {p0, p1}, Lcom/oplus/ocs/camera/producer/info/CameraCharacteristicsWrapper;->get(Landroid/hardware/camera2/CameraCharacteristics$Key;)Ljava/lang/Object;

    move-result-object p0

    return-object p0
.end method"""

    repl = """.method public get(Landroid/hardware/camera2/CameraCharacteristics$Key;)Ljava/lang/Object;
    .registers 4
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "<T:",
            "Ljava/lang/Object;",
            ">(",
            "Landroid/hardware/camera2/CameraCharacteristics$Key<",
            "TT;>;)TT;"
        }
    .end annotation

    invoke-virtual {p1}, Landroid/hardware/camera2/CameraCharacteristics$Key;->getName()Ljava/lang/String;

    move-result-object v0

    const-string v1, "android.lens.facing"

    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v1

    if-eqz v1, :cond_dev_orient

    iget-object v0, p0, Lcom/oplus/ocs/camera/producer/info/CameraDeviceInfoImpl;->mCameraType:Ljava/lang/String;

    if-eqz v0, :cond_dev_facing_back

    const-string v1, "front"

    invoke-virtual {v0, v1}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v0

    if-eqz v0, :cond_dev_facing_back

    const/4 v0, 0x0

    invoke-static {v0}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v0

    return-object v0

    :cond_dev_facing_back
    const/4 v0, 0x1

    invoke-static {v0}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v0

    return-object v0

    :cond_dev_orient
    const-string v1, "android.sensor.orientation"

    invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v0

    if-eqz v0, :cond_dev_orig

    iget-object v0, p0, Lcom/oplus/ocs/camera/producer/info/CameraDeviceInfoImpl;->mCameraType:Ljava/lang/String;

    if-eqz v0, :cond_dev_orient_back

    const-string v1, "front"

    invoke-virtual {v0, v1}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v0

    if-eqz v0, :cond_dev_orient_back

    const/16 v0, 0x10e

    invoke-static {v0}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v0

    return-object v0

    :cond_dev_orient_back
    const/16 v0, 0x5a

    invoke-static {v0}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    move-result-object v0

    return-object v0

    :cond_dev_orig
    iget-object v0, p0, Lcom/oplus/ocs/camera/producer/info/CameraDeviceInfoImpl;->mCameraCharacteristicsWrapper:Lcom/oplus/ocs/camera/producer/info/CameraCharacteristicsWrapper;

    invoke-virtual {v0, p1}, Lcom/oplus/ocs/camera/producer/info/CameraCharacteristicsWrapper;->get(Landroid/hardware/camera2/CameraCharacteristics$Key;)Ljava/lang/Object;

    move-result-object v0

    return-object v0
.end method"""
    if target not in text:
        raise SystemExit("CameraDeviceInfoImpl: expected get() site not found")
    return text.replace(target, repl)


def patch_movie_mode(text):
    """Ensure MovieMode uses safe 8-bit NV12 preview stream by disabling 10-bit preview override."""
    target_on_conf = """    invoke-super {p0, p1, p2, p3, p4}, Lcom/oplus/ocs/camera/producer/mode/VideoMode;->onConfigure(Lcom/oplus/ocs/camera/producer/device/CameraSessionEntity;Lcom/oplus/ocs/camera/common/parameter/SdkCameraDeviceConfig;Ljava/lang/String;Lcom/oplus/ocs/camera/common/util/ApsRequestTag;)V"""
    repl_on_conf = target_on_conf + """

    if-eqz p4, :cond_movie_tag_skip

    const/4 v0, 0x0

    iput-boolean v0, p4, Lcom/oplus/ocs/camera/common/util/ApsRequestTag;->mbVideo10BitsEnable:Z

    :cond_movie_tag_skip"""

    if target_on_conf in text:
        text = text.replace(target_on_conf, repl_on_conf, 1)

    is_10bit_method = """
.method protected isVideo10BitOpen(Ljava/lang/String;)Z
    .registers 3

    const/4 v0, 0x0

    return v0
.end method
"""
    if ".method protected isVideo10BitOpen" not in text:
        text = text.rstrip("\n") + "\n" + is_10bit_method

    return text


def patch_video_mode(text):
    """Disable KEY_HAL_OUTPUT_BUFFER_COMBINED (force 0) to prevent ICP buffer crash in Slow Motion mode."""
    target = """    sget-object v4, Lcom/oplus/ocs/camera/metadata/UConfigureKeys;->KEY_HAL_OUTPUT_BUFFER_COMBINED:Lcom/oplus/ocs/camera/metadata/ConfigureKey;

    invoke-virtual {v1, v4, v10}, Lcom/oplus/ocs/camera/metadata/parameter/PreviewParameter$Builder;->set(Lcom/oplus/ocs/camera/metadata/RequestKey;Ljava/lang/Object;)Lcom/oplus/ocs/camera/metadata/parameter/Parameter$BaseBuilder;"""

    repl = """    sget-object v4, Lcom/oplus/ocs/camera/metadata/UConfigureKeys;->KEY_HAL_OUTPUT_BUFFER_COMBINED:Lcom/oplus/ocs/camera/metadata/ConfigureKey;

    invoke-virtual {v1, v4, v13}, Lcom/oplus/ocs/camera/metadata/parameter/PreviewParameter$Builder;->set(Lcom/oplus/ocs/camera/metadata/RequestKey;Ljava/lang/Object;)Lcom/oplus/ocs/camera/metadata/parameter/Parameter$BaseBuilder;"""

    if target not in text:
        raise SystemExit("VideoMode: expected KEY_HAL_OUTPUT_BUFFER_COMBINED site not found")
    return text.replace(target, repl, 1)


FIX_DNG_METHOD = """
.method public static fixDngMetadata([B)[B
    .registers 9
    .param p0, "data"    # [B

    if-nez p0, :cond_empty
    return-object p0

    :cond_empty
    array-length v0, p0
    const/16 v1, 0x10
    if-ge v0, v1, :cond_check_header
    return-object p0

    :cond_check_header
    const/4 v1, 0x0
    aget-byte v0, p0, v1
    const/16 v1, 0x49
    if-ne v0, v1, :cond_ret

    const/4 v0, 0x1
    aget-byte v0, p0, v0
    if-ne v0, v1, :cond_ret

    const/4 v0, 0x4
    aget-byte v0, p0, v0
    and-int/lit16 v0, v0, 0xff

    const/4 v1, 0x5
    aget-byte v1, p0, v1
    and-int/lit16 v1, v1, 0xff
    shl-int/lit8 v1, v1, 0x8
    or-int/2addr v0, v1

    const/4 v1, 0x6
    aget-byte v1, p0, v1
    and-int/lit16 v1, v1, 0xff
    shl-int/lit8 v1, v1, 0x10
    or-int/2addr v0, v1

    const/4 v1, 0x7
    aget-byte v1, p0, v1
    and-int/lit16 v1, v1, 0xff
    shl-int/lit8 v1, v1, 0x18
    or-int/2addr v0, v1

    array-length v1, p0
    add-int/lit8 v2, v0, 0x2
    if-le v2, v1, :cond_read_count
    return-object p0

    :cond_read_count
    aget-byte v1, p0, v0
    and-int/lit16 v1, v1, 0xff
    add-int/lit8 v2, v0, 0x1
    aget-byte v2, p0, v2
    and-int/lit16 v2, v2, 0xff
    shl-int/lit8 v2, v2, 0x8
    or-int/2addr v1, v2

    add-int/lit8 v0, v0, 0x2
    const/4 v2, 0x0

    :loop_start
    if-ge v2, v1, :cond_ret

    mul-int/lit8 v3, v2, 0xc
    add-int/2addr v3, v0

    array-length v4, p0
    add-int/lit8 v5, v3, 0xc
    if-le v5, v4, :cond_check_tag
    return-object p0

    :cond_check_tag
    aget-byte v4, p0, v3
    and-int/lit16 v4, v4, 0xff
    add-int/lit8 v5, v3, 0x1
    aget-byte v5, p0, v5
    and-int/lit16 v5, v5, 0xff
    shl-int/lit8 v5, v5, 0x8
    or-int/2addr v4, v5

    const v5, 0xc61a
    if-ne v4, v5, :cond_next_entry

    add-int/lit8 v4, v3, 0x8
    aget-byte v4, p0, v4
    and-int/lit16 v4, v4, 0xff

    add-int/lit8 v5, v3, 0x9
    aget-byte v5, p0, v5
    and-int/lit16 v5, v5, 0xff
    shl-int/lit8 v5, v5, 0x8
    or-int/2addr v4, v5

    add-int/lit8 v5, v3, 0xa
    aget-byte v5, p0, v5
    and-int/lit16 v5, v5, 0xff
    shl-int/lit8 v5, v5, 0x10
    or-int/2addr v4, v5

    add-int/lit8 v3, v3, 0xb
    aget-byte v3, p0, v3
    and-int/lit16 v3, v3, 0xff
    shl-int/lit8 v3, v3, 0x18
    or-int/2addr v4, v3

    array-length v3, p0
    add-int/lit8 v5, v4, 0x20
    if-le v5, v3, :cond_write_bl
    return-object p0

    :cond_write_bl
    const/4 v3, 0x0
    :bl_loop
    const/4 v5, 0x4
    if-ge v3, v5, :cond_ret

    mul-int/lit8 v5, v3, 0x8
    add-int/2addr v5, v4

    const/16 v6, 0x40
    aput-byte v6, p0, v5

    const/4 v6, 0x0
    add-int/lit8 v7, v5, 0x1
    aput-byte v6, p0, v7
    add-int/lit8 v7, v5, 0x2
    aput-byte v6, p0, v7
    add-int/lit8 v7, v5, 0x3
    aput-byte v6, p0, v7

    const/4 v6, 0x1
    add-int/lit8 v7, v5, 0x4
    aput-byte v6, p0, v7

    const/4 v6, 0x0
    add-int/lit8 v7, v5, 0x5
    aput-byte v6, p0, v7
    add-int/lit8 v7, v5, 0x6
    aput-byte v6, p0, v7
    add-int/lit8 v7, v5, 0x7
    aput-byte v6, p0, v7

    add-int/lit8 v3, v3, 0x1
    goto :bl_loop

    :cond_next_entry
    add-int/lit8 v2, v2, 0x1
    goto :loop_start

    :cond_ret
    return-object p0
.end method
"""


def patch_util(text):
    """Ensure DNG metadata BlackLevel is set to sensor optical black pedestal (64) to prevent overexposure/lifted shadows."""
    target = """    invoke-virtual {v2}, Ljava/io/ByteArrayOutputStream;->toByteArray()[B

    move-result-object v6"""

    repl = """    invoke-virtual {v2}, Ljava/io/ByteArrayOutputStream;->toByteArray()[B

    move-result-object v6

    invoke-static {v6}, Lcom/oplus/ocs/camera/common/util/Util;->fixDngMetadata([B)[B

    move-result-object v6"""

    if target not in text:
        raise SystemExit("Util: expected toByteArray site in buildRawImage not found")
    return text.replace(target, repl, 1).rstrip("\n") + "\n" + FIX_DNG_METHOD


def patch_jar(source, target, baksmali, smali):
    threads = str(min(4, os.cpu_count() or 1))
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(source) as archive:
        tmp = pathlib.Path(tmp)
        if archive.namelist() != ["classes.dex"]:
            raise SystemExit("unit SDK jar: expected a single classes.dex")
        archive.extract("classes.dex", tmp)
        subprocess.run(["java", "-jar", str(baksmali), "d", "-j", threads, str(tmp / "classes.dex"), "-o", str(tmp / "smali")],
                       check=True)
        path = tmp / "smali/com/oplus/ocs/camera/producer/device/Camera2Impl.smali"
        path.write_text(patch_smali(path.read_text()))

        c_path = tmp / "smali/com/oplus/ocs/camera/consumer/ConsumerImpl.smali"
        c_path.write_text(patch_consumer(c_path.read_text()))

        a_path = tmp / "smali/com/oplus/ocs/camera/consumer/ApsProcessor.smali"
        a_path.write_text(patch_aps_processor(a_path.read_text()))

        w_path = tmp / "smali/com/oplus/ocs/camera/producer/info/CameraCharacteristicsWrapper.smali"
        w_path.write_text(patch_characteristics_wrapper(w_path.read_text()))

        d_path = tmp / "smali/com/oplus/ocs/camera/producer/info/CameraDeviceInfoImpl.smali"
        d_path.write_text(patch_device_info(d_path.read_text()))

        m_path = tmp / "smali/com/oplus/ocs/camera/producer/mode/MovieMode.smali"
        if m_path.exists():
            m_path.write_text(patch_movie_mode(m_path.read_text()))

        v_path = tmp / "smali/com/oplus/ocs/camera/producer/mode/VideoMode.smali"
        if v_path.exists():
            v_path.write_text(patch_video_mode(v_path.read_text()))

        u_path = tmp / "smali/com/oplus/ocs/camera/common/util/Util.smali"
        if u_path.exists():
            u_path.write_text(patch_util(u_path.read_text()))

        subprocess.run(["java", "-jar", str(smali), "a", "-j", threads, str(tmp / "smali"), "-o", str(tmp / "out.dex")],
                       check=True)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_STORED) as out:
            out.writestr(zipfile.ZipInfo("classes.dex", (1980, 1, 1, 0, 0, 0)), (tmp / "out.dex").read_bytes())


if __name__ == "__main__":
    patch_jar(*sys.argv[1:5])
