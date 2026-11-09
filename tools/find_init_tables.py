#!/usr/bin/env python3
"""
find_init_tables.py - locate the Realtek SDK init tables inside an RTL837x
firmware image.

The SDK keeps its switch register initialisation as tables of
{uint16_t addr, uint16_t value} (or {addr, uint32_t value}) in code memory.
This script scans the image for runs of 16 bit values that are valid RTL837x
switch register addresses and prints the surrounding table so that the
initial LED configuration of the board can be read off the dump.
"""
import sys
import struct

# RTL837x switch register address ranges
RANGES = [
    (0x3C00, 0x3C10, "GPIO out 0-31 / out 32-63"),
    (0x4400, 0x4510, "GPIO in / direction"),
    (0x6000, 0x6800, "switch core (MAC/LLDP/...)"),
    (0x6800, 0x6A00, "port/queue config"),
    (0x7000, 0x8000, "QoS / rate limit"),
]
LED_LO, LED_HI = 0x6520, 0x65F4


def classify(v):
    for lo, hi, name in RANGES:
        if lo <= v <= hi:
            return name
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "backup4c2s_1.bin"
    data = open(path, "rb").read()
    n = len(data)

    print(f"file: {path} ({n} bytes)\n")

    # --- 1) 16 bit values that are exactly LED register addresses -------
    print("-- raw 16 bit LED register addresses (0x6520-0x65F4) --")
    hits = []
    for i in range(0, n - 1):
        v = data[i] | (data[i + 1] << 8)
        if LED_LO <= v <= LED_HI:
            # only interesting outside of ASCII text
            if not (0x20 <= data[i] <= 0x7E and 0x20 <= data[i + 1] <= 0x7E):
                hits.append((i, v))
    for off, v in hits:
        w = [data[off - 8 + 2 * k] | (data[off - 8 + 2 * k + 1] << 8) for k in range(8)]
        print(f"  0x{off:06X}  reg 0x{v:04X}   words: "
              + " ".join(f"{x:04X}" for x in w))

    # --- 2) look for {addr, value} tables -------------------------------
    print("\n-- candidate {addr,value} tables --")
    # scan on even and odd alignment
    for align in (0, 1):
        i = align
        while i < n - 3:
            addr = data[i] | (data[i + 1] << 8)
            kind = classify(addr)
            if kind is None or not (LED_LO <= addr <= LED_HI):
                i += 1
                continue
            # collect a run of (addr,value) pairs
            table = []
            j = i
            while j < n - 3:
                a = data[j] | (data[j + 1] << 8)
                if not (0x6000 <= a <= 0x6FFF):
                    break
                v = data[j + 2] | (data[j + 3] << 8)
                table.append((a, v))
                j += 4
            if len(table) >= 3:
                print(f"  @0x{i:06X} (align {align}) {len(table)} entries:")
                for a, v in table[:20]:
                    print(f"      0x{a:04X} = 0x{v:04X}")
            i = max(j, i + 1)

    # --- 3) the '90 xx 6y' pattern: mov dptr,#0x6xxx -------------------
    print("\n-- context of the most frequent 'mov dptr,#0x6xxx' targets --")
    counts = {}
    for m in __import__("re").finditer(b"\x90(.)(.)", data):
        a = m.group(1)[0] | (m.group(2)[0] << 8)
        if 0x6000 <= a <= 0x6FFF:
            counts.setdefault(a, []).append(m.start())
    for a in sorted(counts, key=lambda x: -len(counts[x]))[:6]:
        lst = counts[a]
        print(f"  0x{a:04X}: {len(lst)}x, e.g. @0x{lst[0]:06X}")
        off = lst[0]
        print("      " + data[off:off + 24].hex(" "))


if __name__ == "__main__":
    main()
