"""Indgang for websiden (kører i browseren via Pyodide)."""
from __future__ import annotations
import json
from pathlib import Path
from .config import fra_struxml
from . import rapport


def plan(struxml: str) -> str:
    """Geometri til den interaktive plan på websiden (JSON)."""
    from .struxml import laes
    from .views import plan_data
    return json.dumps(plan_data(laes(struxml)))


def generer(struxml: str, navn: str = "", nummer: str = "", projekterende: str = "",
            kontrol: str = "", beskrivelse: str = "", output: str = "/tmp/femdoc_ud",
            views: str | None = None) -> dict:
    """views: JSON-liste med view-definitioner (se femdoc/views.py); None = standard."""
    p = fra_struxml(struxml, output, navn or None, nummer, json.loads(views) if views else None)
    p.projekterende, p.kontrol, p.beskrivelse = projekterende, kontrol, beskrivelse
    Path(output).mkdir(parents=True, exist_ok=True)
    ud = rapport.byg(p)
    # Samme rækkefølge som i rapporten: visninger først, derefter lastfigurer
    figurer = sorted((str(f) for f in (Path(output) / "figurer").glob("*.png")),
                     key=lambda f: (Path(f).name.startswith("last_"), Path(f).name))
    return {"docx": str(ud), "figurer": figurer}
