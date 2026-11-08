"""Genererer eksempel/struxml/kontorbygning.struxml – en lille, realistisk testmodel.

Kontorbygning i 2 etager, stålskelet med betondæk:
  * Modulnet 3 fag á 6,0 m (x) × 2 fag á 5,0 m (y), etagehøjde 3,5 m
  * Søjler HE-B 200 (S 355), bjælker IPE 300 (S 355) i begge retninger
  * Etagedæk og tagdæk: 220 mm beton C30/37
  * Charnierlejer ved søjlefod
  * Lasttilfælde: egenlast, installationer, nyttelast (kat. B), sne, vind (+x)
  * Lastkombinationer efter EN 1990 (6.10a/6.10b) samt SLS

Materiale- og tværsnitsdefinitioner kopieres fra StruSofts femdesign-api biblioteker:
    python eksempel/generer_testmodel.py <sti til femdesign-api klon>
"""
from __future__ import annotations
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "urn:strusoft"
ET.register_namespace("", NS)
FRØ = uuid.UUID("6f1c2a52-0d7e-4a41-9d0e-2b4f6a1c9e11")
TID = "2026-11-08T12:00:00.000"

# Geometri
FAG_X, N_X = 6.0, 3
FAG_Y, N_Y = 5.0, 2
H, ETAGER = 3.5, 2
LX, LY = FAG_X * N_X, FAG_Y * N_Y


def gid(navn: str) -> str:
    return str(uuid.uuid5(FRØ, navn))


def el(parent, tag, **attr):
    e = ET.SubElement(parent, f"{{{NS}}}{tag}")
    for k, v in attr.items():
        e.set(k.replace("__", "-"), v if isinstance(v, str) else f"{v:g}")
    return e


def punkt(parent, tag, x, y, z):
    return el(parent, tag, x=x, y=y, z=z)


def entitet(parent, tag, navn, **attr):
    return el(parent, tag, guid=gid(navn), last_change=TID, action="added", **attr)


def rektangel(parent, z):
    """Kontur (fire kanter) for et rektangel i niveau z, mod uret set ovenfra."""
    c = el(parent, "contour")
    hjørner = [(0, 0), (LX, 0), (LX, LY), (0, LY)]
    normaler = [(0, 1), (-1, 0), (0, -1), (1, 0)]
    for i, (a, n) in enumerate(zip(hjørner, normaler)):
        b = hjørner[(i + 1) % 4]
        e = el(c, "edge", type="line")
        punkt(e, "point", a[0], a[1], z); punkt(e, "point", b[0], b[1], z)
        punkt(e, "normal", n[0], n[1], 0)
    return c


def hent_bibliotek(api: Path):
    mats = ET.parse(api / "FemDesign.Tests/Composites/materials.struxml").getroot()
    secs = ET.parse(api / "FemDesign.Tests/Assets/sections.struxml").getroot()
    m = {x.get("name"): x for x in mats.iter(f"{{{NS}}}material")}
    s = {x.get("name"): x for x in secs.iter(f"{{{NS}}}section")}
    return ({"S 355": m["S 355"], "C30/37": m["C30/37"]},
            {"HEB200": s["Steel section, HE-B, 200"], "IPE300": s["Steel section, IPE, 300"]})


def byg(api: Path) -> ET.ElementTree:
    materialer, tvaersnit = hent_bibliotek(api)
    db = ET.Element(f"{{{NS}}}database", struxml_version="01.00.000",
                    source_software="FEM-Design 23.00.004", start_time="1970-01-01T00:00:00.000",
                    end_time=TID, guid=gid("database"), convertid="00000000-0000-0000-0000-000000000000",
                    standard="EC", country="S")
    ent = el(db, "entities")
    staal, beton = materialer["S 355"].get("guid"), materialer["C30/37"].get("guid")
    cs = {k: gid(f"complex_section {k}") for k in tvaersnit}

    def stang(navn, typ, a, b, profil, local_y):
        bar = entitet(ent, "bar", navn, name=navn, type=typ)
        part = entitet(bar, "bar_part", navn + ".1", name=navn + ".1", complex_material=staal,
                       made="rolled", complex_section=cs[profil], ecc_calc="true")
        kurve = el(part, "curve", type="line")
        punkt(kurve, "point", *a); punkt(kurve, "point", *b)
        punkt(part, "local-y", *local_y)
        # Bjælker charnierforbundet i enderne, søjler gennemgående
        rel = "false" if typ == "beam" else "true"
        for _ in range(2):
            el(part, "connectivity", m_x="true", m_y="true", m_z="true", r_x="true", r_y=rel, r_z=rel)
        ecc = el(part, "eccentricity", use_default_physical_alignment="true")
        for t in ("analytical", "analytical", "physical", "physical"):
            punkt(ecc, t, 0, 0, 0)
        el(part, "end"); el(bar, "end")

    # Søjler
    n = 0
    for e in range(ETAGER):
        for j in range(N_Y + 1):
            for i in range(N_X + 1):
                n += 1
                x, y = i * FAG_X, j * FAG_Y
                stang(f"C.{n}", "column", (x, y, e * H), (x, y, (e + 1) * H), "HEB200", (0, 1, 0))
    # Bjælker
    n = 0
    for e in range(1, ETAGER + 1):
        z = e * H
        for j in range(N_Y + 1):
            for i in range(N_X):
                n += 1
                stang(f"B.{n}", "beam", (i * FAG_X, j * FAG_Y, z), ((i + 1) * FAG_X, j * FAG_Y, z), "IPE300", (0, 1, 0))
        for i in range(N_X + 1):
            for j in range(N_Y):
                n += 1
                stang(f"B.{n}", "beam", (i * FAG_X, j * FAG_Y, z), (i * FAG_X, (j + 1) * FAG_Y, z), "IPE300", (-1, 0, 0))

    # Dæk
    for e in range(1, ETAGER + 1):
        z = e * H
        navn = f"P.{e}"
        slab = entitet(ent, "slab", navn, name=navn, type="plate")
        part = entitet(slab, "slab_part", navn + ".1", name=navn + ".1", complex_material=beton,
                       alignment="center", align_offset="0", ortho_alfa="0", ortho_ratio="1")
        rektangel(part, z)
        el(part, "thickness", x=0, y=0, z=z, val=0.22)
        punkt(part, "local_pos", LX / 2, LY / 2, z)
        punkt(part, "local_x", 1, 0, 0); punkt(part, "local_y", 0, 1, 0)
        el(part, "end"); el(slab, "end")

    # Laster
    loads = el(ent, "loads")
    lc = {}
    for kort, navn, typ, varighed in [
        ("G", "Egenlast", "dead_load", "permanent"),
        ("Gi", "Installationer og gulv", "static", "permanent"),
        ("Q", "Nyttelast kat. B", "static", "medium-term"),
        ("S", "Sne", "static", "short-term"),
        ("W", "Vind +x", "static", "instantaneous"),
    ]:
        lc[kort] = gid(f"load_case {kort}")

    def fladelast(kort, z, val, navn):
        sl = entitet(loads, "surface_load", navn, load_case=lc[kort], load_projection="false", load_type="force")
        rektangel(el(sl, "region"), z)
        punkt(sl, "direction", 0, 0, -1)
        el(sl, "load", x=0, y=0, z=z, val=val)

    # Vind som linjelast på facaden (x=0), fordelt til de to dækniveauer: 0,7 kN/m² · 3,5 m
    for e in range(1, ETAGER + 1):
        z = e * H
        val = 0.7 * H * (0.5 if e == ETAGER else 1.0)
        ll = entitet(loads, "line_load", f"W {e}", load_case=lc["W"], load_type="force", load_dir="constant",
                     load_projection="false")
        edge = el(ll, "edge", type="line")
        punkt(edge, "point", 0, 0, z); punkt(edge, "point", 0, LY, z); punkt(edge, "normal", 0, 0, 1)
        punkt(ll, "direction", 1, 0, 0)
        punkt(ll, "normal", 0, 0, 1)
        el(ll, "load", x=0, y=0, z=z, val=val); el(ll, "load", x=0, y=LY, z=z, val=val)

    tag_z, etage_z = ETAGER * H, H
    fladelast("Gi", etage_z, 1.0, "Gi etage")
    fladelast("Gi", tag_z, 0.5, "Gi tag")
    fladelast("Q", etage_z, 2.5, "Q etage")
    fladelast("S", tag_z, 0.8, "S tag")
    for kort, navn, typ, varighed in [
        ("G", "Egenlast", "dead_load", "permanent"),
        ("Gi", "Installationer og gulv", "static", "permanent"),
        ("Q", "Nyttelast kat. B", "static", "medium-term"),
        ("S", "Sne", "static", "short-term"),
        ("W", "Vind +x", "static", "instantaneous"),
    ]:
        el(loads, "load_case", guid=lc[kort], last_change=TID, action="added",
           name=navn, type=typ, duration_class=varighed)

    # Lastkombinationer (EN 1990, KFI = 1,0; ψ0: Q 0,6 · S 0,6 · W 0,3)
    kombi = [
        ("ULS 1 – 6.10a egenlast", "ultimate_ordinary", {"G": 1.2, "Gi": 1.2}),
        ("ULS 2 – nyttelast dominerende", "ultimate_ordinary", {"G": 1.0, "Gi": 1.0, "Q": 1.5, "S": 0.9, "W": 0.45}),
        ("ULS 3 – sne dominerende", "ultimate_ordinary", {"G": 1.0, "Gi": 1.0, "S": 1.5, "Q": 0.9, "W": 0.45}),
        ("ULS 4 – vind dominerende", "ultimate_ordinary", {"G": 1.0, "Gi": 1.0, "W": 1.5, "Q": 0.9, "S": 0.9}),
        ("SLS kar. – nyttelast", "serviceability_characteristic", {"G": 1.0, "Gi": 1.0, "Q": 1.0, "S": 0.6, "W": 0.3}),
        ("SLS kvasipermanent", "serviceability_quasi_permanent", {"G": 1.0, "Gi": 1.0, "Q": 0.3}),
    ]
    for navn, typ, faktorer in kombi:
        k = entitet(loads, "load_combination", navn, name=navn, type=typ)
        for kort, g in faktorer.items():
            el(k, "load_case", guid=lc[kort], gamma=g)

    # Understøtninger: charnier ved søjlefod
    sup = el(ent, "supports")
    n = 0
    for j in range(N_Y + 1):
        for i in range(N_X + 1):
            n += 1
            ps = entitet(sup, "point_support", f"S.{n}", name=f"S.{n}")
            g = el(ps, "group")
            punkt(g, "local_x", 1, 0, 0); punkt(g, "local_y", 0, 1, 0)
            r = el(g, "rigidity")
            el(r, "motions", **{f"{a}_{s}": 1e10 for a in "xyz" for s in ("neg", "pos")})
            el(r, "rotations", **{f"{a}_{s}": 0 for a in "xyz" for s in ("neg", "pos")})
            punkt(ps, "position", i * FAG_X, j * FAG_Y, 0)

    # Tværsnit og materialer
    secs = el(db, "sections")
    for k, s in tvaersnit.items():
        secs.append(s)
    for k, s in tvaersnit.items():
        c = el(secs, "complex_section", guid=cs[k], last_change="1970-01-01T00:00:00.000", action="added")
        for pos in ("0", "1"):
            sec = el(c, "section", pos=pos, guid=s.get("guid"))
            punkt(sec, "ecc", 0, 0, 0); el(sec, "end")
    mats = el(db, "materials")
    for m in materialer.values():
        mats.append(m)
    el(db, "end")
    ET.indent(db, "\t")
    return ET.ElementTree(db)


if __name__ == "__main__":
    api = Path(sys.argv[1])
    ud = Path(__file__).parent / "struxml" / "kontorbygning.struxml"
    byg(api).write(ud, encoding="UTF-8", xml_declaration=True)
    print(f"Skrevet: {ud}")
