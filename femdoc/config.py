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


def _sti(basis: Path, v):
    if not v:
        return None
    p = Path(v)
    return p if p.is_absolute() else (basis / p).resolve()


def indlaes(sti: str | Path) -> Projekt:
    sti = Path(sti).resolve()
    basis = sti.parent
    d = yaml.safe_load(sti.read_text(encoding="utf-8"))
    p, fd, rap = d["projekt"], d.get("fem_design", {}), d.get("rapport", {})
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
                   for s in rap.get("sektioner", [])],
        basis=basis,
    )


def fra_struxml(sti: str | Path, output: str | Path | None = None, navn: str | None = None,
                nummer: str = "") -> Projekt:
    """Minimal opsætning når man kun har en .struxml (ingen projekt.yaml)."""
    sti = Path(sti).resolve()
    return Projekt(
        navn=navn or sti.stem, nummer=nummer, beskrivelse="", projekterende="", kontrol="",
        model=sti, fd_sti="", output=Path(output).resolve() if output else sti.parent / f"{sti.stem}_rapport",
        dokumentationsskabelon=None, word_skabelon=None, koer_analyse=False, basis=sti.parent)
