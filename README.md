# switch-analysis-tools

Werkzeuge zur Analyse von **Switch-Flash-Dumps** und zur **seriellen Konsolen-Anbindung**
von Switches, die keine Web-Oberfläche haben.

Entstanden bei der Arbeit an zwei Geräten:

* **Davuaz Da-K6402W** – 4×2.5G + 2×SFP+, Realtek **RTL8372N** (DW8051), unterstützt von
  [RTLPlayground](https://github.com/logicog/RTLPlayground)
* **8×2.5G + 2×SFP+** – MaxLinear **MxL86282** (400-MHz-ARC, Zephyr, GSWIP-Switch-Core),
  kein Web-UI, Konfiguration nur über die serielle Shell

Die beiden Analysen liegen in [`docs/`](docs/).

## Installation

```bash
git clone https://github.com/etzisim/switch-analysis-tools.git
cd switch-analysis-tools

# nur für die Serial-Skripte nötig:
python3 -m venv .venv
.venv/bin/pip install pyserial
```

Alle Skripte laufen direkt aus dem Repo, z. B. `python3 tools/flash_identify.py dump.bin`.

## Werkzeuge

### Flash-Dump analysieren

| Skript | Zweck |
|---|---|
| `flash_identify.py` | Erkennt die Plattform eines Dumps (`rtl837x` vs. `mxl-wsp`) und druckt die Partitionskarte mit den Belegen |
| `regions.py` | Regionskarte im 256-Byte-Raster: Code, Daten, gelöscht |
| `flashmap.py` | Grobe 4-KiB-Karte mit Byte-Histogramm und Bank-Erkennung |
| `strings.py` | ASCII- und UTF-16LE-Strings mit Offsets |
| `magics.py` | Bekannte Magics (MCUboot, RTLPlayground-Update-Header …) |
| `find_init_tables.py` | Init-Tabellen (Register/Wert-Paare) im Dump finden |
| `led_init_from_837x_dump.py` | LED-Register-Programmierung im 8051-Code suchen |
| `machines.py` | RTLPlayground-Machine-Definitionen mit Port-/SFP-Zuordnung listen |

### Serielle Konsole

| Skript | Zweck |
|---|---|
| `console_capture.py` | Konsole mitschreiben, mit Baudraten-Scan (`--scan`) |
| `uart_probe.py` | Eine Konsole an einem Board finden, das nur Testpunkte hat (TP-Pads) |
| `r837x_sdk_console.py` | Switch-Register aus der OEM-SDK-Konsole lesen (`rd <reg>`) |

### Firmware-Images vorbereiten

| Skript | Zweck |
|---|---|
| `find_mac_tag.py` | MAC-Adresse im Flash-Header lokalisieren |
| `prep_web_smart_flash.py` | Vendor-Image mit Header/MAC des eigenen Dumps zusammenführen, ohne den MAC-Tag zu verlieren |

## Beispiele

```bash
# Plattform eines Dumps bestimmen
python3 tools/flash_identify.py backup.bin

# Konsolen-Baudrate suchen und mitschreiben
python3 tools/console_capture.py --port /dev/ttyUSB0 --scan --seconds 30 --out boot.log

# Board mit nur Testpunkten: Adapter-RX an TP14, dann an TP15 probieren
python3 tools/uart_probe.py --port /dev/ttyUSB0 --scan

# MAC im Header lokalisieren (MAC aus der Konsolenausgabe)
python3 tools/find_mac_tag.py backup.bin AA:BB:CC:DD:EE:FF

# Vendor-Image vorbereiten, ohne den MAC-Tag zu verlieren
python3 tools/prep_web_smart_flash.py --current backup.bin --vendor vendor.bin \
        --out merged.bin --dry-run
```

## Bewährte Regeln beim-reverse-Engineering

Aus den beiden Analysen hat sich ein Ablauf bewährt, der zwei Fehlerklassen
vermeidet:

1. **Nie einen String aus einem Firmware-Image als Beweis für die konkrete
   Hardware nehmen.** Ein SDK-Image enthält Codepfade für *viele*
   Chip-/PHY-Kombinationen. Belastbar sind nur Registerwerte, die man **am
   Gerät** liest (`regget 4`, `regget 0x65e0`), und was die Hardware selbst
   hergibt (Portnummern, LEDs, SFP-EEPROM).

2. **Herkunft jeder Aussage trennen.** Was aus dem Dump stammt, was aus dem
   Datenblatt, und was aus der Dokumentation – getrennt ausweisen. Im PR und in
   den Berichten ist das durchgängig getrennt.

## Lizenz

Public Domain / CC0 – frei verwendbar.
