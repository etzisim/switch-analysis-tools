# Analyse von `backup4c2s_1.bin` — Davuaz Da-K6402W (4×2.5G + 2×SFP+)

## 1. Kurzfassung

**Das Board ist im RTLPlayground-Projekt bereits vollständig unterstützt.**

| | |
|---|---|
| Datei | `backup4c2s_1.bin`, 2 097 152 Byte (2 MiB) |
| Plattform | `rtl837x` (DW8051) — Score 9 : 0 |
| SoC | **RTL8372N** (Beleg: `init_8372N_QC, Error CHIP_MODE chip_mode =%d`) |
| PHY | **interne PHYs des RTL8372** – der Dump enthält zwar `RL6818C_...` und
`wd3: -8224 reg:`, das ist aber der generische SDK-Code für Boards **mit**
externem Quad-PHY. Laut `doc/hardware.md` steht der RTL8224 nur auf Devices
mit 8 Ports; `rtl837x_init.c` konfiguriert ihn nur in `rtl8373_init()`. |
| PCB-Silkscreen | `PCB-K0402W-V3.0` / `DIP-K0402WS-V3.0` |
| Sticker | **Davuaz Da-K6402W** |
| Flash | 2 MiB (`BY25Q16BS`, 16 Mbit) — Board hat **zwei** Flash-Chips + Front-Umschalter |
| Firmware | Realtek RTL837x **SDK-Referenzfirmware**, unmanaged, Debug-Konsole @ **9600 baud** |
| Web-UI | **keins** (kein HTTP-Stack im Dump) |

Die Silkscreen-Beschriftung entspricht 1:1 dem im Projekt dokumentierten Board
`doc/devices/PCB-K0402W-V3.0.md` (Top silkscreen: `PCB-K0402W-V3.0 / DIP-K0402WS-V3.0`).
Dasselbe Board wird als HiSource Hi-K0402WS, SICSOLINK SL-G0402F, YuanLey YS25-0402
und Ztyuav Z-QWYT0402 verkauft.

## 2. Flash-Layout (klassisches RTL837x-Schema)

```
0x000000  00 40          <- Bank-Prefetch 0x4000  (RTL837x-Signatur)
0x000002  ...            <- Shared Code (0x0000-0x3FFF)
0x004000  ...            <- Bank 1
0x010000  ...            <- Bank 2
0x01C000  ...            <- Bank 3
0x01D000  ...            <- hier legt der OEM-Installer sein Update-Image ab
0x028000  ...            <- Bank 4 (Ende der Firmware)
0x030000  0xFF ...       <- Rest des 2 MiB-Flash frei (keine Konfiguration, keine MAC)
```

Die Firmware belegt nur 192 KiB. Ab `0x30000` ist der Flash gelöscht — die
Bestandsfirmware speichert **weder Konfiguration noch MAC** im Flash (die MAC
steckt im Chip). Für RTLPlayground heißt das: `.mac_flash_offset = 0`.

Das Flash passt 1:1 zum Layout, das RTLPlayground erwartet (`CONFIG_START 0x70000`,
`FIRMWARE_UPLOAD_START 0x80000`, OEM-Update-Image bei `0x1D000`).

## 3. Was die Firmware über die Konsole kann

Die Debug-Konsole hat ein Menü, dessen Befehlsnamen als Klartext im Flash liegen:

```
wd  wd1  wd2  wd3      Register schreiben (Switch / PHY / SDS / 8224)
rd  rd1  rd2  rd3      Register lesen    -> "reg 0x65e0: data 0x........"
rst                    Chip reset
u0  u1                 Interrupt aus / an
f r 10 11 g1..g4 1..6  PHY-Testmuster
sd pre main post tx eye dump   SerDes-Test
```

`rd <reg>` reicht, um die **LED-Register 0x6520-0x65F4** und die **Chip-ID
in 0x0004** auszulesen (Werkzeug: `analyze/r837x_sdk_console.py`).

## 4. Verwendete Maschinen-Definition

Das Board ist bereits unter `machine/pcb/PCB_K0402W_V3_0.c` beschrieben. Für den
hier abweichenden Markennamen wurde – analog zum bereits vorhandenen
`DAVUAZ_DA_K6501W` – ein eigener Zielname angelegt:

```
machine/DAVUAZ_DA_K6402W.c      -> pcb/PCB_K0402W_V3_0__NORST.c
machine/DAVUAZ_DA_K6402W_init.c -> pcb/2M_PCB43_V2_1_init.c
machine/DAVUAZ_DA_K6402W.h      MACHINE_MODEL "Davuaz Da-K6402W", RTL8372
machine/pcb/PCB_K0402W_V3_0__NORST.c   Board-Definition ohne Reset-Taster
```

**Abweichung zur Upstream-Definition: `reset_pin = GPIO_NA`.**

Die Upstream-Datei `PCB_K0402W_V3_0.c` setzt `reset_pin = GPIO30_ACL_BIT3_EN`.
Das Gerät hier hat **keinen Reset-Taster**, sondern nur einen VLAN-Schalter
(`S<>V`) – der Reset-Taster ist laut Board-Doku eine Nachrüstung (Taster von
TP131 auf GND über 1 kΩ).

GPIO30 ist bei den älteren Revisionen desselben Boards (V1.0/V2.0/U13) der
ModAbs-Pin des linken SFP, wurde bei V3.0 aber für den (nicht bestückten)
Taster umgewidmet. Ohne Taster ist der Pin unbeschaltet; RTLPlayground legt
GPIO-Eingänge **ohne** Pull-up an (`gpio_input_setup()` löscht nur das
Richtungsbit). Liest der Pad low, interpretiert der Boot-Code das als
„Taster gedrückt“:

* Boot-Verzögerung bis zu **30 s**
* nach **10 s** `flash_default_config()` → **Konfiguration wird gelöscht**

Deshalb die Variante `__NORST` mit `reset_pin = GPIO_NA`.

Belegung (aus `PCB_K0402W_V3_0.c`):

* logisch 3 = rechter SFP (SDS0, GPIO37 ModAbs), 4-7 = Kupfer, 8 = linker SFP (SDS1, GPIO38)
* I²C: links SDA4/SCL3, rechts SDA3/SCL3
* `machine_custom_init` setzt `LED_GLB_IO_EN` Bit 6, damit die Port-LEDs leuchten

### Was der Dump hergibt – und was nicht

| Eigenschaft | Beleg im Dump | in der Definition |
|---|---|---|
| SoC | `init_8372N_QC` | `MACHINE_CHIPSET RTL8372` ✓ |
| PHY | aus dem Dump **nicht** ableitbar (generisches SDK-Image). Aus
  `doc/hardware.md` + `rtl837x_init.c`: interne PHYs des RTL8372, kein
  externes RTL8224. ✓ |
| Flash-Größe | 2 MiB, `BY25Q16BS` | ✓ |
| Flash-Layout | Prefetch `00 40`, 4 Bänke, Ende 0x2FFFF | RTLPlayground-Layout ✓ |
| MAC im Flash | 0x1FC000 leer | `mac_flash_offset = 0` ✓ |
| Web-UI | keines | → SOIC-Clip nötig ✓ |
| Konsole | SDK-Menü @ 9600 baud | J2-Pinout ✓ |

**Nicht** aus dem Dump ableitbar: `led_mux`, `led_sets`, SFP-GPIO, Reset-Pin.
Das sind **Laufzeit-Registerwerte**, die die OEM-Firmware erst beim Boot setzt.
Gezielte Suche im Dump:

* 16-Bit-Werte im LED-Registerbereich 0x6520-0x65F4 → nur ASCII-Fehltreffer
* `mov dptr,#0x65e0` (`90 e0 65`) → 0 Treffer
* `led_mux`-Tabelle als Byte-Sequenz und als 5×6-Bit-gepackte Variante → 0 Treffer

Die LED-Belegung kommt daher unverändert aus der am Hardware getesteten
Upstream-Definition für exakt dieses PCB und ist konsistent mit den
Geschwistern (V1.0/V2.0/U13: links = SDS1, rechts = SDS0).

### Frontschalter `S<>V`

Laut Board-Doku schaltet der Frontschalter über die HOLD-Leitung zwischen den
beiden Flash-Chips des Boards (nur einer ist dann aktiv) **und** ist zugleich
der VLAN-Schalter. Für das Flashen:

* Schalter in **`S`**-Stellung, Original-Firmware vorher sichern
* prüfen, ob das Gerät nach dem Flash mit RTLPlayground bootet; wenn nicht, den
  Schalter umstellen und den **anderen** Chip flashen
* der VLAN-Schalter ist unter RTLPlayground gegenstandslos – die VLAN-Funktion
  läuft in Software; in `V` isoliert die Hardware zusätzlich Ports

## 5. Erzeugtes Build

```
RTLPlayground/output/DAVUAZ_DA_K6402W/rtlplayground-v0.1.0-7957081-dirty-DAVUAZ_DA_K6402W.bin  (512 KiB)
RTLPlayground/output/DAVUAZ_DA_K6402W-2M-padded.bin                                            (2 MiB, für flashrom)
RTLPlayground/installer/output/rtlplayground_oem_upgrade.bin                                   (540 KiB)
```

* `make machine_check` → exit 0
* `make -C test` → ALL TESTS PASSED
* md5 der 512-KiB-Datei: `e89e0edc1ed19ab7fa96a64bf1634879`

Der Namenszusatz `-dirty-` kommt daher, dass die neuen Dateien noch nicht
committet sind. Nach einem `git add`/`git commit` entfällt er.

### Doku angepasst

* `doc/devices/PCB-K0402W-V3.0.md` → Brand-Liste um „Davuaz Da-K6402W“ ergänzt
* `doc/supported_devices.md` → Zeile `| Davuaz | Da-K6402W | No | PCB-K0402W-V3.0 | 2M | 4 + 2 |`

## 6. Flashen

Die Bestandsfirmware hat **kein Web-UI** → der Weg über „Firmware update“ der
OEM-Oberfläche existiert nicht. Es bleibt der **SOIC-8-Clip**:

1. Gerät ausschalten, Gehäuse öffnen
2. Clip auf den Flash-Chip (Pin 1 = Punkt-Markierung)
3. **Achtung, zwei Flash-Chips:** Der Front-Umschalter wählt über die HOLD-Leitung
   aus, welcher Chip aktiv ist. Ohne angeschlossene HOLD-Leitung programmiert
   der Clip den, den der Schalter gerade auswählt. Damit lassen sich Original-
   und RTLPlayground-Firmware parallel auf dem Board betreiben.
4. Chip-ID des Flash: `BY25Q16BS` (16 Mbit / 2 MiB)
5. Datei **`DAVUAZ_DA_K6402W-2M-padded.bin`** (auf 2 MiB aufgefüllt) flashen —
   die ungekürzte 512-KiB-Datei beschwert flashrom
6. **Nicht** die aufgefüllte Datei für ein Web-Update verwenden
7. Nach dem Flash startet das Gerät mit RTLPlayground (Web-UI unter
   `192.168.10.247`, Passwort `1234`, Konsole 115200 8N1)

Serienanschluss (Bestandsfirmware, **9600 baud**), Header `J2`:

| J2 Pin | Signal | USB-TTL-Adapter |
|---------|--------|-----------------|
| 1 | 3V3 | **nicht** verbinden |
| 2 | RX (Eingang) | TX |
| 3 | TX (Ausgang) | RX |
| 4 | GND | GND |

## 7. Offene Punkte / nächste Schritte

1. **Erst testen, nicht flashen:** das Gerät läuft unverändert mit der
   OEM-Firmware. Vor dem Flash ggf. `analyze/r837x_sdk_console.py` laufen lassen,
   um Chip-ID und LED-Register zu protokollieren — nützlich als Referenz, falls
   die LEDs nach dem Flash anders wirken als erwartet.
2. **Reset-Taster:** GPIO30 ist in der Definition bereits gesetzt. Laut Board-Doku
   ist der Taster nicht ab Werk bestückt, sondern eine Modifikation (TP131 auf GND
   über 1 kΩ). Ohne Taster keine „reset factory default“-Funktion.
3. **Zweiter Flash-Chip:** Es kann sinnvoll sein, das Original-Firmware auf dem
   zweiten Chip zu lassen, um über den Front-Schalter umschalten zu können.
