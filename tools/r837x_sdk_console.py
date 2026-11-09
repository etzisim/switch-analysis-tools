#!/usr/bin/env python3
"""
r837x_sdk_console.py - read switch registers from a stock Realtek RTL837x
switch over its serial console.

The unmanaged RTL837x switches that ship with the Realtek SDK firmware have a
character based debug console.  Its commands are (the tokens are plain
strings inside the firmware image):

    rd <reg>        read a switch register       -> "reg 0x65e0: data 0x..."
    rd1 <phy> <mmd> <reg>
    rd2 <sds> <page> <reg>
    rd3 <phy> <sds> <page> <reg>
    wd <reg> <val>  write a switch register
    rst              reset the chip
    u0 / u1          interrupt off / on
    f r 10 11 g1..g4 1..6   PHY test patterns
    sd pre main post tx eye dump   SerDes test

This script reads the chip id and all LED related registers and writes a
`reg_dump.txt` in the format that
`tools/led_gpio_utils/dec_leds_from_dump.py` expects, so the LED wiring of
the board can be turned into an RTLPlayground machine definition.

Usage:
    .venv/bin/python analyze/r837x_sdk_console.py --port /dev/ttyUSB0
    .venv/bin/python analyze/r837x_sdk_console.py --port /dev/ttyUSB0 --scan
"""
import argparse
import os
import re
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial is missing: pip install pyserial (e.g. in a venv)")

RE_RESULT = re.compile(r"reg\s*0x([0-9a-fA-F]+)\s*:\s*data\s*0x([0-9a-fA-F]+)", re.I)

# Chip id register and the LED registers of the RTL837x switch core
LED_REGS = [0x6520, 0x6524, 0x6528, 0x652C, 0x6530, 0x6534, 0x6538, 0x653C,
            0x6540, 0x6544, 0x6548, 0x654C, 0x65D8, 0x65DC, 0x65E0, 0x65E4,
            0x65E8, 0x65EC, 0x65F0, 0x65F4, 0x6040]
ALL_REGS = [0x0004] + LED_REGS


def open_port(path, baud, timeout=0.2):
    s = serial.Serial()
    s.port = path
    s.baudrate = baud
    s.timeout = timeout
    s.rtscts = False
    s.xonxoff = False
    s.dtr = False
    s.rts = False
    s.open()
    return s


def drain(s, seconds=0.5):
    end = time.time() + seconds
    buf = b""
    while time.time() < end:
        try:
            chunk = s.read(4096)
        except serial.SerialException:
            break
        if chunk:
            buf += chunk
            end = time.time() + seconds
        else:
            time.sleep(0.02)
    return buf


def read_reg(s, addr, verbose=False):
    """Send `rd <addr>` and return the 32 bit value, or None."""
    s.write(f"rd {addr:x}\r\n".encode())
    s.flush()
    data = drain(s, 1.2)
    if verbose:
        print(f"  rd {addr:x} -> {data!r}")
    m = RE_RESULT.search(data.decode("utf-8", "replace"))
    if m:
        return int(m.group(2), 16)
    # Some console builds ask for the register on a second line.
    s.write(b"rd\r\n")
    s.flush()
    drain(s, 0.4)
    s.write(f"{addr:x}\r\n".encode())
    s.flush()
    data += drain(s, 1.2)
    m = RE_RESULT.search(data.decode("utf-8", "replace"))
    if m:
        return int(m.group(2), 16)
    return None


def scan_bauds(path, bauds):
    for baud in bauds:
        try:
            s = open_port(path, baud)
        except Exception as e:
            print(f"  {baud:>7}: cannot open ({e})")
            continue
        try:
            time.sleep(0.3)
            drain(s, 0.3)
            s.write(b"\r\n")
            s.flush()
            data = drain(s, 1.2)
        finally:
            s.close()
        printable = sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13))
        if data and printable / len(data) > 0.6:
            print(f"  {baud:>7}: ANSWERS -> {data[:160]!r}")
            return baud
        print(f"  {baud:>7}: no answer ({len(data)} bytes)")
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=9600,
                    help="stock firmware baud rate; 9600 on the PCB-K0402W "
                         "family, 57600 on most other RTL837x boards")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--out", default="reg_dump.txt")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--boot-seconds", type=float, default=5.0,
                    help="listen this long for the boot banner")
    args = ap.parse_args()

    if not os.path.exists(args.port):
        sys.exit(f"{args.port} does not exist - plug in the USB adapter")

    if args.scan:
        print(f"probing {args.port}:")
        baud = scan_bauds(args.port, [9600, 57600, 115200, 38400, 230400])
        if baud is None:
            sys.exit("no answer on any baud rate")
        args.baud = baud

    s = open_port(args.port, args.baud)
    print(f"connected to {args.port} at {args.baud} baud")
    banner = drain(s, args.boot_seconds)
    if banner:
        print("--- console banner ---")
        print(banner.decode("utf-8", "replace"))
        print("-----------------------")

    values = {}
    for addr in ALL_REGS:
        v = read_reg(s, addr, args.verbose)
        if v is None:
            print(f"  0x{addr:04X}: no answer")
        else:
            values[addr] = v
            print(f"  0x{addr:04X} = 0x{v:08X}")
    s.close()

    if 0x0004 in values:
        chip = values[0x0004]
        names = {0x83720000: "RTL8372", 0x83727000: "RTL8372N",
                 0x83730000: "RTL8373", 0x83737000: "RTL8373N"}
        print(f"\nchip id register 0x0004 = 0x{chip:08X} -> "
              f"{names.get(chip, 'unknown')}")

    with open(args.out, "w") as f:
        for addr in sorted(values):
            v = values[addr]
            f.write(f"{addr:04x}: {v & 0xff:02X} {(v >> 8) & 0xff:02X} "
                    f"{(v >> 16) & 0xff:02X} {(v >> 24) & 0xff:02X}\n")
    print(f"\n[written to {args.out}]")
    print("next: python3 RTLPlayground/tools/led_gpio_utils/dec_leds_from_dump.py")


if __name__ == "__main__":
    main()
