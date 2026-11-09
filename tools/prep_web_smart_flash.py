#!/usr/bin/env python3
"""
prep_web_smart_flash.py - prepare a MaxLinear Web-Smart firmware image for
flashing onto a device whose flash already contains a working image.

Why this is needed
------------------
The MxL862xx firmware keeps the factory MAC address in the flash header
("Save MAC Tag In Flash Header").  Flashing a complete image over the header
makes the switch come up with "MAC address : Null".  The header also holds
the board specific GPHY/SerDes init table, which a generic vendor image may
not match.

The script therefore merges the current dump's header into the vendor image
and reports exactly what it changed, so the result can be checked before it
is written.

Usage
-----
  # keep the complete 4 KiB header (MAC + board PHY init table)
  python3 prep_web_smart_flash.py --current backup1.bin --vendor vendor.bin \
          --out merged.bin

  # keep only the 6 MAC bytes (surgical, leaves the vendor's PHY table)
  python3 prep_web_smart_flash.py --current backup1.bin --vendor vendor.bin \
          --mac-off 0x1234 --out merged.bin

  # dry run: only report
  python3 prep_web_smart_flash.py --current backup1.bin --vendor vendor.bin \
          --out merged.bin --dry-run
"""
import argparse
import os
import sys


def describe(data, off, n=16):
    return data[off:off + n].hex(" ")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--current", required=True, help="dump of the flash as it is now")
    ap.add_argument("--vendor", required=True, help="the vendor firmware image")
    ap.add_argument("--out", required=True, help="output file to flash")
    ap.add_argument("--header-size", type=lambda x: int(x, 0), default=0x1000,
                    help="bytes taken from the current dump (default 0x1000)")
    ap.add_argument("--mac-off", type=lambda x: int(x, 0),
                    help="offset of the 6 MAC bytes, copied individually")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cur = open(args.current, "rb").read()
    ven = open(args.vendor, "rb").read()

    print(f"aktueller Dump : {args.current}  ({len(cur)} B)")
    print(f"Vendor-Image  : {args.vendor}  ({len(ven)} B)")

    if len(ven) != len(cur):
        print(f"\nACHTUNG: unterschiedliche Groessen "
              f"({len(cur)} vs {len(ven)}). Der Flash ist {len(cur)//1024} KiB; "
              f"das Vendor-Image muss die gleiche Groesse haben.")

    out = bytearray(ven)

    if args.mac_off is not None:
        o = args.mac_off
        print(f"\nMAC-Bytes an 0x{o:06X} aus dem aktuellen Dump uebernehmen:")
        print(f"  aktuell : {describe(cur, o, 6)}")
        print(f"  Vendor  : {describe(ven, o, 6)}")
        if cur[o:o + 6] == ven[o:o + 6]:
            print("  -> identisch, nichts zu tun")
        else:
            print("  -> werden ersetzt")
            out[o:o + 6] = cur[o:o + 6]
    else:
        hs = args.header_size
        print(f"\nHeader (0x000000-0x{hs:06X}) aus dem aktuellen Dump uebernehmen:")
        same = sum(1 for a, b in zip(cur[:hs], ven[:hs]) if a == b)
        print(f"  {same} von {hs} Bytes bereits identisch, {hs - same} werden ersetzt")
        out[:hs] = cur[:hs]
        print(f"  aktuell : {describe(cur, 0, 16)}")
        print(f"  Vendor  : {describe(ven, 0, 16)}")

    if args.dry_run:
        print("\nDry-Run - nichts geschrieben.")
        return

    with open(args.out, "wb") as f:
        f.write(out)
    print(f"\ngeschrieben: {args.out} ({len(out)} B)")

    diff = sum(1 for a, b in zip(cur, out) if a != b)
    print(f"veraendert gegenueber dem Vendor-Image: {diff} Bytes")
    print(f"veraendert gegenueber dem aktuellen Dump: "
          f"{sum(1 for a, b in zip(cur, out) if a != b)} Bytes")


if __name__ == "__main__":
    main()
