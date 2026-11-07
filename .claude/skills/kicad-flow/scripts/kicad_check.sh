#!/usr/bin/env bash
# Verifica un proyecto KiCad (2 o más capas de cobre) y exporta evidencias.
# Uso: kicad_check.sh [--fab] <carpeta_del_proyecto> [carpeta_de_salida]
#   --fab  además genera Gerbers + taladros en <salida>/gerbers
# Salida por defecto: <carpeta_del_proyecto>/out
set -u

FAB=0
if [ "${1:-}" = "--fab" ]; then FAB=1; shift; fi

PROJ_DIR="${1:?Indica la carpeta del proyecto KiCad}"
OUT_DIR="${2:-$PROJ_DIR/out}"
CLI="${KICAD_CLI:-/c/Program Files/KiCad/10.0/bin/kicad-cli.exe}"

SCH=$(ls "$PROJ_DIR"/*.kicad_sch 2>/dev/null | head -1)
PCB=$(ls "$PROJ_DIR"/*.kicad_pcb 2>/dev/null | head -1)
[ -n "$SCH" ] || { echo "No hay .kicad_sch en $PROJ_DIR"; exit 1; }
NAME=$(basename "$SCH" .kicad_sch)

if ls "$PROJ_DIR"/*.lck >/dev/null 2>&1; then
  echo "AVISO: hay archivos .lck; el proyecto está abierto en KiCad."
fi

mkdir -p "$OUT_DIR"
status=0

echo "== ERC =="
"$CLI" sch erc --severity-error --severity-warning --exit-code-violations \
  -o "$OUT_DIR/erc.rpt" "$SCH" >/dev/null 2>&1 || status=1
grep -E '^\[|ERC messages' "$OUT_DIR/erc.rpt"

"$CLI" sch export svg -o "$OUT_DIR" "$SCH" >/dev/null 2>&1
"$CLI" sch export pdf -o "$OUT_DIR/$NAME.pdf" "$SCH" >/dev/null 2>&1

if [ -n "$PCB" ]; then
  # Capas de cobre en orden de stackup, tal como aparecen en la sección (layers ...)
  CU_LAYERS=$(sed -n '/^\t(layers/,/^\t)/p' "$PCB" | grep -oE '"[A-Za-z0-9]+\.Cu"' | tr -d '"' | paste -sd, -)
  N_CU=$(echo "$CU_LAYERS" | tr ',' '\n' | grep -c .)
  echo "== Capas de cobre ($N_CU): $CU_LAYERS =="
  if [ "$N_CU" -gt 2 ] && ! grep -q '(stackup' "$PCB"; then
    echo "AVISO: placa multicapa sin stackup definido (Board Setup > Physical Stackup)."
  fi

  echo "== DRC (zonas rellenadas, con paridad esquemático/PCB) =="
  # --refill-zones rellena en memoria (no guarda): evita falsos 'unconnected' en planos internos
  "$CLI" pcb drc --refill-zones --schematic-parity --severity-error --severity-warning --exit-code-violations \
    -o "$OUT_DIR/drc.rpt" "$PCB" >/dev/null 2>&1 || status=1
  grep -E '^\[|^\*\* Found' "$OUT_DIR/drc.rpt"

  echo "== Renders 3D =="
  "$CLI" pcb render --side top --width 1200 --height 800 -o "$OUT_DIR/render_top.png" "$PCB" >/dev/null 2>&1
  "$CLI" pcb render --side bottom --width 1200 --height 800 -o "$OUT_DIR/render_bottom.png" "$PCB" >/dev/null 2>&1
  "$CLI" pcb render --rotate "-45,0,45" --zoom 0.9 --width 1200 --height 800 -o "$OUT_DIR/render_iso.png" "$PCB" >/dev/null 2>&1

  echo "== Vistas de capas (SVG) =="
  # Vista general: capas externas + serigrafía + contorno
  "$CLI" pcb export svg --layers F.Cu,B.Cu,F.SilkS,Edge.Cuts --mode-single --fit-page-to-board \
    -o "$OUT_DIR/layout.svg" "$PCB" >/dev/null 2>&1
  # Una vista por capa de cobre (incluye internas In1.Cu, In2.Cu, ...)
  for L in $(echo "$CU_LAYERS" | tr ',' ' '); do
    "$CLI" pcb export svg --layers "$L,Edge.Cuts" --mode-single --fit-page-to-board \
      -o "$OUT_DIR/layer_${L%.Cu}.svg" "$PCB" >/dev/null 2>&1
  done

  if [ $FAB -eq 1 ]; then
    echo "== Fabricación (Gerbers + taladros) =="
    GDIR="$OUT_DIR/gerbers"
    mkdir -p "$GDIR"
    "$CLI" pcb export gerbers --check-zones \
      --layers "$CU_LAYERS,F.Mask,B.Mask,F.Paste,B.Paste,F.SilkS,B.SilkS,Edge.Cuts" \
      -o "$GDIR" "$PCB" >/dev/null 2>&1 || { echo "ERROR exportando Gerbers"; status=1; }
    "$CLI" pcb export drill --generate-map --map-format gerberx2 \
      -o "$GDIR/" "$PCB" >/dev/null 2>&1 || { echo "ERROR exportando taladros"; status=1; }
    echo "$(ls "$GDIR" | wc -l) archivos en $GDIR"
  fi
fi

echo "== Archivos en $OUT_DIR =="
ls "$OUT_DIR"
[ $status -eq 0 ] && echo "RESULTADO: sin violaciones" || echo "RESULTADO: hay violaciones (ver .rpt)"
exit $status
