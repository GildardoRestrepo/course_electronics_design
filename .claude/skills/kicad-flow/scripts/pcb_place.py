"""Contorno, colocación, planos y zonas de exclusión de una PCB según un JSON de configuración.

Uso (con el Python de KiCad, con la PCB cerrada en KiCad):
    "/c/Program Files/KiCad/10.0/bin/python.exe" -I pcb_place.py <archivo.kicad_pcb> <config.json>

Es idempotente: reemplaza contorno, planos y zonas de exclusión cada vez. Secciones del JSON
(coordenadas en mm, relativas a la esquina superior izquierda de la placa):

  "board":   {"origin": [100, 100], "size": [50, 30], "edge_width": 0.1}
  "place":   {"U1": [x, y, rotación, ancla], ...}
             ancla: "c" = centro de la huella, "1" = pad 1, "edge" = borde izquierdo del courtyard en x
  "planes":  [{"layer": "In1.Cu", "net": "GND"}, {"layer": "In2.Cu", "net": "+3V3"}]
  "plane":   {"clearance": 0.25, "min_thickness": 0.25, "thermal_gap": 0.3, "spoke": 0.4}
  "keepouts":[{"name": "Antena", "rect": [x, y, ancho, alto], "layers": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]}]
             (zona de exclusión: sin pistas, vías, pads, rellenos ni huellas; p. ej. bajo la antena de un ESP32)

Además deja sin red los pads de pines no conectados (`unconnected-*`), como espera la paridad de KiCad 10.
"""
import json, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM as M

PCB, CFG = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8"))
X0, Y0 = CFG["board"]["origin"]
W, H = CFG["board"]["size"]
b = pcbnew.LoadBoard(PCB)
def L(name):
    lid = b.GetLayerID(name)
    if lid < 0:
        raise SystemExit(f"Capa desconocida: {name}")
    return lid

# 1) pads de pines sin conexión: sin red
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname().startswith("unconnected-"):
            p.SetNetCode(0)

# 2) colocación
missing = []
for fp in b.GetFootprints():
    ref = fp.GetReference()
    if ref not in CFG["place"]:
        missing.append(ref); continue
    x, y, rot, anc = CFG["place"][ref]
    fp.SetOrientationDegrees(rot)
    pos = fp.GetPosition()
    tx, ty = M(X0 + x), M(Y0 + y)
    if anc == "c":
        fp.SetPosition(VECTOR2I(tx, ty))
    elif anc == "1":
        p1 = [p for p in fp.Pads() if p.GetNumber() == "1"][0].GetPosition()
        fp.SetPosition(VECTOR2I(tx + pos.x - p1.x, ty + pos.y - p1.y))
    elif anc == "edge":
        cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        fp.SetPosition(VECTOR2I(tx + pos.x - cy.GetLeft(), ty + pos.y - cy.Centre().y))
    else:
        raise SystemExit(f"{ref}: ancla desconocida {anc}")

# 3) contorno rectangular
for d in list(b.GetDrawings()):
    if d.GetLayer() == pcbnew.Edge_Cuts:
        b.Remove(d)
r = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_RECT)
r.SetStart(VECTOR2I(M(X0), M(Y0))); r.SetEnd(VECTOR2I(M(X0 + W), M(Y0 + H)))
r.SetLayer(pcbnew.Edge_Cuts); r.SetWidth(M(CFG["board"].get("edge_width", 0.1)))
b.Add(r)

# 4) planos y zonas de exclusión (se rehacen siempre)
for z in list(b.Zones()):
    b.Remove(z)


def outline(z, pts):
    o = z.Outline(); o.NewOutline()
    for px, py in pts:
        o.Append(M(px), M(py))


pc = {"clearance": 0.25, "min_thickness": 0.25, "thermal_gap": 0.3, "spoke": 0.4, **CFG.get("plane", {})}
for pl in CFG.get("planes", []):
    z = pcbnew.ZONE(b)
    z.SetLayer(L(pl["layer"]))
    net = b.FindNet(pl["net"])
    if net is None:
        raise SystemExit(f"La red {pl['net']} no existe en la PCB")
    z.SetNetCode(net.GetNetCode())
    outline(z, [(X0, Y0), (X0 + W, Y0), (X0 + W, Y0 + H), (X0, Y0 + H)])
    z.SetAssignedPriority(pl.get("priority", 0))
    z.SetMinThickness(M(pc["min_thickness"])); z.SetLocalClearance(M(pc["clearance"]))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(M(pc["thermal_gap"])); z.SetThermalReliefSpokeWidth(M(pc["spoke"]))
    z.SetZoneName(f"{pl['net']}_{pl['layer']}")
    b.Add(z)

for ko in CFG.get("keepouts", []):
    x, y, w, h = ko["rect"]
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    ls = pcbnew.LSET()
    for ln in ko.get("layers", ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]):
        ls.AddLayer(L(ln))
    z.SetLayerSet(ls)
    outline(z, [(X0 + x, Y0 + y), (X0 + x + w, Y0 + y), (X0 + x + w, Y0 + y + h), (X0 + x, Y0 + y + h)])
    # Por defecto prohíbe pistas, vías, pads y rellenos, pero NO huellas: el courtyard de un módulo
    # ESP32 cubre su propia antena. Se puede cambiar con "footprints": true, "tracks": false, etc.
    for f in ("SetDoNotAllowTracks", "SetDoNotAllowVias", "SetDoNotAllowPads", "SetDoNotAllowZoneFills",
              "SetDoNotAllowFootprints"):
        key = f[13:].lower()
        getattr(z, f)(ko.get(key, key != "footprints"))
    z.SetZoneName(ko.get("name", "Keepout"))
    b.Add(z)
    kb = (M(X0 + x), M(Y0 + y), M(X0 + x + w), M(Y0 + y + h))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            pp = p.GetPosition()
            if kb[0] <= pp.x <= kb[2] and kb[1] <= pp.y <= kb[3] and any(p.IsOnLayer(L(ln)) for ln in ko.get("layers", ["F.Cu", "B.Cu"])):
                print(f"AVISO: el pad {fp.GetReference()}.{p.GetNumber()} cae dentro de la zona '{ko.get('name', 'Keepout')}'")

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(PCB)
print("OK; sin posición en el JSON:", missing or "ninguna")
