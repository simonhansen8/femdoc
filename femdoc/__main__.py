"""Brug:
    python -m femdoc model.struxml              # rapport direkte fra struxml, uden FEM-Design
    python -m femdoc model.struxml --lav-yaml   # opret projekt.yaml ud fra modellen
    python -m femdoc projekt.yaml [--toer]      # fuld kørsel med FEM-Design og resultater
"""
import argparse
import sys
from pathlib import Path
from . import __version__


def main(argv=None) -> int:
    a = argparse.ArgumentParser(
        prog="femdoc", description="Generér statisk dokumentation (Word) fra en FEM-Design model.",
        epilog="Eksempler:\n"
               "  python -m femdoc model.struxml --navn \"Blok B\" --nummer 24-117\n"
               "  python -m femdoc model.struxml --lav-yaml\n"
               "  python -m femdoc projekt.yaml --toer",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("input", help="model.struxml eller projekt.yaml")
    a.add_argument("--version", action="version", version=f"femdoc {__version__}")
    a.add_argument("--toer", action="store_true",
                   help="(yaml) tør kørsel: spring FEM-Design over, brug eksisterende output")
    g = a.add_argument_group("kun for .struxml")
    g.add_argument("-o", "--output", help="output-mappe (standard: <model>_rapport ved siden af modellen)")
    g.add_argument("--navn", help="projektnavn på forsiden (standard: filnavnet)")
    g.add_argument("--nummer", default="", help="projektnummer")
    g.add_argument("--projekterende", default="", help="initialer for projekterende")
    g.add_argument("--kontrol", default="", help="initialer for kontrollant")
    g.add_argument("--beskrivelse", default="", help="kort beskrivelse på forsiden")
    g.add_argument("--lav-yaml", action="store_true",
                   help="opret en projekt.yaml ud fra modellen i stedet for en rapport")
    args = a.parse_args(argv)

    from .config import indlaes, fra_struxml, skabelon_yaml, KonfigFejl
    from .struxml import StruxmlFejl

    sti = Path(args.input)
    endelse = sti.suffix.lower()
    try:
        if endelse == ".struxml":
            if not sti.is_file():
                raise StruxmlFejl(f"Filen findes ikke: {sti}")
            if args.lav_yaml:
                ud = sti.with_name("projekt.yaml")
                if ud.exists():
                    raise KonfigFejl(f"{ud} findes allerede – slet eller omdøb den først.")
                ud.write_text(skabelon_yaml(sti, args.navn, args.nummer), encoding="utf-8")
                print(f"Oprettet: {ud}\nUdfyld den, og kør:  python -m femdoc {ud}")
                return 0
            from . import rapport
            p = fra_struxml(sti, args.output, args.navn, args.nummer)
            p.projekterende, p.kontrol, p.beskrivelse = args.projekterende, args.kontrol, args.beskrivelse
            p.output.mkdir(parents=True, exist_ok=True)
        elif endelse in (".yaml", ".yml"):
            from . import fem, rapport
            p = indlaes(sti)
            fem.koer(p, toer=args.toer)
        else:
            a.error(f"ukendt filtype '{sti.suffix or sti.name}' – angiv en .struxml eller en projekt.yaml")
        ud = rapport.byg(p)
    except (KonfigFejl, StruxmlFejl) as e:
        print(f"Fejl: {e}", file=sys.stderr)
        return 1
    except ImportError as e:
        if "femdesign" in str(e):
            print("Fejl: FEM-Design-pakken er ikke installeret (pip install FEM-Design), "
                  "og den kræver Windows med FEM-Design. Brug --toer for at genbruge eksisterende CSV.",
                  file=sys.stderr)
            return 1
        raise
    print(f"Rapport gemt: {ud}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
