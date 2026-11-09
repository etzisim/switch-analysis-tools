#!/usr/bin/env python3
"""
flash_identify.py - identify which platform a switch flash dump belongs to.

Usage:  python3 flash_identify.py <dump.bin> [--json]

The script looks at the *content* of the dump (not the file name) and prints
a platform verdict plus a partition map.  Two families are recognised:

  * "rtl837x"  - the classic Realtek 8051 (DW8051) stack used by the
                  RTL8372 / RTL8373 and therefore by RTLPlayground.
                  Signature: 2-byte bank prefetch size 0x4000 at offset 0,
                  8051 opcode patterns, Realtek 8x8-bit register names.

  * "mxl-wsp"  - the newer Realtek 32-bit ARC / Zephyr / "WSP" platform
                  (GSWIP switch core, XPCS SerDes, EIP160 MACsec).
                  Signature: 32-bit little-endian pointers with a 0x4000_0000
                  base, "zephyr/arch/arc/..." __FILE__ strings, 0x4000_0000+
                  code addresses.  These SoCs are NOT supported by
                  RTLPlayground (which is 8051 / RTL837x SFR based).
"""
import sys, struct, re, collections

def load(path):
    return open(path, "rb").read()

def find_all(data, pat):
    out, i = [], 0
    while True:
        i = data.find(pat, i)
        if i < 0:
            break
        out.append(i)
        i += 1
    return out

def score_rtl837x(data):
    """Evidence for the classic 8051 / RTL837x stack."""
    ev = []
    # 8051 boot vector: LJMP at offset 0, or the 2-byte bank prefetch size 0x4000
    if len(data) >= 2 and data[0:2] == b"\x00\x40":
        ev.append(("bank prefetch size 0x4000 at offset 0", 3))
    if data[0] == 0x02:
        ev.append(("8051 LJMP at offset 0", 3))
    # 8051 instruction mix in the first 64 kB
    code = data[:0x10000]
    for op, name in ((b"\x90", "MOV DPTR,#imm16"), (b"\x12", "LCALL"), (b"\x02", "LJMP")):
        n = code.count(op)
        if n > 50:
            ev.append((f"{n}x 8051 {name} in first 64 kB", 1))
    # 16-bit code pointers: a real 8051 image calls into the 0x0000-0x3fff
    # shared-code window, so LJMP/LCALL targets concentrate there.  Random data
    # would put only ~12% of them in that window.
    inside = total = 0
    for op in (b"\x12", b"\x02"):
        for i in find_all(code, op):
            if i + 2 < len(code):
                t = code[i+1] | (code[i+2] << 8)
                total += 1
                if 0x0100 <= t < 0x4000:
                    inside += 1
    if total > 300 and inside * 4 > total:
        ev.append((f"{inside}/{total} LJMP/LCALL targets inside the 16 kB shared-code window", 3))
    # Realtek-specific literals
    for lit, name in ((b"\x20\x7b", "SDS_MODES 0x7b20"), (b"\x00\x00\x73\x83", "chip id 0x83730000"),
                      (b"\x00\x00\x72\x83", "chip id 0x83720000")):
        if lit in data:
            ev.append((f"literal {name}", 3))
    return ev

def score_mxl(data):
    """Evidence for the newer ARC / Zephyr / WSP platform."""
    ev = []
    if find_all(data, b"zephyr/arch/arc"):
        ev.append(("'zephyr/arch/arc' __FILE__ string -> 32-bit ARC core", 6))
    for pat, name in ((b"WEST_TOPDIR/f48x_app", "Realtek f48x_app (MXL/WSP platform)"),
                      (b"drivers/mxl/", "Realtek MXL platform drivers"),
                      (b"gswip/switchcore", "GSWIP switch-core driver"),
                      (b"eip160s_macsec", "EIP160 MACsec (L3 managed feature set)"),
                      (b"DWC_xpcs", "Synopsys DWC XPCS 10G SerDes"),
                      (b"usxgmii", "USXGMII SerDes (10G/2.5G)")):
        if find_all(data, pat):
            ev.append((name, 3))
    # 32-bit little endian pointers into a 0x4000_0000 based address space
    hits = 0
    for off in range(0, min(len(data), 0x100000) - 3, 4):
        w = struct.unpack_from("<I", data, off)[0]
        if 0x40000000 <= w < 0x40200000:
            hits += 1
    if hits > 500:
        ev.append((f"{hits} 32-bit pointers with 0x4000_0000 base (no 8051)", 5))
    return ev

def partition_map(data, block=0x1000):
    """Classify the flash into regions by content density."""
    out = []
    cur = None
    for off in range(0, len(data), block):
        blk = data[off:off+block]
        if all(b == 0xFF for b in blk):
            k = "erased (0xff)"
        elif all(b == 0x00 for b in blk):
            k = "zeroed (0x00)"
        else:
            h = collections.Counter(blk)
            top, cnt = h.most_common(1)[0]
            k = "code/data" if cnt < len(blk) * 0.9 else f"mostly 0x{top:02x}"
        if cur and cur[2] == k:
            cur[1] = off + block
        else:
            if cur:
                out.append(cur)
            cur = [off, off + block, k]
    if cur:
        out.append(cur)
    return out

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0]
    data = load(path)
    print(f"file      : {path}")
    print(f"size      : {len(data)} bytes (0x{len(data):X}) = {len(data)//1024} KiB")
    if len(data) >= 3 and data[:3] == b"\xff\xff\xff":
        print("          : looks like a raw dump (no obvious container header)")

    rtl = score_rtl837x(data)
    mxl = score_mxl(data)
    rtl_score = sum(s for _, s in rtl)
    mxl_score = sum(s for _, s in mxl)

    print("\n-- platform evidence --")
    for n, s in rtl:
        print(f"  [rtl837x  +{s}] {n}")
    for n, s in mxl:
        print(f"  [mxl-wsp  +{s}] {n}")

    verdict = "rtl837x" if rtl_score > mxl_score else "mxl-wsp"
    print(f"\nVERDICT: {verdict}  (rtl837x={rtl_score}, mxl-wsp={mxl_score})")
    if verdict == "rtl837x":
        print("  -> this SoC is a DW8051 RTL8372/RTL8373: RTLPlayground can target it.")
    else:
        print("  -> this SoC is a 32-bit ARC Realtek (MXL/WSP) part.")
        print("     RTLPlayground is 8051/RTL837x-SFR based and CANNOT target this SoC.")

    print("\n-- partition map (4 KiB granularity) --")
    for s, e, k in partition_map(data):
        if e - s >= 0x1000:
            print(f"  0x{s:07X} - 0x{e-1:07X}  {e-s:9d} B  {k}")

    print("\n-- notable strings --")
    pats = [b"zephyr/arch/arc", b"f48x_app", b"gswip", b"mxl", b"WSP firmware version",
            b"Mcuboot version", b"Start WSP", b"eip160", b"DWC_xpcs", b"usxgmii",
            b"shell_uart", b"Save MAC Tag In Flash Header", b"Copy firmware to backup slots"]
    for p in pats:
        hits = find_all(data, p)
        if hits:
            print(f"  {p.decode():<40} x{len(hits):<4} first at 0x{hits[0]:07X}")

if __name__ == "__main__":
    main()
