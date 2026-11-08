"""Læser FEM-Designs CSV-lister (tab-separeret, titellinje + kolonneoverskrift)."""
from __future__ import annotations
from pathlib import Path
import io
import pandas as pd


def laes_liste(sti: Path) -> tuple[str, pd.DataFrame]:
    tekst = sti.read_text(encoding="utf-8-sig", errors="replace")
    linjer = [l for l in tekst.splitlines()]
    # Første ikke-tomme linje uden tab er listens titel
    titel = ""
    while linjer and "\t" not in linjer[0]:
        if linjer[0].strip() and not titel:
            titel = linjer[0].strip()
        linjer.pop(0)
    # Stop ved første tomme linje (FD kan lægge flere blokke i samme fil)
    blok = []
    for l in linjer:
        if not l.strip():
            if blok:
                break
            continue
        blok.append(l)
    df = pd.read_csv(io.StringIO("\n".join(blok)), sep="\t")
    # Komma-decimaler (regional=True) -> tal
    for k in df.columns:
        if not pd.api.types.is_numeric_dtype(df[k]):
            konv = pd.to_numeric(df[k].astype(str).str.replace(",", ".", regex=False),
                                 errors="coerce")
            if konv.notna().mean() > 0.8:
                df[k] = konv
    return titel, df
