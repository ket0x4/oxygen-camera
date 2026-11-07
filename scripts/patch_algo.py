#!/usr/bin/env python3
"""Patch OnePlus camera algorithm libraries for Android 17 / SM8350.

1. libAlgoInterface.so:
   superNightProcessV6 fallback black level defaults to 256 (0x100) when
   com.oplus.aps.params.supernight.blacklevel is missing from the sensor
   configuration, causing pinkish/magenta cast on IMX689/IMX766/IMX789
   (whose pedestal is 64). Patch both fallback sites to 64 (0x40).

2. libAlgoProcess.so:
   camApsBufferLockPlanes computes P010 scanline by subtracting plane[1].data - plane[0].data.
   On modern Android gralloc mapper 4.0, P010 returns planeCount=1, leaving plane[1].data=0,
   resulting in a negative scanline (~ -64M) that crashes p010MSB2LSB with SIGSEGV.
   Patch camApsBufferLockPlanes to use the buffer height as scanline and compute plane 1 offset,
   and sanitize scanline in AlgoInterface::process before calling p010MSB2LSB.
"""
import sys


def patch_interface(data):
    """Patch libAlgoInterface.so to default supernight black level to 64 across V3, V6, and V7 algorithms."""
    data = bytearray(data)

    # 1. superNightProcessV6 fallbacks (0x4551bc and 0x455254)
    # 0x4551bc: adrp x21; mov w24, #0x100; add x21, ...
    p1 = bytes.fromhex("55e7ff9018208052b5d20491")
    r1 = bytes.fromhex("55e7ff9018088052b5d20491")
    if data.count(p1) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V6 fallback 1, found {data.count(p1)}")
    i1 = data.find(p1)
    data[i1:i1 + len(p1)] = r1

    # 0x455254: bl APSInterfaceLog::logPrint; mov w24, #0x100; b ...
    p2 = bytes.fromhex("ebd91594182080520b000014")
    r2 = bytes.fromhex("ebd91594180880520b000014")
    if data.count(p2) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V6 fallback 2, found {data.count(p2)}")
    i2 = data.find(p2)
    data[i2:i2 + len(p2)] = r2

    # superNightProcessV6 static black level per-channel additions (0x455624, 0x455760, 0x4557e4, 0x455868)
    # 0x45562c: BL 0 - add w10, w8, #0x100 -> #0x40
    p_v6_bl0 = bytes.fromhex("a80240b9090b40f90a010411ca6600b9")
    r_v6_bl0 = bytes.fromhex("a80240b9090b40f90a010111ca6600b9")
    if data.count(p_v6_bl0) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V6 BL 0, found {data.count(p_v6_bl0)}")
    i_v6_bl0 = data.find(p_v6_bl0)
    data[i_v6_bl0:i_v6_bl0 + len(p_v6_bl0)] = r_v6_bl0

    # 0x455768: BL 1 - add w10, w8, #0x100 -> #0x40
    p_v6_bl1 = bytes.fromhex("a80240b9090b40f90a010411ca6a00b9")
    r_v6_bl1 = bytes.fromhex("a80240b9090b40f90a010111ca6a00b9")
    if data.count(p_v6_bl1) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V6 BL 1, found {data.count(p_v6_bl1)}")
    i_v6_bl1 = data.find(p_v6_bl1)
    data[i_v6_bl1:i_v6_bl1 + len(p_v6_bl1)] = r_v6_bl1

    # 0x4557ec: BL 2 - add w10, w8, #0x100 -> #0x40
    p_v6_bl2 = bytes.fromhex("a80240b9090b40f90a010411ca6e00b9")
    r_v6_bl2 = bytes.fromhex("a80240b9090b40f90a010111ca6e00b9")
    if data.count(p_v6_bl2) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V6 BL 2, found {data.count(p_v6_bl2)}")
    i_v6_bl2 = data.find(p_v6_bl2)
    data[i_v6_bl2:i_v6_bl2 + len(p_v6_bl2)] = r_v6_bl2

    # 0x455870: BL 3 - add w8, w8, #0x100 -> #0x40
    p_v6_bl3 = bytes.fromhex("a80240b9090b40f908010411c87200b9")
    r_v6_bl3 = bytes.fromhex("a80240b9090b40f908010111c87200b9")
    if data.count(p_v6_bl3) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V6 BL 3, found {data.count(p_v6_bl3)}")
    i_v6_bl3 = data.find(p_v6_bl3)
    data[i_v6_bl3:i_v6_bl3 + len(p_v6_bl3)] = r_v6_bl3

    # 2. superNightGetInfoV7 static black level fallbacks (0x464e84 and 0x464fa0)
    # 0x464e84: ldr w8, [x21, #0x1c]; ldr x9, [x24, #0x10]; mov w22, #0x100; mov w25, #0x400
    p_v7_1 = bytes.fromhex("a81e40b9090b40f91620805219808052")
    r_v7_1 = bytes.fromhex("a81e40b9090b40f91608805219808052")
    if data.count(p_v7_1) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V7 fallback 1, found {data.count(p_v7_1)}")
    i_v7_1 = data.find(p_v7_1)
    data[i_v7_1:i_v7_1 + len(p_v7_1)] = r_v7_1

    # 0x464fa0: sub w10, w8, #0xd09; mov w22, #0x100; cmp w10, #4; mov w25, #0x400
    p_v7_2 = bytes.fromhex("0a253451162080525f11007119808052")
    r_v7_2 = bytes.fromhex("0a253451160880525f11007119808052")
    if data.count(p_v7_2) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V7 fallback 2, found {data.count(p_v7_2)}")
    i_v7_2 = data.find(p_v7_2)
    data[i_v7_2:i_v7_2 + len(p_v7_2)] = r_v7_2

    # 3. superNightProcessV3 static black level fallbacks (0x44a350, 0x44a388, 0x44a6b8, 0x44a748, 0x44a7d8)
    # 0x44a350: adrp x23; adrp x20; mov w19, #0x100; add x23, x23, #0x3e8
    p_v3_1 = bytes.fromhex("b73300d034ebfff013208052f7a20f91")
    r_v3_1 = bytes.fromhex("b73300d034ebfff013088052f7a20f91")
    if data.count(p_v3_1) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V3 fallback 1, found {data.count(p_v3_1)}")
    i_v3_1 = data.find(p_v3_1)
    data[i_v3_1:i_v3_1 + len(p_v3_1)] = r_v3_1

    # 0x44a388: BL 0 - adrp x11; add x11; add w10, w8, #0x100; str w10, [x11, #0x64]
    p_v3_2 = bytes.fromhex("ab3300d06ba10f910a0104116a6500b9")
    r_v3_2 = bytes.fromhex("ab3300d06ba10f910a0101116a6500b9")
    if data.count(p_v3_2) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V3 fallback 2, found {data.count(p_v3_2)}")
    i_v3_2 = data.find(p_v3_2)
    data[i_v3_2:i_v3_2 + len(p_v3_2)] = r_v3_2

    # 0x44a6b8: BL 1 - ldr w8, [x25]; ldr x9, [x28, #0x10]; add w10, w8, #0x100; str w10, [x23, #0x68]
    p_v3_3 = bytes.fromhex("280340b9890b40f90a010411ea6a00b9")
    r_v3_3 = bytes.fromhex("280340b9890b40f90a010111ea6a00b9")
    if data.count(p_v3_3) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V3 fallback 3, found {data.count(p_v3_3)}")
    i_v3_3 = data.find(p_v3_3)
    data[i_v3_3:i_v3_3 + len(p_v3_3)] = r_v3_3

    # 0x44a748: BL 2 - ldr w8, [x25]; ldr x9, [x28, #0x10]; add w10, w8, #0x100; str w10, [x23, #0x6c]
    p_v3_4 = bytes.fromhex("280340b9890b40f90a010411ea6e00b9")
    r_v3_4 = bytes.fromhex("280340b9890b40f90a010111ea6e00b9")
    if data.count(p_v3_4) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V3 fallback 4, found {data.count(p_v3_4)}")
    i_v3_4 = data.find(p_v3_4)
    data[i_v3_4:i_v3_4 + len(p_v3_4)] = r_v3_4

    # 0x44a7d8: BL 3 - ldr w8, [x25]; ldr x9, [x28, #0x10]; add w8, w8, #0x100; str w8, [x23, #0x70]
    p_v3_5 = bytes.fromhex("280340b9890b40f908010411e87200b9")
    r_v3_5 = bytes.fromhex("280340b9890b40f908010111e87200b9")
    if data.count(p_v3_5) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V3 fallback 5, found {data.count(p_v3_5)}")
    i_v3_5 = data.find(p_v3_5)
    data[i_v3_5:i_v3_5 + len(p_v3_5)] = r_v3_5

    # 4. Enforce ArcSoft SuperNight 3.0 (V3) pipeline instead of Mariana NPU (V7)
    # File offset 0x00a01158: sSuperNightVersion static variable in .data (VA 0xa02158)
    # Default is -1 (0xffffffffffffffff). Set to 3 (0x0000000000000003).
    sn_ver_data_offset = 0x00a01158
    if data[sn_ver_data_offset:sn_ver_data_offset + 8] == bytes.fromhex("ffffffffffffffff"):
        data[sn_ver_data_offset:sn_ver_data_offset + 8] = (3).to_bytes(8, "little")

    # 0x22eddc in superNightRegister:
    # ldr x8, [x24, #344]; cmn x8, #1; b.eq 22edfc
    # -> mov x8, #3; str x8, [x24, #344]; b 22f3e4 (direct to superNightRegisterV3)
    p_sn_ver = bytes.fromhex("08af40f91f0500b1c0000054")
    r_sn_ver = bytes.fromhex("680080d208af00f980010014")
    if data.count(p_sn_ver) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight version routing, found {data.count(p_sn_ver)}")
    i_sn_ver = data.find(p_sn_ver)
    data[i_sn_ver:i_sn_ver + len(p_sn_ver)] = r_sn_ver

    # 5. ArcSoft SuperNight AWB Gain Decoupling (eliminate residual purple tint)
    # ArcSoft SuperNight RAW applies WbGain internally (ApplyAWBGainAndScale) and converts back to
    # Bayer, outputting a merged RAW buffer to downstream Qualcomm ISP (offlineR2Y/BPS).
    # Downstream ISP then applies ANDROID_COLOR_CORRECTION_GAINS a second time, multiplying
    # Red and Blue by ~1.7x and ~1.9x over Green.
    # Set ArcSoft input WbGain parameters to unit gain 1.0f (0x3f800000) so ArcSoft preserves
    # linear RAW sensor ratios and the downstream ISP performs white balancing once.
    # 0x44acb4 in superNightProcessV3:
    # adrp x19, ac0000; add x19, x19, #0x3e8; mov w9, #0x3f800000;
    # str w9, [x19, #116]; str w9, [x19, #120]; str w9, [x19, #124]; str w9, [x19, #128]; b 44adac
    p_v3_wbgain = bytes.fromhex("a93300d029e943b9292534513f290071e8050054ccebfff08cc123918a000010")
    r_v3_wbgain = bytes.fromhex("b33300d073a20f9109f0a752697600b9697a00b9697e00b9698200b937000014")
    if data.count(p_v3_wbgain) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V3 WBGain, found {data.count(p_v3_wbgain)}")
    i_v3_wbgain = data.find(p_v3_wbgain)
    data[i_v3_wbgain:i_v3_wbgain + len(p_v3_wbgain)] = r_v3_wbgain

    # 0x455d1c in superNightProcessV6:
    # mov w9, #0x3f800000; str w9, [x22, #116]; str w9, [x22, #120]; str w9, [x22, #124]; str w9, [x22, #128]; b 455df0; nop; nop
    p_v6_wbgain = bytes.fromhex("c93300d0296940b9292534513f290071080500548cebff908cb124918a000010")
    r_v6_wbgain = bytes.fromhex("09f0a752c97600b9c97a00b9c97e00b9c98200b9300000141f2003d51f2003d5")
    if data.count(p_v6_wbgain) != 1:
        raise SystemExit(f"libAlgoInterface.so: expected 1 site for supernight V6 WBGain, found {data.count(p_v6_wbgain)}")
    i_v6_wbgain = data.find(p_v6_wbgain)
    data[i_v6_wbgain:i_v6_wbgain + len(p_v6_wbgain)] = r_v6_wbgain

    return bytes(data)


def patch_process(data):
    """Patch libAlgoProcess.so to fix P010 scanline calculation and p010MSB2LSB."""
    data = bytearray(data)
    # 0x157674: camApsBufferLockPlanes YUV420 plane1 calculation fix
    # ldr x11, [sp, #216]; ldr w10, [sp, #212]; sub x11, x11, x9; sdiv x11, x11, x10; stp w10, w11, [x20, #36]
    # -> ldr w10, [sp, #212]; ldur w11, [x29, #-208]; nop; nop; stp w10, w11, [x20, #36]
    p1 = bytes.fromhex("eb6f40f9ead740b96b0109cb6b0dca9a8aae0429")
    r1 = bytes.fromhex("ead740b9ab0353b81f2003d51f2003d58aae0429")
    if data.count(p1) == 1:
        i1 = data.find(p1)
        data[i1:i1 + len(p1)] = r1

    # 0x1577d8: camApsBufferLockPlanes P010 plane1 calculation fix (format 0x36 / 0x7fa30c0a)
    # ldr x10, [sp, #216]; ldr w8, [sp, #212]; sub x10, x10, x9; sdiv x10, x10, x8; stp w8, w10, [x20, #36]
    # -> ldr w8, [sp, #212]; ldur w10, [x29, #-208]; nop; nop; stp w8, w10, [x20, #36]
    p1_p010 = bytes.fromhex("ea6f40f9e8d740b94a0109cb4a0dc89a88aa0429")
    r1_p010 = bytes.fromhex("e8d740b9aa0353b81f2003d51f2003d588aa0429")
    if data.count(p1_p010) == 1:
        i1_p010 = data.find(p1_p010)
        data[i1_p010:i1_p010 + len(p1_p010)] = r1_p010

    # 0x1577f8: P010 UV plane rowStride: ldr w10, [sp, #228] -> ldr w10, [sp, #212]
    p1_p010_uv = bytes.fromhex("eae740b929090091")
    r1_p010_uv = bytes.fromhex("ead740b929090091")
    if data.count(p1_p010_uv) == 1:
        i1_p010_uv = data.find(p1_p010_uv)
        data[i1_p010_uv:i1_p010_uv + len(p1_p010_uv)] = r1_p010_uv

    # 0x257b3c: AlgoInterface::process scanline sanitize for p010MSB2LSB
    # ldr w5, [sp, #1048]; mov x1, x0; bl p010MSB2LSB
    # -> mov w5, w3; mov x1, x0; bl p010MSB2LSB
    p2 = bytes.fromhex("e51b44b9e10300aa03200794")
    r2 = bytes.fromhex("e503032ae10300aa03200794")
    if data.count(p2) != 1:
        raise SystemExit(f"libAlgoProcess.so: expected 1 site for p010MSB2LSB scanline, found {data.count(p2)}")
    i2 = data.find(p2)
    data[i2:i2 + len(p2)] = r2
    return bytes(data)


def patch_imageformatutils(data):
    """Patch libcamximageformatutils.so ValidateBufferSize to return CamxResultSuccess (0)."""
    data = bytearray(data)
    # 0x16390: ValidateBufferSize entry point
    # Replace initial instruction with mov w0, #0 (0x00008052); ret (0xc0035fd6)
    target = bytes.fromhex("86f6ff1700000000c0f7ff1700000000")
    repl = bytes.fromhex("00008052c0035fd6c0f7ff1700000000")
    if target not in data:
        raise SystemExit("libcamximageformatutils.so: ValidateBufferSize target bytes not found")
    idx = data.find(target)
    data[idx:idx + len(repl)] = repl
    return bytes(data)


def patch_chi_override(data):
    """Patch com.qti.chi.override.so to disable HALOutputBufferCombined.

    1. In Pipeline::CreateDescriptor() at 0x2a62d0:
       Change 'str w7, [x2, #80]' (47 50 00 b9) to 'str wzr, [x2, #80]' (5f 50 00 b9).
    2. In ExtensionModule::SearchNumBatchedFrames:
       At 0x2490ac: Change 'str w0, [x21]' (a0 02 00 b9) to 'str wzr, [x21]' (bf 02 00 b9).
       At 0x2491d0: Change 'str w8, [x21]' (a8 02 00 b9) to 'str wzr, [x21]' (bf 02 00 b9).
    This forces HALOutputBufferCombined to 0 across both SearchNumBatchedFrames and Pipeline::CreateDescriptor,
    preventing CamX from allocating/patching a combined buffer offset (0x312000) that exceeds the single-frame
    buffer size (3219456) in HFR / Slow Motion mode.
    """
    data = bytearray(data)

    # 1. Pipeline::CreateDescriptor (0x2a62d0)
    p1 = bytes.fromhex("475000b978ffdf08")
    r1 = bytes.fromhex("5f5000b978ffdf08")
    if data.count(p1) != 1:
        raise SystemExit(f"com.qti.chi.override.so: expected 1 site for Pipeline::CreateDescriptor HALOutputBufferCombined, found {data.count(p1)}")
    i1 = data.find(p1)
    data[i1:i1 + len(p1)] = r1

    # 2. ExtensionModule::SearchNumBatchedFrames site 1 (0x2490ac)
    p2 = bytes.fromhex("807d4a0ba00200b9e00317aa")
    r2 = bytes.fromhex("807d4a0bbf0200b9e00317aa")
    if data.count(p2) != 1:
        raise SystemExit(f"com.qti.chi.override.so: expected 1 site for SearchNumBatchedFrames site 1, found {data.count(p2)}")
    i2 = data.find(p2)
    data[i2:i2 + len(p2)] = r2

    # 3. ExtensionModule::SearchNumBatchedFrames site 2 (0x2491d0)
    p3 = bytes.fromhex("e9031f2aa80200b9050c00b0")
    r3 = bytes.fromhex("e9031f2abf0200b9050c00b0")
    if data.count(p3) != 1:
        raise SystemExit(f"com.qti.chi.override.so: expected 1 site for SearchNumBatchedFrames site 2, found {data.count(p3)}")
    i3 = data.find(p3)
    data[i3:i3 + len(p3)] = r3

    return bytes(data)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit("Usage: patch_algo.py <interface|process|imageformatutils|chi-override> <source.so> <target.so>")
    mode, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(src, "rb") as f:
        content = f.read()
    if mode == "interface":
        patched = patch_interface(content)
    elif mode == "process":
        patched = patch_process(content)
    elif mode == "imageformatutils":
        patched = patch_imageformatutils(content)
    elif mode == "chi-override":
        patched = patch_chi_override(content)
    else:
        raise SystemExit(f"Unknown mode: {mode}")
    with open(dst, "wb") as f:
        f.write(patched)
