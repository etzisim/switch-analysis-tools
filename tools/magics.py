#!/usr/bin/env python3
"""Scan a flash dump for known magics and interesting structures."""
import sys, struct, re

path = sys.argv[1] if len(sys.argv) > 1 else "/home/simon/rtlplayground/backup1.bin"
data = open(path, "rb").read()
N = len(data)

MAGICS = {
    0x6907: "MCUboot image header magic",
    0x12345678: "RTLPlayground update header",
    0x332255ff: "RTLPlayground update reserved",
    0x2FF1D3EA: "??",
    0xA55AA55A: "??",
    0x5AA55AA5: "??",
    0xDEADBEEF: "??",
    0xAA55AA55: "??",
    0x55AA55AA: "??",
    0x0BADC0DE: "??",
    0x464C4153: "FLAS",
    0x504F5354: "POST",
    0x4E554C4C: "NULL",
}

print("-- magic scan (4-byte LE, all offsets) --")
for m, name in MAGICS.items():
    pat = struct.pack("<I", m)
    hits = [i for i in range(N - 3) if data[i:i+4] == pat]
    if hits:
        print(f"  0x{m:08X} {name}: " + ", ".join(f"0x{h:07X}" for h in hits[:20]) +
              (f" (+{len(hits)-20} more)" if len(hits) > 20 else ""))

# ---- MCUboot image header layout ----
# struct image_header { uint32_t ih_magic; uint16_t ih_hdr_size; uint16_t ih_ih_size;
#   uint32_t ih_img_size; uint32_t ih_flags; ... }
print("\n-- possible MCUboot headers (magic 0x6907) --")
for i in range(N - 32):
    if data[i:i+2] == b"\x07\x69":
        hdr_size, ih_size = struct.unpack("<HH", data[i+4:i+8])
        img_size = struct.unpack("<I", data[i+8:i+12])[0]
        if 8 <= hdr_size <= 256 and ih_size <= 1024 and 0 < img_size < N:
            print(f"  0x{i:07X}: hdr_size={hdr_size} ih_size={ih_size} img_size=0x{img_size:X} flags=0x{struct.unpack('<I', data[i+12:i+16])[0]:08X}")

# ---- CRC32 over candidate regions to find "valid image" blocks ----
import binascii
print("\n-- CRC32 of 4KB blocks that contain non-FF data (first 40) --")
n = 0
for off in range(0, N, 0x1000):
    blk = data[off:off+0x1000]
    if all(b == 0xFF for b in blk):
        continue
    c = binascii.crc32(blk) & 0xFFFFFFFF
    print(f"  0x{off:07X}: crc32=0x{c:08X}")
    n += 1
    if n > 400:
        break

# ---- look for a MAC-address-like tag in the first 64 bytes ----
print("\n-- candidate MAC in header 0x00..0x40 --")
for off in range(0, 0x40):
    mac = data[off:off+6]
    if mac == b"\xff\xff\xff\xff\xff\xff":
        continue
    print(f"  0x{off:02X}: {mac.hex(':')}")
