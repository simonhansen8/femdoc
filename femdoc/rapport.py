"""Samler den endelige Word-rapport."""
from __future__ import annotations
from datetime import date
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor, Cm

from .config import Projekt
from .fem import csv_sti, fd_docx_sti

MAX_RAEKKER = 25  # resten ligger i bilag/CSV


def _forside(doc: Document, p: Projekt):
    doc.add_paragraph()
    t = doc.add_paragraph(p.navn)
    t.runs[0].font.size = Pt(26); t.runs[0].bold = True
    doc.add_paragraph("Statisk dokumentation – FEM-beregning").runs[0].font.size = Pt(14)
    tbl = doc.add_table(rows=0, cols=2)
    tbl.style = "Table Grid"
    for k, v in [("Projektnr.", p.nummer), ("Model", p.model.name),
                 ("Projekterende", p.projekterende), ("Kontrol", p.kontrol),
                 ("Dato", date.today().isoformat())]:
        r = tbl.add_row().cells; r[0].text = k; r[1].text = str(v)
    if p.beskrivelse:
        doc.add_paragraph(); doc.add_paragraph(p.beskrivelse)
    doc.add_page_break()


def _df_tabel(doc: Document, df, kolonne: str | None):
    vis = df
    if kolonne and kolonne in df.columns:
        vis = df.reindex(df[kolonne].abs().sort_values(ascending=False).index)
    vis = vis.head(MAX_RAEKKER)
    t = doc.add_table(rows=1, cols=len(vis.columns))
    t.style = "Light Grid Accent 1"
    for i, k in enumerate(vis.columns):
        t.rows[0].cells[i].text = str(k)
    for _, r in vis.iterrows():
        c = t.add_row().cells
        for i, v in enumerate(r):
            c[i].text = f"{v:.3g}" if isinstance(v, float) else str(v)
    for row in t.rows:
        for c in row.cells:
            for par in c.paragraphs:
                for run in par.runs:
                    run.font.size = Pt(8)
    if len(df) > MAX_RAEKKER:
        doc.add_paragraph(f"Viser de {MAX_RAEKKER} mest kritiske af {len(df)} rækker. "
                          "Fuld liste i bilag (CSV).").runs[0].italic = True


def _sektion(doc: Document, p: Projekt, s, oversigt: list):
    doc.add_heading(s.titel, level=2)
    if s.tekst:
        doc.add_paragraph(s.tekst)
    f = csv_sti(p, s.bsc)
    if not f.exists():
        doc.add_paragraph(f"MANGLER: {f.name} blev ikke genereret.").runs[0].font.color.rgb = RGBColor(0xC0, 0, 0)
        oversigt.append((s.titel, "–", "MANGLER")); return
    from .tabeller import laes_liste  # pandas indlæses kun når der er resultattabeller
    titel, df = laes_liste(f)
    if titel:
        doc.add_paragraph(titel).runs[0].italic = True
    status = "–"
    if s.kolonne and s.kolonne in df.columns:
        mx = df[s.kolonne].abs().max()
        linje = f"Største |{s.kolonne}| = {mx:.3g}"
        if s.graense is not None:
            ok = mx <= s.graense
            status = "OK" if ok else "IKKE OK"
            linje += f"  (grænse {s.graense:g}) → {status}"
        par = doc.add_paragraph(); run = par.add_run(linje); run.bold = True
        if status == "IKKE OK":
            run.font.color.rgb = RGBColor(0xC0, 0, 0)
        oversigt.append((s.titel, f"{mx:.3g}", status))
    else:
        oversigt.append((s.titel, "–", "–"))
    _df_tabel(doc, df, s.kolonne)


def _indsaet_docx(doc: Document, kilde: Path):
    """Kopierer FEM-Designs egen dokumentation (views, figurer) ind i rapporten."""
    try:
        from docxcompose.composer import Composer  # bevarer billeder korrekt
    except ImportError:
        doc.add_paragraph(f"Se bilag: {kilde.name} (installer 'docxcompose' for at flette automatisk).")
        return doc
    doc.add_page_break()
    c = Composer(doc)
    c.append(Document(str(kilde)))
    return c.doc


def byg(p: Projekt) -> Path:
    doc = Document(str(p.word_skabelon)) if p.word_skabelon else Document()
    if not p.word_skabelon:
        for s in doc.sections:
            s.left_margin = s.right_margin = Cm(2)
    _forside(doc, p)

    oversigt: list = []
    if p.sektioner:
        doc.add_heading("Sammendrag", level=1)
        sammendrag_par = doc.add_paragraph()

    # Inputdel direkte fra .struxml (kræver ikke FEM-Design)
    if p.model and p.model.suffix.lower() == ".struxml" and p.model.exists():
        from .struxml import laes
        from .modelrapport import tilfoej
        tilfoej(doc, laes(p.model), p.output / "figurer", p.views)

    if p.sektioner:
        doc.add_heading("Resultater", level=1)
    for s in p.sektioner:
        _sektion(doc, p, s, oversigt)

    if p.sektioner:
        # Sammendragstabel indsættes efter overskriften
        t = doc.add_table(rows=1, cols=3); t.style = "Table Grid"
        for i, h in enumerate(["Eftervisning", "Maks.", "Status"]):
            t.rows[0].cells[i].text = h
        for r in oversigt:
            c = t.add_row().cells
            for i, v in enumerate(r):
                c[i].text = v
        sammendrag_par._p.addnext(t._tbl)

    fd = fd_docx_sti(p)
    if fd.exists():
        doc.add_page_break()
        doc.add_heading("Bilag A – Modelvisninger og resultatplots (FEM-Design)", level=1)
        doc = _indsaet_docx(doc, fd)

    ud = p.output / f"{p.nummer or 'rapport'}_statisk_dokumentation.docx"
    doc.save(str(ud))
    return ud
