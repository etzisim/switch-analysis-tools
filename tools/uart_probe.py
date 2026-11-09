#!/usr/bin/env python3
"""
uart_probe.py - find a serial console on a board that only exposes test points.

The MxL86282 based switches have no UART header, just a couple of pads (e.g.
TP14/TP15).  This script listens on the adapter and prints everything that
arrives, while sending a newline every few seconds to trigger the bootloader's
menu ("hit Enter to go") and to wake up a shell prompt.

Procedure
---------
1. Find GND first: measure continuity from each pad to the ground plane.
   NEVER connect the adapter's VCC to the board - it has its own supply.
2. Adapter GND -> board GND, adapter RX -> TP14.  Power the board.
3. If nothing appears, move the adapter RX to TP15 and power-cycle again.
4. If there is still nothing, swap TX/RX or try another baud rate.

Usage
-----
    python3 uart_probe.py --port /dev/ttyUSB0 --seconds 30
    python3 uart_probe.py --port /dev/ttyUSB0 --scan
"""
import argparse
import os
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial is missing: pip install pyserial (e.g. in a venv)")

INTERESTING = (b"uart:", b"~$", b"#", b"WSP", b"Start", b"hit Enter", b"Full Img",
               b"Slot", b"GPHY", b"Mcuboot", b"version", b"flash", b"ERR", b"error")


def open_port(path, baud, timeout=0.15):
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


def listen(s, seconds, poke=True):
    end = time.time() + seconds
    next_poke = time.time() + 2.0
    buf = b""
    t0 = time.time()
    while time.time() < end:
        if poke and time.time() >= next_poke:
            try:
                s.write(b"\r\n")
                s.flush()
            except serial.SerialException:
                pass
            next_poke = time.time() + 2.0
        try:
            chunk = s.read(4096)
        except serial.SerialException:
            break
        if chunk:
            buf += chunk
            print(f"[{time.time()-t0:6.2f}s] {chunk.decode('utf-8', 'replace')}",
                  end="", flush=True)
    return buf


def scan(path, bauds, dwell=4.0):
    for baud in bauds:
        try:
            s = open_port(path, baud)
        except Exception as e:
            print(f"  {baud:>7}: kann nicht öffnen ({e})")
            continue
        print(f"  {baud:>7}: höre zu ...", flush=True)
        try:
            buf = listen(s, dwell)
        finally:
            s.close()
        hits = [w for w in INTERESTING if w.lower() in buf.lower()]
        if buf.strip():
            print(f"          -> {len(buf)} Bytes, Treffer: "
                  f"{[h.decode() for h in hits]}")
            print(f"          {buf[:400]!r}")
        else:
            print("          -> nichts empfangen")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--no-poke", action="store_true",
                    help="kein newline senden (nur zuhören)")
    args = ap.parse_args()

    if not os.path.exists(args.port):
        sys.exit(f"{args.port} existiert nicht - USB-Adapter nicht angesteckt?")

    if args.scan:
        print(f"probing {args.port} (Adapter-RX muss am gesuchten Pad hängen):")
        scan(args.port, [115200, 9600, 38400, 230400, 4800, 57600])
        return

    print(f"höre auf {args.port} @ {args.baud} zu "
          f"({args.seconds:.0f}s), sende alle 2s ein Newline.\n")
    s = open_port(args.port, args.baud)
    try:
        buf = listen(s, args.seconds, poke=not args.no_poke)
    finally:
        s.close()

    print(f"\n[gesamt {len(buf)} Bytes empfangen]")
    hits = [w.decode() for w in INTERESTING if w.lower() in buf.lower()]
    print(f"[Treffer: {hits if hits else 'keine'}]")


if __name__ == "__main__":
    main()
