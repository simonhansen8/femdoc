"""Styring af FEM-Design via StruSofts officielle API (pip install FEM-Design).

Kører kun på Windows med FEM-Design installeret. I 'tør' tilstand (dry run)
springes FEM-Design over, og eksisterende CSV/DOCX i output-mappen bruges,
så rapportdelen kan udvikles og testes uden licens.
"""
from __future__ import annotations
from pathlib import Path
from .config import Projekt


def csv_sti(p: Projekt, bsc: str) -> Path:
    return p.output / "tabeller" / (Path(bsc).stem + ".csv")


def fd_docx_sti(p: Projekt) -> Path:
    return p.output / "fd_dokumentation.docx"


def koer(p: Projekt, toer: bool = False) -> None:
    (p.output / "tabeller").mkdir(parents=True, exist_ok=True)
    if toer:
        print("[tør kørsel] springer FEM-Design over")
        return

    from femdesign.comunication import FemDesignConnection, Verbosity  # type: ignore
    from femdesign.calculate.analysis import Analysis  # type: ignore

    with FemDesignConnection(fd_path=p.fd_sti, minimized=True,
                             output_dir=str(p.output / "fd_log")) as fd:
        fd.SetVerbosity(Verbosity.SCRIPT_LOG_LINES)
        fd.Open(str(p.model))
        if p.koer_analyse:
            fd.RunAnalysis(Analysis.StaticAnalysis())
        # Projektinfo -> vises i FEM-Designs egen hoved/fod i dokumentationen
        fd.SetProjectDescription(p.navn, p.beskrivelse, p.projekterende,
                                 p.kontrol, p.nummer)
        # 1) Views/figurer: FEM-Designs dokumentationsskabelon (.dsc)
        if p.dokumentationsskabelon:
            fd.SaveDocx(str(fd_docx_sti(p)), str(p.dokumentationsskabelon))
        # 2) Tal: listeskabeloner (.bsc) -> CSV
        for s in p.sektioner:
            fd.GenerateListTables(s.bsc, str(csv_sti(p, s.bsc)))
