#!/usr/bin/env python3
"""Extract ASCII + UTF-16LE strings from a flash dump with offsets."""
import sys, re

path = sys.argv[1] if len(sys.argv) > 1 else "/home/simon/rtlplayground/backup1.bin"
minlen = int(sys.argv[2]) if len(sys.argv) > 2 else 5
data = open(path, "rb").read()

print("=== ASCII strings ===")
for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minlen, data):
    print(f"0x{m.start():07X}  {m.group().decode()}")

print("\n=== UTF-16LE strings ===")
for m in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,}" % minlen, data):
    print(f"0x{m.start():07X}  {m.group().decode('utf-16-le')}")
