"""Generador de esquemáticos KiCad 10 por código (jerárquicos, con ERC limpio).

Cada pin se conecta con un tramo de cable de 2.54 mm terminado en etiqueta local, etiqueta
jerárquica, símbolo de alimentación o marca de no-conexión. Así la conectividad no depende de
dibujar cables a mano y el ERC sale limpio. Pines contiguos de la misma red de alimentación se
agrupan bajo un solo símbolo para que los textos no se encimen.

Uso típico (ver 10_4layer_design/4layer_kicad/scripts/gen_datalogger.py):

    from kicad_sch_gen import Design
    d = Design("mi_proyecto", power_nets=("+3V3", "GND"), title_block={...})
    d.add_lib("mi_lib", TEXTO_KICAD_SYM)                 # símbolos propios (opcional)
    root = d.root("A3", title="...")
    root.part("Device:R", "R1", "10k", 100, 50, {"1": "+3V3", "2": "EN"}, fp="Resistor_SMD:R_0805_2012Metric")
    con = d.subsheet(root, "Connectors", "connectors.kicad_sch", ["+3V3", "TX", "RX", "GND"], at=(300, 200))
    con.part("Connector:Conn_01x03_Pin", "J1", "UART", 50, 50, {"1": "TX", "2": "RX", "3": "GND"}, fp=..., hier=True)
    d.write("carpeta_proyecto", template_pro="otro.kicad_pro", netclasses=..., rules=...)

Coordenadas en mm (el origen de cada símbolo se ajusta a la grilla de 1.27 mm). En `conns`:
red = etiqueta local; red de `power_nets` = símbolo `power:<red>`; "NC" = no-conexión;
"PWR_FLAG" = bandera de alimentación. Con `hier=True` todas las redes (incluidas las de
alimentación) salen como etiquetas jerárquicas.
"""
import json, math, os, sys, uuid as _uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kicad_sexpr import Q, parse, dump, flat_symbol, pins  # noqa: E402

STUB = 2.54
SCH_VERSION = "20260306"


def G(v):
    """Ajusta a la grilla de 1.27 mm."""
    return round(round(v / 1.27) * 1.27, 4)


def U():
    return Q(str(_uuid.uuid4()))


def n(v):
    v = round(v, 4)
    return str(int(v)) if v == int(v) else f"{v:g}"


def font(just=None):
    e = ["effects", ["font", ["size", "1.27", "1.27"]]]
    if just:
        e.append(["justify"] + just.split())
    return e


def is_ground(net):
    return net.upper().startswith("GND") or net.upper() in ("VSS", "0V")


class Design:
    def __init__(self, project, power_nets=("VCC", "GND"), title_block=None):
        self.project = project
        self.power_nets = set(power_nets)
        self.title_block = title_block or {}
        self.root_uuid = str(_uuid.uuid4())
        self.custom_src = {}
        self.custom = {}
        self.sheets = []          # (Sheet, archivo, nombre)
        self.cnt = {"pwr": 0, "flg": 0}

    # ------------------------------------------------------------ bibliotecas
    def add_lib(self, name, text, descr="Símbolos propios"):
        self.custom_src[name] = (text, descr)
        self.custom[name] = parse(text)

    def symdef(self, lib_id):
        libname, name = lib_id.split(":")
        return flat_symbol(libname, name, self.custom.get(libname))

    # ------------------------------------------------------------ hojas
    def root(self, paper="A4", title=None):
        sh = Sheet(self, "/" + self.root_uuid, paper, title, self.root_uuid)
        self.sheets.append((sh, f"{self.project}.kicad_sch", "Raíz"))
        return sh

    def subsheet(self, parent, name, file, pins_, at, width=35.56, paper="A4", title=None):
        """Crea el símbolo de hoja en `parent` (pines por el borde izquierdo, con tramo + etiqueta o
        símbolo de alimentación) y devuelve la hoja hija. El primer pin de alimentación conviene
        ponerlo arriba y la tierra abajo: así sus símbolos no chocan con las etiquetas."""
        su = str(_uuid.uuid4())
        sx, sy = G(at[0]), G(at[1])
        h = 2.54 * (len(pins_) + 1)
        sheet = ["sheet", ["at", n(sx), n(sy)], ["size", n(width), n(h)], ["exclude_from_sim", "no"],
                 ["in_bom", "yes"], ["on_board", "yes"], ["dnp", "no"], ["fields_autoplaced", "yes"],
                 ["stroke", ["width", "0.1524"], ["type", "solid"]], ["fill", ["color", "0", "0", "0", "0.0000"]],
                 ["uuid", Q(su)],
                 ["property", Q("Sheetname"), Q(name), ["at", n(sx), n(sy - 0.7116), "0"], font("left bottom")],
                 ["property", Q("Sheetfile"), Q(file), ["at", n(sx), n(sy + h + 0.5884), "0"], font("left top")]]
        last = len(pins_) - 1
        for i, s in enumerate(pins_):
            py = sy + 2.54 * (i + 1)
            sheet.append(["pin", Q(s), "bidirectional", ["at", n(sx), n(py), "180"], ["uuid", U()], font("left")])
            e = (sx - STUB, py)
            parent.wire((sx, py), e)
            if s in self.power_nets:
                d = (0, 1) if is_ground(s) else (0, -1)
                if (d == (0, 1) and i != last) or (d == (0, -1) and i != 0):
                    d = (-1, 0)
                parent.power(s, e, d)
            else:
                parent.label(s, e, (-1, 0))
        page = str(len(self.sheets) + 1)
        sheet.append(["instances", ["project", Q(self.project), ["path", Q(parent.path), ["page", Q(page)]]]])
        parent.items.append(sheet)
        child = Sheet(self, f"{parent.path}/{su}", paper, title, str(_uuid.uuid4()))
        self.sheets.append((child, file, name))
        child.sheet_uuid = su
        return child

    # ------------------------------------------------------------ escritura
    def write(self, out, template_pro=None, netclasses=None, patterns=None, rules=None):
        os.makedirs(out, exist_ok=True)
        for i, (sh, file, _) in enumerate(self.sheets):
            tail = [["sheet_instances", ["path", Q("/"), ["page", Q("1")]]]] if i == 0 else None
            with open(os.path.join(out, file), "w", encoding="utf-8", newline="\n") as f:
                f.write(sh.render(tail))
        if self.custom_src:
            rows = []
            for name, (text, descr) in self.custom_src.items():
                with open(os.path.join(out, f"{name}.kicad_sym"), "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
                rows.append(f'\t(lib (name "{name}")(type "KiCad")(uri "${{KIPRJMOD}}/{name}.kicad_sym")(options "")(descr "{descr}"))')
            with open(os.path.join(out, "sym-lib-table"), "w", encoding="utf-8", newline="\n") as f:
                f.write("(sym_lib_table\n\t(version 7)\n" + "\n".join(rows) + "\n)\n")
        pro = json.load(open(template_pro, encoding="utf-8")) if template_pro else {}
        pro.setdefault("meta", {})["filename"] = f"{self.project}.kicad_pro"
        pro["meta"].setdefault("version", 3)
        pro["sheets"] = [[self.root_uuid if i == 0 else sh.sheet_uuid, nm] for i, (sh, _, nm) in enumerate(self.sheets)]
        pro["boards"] = []
        if netclasses:
            ns = pro.setdefault("net_settings", {"meta": {"version": 5}})
            base = (ns.get("classes") or [{}])[0]
            ns["classes"] = [dict(base, **c) for c in netclasses]
            ns["netclass_patterns"] = [{"netclass": c, "pattern": p} for p, c in (patterns or {}).items()]
        if rules:
            pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {}).update(rules)
        with open(os.path.join(out, f"{self.project}.kicad_pro"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(pro, f, indent=2, ensure_ascii=False)


class Sheet:
    def __init__(self, design, path, paper, title, uuid):
        self.d = design
        self.path = path
        self.paper = paper
        self.title = title
        self.uuid = uuid
        self.items = []
        self.libs = {}

    def lib(self, lib_id):
        if lib_id not in self.libs:
            self.libs[lib_id] = self.d.symdef(lib_id)
        return self.libs[lib_id]

    # ------------------------------------------------------------ primitivas
    def wire(self, a, b):
        self.items.append(["wire", ["pts", ["xy", n(a[0]), n(a[1])], ["xy", n(b[0]), n(b[1])]],
                           ["stroke", ["width", "0"], ["type", "default"]], ["uuid", U()]])

    def label(self, name, p, d, hier=False):
        ang = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[d]
        if hier:
            just = "left" if ang in (0, 90) else "right"
            self.items.append(["hierarchical_label", Q(name), ["shape", "bidirectional"],
                               ["at", n(p[0]), n(p[1]), str(ang)], font(just), ["uuid", U()]])
        else:
            just = "left bottom" if ang in (0, 90) else "right bottom"
            self.items.append(["label", Q(name), ["at", n(p[0]), n(p[1]), str(ang)], font(just), ["uuid", U()]])

    def junction(self, p):
        self.items.append(["junction", ["at", n(p[0]), n(p[1])], ["diameter", "0"], ["color", "0", "0", "0", "0"],
                           ["uuid", U()]])

    def nc(self, p):
        self.items.append(["no_connect", ["at", n(p[0]), n(p[1])], ["uuid", U()]])

    def text(self, s, x, y, size=1.8, bold=True):
        f = ["font", ["size", str(size), str(size)]] + ([["bold", "yes"]] if bold else [])
        self.items.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", n(x), n(y), "0"],
                           ["effects", f, ["justify", "left", "bottom"]], ["uuid", U()]])

    def rect(self, x1, y1, x2, y2, title=None):
        """Recuadro punteado de bloque, con título opcional arriba a la izquierda."""
        self.items.append(["rectangle", ["start", n(x1), n(y1)], ["end", n(x2), n(y2)],
                           ["stroke", ["width", "0"], ["type", "dash"]], ["fill", ["type", "none"]], ["uuid", U()]])
        if title:
            self.text(title, x1 + 1, y1 - 1)

    def symbol(self, lib_id, ref, value, x, y, rot=0, fp="", props_at=None, hide_ref=False, in_bom=True):
        s = self.lib(lib_id)
        sym = ["symbol", ["lib_id", Q(lib_id)], ["at", n(x), n(y), str(rot)], ["unit", "1"], ["body_style", "1"],
               ["exclude_from_sim", "no"], ["in_bom", "yes" if in_bom else "no"], ["on_board", "yes"],
               ["in_pos_files", "yes" if in_bom else "no"], ["dnp", "no"], ["fields_autoplaced", "no"], ["uuid", U()]]
        libprops = {p[1]: p for p in s if isinstance(p, list) and p[0] == "property"}
        (rx, ry, rj), (vx, vy, vj) = props_at or ((x + 2.54, y - 1.27, "left"), (x + 2.54, y + 1.27, "left"))
        vals = {"Reference": ref, "Value": value, "Footprint": fp or libprops["Footprint"][2],
                "Datasheet": libprops["Datasheet"][2], "Description": libprops["Description"][2]}
        for k, v in vals.items():
            if k == "Reference":
                at, just, hide = (rx, ry), rj, hide_ref
            elif k == "Value":
                at, just, hide = (vx, vy), vj, False
            else:
                at, just, hide = (x, y), None, True
            p = ["property", Q(k), Q(v), ["at", n(at[0]), n(at[1]), "0"]]
            if hide:
                p.append(["hide", "yes"])
            p += [["show_name", "no"], ["do_not_autoplace", "no"], font(just)]
            sym.append(p)
        for pn in pins(s):
            sym.append(["pin", Q(pn["num"]), ["uuid", U()]])
        sym.append(["instances", ["project", Q(self.d.project), ["path", Q(self.path), ["reference", Q(ref)], ["unit", "1"]]]])
        self.items.append(sym)
        return s

    def power(self, net, p, d):
        """Símbolo de alimentación (o PWR_FLAG) con el pin en p, dibujado hacia la dirección d."""
        up = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}
        down = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}
        if net == "PWR_FLAG":
            self.d.cnt["flg"] += 1
            ref, lib_id, rot = f"#FLG{self.d.cnt['flg']:02d}", "power:PWR_FLAG", up[d]
        else:
            self.d.cnt["pwr"] += 1
            ref, lib_id = f"#PWR{self.d.cnt['pwr']:02d}", f"power:{net}"
            rot = down[d] if is_ground(net) else up[d]
        vx, vy = p[0] + d[0] * 5.08, p[1] + d[1] * 5.08 - (1.27 if d[1] == 0 else 0)
        self.symbol(lib_id, ref, net, p[0], p[1], rot, props_at=((p[0], p[1], None), (vx, vy, None)), hide_ref=True)

    # ------------------------------------------------------------ componente con conexiones
    def part(self, lib_id, ref, value, x, y, conns, fp="", props="auto", hier=False, in_bom=True):
        """Coloca el símbolo (sin rotar) y conecta cada pin según conns {num_pin: red}."""
        x, y = G(x), G(y)
        s = self.lib(lib_id)
        ps = pins(s)
        xs = [x + p["x"] for p in ps] or [x]
        ys = [y - p["y"] for p in ps] or [y]
        if props == "auto":
            if len(ps) == 2 and ps[0]["x"] == ps[1]["x"]:           # pasivo vertical
                props = ((x + 2.54, y - 1.27, "left"), (x + 2.54, y + 1.27, "left"))
            elif len(ps) == 2:                                       # pasivo horizontal
                props = ((x, y - 3.81, None), (x, y + 3.81, None))
            elif not ps:
                props = ((x + 2.54, y - 1.27, "left"), (x + 2.54, y + 1.27, "left"))
            else:
                props = ((min(xs) + 2.54, min(ys) - 1.27, "left"), (min(xs) + 2.54, max(ys) + 2.54, "left"))
        self.symbol(lib_id, ref, value, x, y, fp=fp, props_at=props, hide_ref=ref.startswith("#"), in_bom=in_bom)
        seen, pwr, side = set(), [], {}
        for p in ps:
            px, py = x + p["x"], y - p["y"]
            key = (round(px, 3), round(py, 3))
            if key in seen:                      # pines apilados (p. ej. varios GND ocultos)
                continue
            seen.add(key)
            net = conns.get(p["num"])
            if net is None:
                raise SystemExit(f"{ref} pin {p['num']} ({p['name']}) sin conexión definida")
            a = math.radians(p["ang"])
            d = (round(-math.cos(a)), round(math.sin(a)))
            if net == "NC":
                self.nc((px, py))
                continue
            e = (round(px + d[0] * STUB, 4), round(py + d[1] * STUB, 4))
            side.setdefault(d, []).append(e)
            self.wire((px, py), e)
            if (net in self.d.power_nets or net == "PWR_FLAG") and not hier:
                pwr.append((net, d, e))
            else:
                self.label(net, e, d, hier=hier)
        # pines contiguos de la misma red de alimentación -> un solo símbolo
        groups = []
        for net, d, e in sorted(pwr, key=lambda t: (t[0], t[1], t[2][1], t[2][0])):
            along = 1 if d[1] == 0 else 0
            g = groups[-1] if groups else None
            if (g and g["net"] == net and g["d"] == d and abs(g["pts"][-1][1 - along] - e[1 - along]) < 1e-3
                    and abs(e[along] - g["pts"][-1][along] - 2.54) < 1e-3):
                g["pts"].append(e)
            else:
                groups.append(dict(net=net, d=d, pts=[e]))
        for g in groups:
            pts, d, net = g["pts"], g["d"], g["net"]
            for a_, b_ in zip(pts, pts[1:]):
                self.wire(a_, b_)
            for j in pts[1:-1]:
                self.junction(j)
            if d[1] == 0 and net != "PWR_FLAG":       # pin lateral: símbolo vertical si es el extremo del lado
                ys_side = [q[1] for q in side[d]]
                if not is_ground(net) and pts[0][1] <= min(ys_side) + 1e-3:
                    self.power(net, pts[0], (0, -1)); continue
                if is_ground(net) and pts[-1][1] >= max(ys_side) - 1e-3:
                    self.power(net, pts[-1], (0, 1)); continue
            self.power(net, pts[0], d)

    def two(self, lib_id, ref, value, x, y, a, b, fp=""):
        """Atajo para pasivos de dos pines: pin 1 -> a, pin 2 -> b."""
        self.part(lib_id, ref, value, x, y, {"1": a, "2": b}, fp=fp)

    # ------------------------------------------------------------ salida
    def render(self, tail=None):
        root = ["kicad_sch", ["version", SCH_VERSION], ["generator", Q("eeschema")], ["generator_version", Q("10.0")],
                ["uuid", Q(self.uuid)], ["paper", Q(self.paper)]]
        tb = dict(self.d.title_block)
        if self.title or tb:
            blk = ["title_block"]
            if self.title:
                blk.append(["title", Q(self.title)])
            for k in ("date", "rev", "company"):
                if k in tb:
                    blk.append([k, Q(tb[k])])
            for i, c in enumerate(tb.get("comments", []), 1):
                blk.append(["comment", str(i), Q(c)])
            root.append(blk)
        root.append(["lib_symbols"] + list(self.libs.values()))
        root += self.items
        if tail:
            root += tail
        root.append(["embedded_fonts", "no"])
        return dump(root) + "\n"
