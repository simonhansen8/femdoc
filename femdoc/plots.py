"""Modelvisninger tegnet direkte fra .struxml (matplotlib, ingen FEM-Design)."""
from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from .struxml import Model

FARVER = {"beam": "#1f4e79", "column": "#c55a11", "truss": "#548235",
          "plate": "#9dc3e6", "wall": "#f4b183", "panel": "#c9c9c9"}
LASTFARVE = "#c00000"


def _lige_akser(ax, pts):
    if not pts:
        return
    xs, ys, zs = zip(*pts)
    c = [(max(v) + min(v)) / 2 for v in (xs, ys, zs)]
    r = max(max(v) - min(v) for v in (xs, ys, zs)) / 2 or 1
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)


def _alle_punkter(m: Model):
    pts = [p for s in m.stænger for p in s.punkter]
    pts += [p for f in m.flader for p in f.kontur]
    pts += [p for u in m.understoetninger for p in u.geometri]
    return pts


def _tegn_3d(ax, m: Model, alpha=0.45, navne=True):
    for f in m.flader:
        if len(f.kontur) >= 3:
            ax.add_collection3d(Poly3DCollection([f.kontur], facecolor=FARVER.get(f.type, "#ccc"),
                                                 edgecolor="#555", linewidths=0.6, alpha=alpha))
    for s in m.stænger:
        if len(s.punkter) >= 2:
            xs, ys, zs = zip(*s.punkter)
            ax.plot(xs, ys, zs, color=FARVER.get(s.type, "#333"), lw=2.2)
            if navne:
                mid = [sum(v) / len(v) for v in (xs, ys, zs)]
                ax.text(*mid, s.navn, fontsize=6, color="#222")
    for u in m.understoetninger:
        if u.type == "punkt" and u.geometri:
            ax.scatter(*zip(*u.geometri), marker="^", s=40, color="#2e7d32", depthshade=False)
        elif len(u.geometri) >= 2:
            xs, ys, zs = zip(*u.geometri)
            ax.plot(xs, ys, zs, color="#2e7d32", lw=3, alpha=0.8)


def _ax3d(titel):
    fig = plt.figure(figsize=(7.5, 5.5), dpi=160)
    ax = fig.add_subplot(projection="3d")
    ax.set_title(titel, fontsize=10)
    ax.set_xlabel("x [m]", fontsize=7); ax.set_ylabel("y [m]", fontsize=7); ax.set_zlabel("z [m]", fontsize=7)
    ax.tick_params(labelsize=6)
    return fig, ax


def isometri(m: Model, ud: Path, elev=25, azim=-60, titel="Modeloversigt (isometri)") -> Path:
    fig, ax = _ax3d(titel)
    _tegn_3d(ax, m)
    _lige_akser(ax, _alle_punkter(m))
    ax.view_init(elev=elev, azim=azim)
    fig.tight_layout(); fig.savefig(ud); plt.close(fig)
    return ud


def plan(m: Model, ud: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=160)
    for f in m.flader:
        if len(f.kontur) >= 3 and f.type != "wall":
            xs, ys, _ = zip(*f.kontur)
            ax.fill(xs, ys, color=FARVER.get(f.type, "#ccc"), alpha=0.35, ec="#555", lw=0.6)
            ax.text(sum(xs) / len(xs), sum(ys) / len(ys), f.navn, fontsize=6, ha="center")
        elif len(f.kontur) >= 2:  # væg ses som linje i plan
            xs, ys, _ = zip(*f.kontur)
            ax.plot(xs, ys, color=FARVER["wall"], lw=3)
    for s in m.stænger:
        if len(s.punkter) >= 2:
            xs, ys, _ = zip(*s.punkter)
            if s.type == "column" or (abs(xs[0] - xs[-1]) < 1e-6 and abs(ys[0] - ys[-1]) < 1e-6):
                ax.plot(xs[0], ys[0], "s", color=FARVER["column"], ms=5)
            else:
                ax.plot(xs, ys, color=FARVER.get(s.type, "#333"), lw=1.8)
            ax.text(xs[0], ys[0], " " + s.navn, fontsize=5.5)
    for u in m.understoetninger:
        if u.type == "punkt" and u.geometri:
            ax.plot(u.geometri[0][0], u.geometri[0][1], "^", color="#2e7d32", ms=6)
    ax.set_aspect("equal"); ax.grid(alpha=0.3)
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.set_title("Plan (set ovenfra)", fontsize=10)
    fig.tight_layout(); fig.savefig(ud); plt.close(fig)
    return ud


def lastplan(m: Model, lasttilfaelde: str, ud: Path) -> Path:
    enhed = {"punkt": "kN", "linje": "kN/m", "flade": "kN/m²"}
    fig, ax = _ax3d(f"Laster – {lasttilfaelde}")
    _tegn_3d(ax, m, alpha=0.15, navne=False)
    for l in m.laster_pr_tilfaelde().get(lasttilfaelde, []):
        if not l.geometri:
            continue
        lab = f"{abs(l.vaerdi):g} {enhed[l.type]}"
        if l.type == "flade" and len(l.geometri) >= 3:
            ax.add_collection3d(Poly3DCollection([l.geometri], facecolor=LASTFARVE, alpha=0.25, edgecolor=LASTFARVE))
        elif len(l.geometri) >= 2:
            xs, ys, zs = zip(*l.geometri)
            ax.plot(xs, ys, zs, color=LASTFARVE, lw=3)
        midt = tuple(sum(v) / len(v) for v in zip(*l.geometri))
        for p in (l.geometri if l.type == "punkt" else [midt]):
            d = l.retning
            ax.quiver(p[0] - d[0], p[1] - d[1], p[2] - d[2], d[0], d[1], d[2],
                      color=LASTFARVE, arrow_length_ratio=0.3, lw=1.5)
        c = [sum(v) / len(v) for v in zip(*l.geometri)]
        ax.text(c[0], c[1], c[2] + 0.3, lab, color=LASTFARVE, fontsize=7, weight="bold")
    _lige_akser(ax, _alle_punkter(m) + [p for l in m.laster for p in l.geometri])
    ax.view_init(elev=25, azim=-60)
    fig.tight_layout(); fig.savefig(ud); plt.close(fig)
    return ud
