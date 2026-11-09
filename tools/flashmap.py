#!/usr/bin/env python3
"""Structural analysis of an RTL837x SPI flash dump."""
import sys, collections

path = sys.argv[1] if len(sys.argv) > 1 else "/home/simon/rtlplayground/backup1.bin"
data = open(path, "rb").read()
print(f"file: {path}")
print(f"size: {len(data)} bytes (0x{len(data):X})")

# ---- byte histogram -------------------------------------------------
hist = collections.Counter(data)
print("\n-- top byte values --")
for b, c in hist.most_common(12):
    print(f"  0x{b:02x} {c:9d}  {100*c/len(data):5.2f}%")

# ---- run-length map of 4KB blocks ----------------------------------
BLOCK = 0x1000
print("\n-- 4KB block classification --")
kinds = []
for off in range(0, len(data), BLOCK):
    blk = data[off:off+BLOCK]
    h = collections.Counter(blk)
    top, cnt = h.most_common(1)[0]
    if cnt == len(blk):
        kinds.append((off, f"fill:{top:02x}"))
    elif cnt > len(blk) * 0.9:
        kinds.append((off, f"mostly:{top:02x}"))
    else:
        kinds.append((off, "data"))

# summarize contiguous runs of the same kind
runs = []
for off, k in kinds:
    if runs and runs[-1][2] == k:
        runs[-1][1] = off + BLOCK
    else:
        runs.append([off, off + BLOCK, k])
for s, e, k in runs:
    if k.startswith("fill:") and e - s > 0x4000:
        continue
    print(f"  0x{s:07X} - 0x{e-1:07X}  ({e-s:8d} B)  {k}")

# ---- find 8051 code banks (LJMP at 0x0000 of a 64K stride) --------
print("\n-- candidate 64K bank starts (bank header check) --")
for base in range(0, len(data), 0x10000):
    head = data[base:base+16]
    if len(head) < 4:
        continue
    if head[0] == 0x02:
        tgt = head[1] | (head[2] << 8)
        print(f"  0x{base:07X}: LJMP 0x{tgt:04X}   {head[:8].hex(' ')}")
