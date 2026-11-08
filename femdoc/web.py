"""Indgang for websiden (kører i browseren via Pyodide)."""
from __future__ import annotations
from pathlib import Path
from .config import fra_struxml
from . import rapport


def generer(struxml: str, navn: str = "", nummer: str = "", projekterende: str = "",
            kontrol: str = "", beskrivelse: str = "", output: str = "/tmp/femdoc_ud") -> dict:
    p = fra_struxml(struxml, output, navn or None, nummer)
    p.projekterende, p.kontrol, p.beskrivelse = projekterende, kontrol, beskrivelse
    Path(output).mkdir(parents=True, exist_ok=True)
    ud = rapport.byg(p)
    figurer = sorted(str(f) for f in (Path(output) / "figurer").glob("*.png"))
    return {"docx": str(ud), "figurer": figurer}
