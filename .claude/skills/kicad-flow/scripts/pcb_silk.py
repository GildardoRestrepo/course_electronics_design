"""Serigrafía: coloca cada referencia junto a su componente sin solapes y añade textos en la cara inferior.

Uso (con el Python de KiCad, con la PCB cerrada en KiCad; correr después del ruteo, porque las vías
también son obstáculo):
    "/c/Program Files/KiCad/10.0/bin/python.exe" -I pcb_silk.py <archivo.kicad_pcb> <config.json>

Sección "silk" del JSON (valores por defecto):
  {"text_height": 0.8, "thickness": 0.13, "edge_margin": 0.3,
   "hide_prefixes": ["H"],                    # p. ej. agujeros de montaje
   "center_min_pads": 21,                     # CI con más pads: referencia al centro del cuerpo
   "manual": {"C11": [x, y, ángulo]},         # posiciones fijas, relativas al origen de la placa
   "bottom_text": [["UPB · ...", 1.0], ...]}  # líneas en B.SilkS (espejadas), donde haya espacio

Para cada referencia prueba posiciones alrededor del courtyard ordenadas por cercanía al componente
y descarta las que tocan pads, vías, serigrafía de otras huellas, otras referencias o el borde. Si
ninguna sirve, deja la referencia en F.Fab y lo informa (usar "manual" para esos casos).
"""
import json, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM as M, ToMM as T

pcb, cfg_all = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8"))
cfg = {"text_height": 0.8, "thickness": 0.13, "edge_margin": 0.3, "hide_prefixes": ["H"], "center_min_pads": 21,
       "manual": {}, "bottom_text": [], **cfg_all.get("silk", {})}
OX, OY = cfg_all.get("board", {}).get("origin", [0, 0])
b = pcbnew.LoadBoard(pcb)
bb = b.GetBoardEdgesBoundingBox()
X0, Y0, X1, Y1 = T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())
H, TH, EDGE = cfg["text_height"], cfg["thickness"], cfg["edge_margin"]


def box(o):
    r = o.GetBoundingBox()
    return (T(r.GetLeft()), T(r.GetTop()), T(r.GetRight()), T(r.GetBottom()))


def inflate(r, d):
    return (r[0] - d, r[1] - d, r[2] + d, r[3] + d)


def hit(a, c):
    return not (a[2] <= c[0] or c[2] <= a[0] or a[3] <= c[1] or c[3] <= a[1])


def outside(rb, m):
    return rb[0] < X0 + m or rb[2] > X1 - m or rb[1] < Y0 + m or rb[3] > Y1 - m


# ---------------------------------------------------------------- obstáculos en F.SilkS
obst = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.IsOnLayer(pcbnew.F_Cu) or p.IsOnLayer(pcbnew.F_Mask):
            obst.append(inflate(box(p), 0.15))
    for g in fp.GraphicalItems():
        if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() != "PCB_TEXT":
            obst.append(inflate(box(g), 0.1))
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        obst.append(inflate(box(t), 0.15))

# ---------------------------------------------------------------- referencias
fps = list(b.GetFootprints())
manual = {k: v for k, v in cfg["manual"].items()}
order = sorted(fps, key=lambda f: (f.GetReference() not in manual,
                                   T(f.GetBoundingBox(False).GetWidth()) * T(f.GetBoundingBox(False).GetHeight())))
unplaced = []
for fp in order:
    refname = fp.GetReference()
    ref = fp.Reference()
    if any(refname.startswith(pfx) and refname[len(pfx):].isdigit() for pfx in cfg["hide_prefixes"]):
        ref.SetVisible(False); continue
    ref.SetLayer(pcbnew.F_SilkS)
    ref.SetTextSize(VECTOR2I(M(H), M(H))); ref.SetTextThickness(M(TH))
    if refname in manual:
        x, y, a = manual[refname]
        ref.SetTextAngleDegrees(a); ref.SetPosition(VECTOR2I(M(OX + x), M(OY + y)))
        obst.append(inflate(box(ref), 0.1))
        continue
    cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    if cy.GetWidth() == 0:
        cy = fp.GetBoundingBox(False)
    l, t, r, btm = T(cy.GetLeft()), T(cy.GetTop()), T(cy.GetRight()), T(cy.GetBottom())
    c = (T(fp.GetPosition().x), T(fp.GetPosition().y))
    cands = [(c[0], c[1], 0)] if fp.GetPadCount() >= cfg["center_min_pads"] else []
    mx, my = (l + r) / 2, (t + btm) / 2
    half_len = 0.4 * H * len(refname) + 0.1
    ring = []
    for dist in (0.45, 0.9, 1.3, 1.8, 2.2):
        for dx in (0, -0.5, 0.5, -1.0, 1.0, -1.5, 1.5, -2.0, 2.0):
            ring += [(mx + dx, t - dist, 0), (mx + dx, btm + dist, 0),
                     (mx + dx, t - dist - half_len + 0.4, 90), (mx + dx, btm + dist + half_len - 0.4, 90)]
        for dy in (0, -0.5, 0.5, -1.0, 1.0, -1.5, 1.5):
            ring += [(l - dist, my + dy, 90), (r + dist, my + dy, 90),
                     (l - dist - half_len + 0.4, my + dy, 0), (r + dist + half_len - 0.4, my + dy, 0)]
    ring.sort(key=lambda q: (q[0] - c[0]) ** 2 + (q[1] - c[1]) ** 2)
    for x, y, ang in cands + ring:
        ref.SetTextAngleDegrees(ang)
        ref.SetPosition(VECTOR2I(M(x), M(y)))
        rb = box(ref)
        if outside(rb, EDGE) or any(hit(rb, o) for o in obst):
            continue
        obst.append(inflate(rb, 0.1))
        break
    else:
        unplaced.append(refname)
        ref.SetLayer(pcbnew.F_Fab)

# ---------------------------------------------------------------- textos en la cara inferior
for d in list(b.GetDrawings()):            # rehacer los textos de una corrida anterior
    if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.B_SilkS and d.GetText() in [s for s, _ in cfg["bottom_text"]]:
        b.Remove(d)
bobst = []
for fp in fps:
    for p in fp.Pads():
        if p.IsOnLayer(pcbnew.B_Cu):
            bobst.append(inflate(box(p), 0.2))
    for g in fp.GraphicalItems():
        if g.GetLayer() == pcbnew.B_SilkS:
            bobst.append(inflate(box(g), 0.2))
for tr in b.GetTracks():
    if tr.GetClass() == "PCB_VIA":
        bobst.append(inflate(box(tr), 0.2))
report = []
for s, h in cfg["bottom_text"]:
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s); t.SetLayer(pcbnew.B_SilkS)
    t.SetTextSize(VECTOR2I(M(h), M(h))); t.SetTextThickness(M(h * 0.15)); t.SetMirrored(True)
    b.Add(t)
    cxm, ok = (X0 + X1) / 2, False
    ys = [Y0 + 1.5 + k * 0.5 for k in range(int((Y1 - Y0 - 3) / 0.5) + 1)]
    ys.sort(key=lambda yy: abs(yy - (Y0 + Y1) / 2))          # preferir el centro de la placa
    for yy in ys:
        for dx in (0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5, -6, 6, -8, 8):
            t.SetPosition(VECTOR2I(M(cxm + dx), M(yy)))
            rb = box(t)
            if outside(rb, 1.0) or any(hit(rb, o) for o in bobst):
                continue
            bobst.append(inflate(rb, 0.3)); ok = True
            break
        if ok:
            break
    report.append(f"{s} @ {T(t.GetPosition().x) - OX:.1f},{T(t.GetPosition().y) - OY:.1f}" if ok else f"NO CABE: {s}")
    if not ok:
        b.Remove(t)

b.Save(pcb)
print("referencias en F.Fab por falta de espacio:", unplaced or "ninguna")
for line in report:
    print(" ", line)
