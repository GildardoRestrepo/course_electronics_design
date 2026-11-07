# Datalogger con ATmega328P en 4 capas — Especificación (v1)

Práctica 10 de Diseño Electrónico IoT. Basada en el diseño de referencia "MCU Dataloguer" (Prof. Fabio Guzmán, UPB): ATmega328P + RTC DS1337 + dos EEPROM 24LC1025 por I²C, en una placa de 4 capas de 50 × 30 mm. Se replica la referencia con correcciones documentadas (ver *Correcciones*). La alimentación se deja **igual que la referencia**.

## Requisitos

| Parámetro | Valor |
|---|---|
| MCU | ATmega328P-AU (TQFP-32), cristal 16 MHz |
| Reloj de tiempo real | DS1337S (SOIC-8), cristal 32.768 kHz, bus I²C |
| Memoria | 2 × 24LC1025 (1 Mbit c/u, SOIC-8), bus I²C |
| Alimentación | BT1 "Battery" → red `VCC` (sin regulador, igual que la referencia; ver *Observaciones*) |
| Indicadores | D2 = LED de encendido · D1 = LED de usuario en PB0 (D8) |
| Conectores | J1 I²C · J2 ICSP · J3 UART · J4 E/S, en hoja jerárquica `connectors.kicad_sch` |
| Placa | **4 capas**, 50 × 30 mm, 1.6 mm, 4 agujeros de montaje M2.5 |
| Documentación en la PCB | **Tabla de stackup** y **tabla de características de la placa** (obligatorias, como en la referencia) |

## Diagrama de bloques

```
BT1 ──► VCC ──┬── U2 ATmega328P ──(16 MHz Y2)
              │        │ PC4/PC5 (SDA/SCL)
              │        ├─────────── U1 DS1337S ──(32.768 kHz Y1)
              │        ├─────────── U3 24LC1025 (A1:A0 = 11)
              │        └─────────── U4 24LC1025 (A1:A0 = 00)
              │        PB3–PB5 + RESET ──► J2 ICSP
              │        PD0/PD1 ─────────► J3 UART
              │        PD2–PD7, PB0 ────► J4 E/S   (PB0 también LED D1)
              └── D2 + R4 (LED encendido)
```

## Hojas del esquemático

1. **Raíz** (`datalogger_v1.kicad_sch`): bloques *Real Time Clock*, *MCU*, *EEPROM* (en rectángulos con título, como la referencia), H1–H4 y el símbolo de la hoja jerárquica.
2. **Connectors** (`connectors.kicad_sch`): J1–J4 con pines jerárquicos `VCC`, `GND`, `SDA`, `SCL`, `SCK`, `MOSI`, `MISO`, `RESET`, `TX`, `RX`, `D2`…`D8`.

## Redes

| Red | Conexiones |
|---|---|
| `VCC` | BT1 +, U2 VCC (4, 6) y AVCC (18), U1 VCC (8), U3/U4 VCC (8), R1, R2, R5, R6, R7, R4 (LED), U3 A0/A1/A2, U4 A2, C2, C3, C6–C11, J1-1, J2-2, J4-8 |
| `GND` | BT1 −, U2 GND (3, 5, 21), U1 GND (4), U3/U4 GND (4) y WP (7), U4 A0/A1, C1–C11, R3 (vía LED D1), D2 cátodo, J1-2, J2-6, J3-3, J4-9 |
| `SDA` / `SCL` | U2 PC4 (27) / PC5 (28), U1 (5/6), U3/U4 (5/6), R6 / R7 (4.7 kΩ a VCC), J1-3 / J1-4 |
| `MOSI` / `MISO` / `SCK` | U2 PB3 (15) / PB4 (16) / PB5 (17) → J2-4 / J2-1 / J2-3 |
| `RESET` | U2 PC6 (29), R5 (10 kΩ a VCC), J2-5 |
| `RX` / `TX` | U2 PD0 (30) / PD1 (31) → J3-1 / J3-2 *(ver nota de cruce)* |
| `D2`…`D7` | U2 PD2 (32), PD3 (1), PD4 (2), PD5 (9), PD6 (10), PD7 (11) → J4-1…J4-6 |
| `D8` | U2 PB0 (12) → ánodo de D1, J4-7 |
| `LED_USR` | cátodo de D1 → R3 (330 Ω) → GND |
| `LED_PWR` | R4 (330 Ω) desde VCC → ánodo de D2 |
| `XTAL1` / `XTAL2` | U2 PB6 (7) / PB7 (8), Y2, C4 / C5 (22 pF a GND) |
| `RTC_X1` / `RTC_X2` | U1 X1 (1) / X2 (2), Y1 |
| `RTC_INTA` / `RTC_SQW` | U1 INTA (3) / SQW/INTB (7), pull-ups R1 / R2 (10 kΩ). *Sin conexión al MCU, igual que la referencia* |
| `AREF` | U2 AREF (20), C1 (100 nF a GND) |

**No-connect** en U2: PB1 (13), PB2 (14), ADC6 (19), ADC7 (22), PC0–PC3 (23–26). `PWR_FLAG` en `VCC` y `GND`.

**Nota de UART:** J3 se rotula desde la placa: J3-1 = `RX` (entra al MCU), J3-2 = `TX` (sale del MCU). El adaptador USB-serie se conecta cruzado (su TX → RX de la placa).

## Direcciones I²C

Byte de control del 24LC1025: `1010 B0 A1 A0`; **A2 debe ir a VCC** (no es configurable). Con A1:A0 distintos, las dos memorias y el RTC no chocan:

| Dispositivo | A1:A0 | Dirección (7 bits) |
|---|---|---|
| U3 24LC1025 | 11 (VCC) | 0x53 (bloque 0) · 0x57 (bloque 1) |
| U4 24LC1025 | 00 (GND) | 0x50 (bloque 0) · 0x54 (bloque 1) |
| U1 DS1337 | — | 0x68 |

## Cálculos

**LEDs (R3, R4 = 330 Ω, LED rojo Vf ≈ 2.0 V):**

| VCC | I_LED | Nota |
|---|---|---|
| 5.0 V | 9.1 mA | Dentro de los 20 mA recomendados por pin del ATmega |
| 4.5 V | 7.6 mA | |
| 3.3 V | 3.9 mA | Aún visible |

**Pull-ups I²C (R6, R7 = 4.7 kΩ):** bus con 3 dispositivos + pistas cortas, C_bus ≲ 50 pF → t_r ≈ 0.85 × 4.7 kΩ × 50 pF ≈ 0.2 µs, dentro de los 1 µs de modo estándar (100 kHz) y de los 0.3 µs de modo rápido (400 kHz).

**Cristal 16 MHz (C4, C5 = 22 pF):** C_L = (22 × 22)/(22 + 22) + C_parásita (≈ 5 pF) ≈ 16 pF, adecuado para cristales de C_L 16–20 pF.

## Correcciones sobre la referencia

| Elemento | Referencia | Este diseño | Motivo |
|---|---|---|---|
| Pines de la hoja *Connectors* | Un solo pin `SCK` | `SCL` (I²C) y `SCK` (SPI) separados | Con un solo pin se unen dos buses distintos o se pierde uno |
| Desacople del ATmega | Solo C3 (100 nF) en la batería | **C6, C7, C8** (100 nF) junto a VCC-4, VCC-6 y AVCC-18 + **C9** (10 µF) bulk | La hoja de datos pide un 100 nF por pin de alimentación |
| Desacople de las EEPROM | Ninguno | **C10, C11** (100 nF) junto a U3/U4 | Ídem |
| BT1 | "Battery" sin footprint definido | Conector **JST PH 2 pines** horizontal | Batería desmontable, conector polarizado |
| Y1 | 32.768 kHz sin especificar | SMD 3.2 × 1.5 mm, **C_L = 6 pF** | El DS1337 exige cristal de 6 pF de carga |

## Observaciones (sin cambiar, por decisión de diseño)

- **Alimentación vs. frecuencia:** a 16 MHz el ATmega328P necesita **VCC ≥ 4.5 V** (hasta 10 MHz desde 2.7 V). La referencia no indica la batería; para operar dentro de especificación, BT1 debe dar 4.5–5.5 V (p. ej. 3 × AA alcalinas frescas o 5 V externo por J1/J4). Con una LiPo de 3.7 V habría que bajar Y2 a 8 MHz.
- **Sin regulador ni protección de polaridad:** la tensión de la batería va directo a `VCC`; el conector JST polarizado reduce el riesgo de invertirla.
- **RTC sin respaldo:** el DS1337 no tiene pin de batería de respaldo; si se corta `VCC` se pierde la hora.
- **Interrupciones del RTC** (`RTC_INTA`, `RTC_SQW`) quedan con pull-up pero sin llegar al MCU, igual que la referencia.

## Lista de materiales (BOM)

| Ref | Valor | Símbolo KiCad | Footprint KiCad |
|---|---|---|---|
| U2 | ATmega328P-AU | `MCU_Microchip_ATmega:ATmega328P-A` | `Package_QFP:TQFP-32_7x7mm_P0.8mm` |
| U1 | DS1337S | **propio** `datalogger:DS1337S` (no está en la biblioteca estándar) | `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm` |
| U3, U4 | 24LC1025 | `Memory_EEPROM:24LC1025` | `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm` |
| Y2 | 16 MHz | `Device:Crystal` | `Crystal:Crystal_SMD_HC49-SD` |
| Y1 | 32.768 kHz, 6 pF | `Device:Crystal` | `Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm` |
| C4, C5 | 22 pF C0G | `Device:C` | `Capacitor_SMD:C_0805_2012Metric` |
| C1, C2, C3, C6, C7, C8, C10, C11 | 100 nF X7R | `Device:C` | ídem |
| C9 | 10 µF X5R 10 V | `Device:C` | ídem |
| R1, R2, R5 | 10 kΩ | `Device:R` | `Resistor_SMD:R_0805_2012Metric` |
| R3, R4 | 330 Ω | `Device:R` | ídem |
| R6, R7 | 4.7 kΩ | `Device:R` | ídem |
| D1, D2 | LED rojo | `Device:LED` | `LED_SMD:LED_0805_2012Metric` |
| BT1 | Batería (ver observaciones) | `Device:Battery` | `Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal` |
| J1 | I²C: VCC, GND, SDA, SCL | `Connector:Conn_01x04_Pin` | `Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Horizontal` |
| J2 | ICSP AVR: MISO, VCC, SCK, MOSI, RESET, GND | `Connector_Generic:Conn_02x03_Odd_Even` | `Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical` |
| J3 | UART: RX, TX, GND | `Connector:Conn_01x03_Pin` | `Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Horizontal` |
| J4 | E/S: D2–D8, VCC, GND | `Connector:Conn_01x09_Pin` | `Connector_PinHeader_2.54mm:PinHeader_1x09_P2.54mm_Vertical` |
| H1–H4 | M2.5 | `Mechanical:MountingHole` | `MountingHole:MountingHole_2.7mm_M2.5` |

## PCB: stackup y reglas

Stackup **por defecto de KiCad para 4 capas** (el mismo de la tabla de la referencia), espesor total 1.6 mm:

| Capa | Tipo | Material | Espesor | εr | tan δ |
|---|---|---|---|---|---|
| F.Mask | máscara | — | 0.01 mm | 3.3 | 0 |
| F.Cu | cobre | — | 0.035 mm | — | — |
| Dieléctrico 1 | prepreg | FR4 | 0.1 mm | 4.5 | 0.02 |
| In1.Cu | cobre — **plano GND** | — | 0.035 mm | — | — |
| Dieléctrico 2 | core | FR4 | 1.24 mm | 4.5 | 0.02 |
| In2.Cu | cobre — **plano VCC** | — | 0.035 mm | — | — |
| Dieléctrico 3 | prepreg | FR4 | 0.1 mm | 4.5 | 0.02 |
| B.Cu | cobre | — | 0.035 mm | — | — |
| B.Mask | máscara | — | 0.01 mm | 3.3 | 0 |

| Regla | Valor | Nota |
|---|---|---|
| Pista mínima / separación mínima | 0.2 mm / 0.2 mm | La referencia muestra separación 0.0 mm (regla sin configurar) |
| Agujero mínimo | 0.3 mm | Vías 0.3 / 0.6 mm, solo pasantes |
| Clase `Power` (VCC, GND) | 0.4 mm | Las demás redes 0.2 mm |
| Acabado / impedancia controlada | Ninguno / No | Igual que la referencia |

**Asignación de capas:** F.Cu componentes y señales · In1.Cu plano GND continuo · In2.Cu plano VCC · B.Cu señales de cruce. Cada pad de GND/VCC baja al plano con su propia vía.

**Tablas obligatorias en la PCB** (en `User.Drawings`, fuera del contorno, como en la referencia): se insertan en KiCad al final, cuando el stackup y las reglas estén definitivos, con *Place → Add Stackup Table* y *Place → Add Board Characteristics*. Son una foto estática: si cambia el stackup o las reglas, hay que borrarlas y volver a insertarlas.

## Plan de trabajo

1. [x] Símbolo propio `DS1337S` en `datalogger.kicad_sym` + tabla de bibliotecas del proyecto. ✅ 2026-11-07
2. [x] Esquemático raíz + hoja `connectors` → ERC 0/0 (35 símbolos, 34 redes; netlist verificado contra la tabla de redes). ✅ 2026-11-07
3. [x] Usuario: *Actualizar PCB desde esquemático* (F8) con stackup de 4 capas por defecto. ✅ 2026-11-07
4. [x] Contorno 50 × 30 mm, H1–H4 M2.5 a 3.5 mm de las esquinas, planos In1 = GND e In2 = VCC (separación 0.25 mm, alivio térmico). ✅ 2026-11-07
5. [x] Colocación (cristales pegados a sus pines, desacoples junto a cada pin de alimentación). ✅ 2026-11-07
6. [x] Ruteo, DRC 0 violaciones (todas las severidades, con paridad). ✅ 2026-11-07
7. [x] Tablas de stackup y características (en User.Drawings), renders, vistas por capa, Gerbers, nota en `00_docs/10_4layer_design.md`. ✅ 2026-11-07

## PCB (v1)

**Colocación** (coordenadas desde la esquina superior izquierda):

| Zona | Componentes |
|---|---|
| Fila superior | U3, C10, U4, C11 (EEPROM + desacople), R6/R7 (pull-ups I²C), J3 UART acodado hacia arriba |
| Centro | U2 ATmega328P con C6/C7 (VCC) a la izquierda, C1 (AREF) y C8 (AVCC) a la derecha, R5 (RESET) arriba a la derecha |
| Bajo U2 | Y2 16 MHz con C4/C5 bajo sus pads |
| Izquierda | BT1 (JST, boca hacia el borde), C3/C9, U1 DS1337 con Y1 y R1/R2/C2 |
| Derecha | D1/R3 (LED usuario), D2/R4 (LED encendido), J1 I²C acodado hacia fuera |
| Borde inferior | J4 E/S (1×9) y J2 ICSP (2×3) |

**Ruteo**

- Fan-out: cada pad SMD de VCC/GND baja con un tramo de 0.3 mm a su propia vía (23 a GND, 24 a VCC). Los pads pasantes (J1–J4, BT1) se conectan a los planos con alivio térmico.
- Señales en 0.2 mm: 223 mm en F.Cu y 212 mm en B.Cu, 22 vías de señal (0.3/0.6 mm, pasantes).
- In1.Cu queda como plano GND casi continuo (≈ 1250 mm² de 1500 mm²): cada señal de F.Cu tiene referencia de tierra justo debajo.
- Pines sin uso del ATmega (PB1, PB2, ADC6, ADC7, PC0–PC3): pads sin red.

**Serigrafía**: referencias de 0.8 mm junto a cada componente (U2 al centro del TQFP); en B.SilkS: "UPB · Diseño Electrónico IoT", "Datalogger 4 capas · v1", "G. Restrepo · 2026".

**Regla propia** (`datalogger_v1.kicad_dru`): la serigrafía de las colas de J1/J3 sale del borde a propósito (headers acodados), así que se ignora `silk_clearance` contra `Edge.Cuts` solo para esas dos huellas.

---
## Enlaces
[[diseno_electronico_iot|Diseño Electrónico IoT]]
