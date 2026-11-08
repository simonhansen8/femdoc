"""Læser en FEM-Design .struxml uden FEM-Design installeret.

Udtrækker det der skal i inputdelen af en statisk dokumentation:
projektinfo, materialer, tværsnit, bjælker/søjler, plader/vægge, understøtninger,
lasttilfælde, lastkombinationer og lastgeometri (til plots).

.struxml indeholder normalt ikke beregningsresultater.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import xml.etree.ElementTree as ET

Punkt = tuple[float, float, float]


def _tag(e) -> str:
    return e.tag.split("}", 1)[1] if "}" in e.tag else e.tag


def _kids(e, navn):
    return [c for c in e if _tag(c) == navn]


def _kid(e, navn):
    for c in e:
        if _tag(c) == navn:
            return c
    return None


def _p(e) -> Punkt:
    return (float(e.get("x", 0)), float(e.get("y", 0)), float(e.get("z", 0)))


def _kontur(e) -> list[Punkt]:
    """Punkter langs en <contour>/<region>/<edge>-struktur (buer tilnærmes med deres punkter)."""
    pts: list[Punkt] = []
    for edge in (x for x in e.iter() if _tag(x) == "edge"):
        for p in _kids(edge, "point"):
            q = _p(p)
            if not pts or pts[-1] != q:
                pts.append(q)
    if len(pts) > 2 and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


@dataclass
class Stang:
    navn: str
    type: str            # beam / column / truss
    punkter: list[Punkt]
    tvaersnit: str
    materiale: str

    @property
    def laengde(self) -> float:
        return sum(sum((a - b) ** 2 for a, b in zip(p, q)) ** 0.5
                   for p, q in zip(self.punkter, self.punkter[1:]))


@dataclass
class Flade:
    navn: str
    type: str            # plate / wall / panel
    kontur: list[Punkt]
    tykkelse: float | None
    materiale: str


@dataclass
class Understoetning:
    navn: str
    type: str            # punkt / linje / flade
    geometri: list[Punkt]
    fast: str            # kort beskrivelse af stivheder


@dataclass
class Last:
    type: str            # punkt / linje / flade
    lasttilfaelde: str
    geometri: list[Punkt]
    vaerdi: float        # kN, kN/m eller kN/m²
    retning: Punkt


@dataclass
class Lasttilfaelde:
    navn: str
    type: str
    varighed: str


@dataclass
class Lastkombination:
    navn: str
    type: str
    faktorer: list[tuple[str, float]]


@dataclass
class Model:
    fil: Path
    software: str
    standard: str
    land: str
    materialer: dict[str, str] = field(default_factory=dict)          # guid -> navn
    materiale_data: list[dict] = field(default_factory=list)
    tvaersnit: dict[str, str] = field(default_factory=dict)           # guid -> navn
    stænger: list[Stang] = field(default_factory=list)
    flader: list[Flade] = field(default_factory=list)
    understoetninger: list[Understoetning] = field(default_factory=list)
    lasttilfaelde: list[Lasttilfaelde] = field(default_factory=list)
    lastkombinationer: list[Lastkombination] = field(default_factory=list)
    laster: list[Last] = field(default_factory=list)
    antal: dict[str, int] = field(default_factory=dict)              # alle entity-typer

    def laster_pr_tilfaelde(self) -> dict[str, list[Last]]:
        d: dict[str, list[Last]] = defaultdict(list)
        for l in self.laster:
            d[l.lasttilfaelde].append(l)
        return d


_UKENDT = "(fra FEM-Design bibliotek)"

_LASTTYPER = {
    "dead_load": "Egenlast", "static": "Statisk", "soil_dead_load": "Jordlast",
    "shrinkage": "Svind", "prestressing": "Forspænding", "fire": "Brand",
    "seis_sxp": "Seismisk", "seis_sxm": "Seismisk", "seis_syp": "Seismisk",
    "seis_sym": "Seismisk",
}
_KOMBITYPER = {
    "ultimate_ordinary": "ULS", "ultimate_accidental": "ULS ulykke",
    "ultimate_seismic": "ULS seismisk", "serviceability_quasi_permanent": "SLS kvasipermanent",
    "serviceability_frequent": "SLS hyppig", "serviceability_characteristic": "SLS karakteristisk",
}


def _stivhed(group) -> str:
    rig = _kid(group, "rigidity") if group is not None else None
    if rig is None:
        return "defineret ved type"
    ud = []
    for navn, kort in (("motions", "u"), ("rotations", "r")):
        m = _kid(rig, navn)
        if m is None:
            continue
        for akse in "xyz":
            v = float(m.get(f"{akse}_pos", 0) or 0)
            if v >= 1e7:
                ud.append(f"{kort}{akse}")
    return "fast: " + ", ".join(ud) if ud else "fjedrende/fri"


def laes(sti: str | Path) -> Model:
    sti = Path(sti)
    rod = ET.parse(sti).getroot()
    m = Model(fil=sti, software=rod.get("source_software", "?"),
              standard=rod.get("standard", "?"), land=rod.get("country", "?"))

    # Materialer og tværsnit
    for sekt in ("materials", "reinforcing_materials"):
        for blok in _kids(rod, sekt):
            for mat in _kids(blok, "material"):
                m.materialer[mat.get("guid")] = mat.get("name", "?")
                data = next(iter(mat), None)
                m.materiale_data.append({
                    "Navn": mat.get("name", "?"),
                    "Type": _tag(data) if data is not None else "?",
                    "E [GPa]": (float(data.get("E_0", 0)) / 1e6) if data is not None and data.get("E_0") else None,
                    "Densitet [t/m³]": float(data.get("mass")) if data is not None and data.get("mass") else None,
                })
    sektioner: dict[str, str] = {}
    komplekse: dict[str, str] = {}
    for blok in _kids(rod, "sections"):
        for s in _kids(blok, "section"):
            sektioner[s.get("guid")] = s.get("fd_name_size") and \
                f"{s.get('fd_name_type', '')} {s.get('fd_name_size')}".strip() or s.get("name", "?")
        for cs in _kids(blok, "complex_section"):
            ref = [sektioner.get(x.get("guid"), "?") for x in _kids(cs, "section")]
            komplekse[cs.get("guid")] = " → ".join(dict.fromkeys(ref)) or "?"
    m.tvaersnit = komplekse

    ent = _kid(rod, "entities")
    if ent is None:
        return m
    for e in ent:
        m.antal[_tag(e)] = m.antal.get(_tag(e), 0) + 1

    # Stænger
    for bar in _kids(ent, "bar"):
        del_ = _kid(bar, "bar_part")
        if del_ is None:
            continue
        kurve = _kid(del_, "curve")
        pts = [_p(p) for p in _kids(kurve, "point")] if kurve is not None else []
        m.stænger.append(Stang(
            navn=del_.get("name", "?").rsplit(".", 1)[0] if del_.get("name", "").count(".") > 1 else del_.get("name", "?"),
            type=bar.get("type", "beam"), punkter=pts,
            tvaersnit=komplekse.get(del_.get("complex_section"), _UKENDT),
            materiale=m.materialer.get(del_.get("complex_material"), _UKENDT)))

    # Plader og vægge
    for slab in _kids(ent, "slab"):
        del_ = _kid(slab, "slab_part")
        if del_ is None:
            continue
        tyk = [float(t.get("val")) for t in _kids(del_, "thickness")]
        m.flader.append(Flade(
            navn=slab.get("name", "?"), type=slab.get("type", "plate"),
            kontur=_kontur(del_),
            tykkelse=max(tyk) if tyk else None,
            materiale=m.materialer.get(del_.get("complex_material"), _UKENDT)))
    for pan in _kids(ent, "panel"):
        reg = _kid(pan, "region")
        reg = pan if reg is None else reg
        m.flader.append(Flade(
            navn=pan.get("name", "?"), type="panel", kontur=_kontur(reg),
            tykkelse=float(pan.get("thickness")) if pan.get("thickness") else None,
            materiale=m.materialer.get(pan.get("complex_material"), _UKENDT)))

    # Understøtninger
    sup = _kid(ent, "supports")
    if sup is not None:
        for s in sup:
            t = _tag(s)
            if t == "point_support":
                pos = _kid(s, "position")
                m.understoetninger.append(Understoetning(
                    s.get("name", "?"), "punkt", [_p(pos)] if pos is not None else [], _stivhed(_kid(s, "group"))))
            elif t == "line_support":
                edge = _kid(s, "edge")
                m.understoetninger.append(Understoetning(
                    s.get("name", "?"), "linje", [_p(p) for p in _kids(edge, "point")] if edge is not None else [],
                    _stivhed(_kid(s, "group"))))
            elif t == "surface_support":
                m.understoetninger.append(Understoetning(
                    s.get("name", "?"), "flade", _kontur(s), _stivhed(s)))

    # Laster
    loads = _kid(ent, "loads")
    if loads is not None:
        lc_navn: dict[str, str] = {}
        for lc in _kids(loads, "load_case"):
            lc_navn[lc.get("guid")] = lc.get("name", "?")
            m.lasttilfaelde.append(Lasttilfaelde(
                lc.get("name", "?"), _LASTTYPER.get(lc.get("type", ""), lc.get("type", "")),
                lc.get("duration_class", "")))
        for k in _kids(loads, "load_combination"):
            m.lastkombinationer.append(Lastkombination(
                k.get("name", "?"), _KOMBITYPER.get(k.get("type", ""), k.get("type", "")),
                [(lc_navn.get(x.get("guid"), "?"), float(x.get("gamma", 1))) for x in _kids(k, "load_case")]))
        for l in loads:
            t = _tag(l)
            typ = {"point_load": "punkt", "line_load": "linje", "surface_load": "flade"}.get(t)
            if not typ or l.get("load_type", "force") != "force":
                continue
            vals = [float(x.get("val", 0)) for x in _kids(l, "load")]
            d = _kid(l, "direction")
            if typ == "punkt":
                geo = [_p(x) for x in _kids(l, "load")]
            elif typ == "linje":
                edge = _kid(l, "edge")
                geo = [_p(p) for p in _kids(edge, "point")] if edge is not None else []
            else:
                geo = _kontur(l)
            m.laster.append(Last(typ, lc_navn.get(l.get("load_case"), "?"), geo,
                                 max(vals, key=abs) if vals else 0.0,
                                 _p(d) if d is not None else (0, 0, -1)))
    return m
