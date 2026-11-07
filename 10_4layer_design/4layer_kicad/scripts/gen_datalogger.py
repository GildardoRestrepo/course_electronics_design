"""Genera el esquemático del datalogger (práctica 10) con kicad_sch_gen de la skill kicad-flow.

Uso (desde la raíz del repo, con el Python de KiCad):
    "/c/Program Files/KiCad/10.0/bin/python.exe" -I 10_4layer_design/4layer_kicad/scripts/gen_datalogger.py [carpeta_salida]

Por defecto escribe en la carpeta del proyecto (sobrescribe los .kicad_sch: cerrar KiCad antes).
El símbolo propio DS1337S se lee de datalogger.kicad_sym y la configuración del proyecto se toma
del datalogger_v1.kicad_pro existente.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(PROJ, "..", ".."))
sys.path.insert(0, os.path.join(REPO, ".claude", "skills", "kicad-flow", "scripts"))
from kicad_sch_gen import Design  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else PROJ

d = Design("datalogger_v1", power_nets=("VCC", "GND"),
           title_block={"date": "07/11/2026", "rev": "v1", "company": "UPB",
                        "comments": ["Práctica 10 — Diseño en 4 capas"]})
d.add_lib("datalogger", open(os.path.join(PROJ, "datalogger.kicad_sym"), encoding="utf-8").read(),
          "Símbolos propios del datalogger")

FP = dict(R="Resistor_SMD:R_0805_2012Metric", C="Capacitor_SMD:C_0805_2012Metric",
          LED="LED_SMD:LED_0805_2012Metric", SOIC8="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")


def R(sh, ref, val, x, y, a, b):
    sh.two("Device:R", ref, val, x, y, a, b, fp=FP["R"])


def C(sh, ref, val, x, y, a, b):
    sh.two("Device:C", ref, val, x, y, a, b, fp=FP["C"])


root = d.root("A3", title="Datalogger ATmega328P — 4 capas")

# --- Real Time Clock
root.rect(25, 25, 165, 105, "Real Time Clock")
root.part("datalogger:DS1337S", "U1", "DS1337S", 90, 65,
          {"1": "RTC_X1", "2": "RTC_X2", "3": "RTC_INTA", "4": "GND", "5": "SDA", "6": "SCL", "7": "RTC_SQW", "8": "VCC"},
          fp=FP["SOIC8"])
root.part("Device:Crystal", "Y1", "32.768kHz 6pF", 50, 65, {"1": "RTC_X1", "2": "RTC_X2"},
          fp="Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm")
R(root, "R1", "10k", 130, 60, "VCC", "RTC_INTA")
R(root, "R2", "10k", 142.24, 60, "VCC", "RTC_SQW")
C(root, "C2", "100nF", 154.94, 60, "VCC", "GND")

# --- EEPROM (A2 siempre a VCC; U3 A1:A0 = 11, U4 A1:A0 = 00)
root.rect(25, 115, 165, 200, "EEPROM")
root.part("Memory_EEPROM:24LC1025", "U3", "24LC1025", 55, 150,
          {"1": "VCC", "2": "VCC", "3": "VCC", "4": "GND", "5": "SDA", "6": "SCL", "7": "GND", "8": "VCC"}, fp=FP["SOIC8"])
root.part("Memory_EEPROM:24LC1025", "U4", "24LC1025", 115, 150,
          {"1": "GND", "2": "GND", "3": "VCC", "4": "GND", "5": "SDA", "6": "SCL", "7": "GND", "8": "VCC"}, fp=FP["SOIC8"])
C(root, "C10", "100nF", 40, 182.88, "VCC", "GND")
C(root, "C11", "100nF", 52.07, 182.88, "VCC", "GND")
R(root, "R6", "4.7k", 130, 182.88, "VCC", "SDA")
R(root, "R7", "4.7k", 142.24, 182.88, "VCC", "SCL")

# --- MCU
root.rect(175, 25, 400, 175, "MCU")
mcu = {"1": "D3", "2": "D4", "3": "GND", "4": "VCC", "7": "XTAL1", "8": "XTAL2", "9": "D5", "10": "D6", "11": "D7",
       "12": "D8", "13": "NC", "14": "NC", "15": "MOSI", "16": "MISO", "17": "SCK", "18": "VCC", "19": "NC",
       "20": "AREF", "22": "NC", "23": "NC", "24": "NC", "25": "NC", "26": "NC", "27": "SDA", "28": "SCL",
       "29": "RESET", "30": "RX", "31": "TX", "32": "D2"}
root.part("MCU_Microchip_ATmega:ATmega328P-A", "U2", "ATmega328P-AU", 240, 100, mcu,
          fp="Package_QFP:TQFP-32_7x7mm_P0.8mm")
C(root, "C1", "100nF", 205.74, 80, "AREF", "GND")
root.part("Device:Crystal", "Y2", "16MHz", 300, 45, {"1": "XTAL1", "2": "XTAL2"}, fp="Crystal:Crystal_SMD_HC49-SD")
C(root, "C4", "22pF", 290.83, 60, "XTAL1", "GND")
C(root, "C5", "22pF", 309.88, 60, "XTAL2", "GND")
R(root, "R5", "10k", 300, 90, "VCC", "RESET")
root.part("Device:LED", "D1", "LED", 300, 120, {"1": "LED_USR", "2": "D8"}, fp=FP["LED"])
R(root, "R3", "330", 285.75, 135, "LED_USR", "GND")
root.part("Device:Battery", "BT1", "Battery", 345, 50, {"1": "VCC", "2": "GND"},
          fp="Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal")
C(root, "C3", "100nF", 360.68, 50, "VCC", "GND")
C(root, "C9", "10uF", 373.38, 50, "VCC", "GND")
root.part("power:PWR_FLAG", "#FLG01", "PWR_FLAG", 386.08, 38.1, {"1": "VCC"}, props=((386.08, 34, None), (386.08, 34, None)))
root.part("power:PWR_FLAG", "#FLG02", "PWR_FLAG", 393.7, 60, {"1": "GND"}, props=((393.7, 56, None), (393.7, 56, None)))
R(root, "R4", "330", 345, 90, "VCC", "LED_PWR")
root.part("Device:LED", "D2", "LED", 365, 105, {"1": "GND", "2": "LED_PWR"}, fp=FP["LED"])
C(root, "C6", "100nF", 330.2, 150, "VCC", "GND")
C(root, "C7", "100nF", 342.9, 150, "VCC", "GND")
C(root, "C8", "100nF", 355.6, 150, "VCC", "GND")
root.text("C6, C7, C8: junto a VCC (4), VCC (6) y AVCC (18) de U2", 320, 166, 1.27)

for i, xx in enumerate((200, 215, 230, 245), 1):
    root.part("Mechanical:MountingHole", f"H{i}", "MountingHole", xx, 195, {},
              fp="MountingHole:MountingHole_2.7mm_M2.5", in_bom=False)

# --- hoja Connectors
con = d.subsheet(root, "Connectors", "connectors.kicad_sch",
                 ["VCC", "SDA", "SCL", "SCK", "MOSI", "MISO", "RESET", "TX", "RX",
                  "D2", "D3", "D4", "D5", "D6", "D7", "D8", "GND"], at=(300, 200),
                 title="Datalogger ATmega328P — Conectores")
con.text("I2C", 40, 40); con.text("ICSP (AVR)", 40, 80); con.text("UART", 40, 120); con.text("E/S digitales", 140, 40)
PH = "Connector_PinHeader_2.54mm:"
con.part("Connector:Conn_01x04_Pin", "J1", "I2C", 55, 55, {"1": "VCC", "2": "GND", "3": "SDA", "4": "SCL"},
         fp=PH + "PinHeader_1x04_P2.54mm_Horizontal", hier=True)
con.part("Connector_Generic:Conn_02x03_Odd_Even", "J2", "ICSP", 60, 95,
         {"1": "MISO", "2": "VCC", "3": "SCK", "4": "MOSI", "5": "RESET", "6": "GND"},
         fp=PH + "PinHeader_2x03_P2.54mm_Vertical", hier=True)
con.part("Connector:Conn_01x03_Pin", "J3", "UART", 55, 135, {"1": "RX", "2": "TX", "3": "GND"},
         fp=PH + "PinHeader_1x03_P2.54mm_Horizontal", hier=True)
con.part("Connector:Conn_01x09_Pin", "J4", "E/S", 150, 65,
         {"1": "D2", "2": "D3", "3": "D4", "4": "D5", "5": "D6", "6": "D7", "7": "D8", "8": "VCC", "9": "GND"},
         fp=PH + "PinHeader_1x09_P2.54mm_Vertical", hier=True)

d.write(OUT, template_pro=os.path.join(PROJ, "datalogger_v1.kicad_pro"),
        netclasses=[dict(name="Default", track_width=0.2, clearance=0.2, via_diameter=0.6, via_drill=0.3),
                    dict(name="Power", track_width=0.4, clearance=0.2, via_diameter=0.6, via_drill=0.3, priority=0)],
        patterns={"VCC": "Power", "GND": "Power"},
        rules=dict(min_clearance=0.2, min_track_width=0.2, min_through_hole_diameter=0.3,
                   min_via_diameter=0.6, min_via_annular_width=0.15))
print("OK", OUT)
