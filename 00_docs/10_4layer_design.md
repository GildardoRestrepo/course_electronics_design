---
type: referencia
---

# Práctica #10: Diseño en 4 capas en KiCad (Datalogger)

**Fecha:** 07/11/2026
**Estudiante:** Gildardo Estevan Restrepo Duque
**Guía:** Diseño 4 capas KiCad (Datalogger) — Prof. Fabio Guzmán, UPB

---

## Objetivo

Diseñar en KiCad una PCB de **4 capas** para un datalogger con microcontrolador: un ATmega328P a 16 MHz guarda datos en dos memorias EEPROM 24LC1025 y lleva la hora con un RTC DS1337, todo por I²C. La placa mide 50 × 30 mm y debe incluir la **tabla de stackup** y la **tabla de características de la placa**, como el diseño de referencia.

## Archivos de esta práctica

- Especificación completa (redes, direcciones I²C, cálculos, BOM, stackup, colocación): [`especificacion.md`](../10_4layer_design/4layer_kicad/especificacion.md)
- Proyecto KiCad: [`10_4layer_design/4layer_kicad`](../10_4layer_design/4layer_kicad) (`datalogger_v1.kicad_pro`)
- Evidencias en [`project_assets/`](../10_4layer_design/project_assets):
  - Esquemático: [`datalogger_v1_sch.pdf`](../10_4layer_design/project_assets/datalogger_v1_sch.pdf)
  - PCB con las tablas de stackup y características: [`datalogger_v1_pcb.pdf`](../10_4layer_design/project_assets/datalogger_v1_pcb.pdf)
  - Renders 3D (`render_top/bottom/iso.png`), una vista por capa de cobre (`layer_F/In1/In2/B.svg`) y la lista de materiales (`bom.csv`)

## Esquemático

Dos hojas, como la referencia:

- **Raíz:** bloques *Real Time Clock* (U1 DS1337S + Y1 32.768 kHz + pull-ups de las interrupciones), *MCU* (U2 ATmega328P-AU + Y2 16 MHz + reset + LEDs + batería) y *EEPROM* (U3/U4 24LC1025 + pull-ups I²C de 4.7 kΩ).
- **Connectors:** J1 I²C, J2 ICSP (pinout AVR estándar), J3 UART y J4 E/S (D2–D8), conectados por etiquetas jerárquicas.

El DS1337 no está en la biblioteca de KiCad; se hizo un símbolo propio (`datalogger.kicad_sym`) con el pinout de la hoja de datos. Las EEPROM quedan en direcciones distintas (U3: A1:A0 = 11 → 0x53/0x57; U4: A1:A0 = 00 → 0x50/0x54; A2 siempre a VCC) y no chocan con el RTC (0x68).

**ERC:** 0 errores, 0 advertencias. Netlist verificado red por red contra la especificación.

## Correcciones sobre la referencia

| Elemento | Referencia | Este diseño | Motivo |
|---|---|---|---|
| Hoja *Connectors* | Un solo pin `SCK` | `SCL` (I²C) y `SCK` (SPI) separados | Con un solo pin se unen dos buses distintos o se pierde uno |
| Desacople del ATmega | Solo C3 en la batería | C6, C7, C8 (100 nF) en VCC-4, VCC-6 y AVCC-18 + C9 (10 µF) | La hoja de datos pide un 100 nF por pin de alimentación |
| Desacople de las EEPROM | Ninguno | C10, C11 (100 nF) | Ídem |
| BT1 | Sin footprint definido | Conector JST PH de 2 pines | Batería desmontable y polarizada |
| Y1 | 32.768 kHz sin especificar | C_L = 6 pF | Lo exige el DS1337 |

**Observación sin cambiar** (se dejó igual que la referencia): a 16 MHz el ATmega328P necesita VCC ≥ 4.5 V, así que la batería debe dar 4.5–5.5 V (p. ej. 3 × AA o 5 V externo).

## PCB de 4 capas

**Stackup** (el de KiCad por defecto, igual a la tabla de la referencia): F.Cu / prepreg 0.1 mm / **In1.Cu = plano GND** / core 1.24 mm / **In2.Cu = plano VCC** / prepreg 0.1 mm / B.Cu; 1.6 mm en total, FR4 εr 4.5.

**Reglas:** pista y separación mínimas de 0.2 mm, agujero mínimo de 0.3 mm, vías pasantes de 0.3/0.6 mm. Clase *Power* (VCC, GND) a 0.4 mm. La tabla de la referencia mostraba separación 0.0 mm porque la regla estaba sin configurar.

**Colocación:**

- Fila superior: U3 y U4 con su capacitor de desacople al lado, R6/R7 (pull-ups I²C) y J3 (UART, acodado hacia arriba).
- Centro: U2 con C6/C7 a la izquierda (VCC), C1 (AREF) y C8 (AVCC) a la derecha y R5 (reset) junto al pin 29.
- Bajo U2: el cristal de 16 MHz con C4/C5 debajo de sus pads.
- Izquierda: BT1 con la boca hacia el borde, C3/C9 y el RTC con su cristal.
- Derecha: los dos LEDs con sus resistencias y J1 (I²C, acodado hacia fuera).
- Borde inferior: J4 (E/S) y J2 (ICSP). Agujeros M2.5 en las cuatro esquinas.

**Ruteo:**

- Cada pad SMD de VCC o GND baja con un tramo corto a su propia vía hacia el plano interno (47 vías). Los pines pasantes de los conectores tocan los planos directamente con alivio térmico.
- Las señales van en F.Cu y B.Cu con pistas de 0.2 mm (≈ 435 mm en total y 22 vías). In1.Cu queda como plano de tierra casi continuo, así todas las señales tienen su retorno justo debajo.
- Para que la señal de reset pudiera salir del pin 29 del ATmega, U2 se bajó 0.7 mm y R5 se acercó al pin.

**Serigrafía:** referencias de 0.8 mm junto a cada componente; en la cara inferior "UPB · Diseño Electrónico IoT", "Datalogger 4 capas · v1" y "G. Restrepo · 2026". Las colas de los headers acodados J1 y J3 sobresalen del borde a propósito; una regla del proyecto (`datalogger_v1.kicad_dru`) acepta solo ese caso.

**Tablas:** la tabla de stackup y la de características de la placa están en *User.Drawings*, arriba y abajo de la placa.

**DRC con paridad esquemático/PCB (todas las severidades):** 0 violaciones, 0 conexiones pendientes, 0 errores de huella.

## Fabricación

Los Gerbers (las 4 capas de cobre, máscaras, pasta, serigrafía y contorno) y el archivo de taladros se generan con:

```bash
bash .claude/skills/kicad-flow/scripts/kicad_check.sh --fab 10_4layer_design/4layer_kicad
```

---
## Enlaces
[[diseno_electronico_iot|Diseño Electrónico IoT]]
