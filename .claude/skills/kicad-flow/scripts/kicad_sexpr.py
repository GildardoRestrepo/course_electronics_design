"""Parser y escritor mínimo de S-expressions de KiCad 10, y extracción de símbolos de biblioteca.

Uso como módulo (lo importan kicad_sch_gen.py y los generadores de cada proyecto):
    from kicad_sexpr import Q, parse, dump, flat_symbol, pins
"""
import copy, os, re

LIBDIR = os.environ.get("KICAD_SYMBOL_DIR", "C:/Program Files/KiCad/10.0/share/kicad/symbols")


class Q(str):
    """Cadena entre comillas."""


def parse(text):
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()"]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            x = stack.pop()
            stack[-1].append(x)
        elif t.startswith('"'):
            stack[-1].append(Q(t[1:-1].replace('\\"', '"').replace("\\\\", "\\")))
        else:
            stack[-1].append(t)
    return stack[0][0]


def _atom(a):
    if isinstance(a, Q):
        return '"' + a.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return str(a)


def dump(node, ind=0):
    if not isinstance(node, list):
        return _atom(node)
    simple = all(not isinstance(c, list) for c in node)
    if simple:
        return "(" + " ".join(_atom(c) for c in node) + ")"
    tab = "\t" * ind
    out = "("
    first = True
    for c in node:
        if isinstance(c, list):
            out += "\n" + tab + "\t" + dump(c, ind + 1)
        else:
            out += ("" if first else " ") + _atom(c)
        first = False
    return out + "\n" + tab + ")"


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None


_libcache = {}


def lib(libname):
    if libname not in _libcache:
        with open(f"{LIBDIR}/{libname}.kicad_sym", encoding="utf-8") as f:
            _libcache[libname] = parse(f.read())
    return _libcache[libname]


def raw_symbol(libtree, name):
    for s in find(libtree, "symbol"):
        if s[1] == name:
            return s
    raise KeyError(name)


def flat_symbol(libname, name, libtree=None):
    """Símbolo aplanado (resuelve extends) con nombre 'lib:name' como se embebe en el .kicad_sch."""
    t = libtree if libtree is not None else lib(libname)
    s = copy.deepcopy(raw_symbol(t, name))
    ext = first(s, "extends")
    if ext:
        parent = flat_symbol(libname, ext[1], t)
        pname = parent[1].split(":", 1)[1]
        child_props = {p[1]: p for p in find(s, "property")}
        new = [ "symbol", Q(f"{libname}:{name}") ]
        props_done = set()
        for c in parent[2:]:
            if isinstance(c, list) and c[0] == "property":
                if c[1] in child_props:
                    new.append(child_props[c[1]]); props_done.add(c[1])
                else:
                    new.append(c)
            elif isinstance(c, list) and c[0] == "symbol":
                c = copy.deepcopy(c)
                c[1] = Q(name + c[1][len(pname):])
                new.append(c)
            else:
                new.append(c)
        # propiedades del hijo que el padre no tenía: antes de las subunidades
        extra = [p for k, p in child_props.items() if k not in props_done]
        idx = next(i for i, c in enumerate(new) if isinstance(c, list) and c[0] == "symbol")
        new[idx:idx] = extra
        return new
    s[1] = Q(f"{libname}:{name}")
    return s


def pins(sym):
    """Lista de pines (número, nombre, tipo, x, y, ángulo) de la unidad 1 / comunes."""
    out = []
    for sub in find(sym, "symbol"):
        m = re.search(r"_(\d+)_(\d+)$", sub[1])
        unit = int(m.group(1))
        if unit not in (0, 1):
            continue
        for p in find(sub, "pin"):
            at = first(p, "at")
            out.append(dict(num=first(p, "number")[1], name=first(p, "name")[1], type=p[1],
                            x=float(at[1]), y=float(at[2]), ang=int(float(at[3]) if len(at) > 3 else 0),
                            hidden=any(isinstance(c, list) and c[0] == "hide" for c in p) or "hide" in p))
    return out
