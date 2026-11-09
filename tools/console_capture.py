#!/usr/bin/env python3
"""
console_capture.py - talk to a switch serial console and capture the output.

Used to identify a board from its running firmware: the boot log and a few
read-only shell commands reveal the SoC, the PHY and the port wiring.

Requires pyserial:
    python3 -m venv .venv && .venv/bin/pip install pyserial
    .venv/bin/python analyze/console_capture.py --help

Examples
--------
# 1) try the common baud rates and dump whatever the switch says
.venv/bin/python analyze/console_capture.py --port /dev/ttyUSB0 --scan

# 2) record a cold boot (press the reset button while it is running)
.venv/bin/python analyze/console_capture.py --port /dev/ttyUSB0 --baud 115200 \
    --seconds 60 --out boot.log

# 3) ask the switch a few read-only questions
.venv/bin/python analyze/console_capture.py --port /dev/ttyUSB0 --baud 115200 \
    --cmds "firmware_ver,chiptest,link,sfp_cli" --out info.log
"""
import argparse
import os
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial is missing: pip install pyserial (e.g. in a venv)")

# The firmware in the analysed dump uses a Zephyr shell with this prompt.
PROMPTS = (b"uart:~$", b"~$", b"#", b">", b":", b"CMD:")

# Read-only commands that exist in the analysed firmware.  The names were taken
# from the command table inside the flash dump (they appear as plain strings
# next to their help texts), so they can be sent as they are.
IDENT_CMDS = [
    "version",
    "uptime",
    "firmware_ver",
    "chiptest",
    "port",
    "link state",
    "sfp_cli",
    "xpcs_cli",
    "mdio",
    "kernel",
]


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


def drain(s, seconds=0.4):
    """Read everything that is available for `seconds`."""
    end = time.time() + seconds
    buf = b""
    while time.time() < end:
        try:
            chunk = s.read(4096)
        except serial.SerialException:
            break
        if chunk:
            buf += chunk
            end = time.time() + seconds      # keep reading while data flows
        else:
            time.sleep(0.02)
    return buf


def looks_alive(data):
    """Heuristic: does the console look like it answered us?"""
    if not data:
        return False
    printable = sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13))
    return printable / len(data) > 0.7


def scan_bauds(path, bauds, dwell=1.2):
    """Try every baud rate, send a newline, return the first that answers."""
    for baud in bauds:
        try:
            s = open_port(path, baud)
        except Exception as e:
            print(f"  {baud:>7}: cannot open ({e})")
            continue
        try:
            time.sleep(0.25)
            drain(s, 0.3)
            s.write(b"\r\n")
            s.flush()
            data = drain(s, dwell)
        finally:
            s.close()
        if looks_alive(data):
            print(f"  {baud:>7}: ANSWERS -> {data[:200]!r}")
            return baud, data
        print(f"  {baud:>7}: no answer ({len(data)} bytes)")
    return None, b""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/ttyUSB0", help="serial device")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--scan", action="store_true",
                    help="probe several baud rates for a response")
    ap.add_argument("--seconds", type=float, default=10.0,
                    help="how long to listen in total")
    ap.add_argument("--out", help="write the capture to this file")
    ap.add_argument("--cmds", default="",
                    help="comma separated shell commands to send after connecting")
    ap.add_argument("--preset", choices=("ident",),
                    help="'ident' sends the read-only identification commands "
                         "that the analysed firmware provides")
    ap.add_argument("--cmd-delay", type=float, default=0.3,
                    help="pause between commands")
    ap.add_argument("--raw", action="store_true", help="do not send any newline")
    args = ap.parse_args()

    if not os.path.exists(args.port):
        sys.exit(f"{args.port} does not exist - plug in the USB adapter")

    if args.scan:
        bauds = [115200, 57600, 38400, 9600, 230400, 4800]
        print(f"probing {args.port}:")
        baud, _ = scan_bauds(args.port, bauds)
        if baud is None:
            sys.exit("no answer on any baud rate - check wiring, TX/RX and GND")
        print(f"\nusing {baud} baud\n")
        args.baud = baud

    s = open_port(args.port, args.baud)
    log = []

    def record(data):
        if data:
            log.append(data)
            sys.stdout.write(data.decode("utf-8", "replace"))
            sys.stdout.flush()

    try:
        record(drain(s, 0.5))

        cmds = []
        if args.preset == "ident":
            cmds = IDENT_CMDS
        if args.cmds:
            cmds += [c.strip() for c in args.cmds.split(",") if c.strip()]

        for cmd in cmds:
            s.write(cmd.encode() + b"\r")
            s.flush()
            time.sleep(args.cmd_delay)
            record(drain(s, 1.0))

        deadline = time.time() + args.seconds
        while time.time() < deadline:
            record(drain(s, 0.3))
    except serial.SerialException as e:
        print(f"\nserial error: {e}", file=sys.stderr)
    finally:
        s.close()

    if args.out:
        with open(args.out, "wb") as f:
            f.write(b"".join(log))
        print(f"\n[written to {args.out}, {sum(len(x) for x in log)} bytes]")


if __name__ == "__main__":
    main()
