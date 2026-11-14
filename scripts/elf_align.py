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
GNU_RELRO = 0x6474E552


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


def relro_end(data):
    """Virtual end of PT_GNU_RELRO, or None for non-ELF64/32-bit."""
    header = _elf64_program_headers(data)
    if header is None:
        return None
    endian, phoff, phentsize, phnum = header
    for index in range(phnum):
        offset = phoff + index * phentsize
        if struct.unpack_from(endian + "I", data, offset)[0] == GNU_RELRO:
            vaddr = struct.unpack_from(endian + "Q", data, offset + 0x10)[0]
            memsz = struct.unpack_from(endian + "Q", data, offset + 0x28)[0]
            return vaddr + memsz
    return None


def check_relro(data):
    """RELRO end modulo 16 KB; 0 is compliant, None means no RELRO."""
    end = relro_end(data)
    return None if end is None else end % ALIGN_16K


def check_tree_relro(root):
    """Return [(path, remainder)] for ELF64 libraries with a misaligned RELRO end."""
    bad = []
    for path in pathlib.Path(root).rglob("*.so"):
        value = check_relro(path.read_bytes())
        if value:
            bad.append((str(path), value))
    return bad


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
    if len(sys.argv) != 3 or sys.argv[1] not in ("check", "align", "relro", "native"):
        raise SystemExit("Usage: elf_align.py {check|align|relro|native} <directory-or-file>")
    target = pathlib.Path(sys.argv[2])
    if sys.argv[1] == "native":
        data = target.read_bytes()
        value = alignment(data)
        relro = check_relro(data)
        ok = (value is None or value >= ALIGN_16K) and (relro is None or relro == 0)
        print(f"{target}: p_align={hex(value) if value else 'n/a'} relro_end_mod={relro}")
        raise SystemExit(0 if ok else 1)
    if sys.argv[1] == "relro":
        if target.is_file():
            value = check_relro(target.read_bytes())
            print(f"{target}: relro_end_mod={value}")
            raise SystemExit(0 if not value else 1)
        bad = check_tree_relro(target)
        print(f"{len(bad)} ELF64 libraries have a non-16 KB RELRO end")
        for path, value in bad[:20]:
            print(f"  {path}: +0x{value:x}")
        raise SystemExit(0)
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
