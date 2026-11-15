"""Rapportsektioner bygget direkte fra .struxml: modelbeskrivelse, materialer, tværsnit,
understøtninger, laster og lastkombinationer, med automatisk genererede modelvisninger."""
from __future__ import annotations
from collections import Counter, defaultdict
from pathlib import Path
from docx.shared import Cm, Pt

from .struxml import Model, LANDE
from .tal import tal
from . import plots

ENHED = {"punkt": "kN", "linje": "kN/m", "flade": "kN/m²"}
LASTNAVNE = {"punkt": "Punktlast", "linje": "Linjelast", "flade": "Fladelast"}


def _tabel(doc, overskrifter, raekker, bredde_pt=8):
    t = doc.add_table(rows=1, cols=len(overskrifter))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(overskrifter):
        t.rows[0].cells[i].text = str(h)
    for r in raekker:
        c = t.add_row().cells
        for i, v in enumerate(r):
            c[i].text = tal(v) if v is None or isinstance(v, float) else str(v)
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
    ental = {"beam": "Bjælke", "column": "Søjle", "truss": "Gitterstang",
             "plate": "Plade", "wall": "Væg", "panel": "Panel"}
    elementer = ", ".join(f"{n} {navne.get(t, t)}" for t, n in typer.items()) or "ingen konstruktionselementer"
    doc.add_paragraph(
        f"Beregningsmodellen er opbygget i {m.software} (norm: {m.standard}, "
        f"nationalt anneks: {LANDE.get(m.land, m.land)}). "
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
        kol = ["Navn", "Type", "E [GPa]", "Styrke [MPa]", "Densitet [t/m³]"]
        _tabel(doc, kol, list(dict.fromkeys(tuple(d.get(k) for k in kol) for d in m.materiale_data)))
        doc.add_paragraph("Styrke er den karakteristiske værdi: fyk for stål og armering, fck for beton "
                          "og fm,k for træ.").runs[0].font.size = Pt(8)

    if m.stænger:
        doc.add_heading("Stangelementer", level=2)
        grupper: dict[tuple, list] = defaultdict(list)
        for s in m.stænger:
            grupper[(ental.get(s.type, s.type), s.tvaersnit, s.materiale)].append(s)
        doc.add_paragraph("Oversigt pr. type, tværsnit og materiale:")
        _tabel(doc, ["Type", "Tværsnit", "Materiale", "Antal", "Samlet længde [m]"],
               [[*k, len(v), sum(s.laengde for s in v)] for k, v in grupper.items()])
        if len(m.stænger) > len(grupper):
            doc.add_paragraph("Alle stangelementer:")
        _tabel(doc, ["Navn", "Type", "Tværsnit", "Materiale", "Længde [m]"],
               [[s.navn, ental.get(s.type, s.type), s.tvaersnit, s.materiale, s.laengde] for s in m.stænger])
    if m.flader:
        doc.add_heading("Plader og vægge", level=2)
        _tabel(doc, ["Navn", "Type", "Tykkelse [mm]", "Materiale"],
               [[f.navn, ental.get(f.type, f.type),
                 None if f.tykkelse is None else round(f.tykkelse * 1000), f.materiale] for f in m.flader])
    if m.understoetninger:
        doc.add_heading("Understøtninger", level=2)
        _tabel(doc, ["Navn", "Type", "Frihedsgrader"],
               [[u.navn, u.type.capitalize(), u.fast] for u in m.understoetninger])

    doc.add_heading("Laster", level=1)
    if m.lasttilfaelde:
        doc.add_heading("Lasttilfælde", level=2)
        pr = m.laster_pr_tilfaelde()
        _tabel(doc, ["Navn", "Type", "Varighed", "Antal laster"],
               [[l.navn, l.type, l.varighed, len(pr.get(l.navn, []))] for l in m.lasttilfaelde])
        if any(l.type == "Egenlast" for l in m.lasttilfaelde):
            doc.add_paragraph("Lasttilfælde af typen Egenlast omfatter konstruktionens egenvægt, "
                              "som FEM-Design beregner automatisk ud fra tværsnit og densitet.")
        for i, lc in enumerate(m.lasttilfaelde, 1):
            if pr.get(lc.navn):
                doc.add_heading(f"Lasttilfælde: {lc.navn}", level=3)
                _tabel(doc, ["Last", "Værdi", "Retning", "Antal"], _lastoversigt(pr[lc.navn]))
                sti = plots.lastplan(m, lc.navn, billedmappe / f"last_{i:02d}.png")
                _figur(doc, sti, f"Laster i lasttilfælde '{lc.navn}'", nr)
    else:
        doc.add_paragraph("Ingen lasttilfælde i modellen.")
    if m.lastkombinationer:
        doc.add_heading("Lastkombinationer", level=2)
        _tabel(doc, ["Kombination", "Type", "Indhold"],
               [[k.navn, k.type, " + ".join(f"{tal(g)}·{n}" for n, g in k.faktorer)] for k in m.lastkombinationer])


def _retning(d) -> str:
    """Kort tekst for en lastretning, fx '−z (nedad)' eller '+x'."""
    L = sum(v * v for v in d) ** 0.5 or 1.0
    enhed = [v / L for v in d]
    for i, akse in enumerate("xyz"):
        if abs(abs(enhed[i]) - 1) < 1e-3:
            tegn = "+" if enhed[i] > 0 else "−"
            return f"{tegn}{akse}" + (" (nedad)" if akse == "z" and tegn == "−" else "")
    return "(" + "; ".join(tal(v, 2) for v in enhed) + ")"


def _lastoversigt(laster) -> list[list]:
    """Laster i ét lasttilfælde samlet pr. (type, værdi, retning)."""
    tael: Counter = Counter()
    for l in laster:
        tael[(l.type, round(abs(l.vaerdi), 6), _retning(l.retning))] += 1
    return [[LASTNAVNE.get(t, t), f"{tal(v)} {ENHED.get(t, '')}", r, n]
            for (t, v, r), n in sorted(tael.items(), key=lambda x: (x[0][0], -x[0][1]))]
