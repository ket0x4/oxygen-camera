#!/usr/bin/env python3
"""Force ELF64 PT_LOAD segments to at least 16 KB alignment.

Android 15+ devices with 16 KB pages, and the Google Play page-size check,
require every PT_LOAD segment to declare p_align >= 0x4000.  OnePlus and
third-party blobs built with 4 KB pages still declare 0x1000.  Raising the
field is enough for the check and does not move any bytes: the arm64 kernel
maps the segments with its own page size, and bionic only rejects p_align
values that are not powers of two.
"""
import pathlib
import struct
import sys

ALIGN_16K = 0x4000


def _elf64_program_headers(data):
    if len(data) < 64 or data[:4] != b"\x7fELF" or data[4] != 2:
        return None
    endian = "<" if data[5] == 1 else ">"
    try:
        phoff = struct.unpack_from(endian + "Q", data, 32)[0]
        phentsize, phnum = struct.unpack_from(endian + "HH", data, 54)
    except struct.error:
        return None
    if phentsize < 56 or phoff + phentsize * phnum > len(data):
        return None
    return endian, phoff, phentsize, phnum


def alignment(data):
    """Smallest PT_LOAD p_align of an ELF64, or None for non-ELF/32-bit."""
    header = _elf64_program_headers(data)
    if header is None:
        return None
    endian, phoff, phentsize, phnum = header
    values = []
    for index in range(phnum):
        offset = phoff + index * phentsize
        if struct.unpack_from(endian + "I", data, offset)[0] != 1:
            continue
        values.append(struct.unpack_from(endian + "Q", data, offset + 0x30)[0])
    return min(values) if values else None


def align(data):
    """Return data with every PT_LOAD p_align raised to at least 16 KB."""
    header = _elf64_program_headers(data)
    if header is None:
        return data
    endian, phoff, phentsize, phnum = header
    out = bytearray(data)
    changed = False
    for index in range(phnum):
        offset = phoff + index * phentsize
        if struct.unpack_from(endian + "I", out, offset)[0] != 1:
            continue
        align_offset = offset + 0x30
        current = struct.unpack_from(endian + "Q", out, align_offset)[0]
        if current < ALIGN_16K:
            struct.pack_into(endian + "Q", out, align_offset, ALIGN_16K)
            changed = True
    return bytes(out) if changed else data


def align_tree(root):
    """Align every ELF64 .so under root in place; returns (patched, total)."""
    patched = 0
    total = 0
    for path in pathlib.Path(root).rglob("*.so"):
        data = path.read_bytes()
        if alignment(data) is None:
            continue
        total += 1
        aligned = align(data)
        if aligned != data:
            path.write_bytes(aligned)
            patched += 1
    return patched, total


def check_tree(root):
    """Return [(path, p_align)] for ELF64 .so files below 16 KB."""
    bad = []
    for path in pathlib.Path(root).rglob("*.so"):
        data = path.read_bytes()
        value = alignment(data)
        if value is not None and value < ALIGN_16K:
            bad.append((str(path), value))
    return bad


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "align"):
        raise SystemExit("Usage: elf_align.py {check|align} <directory-or-file>")
    target = pathlib.Path(sys.argv[2])
    if target.is_file():
        value = alignment(target.read_bytes())
        if sys.argv[1] == "check":
            if value is not None and value < ALIGN_16K:
                raise SystemExit(f"{target}: p_align 0x{value:x}")
            print(f"{target}: ok (0x{value:x})" if value else f"{target}: not ELF64")
        else:
            target.write_bytes(align(target.read_bytes()))
    else:
        patched, total = align_tree(target)
        bad = check_tree(target)
        print(f"aligned {patched}/{total} ELF64 libraries; {len(bad)} still below 16 KB")
        for path, value in bad[:20]:
            print(f"  {path}: 0x{value:x}")
        raise SystemExit(0 if not bad else 1)
