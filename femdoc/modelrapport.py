"""Rapportsektioner bygget direkte fra .struxml: modelbeskrivelse, materialer, tværsnit,
understøtninger, laster og lastkombinationer, med automatisk genererede modelvisninger."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
from docx.shared import Cm, Pt

from .struxml import Model
from . import plots


def _tabel(doc, overskrifter, raekker, bredde_pt=8):
    t = doc.add_table(rows=1, cols=len(overskrifter))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(overskrifter):
        t.rows[0].cells[i].text = str(h)
    for r in raekker:
        c = t.add_row().cells
        for i, v in enumerate(r):
            c[i].text = "–" if v is None else (f"{v:.3g}" if isinstance(v, float) else str(v))
    for row in t.rows:
        for c in row.cells:
            for par in c.paragraphs:
                for run in par.runs:
                    run.font.size = Pt(bredde_pt)
    doc.add_paragraph()
    return t


def _figur(doc, sti: Path, tekst: str, nr: list):
    nr[0] += 1
    doc.add_picture(str(sti), width=Cm(15.5))
    cap = doc.add_paragraph(f"Figur {nr[0]}: {tekst}")
    cap.runs[0].italic = True; cap.runs[0].font.size = Pt(9)


def tilfoej(doc, m: Model, billedmappe: Path, views: list[dict] | None = None):
    billedmappe.mkdir(parents=True, exist_ok=True)
    for gammel in billedmappe.glob("*.png"):  # fjern figurer fra tidligere kørsler
        gammel.unlink()
    nr = [0]

    doc.add_heading("Modelbeskrivelse", level=1)
    typer = Counter(s.type for s in m.stænger) + Counter(f.type for f in m.flader)
    navne = {"beam": "bjælker", "column": "søjler", "truss": "gitterstænger",
             "plate": "plader", "wall": "vægge", "panel": "paneler"}
    elementer = ", ".join(f"{n} {navne.get(t, t)}" for t, n in typer.items()) or "ingen konstruktionselementer"
    doc.add_paragraph(
        f"Beregningsmodellen er opbygget i {m.software} (norm: {m.standard}, nationalt anneks: {m.land}). "
        f"Modellen består af {elementer} samt {len(m.understoetninger)} understøtninger. "
        f"Der er defineret {len(m.lasttilfaelde)} lasttilfælde og {len(m.lastkombinationer)} lastkombinationer. "
        f"Modelfil: {m.fil.name}.")

    if m.stænger or m.flader:
        from .views import STANDARD, tegn
        valgte = STANDARD if views is None else views
        figurer = tegn(m, valgte, billedmappe)
        if views is not None and figurer:
            doc.add_heading("Visninger", level=2)
        for sti, tekst in figurer:
            _figur(doc, sti, tekst, nr)

    if m.materiale_data:
        doc.add_heading("Materialer", level=2)
        _tabel(doc, ["Navn", "Type", "E [GPa]", "Densitet [t/m³]"],
               [list(d.values()) for d in m.materiale_data])

    if m.stænger:
        doc.add_heading("Stangelementer", level=2)
        _tabel(doc, ["Navn", "Type", "Tværsnit", "Materiale", "Længde [m]"],
               [[s.navn, navne.get(s.type, s.type), s.tvaersnit, s.materiale, s.laengde] for s in m.stænger])
    if m.flader:
        doc.add_heading("Plader og vægge", level=2)
        _tabel(doc, ["Navn", "Type", "Tykkelse [mm]", "Materiale"],
               [[f.navn, navne.get(f.type, f.type),
                 None if f.tykkelse is None else round(f.tykkelse * 1000), f.materiale] for f in m.flader])
    if m.understoetninger:
        doc.add_heading("Understøtninger", level=2)
        _tabel(doc, ["Navn", "Type", "Frihedsgrader"],
               [[u.navn, u.type, u.fast] for u in m.understoetninger])

    doc.add_heading("Laster", level=1)
    if m.lasttilfaelde:
        doc.add_heading("Lasttilfælde", level=2)
        pr = m.laster_pr_tilfaelde()
        _tabel(doc, ["Navn", "Type", "Varighed", "Antal laster"],
               [[l.navn, l.type, l.varighed, len(pr.get(l.navn, []))] for l in m.lasttilfaelde])
        for i, lc in enumerate(m.lasttilfaelde, 1):
            if pr.get(lc.navn):
                sti = plots.lastplan(m, lc.navn, billedmappe / f"last_{i:02d}.png")
                _figur(doc, sti, f"Laster i lasttilfælde '{lc.navn}'", nr)
    else:
        doc.add_paragraph("Ingen lasttilfælde i modellen.")
    if m.lastkombinationer:
        doc.add_heading("Lastkombinationer", level=2)
        _tabel(doc, ["Kombination", "Type", "Indhold"],
               [[k.navn, k.type, " + ".join(f"{g:g}·{n}" for n, g in k.faktorer)] for k in m.lastkombinationer])
