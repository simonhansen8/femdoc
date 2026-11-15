"""Indlæser og validerer projektets input (projekt.yaml)."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class TabelSektion:
    titel: str
    bsc: str                    # FEM-Design listeskabelon (.bsc) der eksporteres til CSV
    kolonne: str | None = None  # kolonne der opsummeres (max |værdi|)
    graense: float | None = None  # fx 1.0 for udnyttelsesgrad
    tekst: str = ""


@dataclass
class Projekt:
    navn: str
    nummer: str
    beskrivelse: str
    projekterende: str
    kontrol: str
    model: Path
    fd_sti: str
    output: Path
    dokumentationsskabelon: Path | None   # FEM-Design .dsc med alle views
    word_skabelon: Path | None            # firmaets .docx/.dotx
    koer_analyse: bool
    sektioner: list[TabelSektion] = field(default_factory=list)
    basis: Path = Path(".")
    views: list[dict] | None = None      # None = standardvisninger


def _sti(basis: Path, v):
    if not v:
        return None
    p = Path(v)
    return p if p.is_absolute() else (basis / p).resolve()


class KonfigFejl(ValueError):
    """Fejl i projekt.yaml, formuleret så ingeniøren kan rette den."""


def _kraev(d, noegle: str, sted: str):
    if not isinstance(d, dict) or d.get(noegle) in (None, ""):
        raise KonfigFejl(f"projekt.yaml mangler '{noegle}' under '{sted}'.")
    return d[noegle]


def indlaes(sti: str | Path) -> Projekt:
    sti = Path(sti).resolve()
    basis = sti.parent
    if not sti.is_file():
        raise KonfigFejl(f"Filen findes ikke: {sti}")
    try:
        d = yaml.safe_load(sti.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise KonfigFejl(f"{sti.name} er ikke gyldig YAML:\n{e}") from None
    if not isinstance(d, dict):
        raise KonfigFejl(f"{sti.name} ser ikke ud som en projekt.yaml (se eksempel/projekt.yaml).")
    p, fd, rap = _kraev(d, "projekt", "rod"), d.get("fem_design") or {}, d.get("rapport") or {}
    _kraev(p, "navn", "projekt"); _kraev(fd, "model", "fem_design")
    for i, s in enumerate(rap.get("sektioner") or [], 1):
        for k in ("titel", "bsc"):
            _kraev(s, k, f"rapport.sektioner nr. {i}")
        ukendt = set(s) - set(TabelSektion.__dataclass_fields__)
        if ukendt:
            raise KonfigFejl(f"Ukendt felt {', '.join(sorted(ukendt))} i rapport.sektioner nr. {i} "
                             f"(tilladt: {', '.join(TabelSektion.__dataclass_fields__)}).")
    from .views import valider
    views = rap.get("views")
    try:
        valider(views)
    except ValueError as e:
        raise KonfigFejl(f"Fejl i rapport.views: {e}") from None
    return Projekt(
        navn=p["navn"], nummer=str(p.get("nummer", "")),
        beskrivelse=p.get("beskrivelse", ""),
        projekterende=p.get("projekterende", ""), kontrol=p.get("kontrol", ""),
        model=_sti(basis, fd["model"]),
        fd_sti=fd.get("program", r"C:\Program Files\StruSoft\FEM-Design 24\fd3dstruct.exe"),
        output=_sti(basis, rap.get("output", "output")),
        dokumentationsskabelon=_sti(basis, fd.get("dokumentationsskabelon")),
        word_skabelon=_sti(basis, rap.get("word_skabelon")),
        koer_analyse=bool(fd.get("koer_analyse", False)),
        sektioner=[TabelSektion(**{**s, "bsc": str(_sti(basis, s["bsc"]))})
                   for s in rap.get("sektioner") or []],
        basis=basis,
        views=views,
    )


def fra_struxml(sti: str | Path, output: str | Path | None = None, navn: str | None = None,
                nummer: str = "", views: list[dict] | None = None) -> Projekt:
    """Minimal opsætning når man kun har en .struxml (ingen projekt.yaml)."""
    sti = Path(sti).resolve()
    return Projekt(
        navn=navn or sti.stem, nummer=nummer, beskrivelse="", projekterende="", kontrol="",
        model=sti, fd_sti="", output=Path(output).resolve() if output else sti.parent / f"{sti.stem}_rapport",
        dokumentationsskabelon=None, word_skabelon=None, koer_analyse=False, basis=sti.parent,
        views=views)


def skabelon_yaml(struxml: str | Path, navn: str | None = None, nummer: str = "") -> str:
    """En udfyldt projekt.yaml til modellen, med en etageplan pr. kote."""
    from .struxml import laes
    from .views import niveauer, STANDARD
    sti = Path(struxml)
    m = laes(sti)
    q = lambda t: '"' + str(t).replace("\\", "\\\\").replace('"', '\\"') + '"'
    linjer = [
        "# Det eneste ingeniøren udfylder pr. projekt. Se eksempel/projekt.yaml for alle muligheder.",
        "projekt:",
        f"  navn: {q(navn or sti.stem)}",
        f"  nummer: {q(nummer)}",
        '  beskrivelse: ""',
        '  projekterende: ""',
        '  kontrol: ""',
        "",
        "fem_design:",
        r"  program: 'C:\Program Files\StruSoft\FEM-Design 24\fd3dstruct.exe'",
        f"  model: {q(sti.name)}",
        "  koer_analyse: false",
        "  # dokumentationsskabelon: \"skabeloner/standard_views.dsc\"",
        "",
        "rapport:",
        '  output: "output"',
        "  # Snit: lodret plan gennem linjen fra -> til (x, y i meter), set mod venstre for tegneretningen.",
        "  views:",
    ]
    for v in STANDARD:
        linjer.append("    - {" + ", ".join(f"{k}: {q(x) if isinstance(x, str) and k == 'navn' else x}"
                                             for k, x in v.items()) + "}")
    for z in niveauer(m):
        linjer.append(f"    - {{type: plan, z: {z:g}}}")
    x0, y0, x1, y1 = _bbox(m)
    linjer += [
        f"    # - {{type: snit, navn: \"A-A\", fra: [{x0 - 1:g}, {(y0 + y1) / 2:g}], til: [{x1 + 1:g}, {(y0 + y1) / 2:g}]}}",
        "  word_skabelon: null               # fx \"skabeloner/firma.dotx\"",
        "  # Resultattabeller fra FEM-Design (kræver .bsc listeskabeloner):",
        "  sektioner: []",
        "  #  - titel: \"Udnyttelse af stålbjælker\"",
        "  #    bsc: \"skabeloner/steel_utilization.bsc\"",
        "  #    kolonne: \"Max.\"",
        "  #    graense: 1.0",
        "",
    ]
    return "\n".join(linjer)


def _bbox(m) -> tuple[float, float, float, float]:
    from .plots import _alle_punkter
    pts = _alle_punkter(m) or [(0, 0, 0)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)
