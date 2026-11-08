"""Brug:
    python -m femdoc model.struxml              # rapport direkte fra struxml, uden FEM-Design
    python -m femdoc projekt.yaml [--toer]      # fuld kørsel med FEM-Design og resultater
"""
import argparse
from pathlib import Path
from .config import indlaes, fra_struxml
from . import fem, rapport


def main():
    a = argparse.ArgumentParser(prog="femdoc", description="Generér FEM-Design dokumentation")
    a.add_argument("input", help="model.struxml eller projekt.yaml")
    a.add_argument("--toer", action="store_true",
                   help="(yaml) tør kørsel: spring FEM-Design over, brug eksisterende output")
    a.add_argument("-o", "--output", help="(struxml) output-mappe")
    a.add_argument("--navn", help="(struxml) projektnavn på forsiden")
    a.add_argument("--nummer", default="", help="(struxml) projektnummer")
    args = a.parse_args()

    if Path(args.input).suffix.lower() == ".struxml":
        p = fra_struxml(args.input, args.output, args.navn, args.nummer)
        p.output.mkdir(parents=True, exist_ok=True)
    else:
        p = indlaes(args.input)
        fem.koer(p, toer=args.toer)
    print(f"Rapport gemt: {rapport.byg(p)}")


if __name__ == "__main__":
    main()
