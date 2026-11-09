#!/usr/bin/env python3
"""Summarise all RTLPlayground machine/pcb definitions."""
import glob, os, re

rows = []
for f in sorted(glob.glob("RTLPlayground/machine/pcb/*.c")):
    if f.endswith("_init.c"):
        continue
    src = open(f).read()
    def num(key, default=None):
        m = re.search(r"\." + key + r"\s*=\s*([^,\n]+)", src)
        if not m:
            return default
        v = m.group(1).strip()
        try:
            return int(v, 0)
        except ValueError:
            return v
    def arr(key):
        m = re.search(r"\." + key + r"\s*=\s*\{([^}]*)\}", src)
        if not m:
            return []
        return [x.strip() for x in m.group(1).split(",") if x.strip()]

    l2p = arr("log_to_phys_port")
    isfp = arr("is_sfp")
    n_sfp = num("n_sfp", 0)
    n_10g = num("n_10g", 0)
    # header
    base = os.path.basename(f)[:-2]
    hdr = f"RTLPlayground/machine/pcb/{base}.h"
    model = chipset = ""
    for cand in (f"RTLPlayground/machine/{base}.h", hdr):
        if os.path.exists(cand):
            t = open(cand).read()
            m = re.search(r'#define\s+MACHINE_MODEL\s+"([^"]*)"', t)
            if m:
                model = m.group(1)
            m = re.search(r"#define\s+MACHINE_CHIPSET\s+(\w+)", t)
            if m:
                chipset = m.group(1)
    rows.append((os.path.basename(f), n_sfp, n_10g, len(l2p), chipset, model, l2p, isfp))

print(f"{'file':<45} {'sfp':>3} {'10g':>3} {'nport':>5} {'chip':<8} model")
print("-" * 120)
for r in sorted(rows, key=lambda x: (-x[1], x[0])):
    print(f"{r[0]:<45} {r[1]:>3} {r[2]:>3} {r[3]:>5} {r[4]:<8} {r[5]}")
    if r[1] >= 2:
        print(f"{'':<45} l2p={r[6]}")
        print(f"{'':<45} sfp={r[7]}")
