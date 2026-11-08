"""Brugerdefinerede views: snit, etageplaner og 3D-vinkler.

Et view beskrives som en simpel ordbog, så det kan komme fra websiden (JSON)
eller fra projekt.yaml:

    {"type": "3d",       "navn": "Isometri",       "azim": -60, "elev": 25}
    {"type": "oversigt", "navn": "Plan med snit"}
    {"type": "plan",     "navn": "Plan kote 3,50", "z": 3.5}
    {"type": "snit",     "navn": "A-A", "fra": [0, 5], "til": [18, 5], "dybde": 1.0}

Et snit er en lodret plan gennem linjen fra→til (set ovenfra). Elementer inden for
±dybde/2 af linjen tegnes i opstalt; elementer der krydser snitplanen vises som snitflader.
"""
from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

from .struxml import Model
from . import plots

STANDARD = [
    {"type": "3d", "navn": "Isometri", "azim": -60, "elev": 25},
    {"type": "3d", "navn": "Isometri set fra modsat side", "azim": 120, "elev": 25},
    {"type": "oversigt", "navn": "Plan set ovenfra"},
]

TOL = 0.02


def niveauer(m: Model) -> list[float]:
    """Koter med vandrette elementer (bjælker og dæk) – kandidater til etageplaner."""
    z = set()
    for s in m.stænger:
        if len(s.punkter) >= 2 and abs(s.punkter[0][2] - s.punkter[-1][2]) < TOL:
            z.add(round(s.punkter[0][2], 3))
    for f in m.flader:
        zs = [p[2] for p in f.kontur]
        if zs and max(zs) - min(zs) < TOL:
            z.add(round(zs[0], 3))
    return sorted(z)


def plan_data(m: Model) -> dict:
    """Let geometri til websidens interaktive plan."""
    pts = plots._alle_punkter(m)
    xs, ys = [p[0] for p in pts] or [0], [p[1] for p in pts] or [0]
    knuder = sorted({(round(p[0], 3), round(p[1], 3)) for p in pts})
    return {
        "staenger": [{"navn": s.navn, "type": s.type, "punkter": [list(p) for p in s.punkter]}
                     for s in m.stænger if len(s.punkter) >= 2],
        "flader": [{"navn": f.navn, "type": f.type, "kontur": [list(p) for p in f.kontur]}
                   for f in m.flader if len(f.kontur) >= 2],
        "understoetninger": [{"navn": u.navn, "type": u.type, "geometri": [list(p) for p in u.geometri]}
                             for u in m.understoetninger],
        "niveauer": niveauer(m),
        "knuder": [list(k) for k in knuder],
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
    }


# ---------------------------------------------------------------- snit

class _Snit:
    def __init__(self, fra, til, dybde):
        self.ax, self.ay = fra
        dx, dy = til[0] - fra[0], til[1] - fra[1]
        self.L = (dx * dx + dy * dy) ** 0.5 or 1.0
        self.ux, self.uy = dx / self.L, dy / self.L
        self.t = max(dybde, 0.01) / 2

    def s(self, p):  # afstand langs snittet
        return (p[0] - self.ax) * self.ux + (p[1] - self.ay) * self.uy

    def d(self, p):  # afstand vinkelret på snittet
        return -(p[0] - self.ax) * self.uy + (p[1] - self.ay) * self.ux

    def inden_for(self, s):
        return -TOL <= s <= self.L + TOL


def _krydsning(p, q, dp, dq):
    k = dp / (dp - dq)
    return tuple(a + k * (b - a) for a, b in zip(p, q))


def snit(m: Model, view: dict, ud: Path) -> Path:
    sn = _Snit(view["fra"], view["til"], float(view.get("dybde", 1.0)))
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=160)
    zs = []

    # Flader: i planen -> opstalt, krydser planen -> snitlinje
    for f in m.flader:
        if len(f.kontur) < 3:
            continue
        ds = [sn.d(p) for p in f.kontur]
        farve = plots.FARVER.get(f.type, "#ccc")
        if all(abs(d) <= sn.t for d in ds):
            poly = [(sn.s(p), p[2]) for p in f.kontur]
            ax.add_patch(Polygon(poly, closed=True, fc=farve, ec="#555", alpha=0.35, lw=0.8))
            zs += [p[1] for p in poly]
            cx = sum(p[0] for p in poly) / len(poly); cz = sum(p[1] for p in poly) / len(poly)
            ax.text(cx, cz, f.navn, fontsize=7, ha="center", va="center", color="#333")
            continue
        snitpkt = []
        for p, q, dp, dq in zip(f.kontur, f.kontur[1:], ds, ds[1:]):
            if abs(dp) < 1e-9:
                snitpkt.append(p)
            elif dp * dq < 0:
                snitpkt.append(_krydsning(p, q, dp, dq))
        if len(snitpkt) >= 2:
            proj = sorted((sn.s(p), p[2]) for p in snitpkt)
            (s0, z0), (s1, z1) = proj[0], max(proj, key=lambda p: (p[0], p[1]))
            if abs(s1 - s0) < TOL:  # lodret snitflade (væg)
                z0, z1 = min(p[1] for p in proj), max(p[1] for p in proj)
            s0, s1 = max(s0, 0), min(s1, sn.L)
            if s1 >= s0 and (s1 - s0 > TOL or abs(z1 - z0) > TOL):
                ax.plot([s0, s1], [z0, z1], color="#555",
                        lw=4.5 if f.type != "wall" else 6, solid_capstyle="butt", zorder=3)
                tyk = f" ({round(f.tykkelse * 1000)} mm)" if f.tykkelse else ""
                ax.text((s0 + s1) / 2, max(z0, z1) + 0.25, f.navn + tyk, fontsize=7, ha="center", color="#333")
                zs += [z0, z1]

    # Stænger
    for st in m.stænger:
        if len(st.punkter) < 2:
            continue
        p, q = st.punkter[0], st.punkter[-1]
        dp, dq = sn.d(p), sn.d(q)
        farve = plots.FARVER.get(st.type, "#333")
        if abs(dp) <= sn.t and abs(dq) <= sn.t:
            s0, s1 = sn.s(p), sn.s(q)
            if not (sn.inden_for(s0) or sn.inden_for(s1)):
                continue
            ax.plot([s0, s1], [p[2], q[2]], color=farve, lw=2.4, zorder=4)
            ax.text((s0 + s1) / 2, (p[2] + q[2]) / 2, " " + st.navn, fontsize=6.5, color="#222",
                    rotation=90 if abs(s0 - s1) < TOL else 0, va="bottom", ha="left")
            zs += [p[2], q[2]]
        elif dp * dq < 0:
            c = _krydsning(p, q, dp, dq)
            sc = sn.s(c)
            if sn.inden_for(sc):
                ax.plot(sc, c[2], marker="s", ms=6, mfc="white", mec=farve, mew=1.8, zorder=5)
                ax.text(sc, c[2] - 0.12, st.navn, fontsize=6, ha="center", va="top", color="#222")
                zs.append(c[2])

    # Understøtninger
    for u in m.understoetninger:
        for p in (u.geometri if u.type == "punkt" else u.geometri[:1]):
            if abs(sn.d(p)) <= sn.t and sn.inden_for(sn.s(p)):
                ax.plot(sn.s(p), p[2], "^", color="#2e7d32", ms=9, zorder=6)
                zs.append(p[2])

    zmin, zmax = (min(zs), max(zs)) if zs else (0, 1)
    ax.set_xlim(-0.05 * sn.L, 1.05 * sn.L)
    ax.set_ylim(zmin - 0.6, zmax + 0.6)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.3)
    ax.set_xlabel(f"Afstand langs snit [m]  (fra ({view['fra'][0]:g}; {view['fra'][1]:g}) "
                  f"til ({view['til'][0]:g}; {view['til'][1]:g}), dybde ±{sn.t:g} m)", fontsize=8)
    ax.set_ylabel("Kote z [m]")
    ax.set_title(f"Snit {view.get('navn', '')}", fontsize=10)
    fig.tight_layout(); fig.savefig(ud); plt.close(fig)
    return ud


# ---------------------------------------------------------------- etageplan

def _kote_navn(z) -> str:
    return f"Plan kote {float(z):g} m".replace(".", ",")


def etageplan(m: Model, view: dict, ud: Path) -> Path:
    z = float(view["z"])
    fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=160)
    for f in m.flader:
        zs = [p[2] for p in f.kontur]
        if not zs:
            continue
        if max(zs) - min(zs) < TOL and abs(zs[0] - z) < TOL:
            xs, ys = [p[0] for p in f.kontur], [p[1] for p in f.kontur]
            ax.fill(xs, ys, color=plots.FARVER.get(f.type, "#ccc"), alpha=0.35, ec="#555", lw=0.6)
            tyk = f"\n{round(f.tykkelse * 1000)} mm" if f.tykkelse else ""
            ax.text(sum(xs) / len(xs), sum(ys) / len(ys), f.navn + tyk, fontsize=7, ha="center", va="center")
        elif min(zs) - TOL <= z <= max(zs) + TOL and max(zs) - min(zs) >= TOL:  # væg
            xs, ys = [p[0] for p in f.kontur], [p[1] for p in f.kontur]
            ax.plot(xs, ys, color=plots.FARVER["wall"], lw=4)
    for s in m.stænger:
        if len(s.punkter) < 2:
            continue
        p, q = s.punkter[0], s.punkter[-1]
        if abs(p[2] - z) < TOL and abs(q[2] - z) < TOL:
            ax.plot([p[0], q[0]], [p[1], q[1]], color=plots.FARVER.get(s.type, "#333"), lw=2)
            ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, s.navn, fontsize=6, ha="center", va="bottom")
        elif min(p[2], q[2]) - TOL <= z <= max(p[2], q[2]) + TOL and abs(p[0] - q[0]) < TOL and abs(p[1] - q[1]) < TOL:
            # søjle der ender i eller går gennem koten; vis kun den underliggende
            if min(p[2], q[2]) < z - TOL:
                ax.plot(p[0], p[1], "s", color=plots.FARVER["column"], ms=6)
                ax.text(p[0], p[1], "  " + s.navn, fontsize=6, va="top")
    for u in m.understoetninger:
        for p in u.geometri[:1]:
            if abs(p[2] - z) < TOL:
                ax.plot(p[0], p[1], "^", color="#2e7d32", ms=7)
    ax.set_aspect("equal"); ax.grid(alpha=0.3)
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
    ax.set_title(view.get("navn") or _kote_navn(z), fontsize=10)
    fig.tight_layout(); fig.savefig(ud); plt.close(fig)
    return ud


# ---------------------------------------------------------------- samlet

def _filnavn(i: int, v: dict) -> str:
    sikker = "".join(c if c.isalnum() else "_" for c in str(v.get("navn", v["type"])))[:30]
    return f"view_{i:02d}_{sikker}.png"


def tegn(m: Model, views: list[dict], mappe: Path) -> list[tuple[Path, str]]:
    """Tegner alle views og returnerer (fil, figurtekst)."""
    mappe.mkdir(parents=True, exist_ok=True)
    snit_liste = [v for v in views if v.get("type") == "snit"]
    ud = []
    for i, v in enumerate(views, 1):
        f = mappe / _filnavn(i, v)
        t = v.get("type")
        if t == "3d":
            plots.isometri(m, f, elev=float(v.get("elev", 25)), azim=float(v.get("azim", -60)),
                           titel=v.get("navn", "3D"))
            ud.append((f, v.get("navn", "3D-visning")))
        elif t == "oversigt":
            plots.plan(m, f, snit=snit_liste)
            navn = v.get("navn", "Plan")
            ud.append((f, navn + (" med snitmarkeringer" if snit_liste and "snit" not in navn.lower() else "")))
        elif t == "plan":
            etageplan(m, v, f)
            ud.append((f, v.get("navn") or _kote_navn(v["z"])))
        elif t == "snit":
            snit(m, v, f)
            ud.append((f, f"Snit {v.get('navn', '')}"))
    return ud
