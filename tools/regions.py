#!/usr/bin/env python3
"""Fine-grained flash region map: find code banks, header, config areas."""
import sys, collections, re

path = sys.argv[1] if len(sys.argv) > 1 else "/home/simon/rtlplayground/backup1.bin"
data = open(path, "rb").read()
N = len(data)
print(f"size 0x{N:X}")

# ---------- classify every 256-byte block ----------
BLOCK = 0x100
kinds = []
for off in range(0, N, BLOCK):
    blk = data[off:off+BLOCK]
    h = collections.Counter(blk)
    top, cnt = h.most_common(1)[0]
    if cnt == len(blk):
        kinds.append("F" if top == 0xFF else ("Z" if top == 0x00 else "?"))
    elif cnt >= len(blk) * 0.95:
        kinds.append("f" if top == 0xFF else ("z" if top == 0x00 else "."))
    else:
        kinds.append("D")

runs = []
for i, k in enumerate(kinds):
    o = i * BLOCK
    if runs and runs[-1][2] == k:
        runs[-1][1] = o + BLOCK
    else:
        runs.append([o, o + BLOCK, k])

print("\n-- region runs (256B granularity) --")
for s, e, k in runs:
    print(f"  0x{s:07X} - 0x{e-1:07X}  {e-s:8d} B  {k}")

# ---------- find 8051 code: scan for LJMP at 16K-aligned offsets ----------
print("\n-- LJMP at aligned offsets (0x1000 stride) --")
for base in range(0, N, 0x1000):
    if data[base] == 0x02 and base + 2 < N:
        tgt = data[base+1] | (data[base+2] << 8)
        print(f"  0x{base:07X}: LJMP 0x{tgt:04X}  |  next bytes: {data[base:base+12].hex(' ')}")

# ---------- find MCUboot / flash header magic candidates ----------
print("\n-- first 4 bytes of every 4KB block that are not 00/ff --")
for base in range(0, N, 0x1000):
    h = data[base:base+4]
    if h[:2] != b"\x00\x00" and h[:2] != b"\xff\xff":
        pass  # too noisy, skip

# ---------- look for the MAC tag / flash header ----------
print("\n-- header candidate region 0x0..0x100 (hex) --")
for off in range(0, 0x100, 16):
    print(f"  0x{off:04X}: {data[off:off+16].hex(' ')}")
