#!/usr/bin/env python3
"""
led_init_from_837x_dump.py - recover the LED/port wiring of an RTL837x switch
from a raw flash dump.

The stock Realtek RTL837x firmware programs the LED registers of the switch
during its init.  In 8051 code that looks like

    90 e0 65     mov  dptr,#0x65e0      ; RTL837X_REG_LED_GLB_MUX_1
    74 xx        mov  a,#0xxx
    f0           movx @dptr,a           ; low byte
    ...                                  ; high byte / full 32 bit write

This script scans the dump for `mov dptr,#<reg>` sequences and reports the
value that is written afterwards.  The result is the LED configuration of the
board, which is what a RTLPlayground machine definition needs.
"""
import sys
import re
import struct

# Register addresses of interest (switch register space of the RTL837x)
LEDS = {
    0x6520: "LED_MODE",
    0x6524: "LED3_0_SET3",
    0x6528: "LED3_0_SET1",
    0x652C: "LED3_2_SET3",
    0x6530: "LED1_0_SET3",
    0x6534: "LED3_2_SET2",
    0x6538: "LED1_0_SET2",
    0x653C: "LED3_2_SET1",
    0x6540: "LED1_0_SET1",
    0x6544: "LED3_2_SET0",
    0x6548: "LED1_0_SET0",
    0x654C: "LED_PORT_SET_SEL",
    0x65D8: "LED_GLB_ACTIVE",
    0x65DC: "LED_GLB_IO_EN",
    0x65E0: "LED_GLB_MUX_1",
    0x65E4: "LED_GLB_MUX_2",
    0x65E8: "LED_GLB_MUX_3",
    0x65EC: "LED_GLB_MUX_4",
    0x65F0: "LED_GLB_MUX_5",
    0x65F4: "LED_GLB_MUX_6",
    0x6040: "HW_CONF",
}

# Registers whose value is a 32 bit word; others are 16 bit.
WIDTH32 = {0x65D8, 0x65DC}


def find_writes(data, addr, window=24):
    """Find `mov dptr,#addr` and try to read back the value that is stored."""
    pat = b"\x90" + struct.pack("<H", addr)
    out = []
    i = 0
    while True:
        i = data.find(pat, i)
        if i < 0:
            break
        ctx = data[i:i + window]
        out.append((i, ctx))
        i += 1
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "backup4c2s_1.bin"
    data = open(path, "rb").read()
    print(f"file: {path} ({len(data)} bytes)")

    print("\n-- LED register writes found in the image --")
    for addr, name in sorted(LEDS.items()):
        hits = find_writes(data, addr)
        if not hits:
            continue
        print(f"\n  {name} (0x{addr:04X}) - {len(hits)} occurrence(s)")
        for off, ctx in hits[:12]:
            print(f"    0x{off:06X}: {ctx.hex(' ')}")

    print("\n-- all `mov dptr,#imm16` targets in the 0x6xxx range --")
    hits = {}
    for m in re.finditer(b"\x90(.)(.)", data):
        a = m.group(1)[0] | (m.group(2)[0] << 8)
        if 0x6000 <= a <= 0x6FFF:
            hits.setdefault(a, []).append(m.start())
    for a in sorted(hits):
        print(f"  0x{a:04X}: {len(hits[a])}x  first at 0x{hits[a][0]:06X}")


if __name__ == "__main__":
    main()
