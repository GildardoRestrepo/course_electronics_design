---
name: kicad-flow
description: Flujo de trabajo para diseñar, revisar y documentar circuitos en KiCad 10 dentro de este repo (prácticas de Diseño Electrónico IoT), en placas de 2 o 4 capas y con módulos ESP32. Úsala cuando el usuario quiera crear o modificar un esquemático o PCB, definir stackup o planos, correr ERC/DRC, rutear, exportar renders/Gerbers/BOM, revisar capturas de KiCad o preparar evidencias de una práctica de KiCad.
---

# Flujo KiCad

## Entorno
- KiCad 10.0.5 en Windows. CLI: `/c/Program Files/KiCad/10.0/bin/kicad-cli.exe` (bash).
- Python con `pcbnew`: `/c/Program Files/KiCad/10.0/bin/python.exe` (solo para scripts de PCB; no hay `kipy` y la API IPC está apagada).
- Bibliotecas estándar: `/c/Program Files/KiCad/10.0/share/kicad/{symbols,footprints,3dmodels}`.
- Cada proyecto vive en `NN_<práctica>/<nombre_proyecto>/` y solo se versionan `.kicad_pro`, `.kicad_sch` y `.kicad_pcb` (más libs propias). `.kicad_prl`, backups e `.history` están en `.gitignore`.

## Regla de oro: un solo editor a la vez
Los `.kicad_sch` / `.kicad_pcb` son S-expressions editables como texto, pero KiCad sobrescribe el archivo al guardar.
1. Antes de editar un archivo, pide al usuario que lo cierre en KiCad (si existe un `*.lck` en la carpeta, sigue abierto).
2. Edita, valida con el script y avisa al usuario para que lo vuelva a abrir.
3. Si el usuario editó en KiCad, vuelve a leer el archivo antes de tocarlo. Haz commit antes de cambios grandes para poder revertir.

## Ciclo de diseño
1. **Definir** el circuito con el usuario: función, alimentación, valores calculados (p. ej. R de un LED = (Vbat − Vf) / I).
2. **Esquemático**: símbolos de la biblioteca estándar, etiquetas de red con nombres claros (`vbat`, `gnd`, `led_a`), todas las unidades de un símbolo multi-unidad colocadas o usar un símbolo de una unidad, flags `PWR_FLAG` en redes de alimentación.
3. **ERC** sin errores ni advertencias (o justificadas).
4. **Footprints** coherentes con la pieza real (p. ej. resistencia 1/4 W THT → `Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal`). El usuario ejecuta *Actualizar PCB desde esquemático* (F8) en KiCad.
5. **PCB**: número de capas y stackup (ver *Diseño multicapa*), contorno en `Edge.Cuts` (rectángulo cerrado), colocación, ruteo, planos de GND/alimentación, textos de serigrafía legibles y a ≥ 0.5 mm del borde (evita `silk_edge_clearance`).
6. **DRC** con paridad esquemático/PCB sin violaciones.
7. **Evidencias**: renders, vistas de capas y PDF en la carpeta de recursos de la práctica (`NN_<práctica>/project_assets/`), nota de la práctica en `00_docs/NN_<práctica>.md`.

## Verificación y exportación
```bash
bash .claude/skills/kicad-flow/scripts/kicad_check.sh [--fab] <carpeta_proyecto> [carpeta_salida]
```
En proyectos jerárquicos toma como raíz el `.kicad_sch` (y la `.kicad_pcb`) con el mismo nombre que el `.kicad_pro`. Genera `erc.rpt`, `drc.rpt`, esquemático en SVG/PDF, `render_top/bottom/iso.png`, `layout.svg` (capas externas + serigrafía) y un `layer_<capa>.svg` por cada capa de cobre (incluidas las internas `In1`, `In2`, …). Detecta cuántas capas de cobre tiene la placa y avisa si una placa multicapa no tiene stackup. El DRC corre con `--refill-zones` (rellena en memoria, no guarda), así los planos internos no dan falsos *unconnected*. Con `--fab` también exporta Gerbers de todas las capas de cobre + máscaras, pasta, serigrafía y `Edge.Cuts`, y taladros Excellon con mapa, en `<salida>/gerbers/`. Devuelve código 1 si hay violaciones. Mira los PNG con la herramienta Read para revisar el diseño visualmente en vez de depender solo de capturas.

Otros comandos útiles de `kicad-cli`:
- BOM: `sch export bom -o bom.csv <sch>`
- Netlist: `sch export netlist -o net.xml <sch>`
- Posiciones para ensamblaje (SMT): `pcb export pos --format csv --units mm -o pos.csv <pcb>`
- Estadísticas de la placa: `pcb export stats -o stats.txt <pcb>`
- No usar `pcb export gerbers` sin `--layers`: toma la configuración de ploteo guardada y puede omitir las capas internas.

## Diseño multicapa (4 capas)
**Stackup y reglas primero**, antes de colocar componentes:
- Stackup recomendado: `F.Cu` señales/componentes · `In1.Cu` **GND sólido** · `In2.Cu` alimentación (3V3, VIN) · `B.Cu` señales. Toda señal rápida debe tener un plano de GND continuo justo al lado; no cortar `In1.Cu` con pistas.
- El usuario define el stackup en KiCad (*Board Setup → Physical Stackup*), según el fabricante elegido (p. ej. el stackup estándar de 4 capas de JLCPCB). **El stackup no es accesible desde `pcbnew` en Python** (`GetStackupDescriptor()` devuelve un `SwigPyObject` sin tipo); no intentar editarlo por script.
- Reglas del fabricante en *Board Setup → Design Rules* (ancho/separación mínimos, vía mínima, anillo, distancia al borde). Confirmar valores en la web del fabricante; usar margen (p. ej. 0.15/0.15 mm y vía 0.3/0.6 mm) en vez del mínimo absoluto.
- **Solo vías pasantes** (sin ciegas/enterradas): son más baratas y el taladro se exporta en un solo archivo.
- Clases de red (*netclasses*) para potencia (pistas anchas), señal y, si aplica, pares diferenciales (USB D+/D− a 90 Ω). Viven en `net_settings` del `.kicad_pro` (JSON); se pueden editar por texto con KiCad cerrado.

**Con `pcbnew` (Python) sí se puede**:
- Cambiar el número de capas: `board.SetCopperLayerCount(4)` (verificado en KiCad 10).
- Crear zonas/planos (`pcbnew.ZONE`, `SetLayer`, `SetNetCode`, contorno con `Outline()`), rellenarlas con `pcbnew.ZONE_FILLER(board).Fill(board.Zones())` y guardar.
- Vías de cosido (*stitching*) en grilla asignadas a GND.

**Planos y zonas**:
- Una zona GND en `In1.Cu` que cubra toda la placa; en `In2.Cu` la alimentación (se puede dividir 3V3/VIN con separación ≥ 0.5 mm, sin que una señal de `F.Cu` cruce el corte por encima).
- Rellenos de GND también en `F.Cu`/`B.Cu`, cosidos al plano interno con vías cada ~5–10 mm y alrededor del borde.
- Tras mover algo, rellenar zonas (tecla **B**) antes de mirar el DRC en KiCad.

**Ruteo por script (práctica 10)**: con planos internos, primero un *fan-out* (cada pad SMD de VCC/GND → tramo corto a vía; los pads pasantes tocan el plano solos) y luego las señales en F.Cu/B.Cu con un A* sobre grilla de 0.25 mm, inflando obstáculos con separación + medio ancho + ~0.06 mm de margen. Si una red falla, pasarla al frente del orden y repetir desde la placa sin pistas; si sigue fallando, abrir espacio en la colocación (p. ej. el canal sobre un TQFP). Verificar siempre con DRC (`--refill-zones`).

**Tablas de stackup y características**: no hay API en Python para generarlas; el usuario las inserta en KiCad (*Place → Add Stackup Table* / *Add Board Characteristics*) en `User.Drawings`, fuera del contorno, al final del diseño.

**Revisión visual**: revisar cada `layer_<capa>.svg` (sobre todo que `In1.Cu` sea un plano casi continuo) además de los renders 3D, que solo muestran las capas externas.

## ESP32 (proyecto final)
- Símbolos y footprints en la biblioteca estándar `RF_Module` (p. ej. `ESP32-WROOM-32E`, `ESP32-S3-WROOM-1`, `ESP32-C3-WROOM-02`, `ESP32-C6-MINI-1`); modelos 3D incluidos.
- **Antena**: el módulo va al borde de la placa con la antena hacia fuera (o sobresaliendo). Bajo la antena **ningún cobre en ninguna capa**: zona de exclusión (*Rule Area*) con *keepout* de pistas, vías, zonas y footprints en las 4 capas, con el tamaño que indica la hoja de datos del módulo.
- Desacople: 10 µF + 100 nF junto a los pines de 3V3, cada capacitor con su vía directa al plano GND. Regulador 3V3 capaz de ≥ 500 mA (picos de Wi-Fi).
- Arranque y programación: pull-up 10 kΩ + 1 µF en `EN`, botones `EN`/`BOOT` (BOOT = GPIO0 en ESP32 clásico y S3, GPIO9 en C3/C6; confirmar los strapping pins en la hoja de datos), acceso a UART (TX/RX) o USB nativo (S3/C3) con par diferencial.
- No usar como I/O los pines de la flash interna (GPIO6–11 en ESP32 clásico) ni dejar strapping pins con cargas que alteren el arranque.

## Lectura de capturas del usuario
Las capturas muestran lo que el usuario ve en ese momento (selecciones, errores en pantalla). Contrástalas siempre con los archivos y los reportes: el visor 3D dibuja una placa de relleno aunque no exista `Edge.Cuts`, y la ratsnest (líneas finas) no son pistas.

## Edición de archivos
- Leer el archivo completo antes de editar; conservar `uuid`s existentes y generar nuevos para elementos nuevos.
- Coordenadas en mm; el esquemático usa grilla de 1.27 mm (pines en múltiplos de 2.54).
- Para PCB, preferir scripts con `pcbnew` (cargar, modificar, `board.Save()`) sobre editar texto a mano cuando se trate de pistas o contornos.
- Al cambiar un footprint con `pcbnew` (`FootprintLoad`), conservar la paridad: `SetPath()` del footprint viejo, `SetFPID(LIB_ID("<lib>", "<nombre>"))` con el nombre de biblioteca, copiar los campos (p. ej. `Description`) recorriendo `GetFields()` y reasignar las redes de los pads.
- Hacer **un reemplazo de footprint por ejecución** de Python: tras `b.Remove()`/`b.Add()`, SWIG devuelve `SwigPyObject` sin tipo para los demás footprints. Colocar en otra ejecución.
- Al cambiar un footprint en el `.kicad_sch` por texto, no tocar la sección `lib_symbols` (es la copia de la biblioteca; si cambia, el ERC avisa `lib_symbol_mismatch`). Editar solo la propiedad del símbolo colocado.
- Pads de pines con no-connect: F8 les asigna la red `unconnected-(<Ref>-<Pin>-Pad<N>)`. En pines **pasivos** el DRC con paridad lo acepta; en pines de otro tipo (p. ej. E/S de un MCU) KiCad 10 marca `net_conflict` ("No se encontró un pin correspondiente en el esquema"). Solución verificada: dejar esos pads **sin red** (`pad.SetNetCode(0)`).
- `fp.Remove(item)` también rompe la iteración de `GraphicalItems()` de otras huellas (SWIG). Para sacar serigrafía de una huella, moverla de capa (`SetLayer(F_Fab)`) en vez de borrarla, y aun así eso causa `lib_footprint_mismatch`. Si la serigrafía de un conector acodado sale del borde a propósito, preferir una regla en `<proyecto>.kicad_dru`: `(rule "..." (layer "F.SilkS") (condition "A.memberOfFootprint('J1') && B.Layer == 'Edge.Cuts'") (constraint silk_clearance) (severity ignore))`. El chequeo de borde de serigrafía usa `silk_clearance`, no `edge_clearance`.
- Referencias en serigrafía: tamaño mínimo 0.8 mm (regla `min_text_height`); colocarlas por script probando posiciones alrededor del courtyard **ordenadas por cercanía** al componente y verificando contra pads, vías, serigrafía ajena y borde. Si no, quedan lejos y confunden.
- Tras cualquier edición, correr el script de verificación antes de entregar.
