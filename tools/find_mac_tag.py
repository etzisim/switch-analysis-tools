#!/usr/bin/env python3
"""
find_mac_tag.py - locate the factory MAC address inside a MaxLinear
MXL862xx flash dump.

The MxL862xx firmware stores the factory MAC in the flash header
("Save MAC Tag In Flash Header" / "add WSP MAC tag in flash header").  If the
header is overwritten by a full image flash, the switch comes up with
"MAC address : Null".

The MAC is printed on the serial console at boot
("MAC address  : %02X:%02X:%02X:%02X:%02X:%02X"), so:

    1) read the MAC from the console
    2) run this script to find where it lives in the header
    3) use that offset when preparing a vendor image

Usage:
    python3 find_mac_tag.py <dump.bin> AA:BB:CC:DD:EE:FF
    python3 find_mac_tag.py <dump.bin>            # only scan, report candidates
"""
import sys
import re


def mac_candidates(data):
    """Every position where a plausible MAC could sit."""
    out = []
    for i in range(len(data) - 5):
        b = data[i:i + 6]
        # locally administered or globally unique, unicast, not all-zero
        if b[0] & 1:
            continue
        if b[0] in (0x00, 0xFF) or b[5] in (0x00, 0xFF):
            continue
        if b == b"\x00" * 6 or b == b"\xff" * 6:
            continue
        out.append((i, b))
    return out


def find_exact(data, mac):
    """All positions of the exact MAC bytes."""
    hits = []
    i = 0
    while True:
        i = data.find(mac, i)
        if i < 0:
            break
        hits.append(i)
        i += 1
    return hits


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    data = open(path, "rb").read()
    print(f"file: {path} ({len(data)} bytes)")

    if len(sys.argv) >= 3:
        mac = sys.argv[2].replace("-", ":").replace(".", ":")
        raw = bytes(int(x, 16) for x in mac.split(":"))
        hits = find_exact(data, raw)
        print(f"\nMAC {mac} -> {len(hits)} Treffer")
        for h in hits:
            region = "HEADER (0x000-0xFFF)" if h < 0x1000 else \
                     "Bootloader" if h < 0xA000 else \
                     "WSP-Anwendung" if h < 0x137000 else \
                     "GPHY-FW" if h < 0x160000 else "Config/Bereich"
            ctx = data[max(0, h - 8):h + 14].hex(" ")
            print(f"  0x{h:06X}  [{region}]  ...{ctx}...")
        if not hits:
            print("  nicht gefunden - steht die MAC vielleicht im OTP statt im Flash?")
        return

    print("\nScan nach plausiblen MAC-Kandidaten im Header (0x000-0xFFF):")
    cands = [c for c in mac_candidates(data[:0x1000])]
    print(f"  {len(cands)} Kandidaten (zu viele für eine automatische Zuordnung)")
    print("  Bitte die MAC aus der Konsolenausgabe übergeben.")


if __name__ == "__main__":
    main()
