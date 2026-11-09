# Analyse `backup1.bin` — 8×2.5G + 2×SFP+ (MaxLinear MxL86282)

## 1. Kurzfassung

**Der Chip ist kein Realtek, sondern MaxLinear.** Er ist damit **kein
RTLPlayground-Ziel**: RTLPlayground adressiert die SFRs der RTL8372/RTL8373
(DW8051, 8 Bit) direkt, dieser Chip hat einen 32-Bit-ARC-Kern, Zephyr und
einen komplett anderen Flash-Aufbau.

| | |
|---|---|
| Datei | `backup1.bin`, 2 097 152 Byte (2 MiB) |
| Plattform | MaxLinear **MXL** (nicht Realtek), Zephyr auf **ARC** 32-Bit |
| SoC | **MxL86282-Klasse**: 8 integrierte 2.5G-PHYs (`GPY2XX0`…`GPY2XX7`) + 2× 10G-SerDes (`usxgmii0`/`usxgmii1`) + 2 SFP+-Käfige |
| Switch-Core | **GSWIP** (Realtek-IP, von MaxLinear lizenziert) |
| CPU | 400 MHz ARC (Datenblatt MxL86282: „400MHz ARC CPU: Web smart") |
| Firmware | „WSP"-Firmware auf Zephyr, **kein Web-UI**, **kein Netzwerk-Stack** (0× DHCP/TCP/UDP/ARP/Socket) |
| Flash | 2 MiB, Header + Bootloader + WSP-App + GPHY-FW + Config |

Der **exakte Typennamen** („MxL86282") steht **nicht** im Dump; er ist aus der
Architektur (8 PHY + 2 SerDes) und der MaxLinear-Produktlinie abgeleitet und
muss an der Aufschrift des SoCs bestätigt werden.

## 2. Flash-Layout

```
0x000000-0x0006FF   Flash-Header (Magic A5 00 5A FF, MAC-Tag, GPHY-/SerDes-Init-Tabelle)
0x000700-0x003FFF   Fortsetzung der Init-Tabelle, danach nullgesetzt
0x004000-0x00AFFF   Bootloader (SSB): "hit Enter to go", "(1)Full Img, (2)Update Img",
                     "Plz snd img bin...", "Open slot %u", "Erase slot %u",
                     "Start WSP", "flash_mxl", "GPHY/Mcuboot/WSP version"
0x00A000-0x0F4AFF   WSP-Anwendung (Zephyr, 957 KiB belegt)
0x0F4B00-0x136EFF   gelöscht (0xFF) - freier Bereich
0x137000-0x15DFFF   GPHY-Firmware (RL-/GPY-2.5G-PHY, ~152 KiB)
0x162000-0x162FFF   SFP-Kompatibilitätsdatenbank (Vendor/Part-Number-Whitelist)
0x163000-0x1636FF   Port-/PHY-Konfiguration + "user settings partition"
0x164000-0x1FFFFF   gelöscht (0xFF)
```

Die Kopfzeile bei `0x6728` enthält zweimal `0x00100000` → zwei Slots à 1 MiB
(A/B-Slot-Schema, MCUboot-artig).

## 3. Was die Firmware kann – und was nicht

| | |
|---|---|
| **Layer 2** | vollständig: `switch_cli` mit ~120 GSWIP-Kommandos (VLAN, Extended VLAN, QoS mit Shaper/WRED/Meter/Scheduler/Remarking, STP, Trunking, MAC-Tabellen, Multicast-Snooping, PCE, Port-Konfig, RMON), dazu `sfp_cli`, `xpcs_cli`, `mac_cli`, `msec_cli` (MACsec) |
| **Stack** | Zephyr-NET: RSTP, LACP, LLDP, Loop-Detect, IGMP, Bridge |
| **Netzwerk auf dem Gerät** | voller IP-Stack vorhanden (DHCP, TCP, UDP, Socket) – aber **kein** Telnet, **kein** SSH, **kein** HTTP/TLS |
| **Web-UI** | **nicht vorhanden**: 0× `HTTP/1`, `<html`, `Content-Type`, `index.html`, `favicon`, TLS, gzip-Magic. Nur ein Websocket-**Client** |
| **Konfigurationszugang** | ausschließlich die lokale Shell über UART (`uart:~$`) |
| **Seriennummer/Update** | der Bootloader kann ein Image **über die serielle Schnittstelle** einspielen |

### Befehlsnamen (aus dem Dump extrahiert, als eigenständige Tokens belegt)

`switch_cli` `sfp_cli` `xpcs_cli` `mac_cli` `msec_cli` `ifconfig` `chiptest`
`firmware_ver` `firmware_copy` `reset_user_settings` `crc32` `mem_rd` `mem_wr`
`reg_wr` `help` `link` `port` `mdio` `gphy_cfg`

## 4. Die beiden Flash-Chips

Der 8+2 hat **zwei** SPI-Flash-Chips und einen Frontschalter (`S<>V`), der per
HOLD-Leitung den aktiven Chip auswählt. Belegt durch vier Dumps mit beiden
Schalterstellungen:

| Vergleich | Ergebnis |
|---|---|
| Chip 1 in Stellung `S` vs. `V` | **0 Byte Unterschied** – der Schalter schreibt nichts |
| Chip 1 vs. Chip 2 | **1562 Byte**, ausschließlich im Konfigurationsbereich |
| Codebereich `0x00000-0x161FFF` | **byteidentisch** – beide Chips haben dieselbe Firmware |

Die 1562 Byte sind:
* 7 Einzelbytes in der SFP-Datenbank (`0x162000`) – gespeicherte Modul-Kalibrierwerte
* 43 Byte in Chip 2 (`0x1630E8`–`0x163644`) – die gespeicherte *user settings
  partition* mit sieben MAC-Adressen `22:02:04:BA:02:01` … `22:02:04:BA:08:01`.
  Chip 1 hat dort noch `0xFF`, seine Settings wurden nie geschrieben.

**In keinem der beiden Chips ist ein Webinterface integriert.**

## 5. Wege zu einem gemanagten Gerät

| Route | Aufwand | Bewertung |
|---|---|---|
| **A** Web-Smart-Firmware (MxL86282**S**) per Bootloader-Update oder CH341A einspielen | Stunden, wenn das Image vorhanden | **beste Option** – aber: das Image ist nicht öffentlich (MaxLinear → OEM), und ein „Full Img" überschreibt den Flash-Header mit dem MAC-Tag → „MAC address : Null". Deshalb **Option 2 („Update Img")** und die ersten 4 KiB des Flash separat sichern. Kein OTP-Gating gefunden (die Fuse-Bits betreffen nur Cascaded-Mode/XPCS/GPHY). |
| **B** externe Web-UI über die serielle Shell | 6–10 Wochen | solide: die komplette Layer-2-Konfiguration ist über `switch_cli` erreichbar. Erfordert UART über die Testpunkte (TP14/TP15). |
| **C** OpenWrt auf dem Gerät | unrealistisch | Es gibt **kein** OpenWrt-Target für ARC; Speicher-Map/Clock/ICU/Slice sind proprietär; und vor allem: die MxL-Firmware **ist** der Switch-Treiber – Linux würde sie ersetzen und der Switch-Fabric wäre unerreichbar (die interne GSWIP-Registerkarte ist nicht öffentlich). |
| **D** OpenWrt auf einem anderen Board | Stunden | **BPI-R4 Pro (MT7988A + MxL86252C)**: 4× 2.5G + 2× 10G, DSA-Treiber `mxl862xx` ist im Kernel, OpenWrt-Images existieren. |

## 6. Offene Punkte

1. **Typennummer bestätigen** – Aufschrift auf dem SoC.
2. **UART** – es gibt keinen Header, nur Testpunkte (TP14/TP15). Der GND-Pad muss
   per Durchgangsmessung gefunden werden; Adapter-VCC **nicht** anschließen.
3. **Baudrate** der Shell steht nicht im Dump („UART_0" ist alles) – mit
   `uart_probe.py --scan` ermitteln.
4. **Web-Smart-Image** beschaffen (Board-Hersteller oder MaxLinear).
