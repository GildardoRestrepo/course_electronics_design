"""Router de grilla (A*) para PCBs de 2 o 4 capas con planos internos.

Uso (con el Python de KiCad, con la PCB cerrada en KiCad):
    "/c/Program Files/KiCad/10.0/bin/python.exe" -I pcb_route.py <archivo.kicad_pcb> <config.json>

Pasos:
  1) Fan-out: cada pad SMD de una red de plano (route.plane_nets) baja con un tramo corto a su
     propia vía; los pads pasantes ya tocan los planos internos.
  2) Señales en F.Cu/B.Cu con vías pasantes, red por red (primero route.priority, luego las más
     cortas). Si una red falla, pasa al frente del orden y se repite todo desde la PCB original,
     hasta route.max_attempts veces. Se guarda el mejor intento.

Respeta las pistas ya existentes (rutas hechas a mano: quedan como obstáculo y como parte de su red)
y las zonas de exclusión (rule areas sin pistas/vías). Sección "route" del JSON (valores por defecto):

  {"grid": 0.25, "clearance": 0.2, "edge_clearance": 0.5, "hole_clearance": 0.25, "track": 0.2,
   "fanout_track": 0.3, "via": [0.6, 0.3], "margin": 0.06, "via_cost": 8, "plane_nets": ["GND", "VCC"],
   "priority": ["/XTAL1", ...], "max_attempts": 6}

Verificar siempre después con DRC (`kicad_check.sh`, que rellena zonas).
"""
import heapq, json, math, sys
import pcbnew
from pcbnew import VECTOR2I, FromMM as M, ToMM as T

DEFAULTS = dict(grid=0.25, clearance=0.2, edge_clearance=0.5, hole_clearance=0.25, track=0.2, fanout_track=0.3,
                via=[0.6, 0.3], margin=0.06, via_cost=8.0, layer_cost=[1.0, 1.15], turn_cost=0.3,
                plane_nets=["GND", "VCC"], priority=[], max_attempts=6)
DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]


class Router:
    def __init__(self, pcb, cfg, extra_prio):
        self.c = dict(DEFAULTS, **cfg)
        self.b = pcbnew.LoadBoard(pcb)
        c = self.c
        self.G, self.CLR, self.TW = c["grid"], c["clearance"], c["track"]
        self.VD, self.VDR = c["via"]
        self.MARG = c["margin"]
        bb = self.b.GetBoardEdgesBoundingBox()
        self.X0, self.Y0, self.X1, self.Y1 = T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())
        self.NX = int(round((self.X1 - self.X0) / self.G)) + 1
        self.NY = int(round((self.Y1 - self.Y0) / self.G)) + 1
        self.occ = [[0] * (self.NX * self.NY) for _ in LAYERS]
        self.vocc = [[0] * (self.NX * self.NY) for _ in LAYERS]
        self.prio_list = list(extra_prio) + [p for p in c["priority"] if p not in extra_prio]
        self.nets, self.pads_by_net, self.existing = {}, {}, {}
        self.fails = []
        self._obstacles()

    # ------------------------------------------------------------ grilla
    def cx(self, i): return self.X0 + i * self.G
    def cy(self, j): return self.Y0 + j * self.G
    def idx(self, i, j): return j * self.NX + i
    def xy(self, k): return self.cx(k % self.NX), self.cy(k // self.NX)

    def _set(self, arr, k, net):
        v = arr[k]
        if v == 0:
            arr[k] = net
        elif v != net:
            arr[k] = -1

    def mark(self, arr, dist_fn, box, infl, net):
        l, t, r, btm = box
        G, X0, Y0 = self.G, self.X0, self.Y0
        i0, i1 = max(0, int((l - infl - X0) / G)), min(self.NX - 1, int((r + infl - X0) / G) + 1)
        j0, j1 = max(0, int((t - infl - Y0) / G)), min(self.NY - 1, int((btm + infl - Y0) / G) + 1)
        for j in range(j0, j1 + 1):
            y = self.cy(j)
            for i in range(i0, i1 + 1):
                if dist_fn(self.cx(i), y) <= infl:
                    self._set(arr, self.idx(i, j), net)

    @staticmethod
    def rect_dist(rc):
        l, t, r, btm = rc
        return lambda x, y: math.hypot(max(l - x, 0, x - r), max(t - y, 0, y - btm))

    @staticmethod
    def seg_dist(a, c):
        ax, ay = a; bx, by = c
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        def f(x, y):
            u = 0 if L2 == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
            return math.hypot(x - (ax + u * dx), y - (ay + u * dy))
        return f

    @staticmethod
    def circ_dist(c, r):
        return lambda x, y: max(0.0, math.hypot(x - c[0], y - c[1]) - r)

    # ------------------------------------------------------------ obstáculos
    def _obstacles(self):
        b, CLR, TW, VD, MARG = self.b, self.CLR, self.TW, self.VD, self.MARG
        for fp in b.GetFootprints():
            for p in fp.Pads():
                bx = p.GetBoundingBox()
                rc = (T(bx.GetLeft()), T(bx.GetTop()), T(bx.GetRight()), T(bx.GetBottom()))
                net = p.GetNetCode()
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    c = (T(p.GetPosition().x), T(p.GetPosition().y)); r = T(p.GetDrillSize().x) / 2
                    box = (c[0] - r, c[1] - r, c[0] + r, c[1] + r)
                    for li in range(2):
                        self.mark(self.occ[li], self.circ_dist(c, r), box, self.c["hole_clearance"] + TW / 2 + MARG, -1)
                        self.mark(self.vocc[li], self.circ_dist(c, r), box, self.c["hole_clearance"] + VD / 2 + MARG, -1)
                    continue
                layers = [li for li, Lr in enumerate(LAYERS) if p.IsOnLayer(Lr)]
                key = net if net > 0 else -1
                for li in layers:
                    self.mark(self.occ[li], self.rect_dist(rc), rc, CLR + TW / 2 + MARG, key)
                    self.mark(self.vocc[li], self.rect_dist(rc), rc, CLR + VD / 2 + MARG, key)
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                    for li in range(2):
                        self.mark(self.vocc[li], self.rect_dist(rc), rc, CLR + VD / 2 + MARG, key)
                if net > 0:
                    self.nets[net] = p.GetNetname()
                    self.pads_by_net.setdefault(net, []).append((p, rc, layers, fp.GetReference()))
        # borde
        ec = self.c["edge_clearance"]
        for li in range(2):
            for arr, infl in ((self.occ[li], ec + TW / 2 + MARG), (self.vocc[li], ec + VD / 2 + MARG)):
                for j in range(self.NY):
                    for i in range(self.NX):
                        x, y = self.cx(i), self.cy(j)
                        if min(x - self.X0, self.X1 - x, y - self.Y0, self.Y1 - y) <= infl:
                            arr[self.idx(i, j)] = -1
        # zonas de exclusión
        for z in b.Zones():
            if not z.GetIsRuleArea():
                continue
            o = z.Outline(); zb = z.GetBoundingBox()
            box = (T(zb.GetLeft()), T(zb.GetTop()), T(zb.GetRight()), T(zb.GetBottom()))
            inside = lambda x, y, o=o: 0.0 if o.Contains(VECTOR2I(M(x), M(y))) else 1e9
            for li, Lr in enumerate(LAYERS):
                if z.IsOnLayer(Lr) and z.GetDoNotAllowTracks():
                    self.mark(self.occ[li], inside, box, 0, -1)
                    self.mark(self.occ[li], self.rect_dist(box), box, TW / 2 + MARG, -1)
            if z.GetDoNotAllowVias():
                for li in range(2):
                    self.mark(self.vocc[li], self.rect_dist(box), box, VD / 2 + MARG, -1)
        # pistas y vías existentes (ruteo manual previo)
        for t in b.GetTracks():
            net = t.GetNetCode()
            if t.GetClass() == "PCB_VIA":
                p = (T(t.GetPosition().x), T(t.GetPosition().y))
                self._mark_via(p, T(t.GetWidth(pcbnew.F_Cu)) / 2 if self._via_width_takes_layer() else T(t.GetWidth()) / 2, net)
                k = self.idx(int(round((p[0] - self.X0) / self.G)), int(round((p[1] - self.Y0) / self.G)))
                self.existing.setdefault(net, set()).update({(0, k), (1, k)})
            else:
                if t.GetLayer() not in LAYERS:
                    continue
                li = LAYERS.index(t.GetLayer())
                a = (T(t.GetStart().x), T(t.GetStart().y)); c = (T(t.GetEnd().x), T(t.GetEnd().y))
                self._mark_track(a, c, li, net, T(t.GetWidth()))
                n_ = max(1, int(math.hypot(c[0] - a[0], c[1] - a[1]) / self.G))
                cells = {(li, self.idx(int(round((a[0] + (c[0] - a[0]) * s / n_ - self.X0) / self.G)),
                                       int(round((a[1] + (c[1] - a[1]) * s / n_ - self.Y0) / self.G)))) for s in range(n_ + 1)}
                self.existing.setdefault(net, set()).update(cells)

    def _via_width_takes_layer(self):
        try:
            pcbnew.PCB_VIA(self.b).GetWidth(pcbnew.F_Cu)
            return True
        except TypeError:
            return False

    # ------------------------------------------------------------ cobre nuevo
    def _mark_track(self, a, c, li, net, w):
        box = (min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1]))
        self.mark(self.occ[li], self.seg_dist(a, c), box, w / 2 + self.CLR + self.TW / 2 + self.MARG, net)
        self.mark(self.vocc[li], self.seg_dist(a, c), box, w / 2 + self.CLR + self.VD / 2 + self.MARG, net)

    def _mark_via(self, p, r, net):
        box = (p[0] - r, p[1] - r, p[0] + r, p[1] + r)
        for li in range(2):
            self.mark(self.occ[li], self.circ_dist(p, r), box, self.CLR + self.TW / 2 + self.MARG, net)
            self.mark(self.vocc[li], self.circ_dist(p, r), box, max(self.CLR, 0.25) + self.VD / 2 + self.MARG, net)

    def add_track(self, a, c, li, net, w):
        t = pcbnew.PCB_TRACK(self.b)
        t.SetStart(VECTOR2I(M(a[0]), M(a[1]))); t.SetEnd(VECTOR2I(M(c[0]), M(c[1])))
        t.SetWidth(M(w)); t.SetLayer(LAYERS[li]); t.SetNetCode(net)
        self.b.Add(t)
        self._mark_track(a, c, li, net, w)

    def add_via(self, p, net):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(VECTOR2I(M(p[0]), M(p[1])))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        try:
            v.SetWidth(M(self.VD))
        except TypeError:
            v.SetWidth(pcbnew.F_Cu, M(self.VD))
        v.SetDrill(M(self.VDR)); v.SetNetCode(net)
        self.b.Add(v)
        self._mark_via(p, self.VD / 2, net)

    # ------------------------------------------------------------ búsqueda
    def ok(self, li, k, net):
        v = self.occ[li][k]
        return v == 0 or v == net

    def via_ok(self, k, net):
        return all(self.vocc[li][k] in (0, net) and self.occ[li][k] in (0, net) for li in range(2))

    def astar(self, starts, goal_fn, net, layers=(0, 1), heur=None, max_exp=400000):
        NX, NY = self.NX, self.NY
        lc, turn, vc = self.c["layer_cost"], self.c["turn_cost"], self.c["via_cost"]
        pq, best, prev = [], {}, {}
        start_set = set(starts)
        for s in starts:
            best[(s, None)] = 0.0; prev[(s, None)] = None
            heapq.heappush(pq, (0.0, 0.0, s, (9, 9)))
            best[(s, (9, 9))] = 0.0; prev[(s, (9, 9))] = None
        exp = 0
        while pq:
            f, g, s, d = heapq.heappop(pq)
            if best.get((s, d), 1e18) < g - 1e-9:
                continue
            li, k = s
            if s not in start_set and goal_fn(li, k):
                path, node = [], (s, d)
                while node is not None:
                    path.append(node[0]); node = prev[node]
                return path[::-1]
            exp += 1
            if exp > max_exp:
                return None
            i, j = k % NX, k // NX
            for di, dj, cst in DIRS:
                ni, nj = i + di, j + dj
                if not (0 <= ni < NX and 0 <= nj < NY):
                    continue
                nk = nj * NX + ni
                if not self.ok(li, nk, net):
                    continue
                if di and dj and not (self.ok(li, j * NX + i + di, net) or self.ok(li, (j + dj) * NX + i, net)):
                    continue
                ng = g + cst * lc[li] + (turn if d not in ((9, 9), (0, 0)) and d != (di, dj) else 0)
                ns, nd = (li, nk), (di, dj)
                if ng < best.get((ns, nd), 1e18):
                    best[(ns, nd)] = ng; prev[(ns, nd)] = (s, d)
                    heapq.heappush(pq, (ng + (heur(ni, nj) if heur else 0), ng, ns, nd))
            if len(layers) == 2 and self.via_ok(k, net):
                ns, ng = (1 - li, k), g + vc
                if ng < best.get((ns, (0, 0)), 1e18):
                    best[(ns, (0, 0))] = ng; prev[(ns, (0, 0))] = (s, d)
                    heapq.heappush(pq, (ng + (heur(i, j) if heur else 0), ng, ns, (0, 0)))
        return None

    def pad_cells(self, rc, layers, net, pad, shrink=0.08):
        l, t, r, btm = rc
        out = []
        for j in range(max(0, int((t - self.Y0) / self.G)), min(self.NY - 1, int((btm - self.Y0) / self.G) + 1) + 1):
            for i in range(max(0, int((l - self.X0) / self.G)), min(self.NX - 1, int((r - self.X0) / self.G) + 1) + 1):
                x, y = self.cx(i), self.cy(j)
                if not (l + shrink <= x <= r - shrink and t + shrink <= y <= btm - shrink):
                    continue
                if not all(pad.HitTest(VECTOR2I(M(x + dx), M(y + dy))) for dx, dy in
                           ((0, 0), (shrink, 0), (-shrink, 0), (0, shrink), (0, -shrink))):
                    continue
                for li in layers:
                    if self.ok(li, self.idx(i, j), net):
                        out.append((li, self.idx(i, j)))
        return out

    def commit(self, path, net, w):
        run = [path[0]]
        for a, c in zip(path, path[1:]):
            if a[0] != c[0]:
                self._flush(run, net, w)
                self.add_via(self.xy(a[1]), net)
                run = [c]
            else:
                run.append(c)
        self._flush(run, net, w)
        # Si la ruta empieza o termina en medio de un tramo existente (unión en T), partir ese tramo:
        # KiCad solo reconoce como unión los extremos de pista.
        for li, k in (path[0], path[-1]):
            px, py = self.xy(k)
            P = VECTOR2I(M(px), M(py))
            for t in list(self.b.GetTracks()):
                if t.GetClass() != "PCB_TRACK" or t.GetNetCode() != net or t.GetLayer() != LAYERS[li]:
                    continue
                s, e = VECTOR2I(t.GetStart()), VECTOR2I(t.GetEnd())   # copias: GetEnd() es una referencia
                if (s - P).EuclideanNorm() < M(0.01) or (e - P).EuclideanNorm() < M(0.01):
                    continue
                if self.seg_dist((T(s.x), T(s.y)), (T(e.x), T(e.y)))(px, py) < 0.01:
                    t.SetEnd(P)
                    nt = pcbnew.PCB_TRACK(self.b)
                    nt.SetStart(P); nt.SetEnd(e); nt.SetWidth(t.GetWidth()); nt.SetLayer(t.GetLayer())
                    nt.SetNetCode(net)
                    self.b.Add(nt)
                    break

    def _flush(self, run, net, w):
        if len(run) < 2:
            return
        li = run[0][0]
        pts = [self.xy(k) for _, k in run]
        seg_start = pts[0]
        for a, c, d in zip(pts, pts[1:], pts[2:] + [None]):
            if d is None or (round(c[0] - a[0], 4), round(c[1] - a[1], 4)) != (round(d[0] - c[0], 4), round(d[1] - c[1], 4)):
                self.add_track(seg_start, c, li, net, w)
                seg_start = c

    # ------------------------------------------------------------ flujo
    def run(self):
        planes = set(self.c["plane_nets"])
        for net, plist in sorted(self.pads_by_net.items()):
            if self.nets[net] not in planes:
                continue
            for p, rc, layers, ref in plist:
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                    continue
                if any((0, k) in self.existing.get(net, ()) for _, k in self.pad_cells(rc, [0], net, p)):
                    continue                      # ya tiene conexión hecha a mano
                starts = self.pad_cells(rc, [0], net, p)
                goal = lambda li, k, net=net: self.via_ok(k, net)
                path = self.astar(starts, goal, net, layers=(0,), max_exp=20000) if starts else None
                if not path:
                    self.fails.append(f"fanout {ref}.{p.GetNumber()} {self.nets[net]}"); continue
                self.commit(path, net, self.c["fanout_track"])
                self.add_via(self.xy(path[-1][1]), net)

        sig = [n for n in self.pads_by_net if self.nets[n] not in planes and len(self.pads_by_net[n]) > 1]
        rank = {name: k for k, name in enumerate(self.prio_list)}

        def hpwl(n):
            xs = [(rc[0] + rc[2]) / 2 for _, rc, _, _ in self.pads_by_net[n]]
            ys = [(rc[1] + rc[3]) / 2 for _, rc, _, _ in self.pads_by_net[n]]
            return (max(xs) - min(xs)) + (max(ys) - min(ys))
        sig.sort(key=lambda n: (rank.get(self.nets[n], len(rank)), hpwl(n)))

        for net in sig:
            plist = self.pads_by_net[net][:]
            tree = set(self.pad_cells(plist[0][1], plist[0][2], net, plist[0][0])) | self.existing.get(net, set())
            done = [plist.pop(0)]
            while plist:
                def dist_to_done(e):
                    ex, ey = (e[1][0] + e[1][2]) / 2, (e[1][1] + e[1][3]) / 2
                    return min(math.hypot(ex - (d[1][0] + d[1][2]) / 2, ey - (d[1][1] + d[1][3]) / 2) for d in done)
                plist.sort(key=dist_to_done)
                p, rc, layers, ref = plist.pop(0)
                starts = self.pad_cells(rc, layers, net, p)
                if set(starts) & tree:
                    tree |= set(starts); done.append((p, rc, layers, ref)); continue
                txs = [(k % self.NX, k // self.NX) for _, k in tree]
                step = max(1, len(txs) // 40)
                heur = lambda i, j, txs=txs, step=step: min(math.hypot(i - a, j - c) for a, c in txs[::step]) * 0.9
                path = self.astar(starts, lambda li, k, tree=tree: (li, k) in tree, net, heur=heur) if starts else None
                if not path:
                    self.fails.append(f"{self.nets[net]}: {ref}.{p.GetNumber()}")
                    continue
                self.commit(path, net, self.TW)
                cells = set(path)
                tree |= cells | set(starts) | {(1 - li, k) for li, k in cells if (1 - li, k) in cells}
                done.append((p, rc, layers, ref))
        return self.fails

    def prune(self):
        """Quita tramos con un extremo libre (restos de la discretización). Devuelve cuántos quitó."""
        removed = 0
        while True:
            tracks = [t for t in self.b.GetTracks() if t.GetClass() == "PCB_TRACK"]
            vias = [t for t in self.b.GetTracks() if t.GetClass() == "PCB_VIA"]
            pads = [p for fp in self.b.GetFootprints() for p in fp.Pads()]
            dead = []
            for t in tracks:
                net, layer, w = t.GetNetCode(), t.GetLayer(), t.GetWidth()
                for end in (t.GetStart(), t.GetEnd()):
                    if any(p.GetNetCode() == net and p.IsOnLayer(layer) and p.HitTest(end) for p in pads):
                        continue
                    if any(v.GetNetCode() == net and (v.GetPosition() - end).EuclideanNorm() <= w for v in vias):
                        continue
                    if any(o is not t and o.GetNetCode() == net and o.GetLayer() == layer and o.HitTest(end, w // 2)
                           for o in tracks):
                        continue
                    dead.append(t)
                    break
            if not dead:
                return removed
            for t in dead:
                self.b.Remove(t)
            removed += len(dead)


def main():
    pcb, cfg_path = sys.argv[1], sys.argv[2]
    cfg = json.load(open(cfg_path, encoding="utf-8")).get("route", {})
    max_att = cfg.get("max_attempts", DEFAULTS["max_attempts"])
    extra, best = [], None
    for att in range(1, max_att + 1):
        r = Router(pcb, cfg, extra)
        fails = r.run()
        print(f"intento {att}: {len(fails)} fallos {fails if fails else ''}")
        if best is None or len(fails) < len(best[1]):
            best = (r, fails)
        if not fails:
            break
        failed_nets = [f.split(":")[0] for f in fails if not f.startswith("fanout")]
        new = [n for n in failed_nets if n not in extra]
        if not new:
            break                                   # ya estaban al frente: hace falta cambiar la colocación
        extra = new + extra
    r, fails = best
    pruned = r.prune()
    if pruned:
        print(f"tramos colgantes eliminados: {pruned}")
    pcbnew.ZONE_FILLER(r.b).Fill(r.b.Zones())
    r.b.Save(pcb)
    nt = sum(1 for t in r.b.GetTracks() if t.GetClass() == "PCB_TRACK")
    nv = sum(1 for t in r.b.GetTracks() if t.GetClass() == "PCB_VIA")
    print(f"guardado: {nt} pistas, {nv} vías; fallos: {fails or 'ninguno'}")
    if fails:
        print("Sugerencia: abrir espacio en la colocación alrededor de los pads que fallan y repetir.")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
