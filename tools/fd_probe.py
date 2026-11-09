"""fd_probe – undersøger hvad din FEM-Design kan automatisere af views, snit og dokumentation.

Kør på en Windows-maskine med FEM-Design installeret (kun Pythons standardbibliotek):

    python tools/fd_probe.py                 # finder FEM-Design selv
    python tools/fd_probe.py --fd "C:\\Program Files\\StruSoft\\FEM-Design 24\\fd3dstruct.exe"

Programmet
  1. læser (kun læser) FEM-Designs fdscript.xsd og example.fdscript og lister alle scriptkommandoer,
  2. kører en lille test: åbner en .struxml, gemmer dokumentationen som .docx og undersøger indholdet,
  3. skriver rapport.md og en zip i en NY mappe (standard: femdoc-test ved siden af scriptet).
Det ændrer intet i FEM-Designs installation og rører ikke dine andre filer.
"""
from __future__ import annotations
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MODEL_URL = "https://raw.githubusercontent.com/simonhansen8/femdoc/main/eksempel/struxml/kontorbygning.struxml"
NOEGLEORD = ("view", "picture", "image", "window", "section", "snit", "export", "emf", "png", "jpg", "bmp",
             "dxf", "dwg", "pdf", "doc", "draw", "screen", "print", "template", "child", "save")


def find_fd(arg: str | None) -> Path | None:
    if arg:
        p = Path(arg)
        return p if p.exists() else None
    kandidater = []
    for rod in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        kandidater += glob.glob(os.path.join(rod, "StruSoft", "FEM-Design*", "fd3dstruct.exe"))
    kandidater.sort(key=lambda s: [int(x) for x in re.findall(r"\d+", s)] or [0], reverse=True)
    return Path(kandidater[0]) if kandidater else None


def tag(e) -> str:
    return e.tag.split("}", 1)[1] if "}" in e.tag else e.tag


def laes_xsd(sti: Path) -> list[dict]:
    """Alle elementer/typer i fdscript.xsd med attributter og vaerdier (fixed/default)."""
    rod = ET.parse(sti).getroot()
    ud = []
    for e in rod.iter():
        t = tag(e)
        if t not in ("element", "complexType", "simpleType", "attribute"):
            continue
        navn = e.get("name") or e.get("ref")
        if not navn:
            continue
        ud.append({"art": t, "navn": navn, "type": e.get("type", ""), "fixed": e.get("fixed", ""),
                   "default": e.get("default", ""), "use": e.get("use", "")})
    return ud


def kommandoer(xsd_poster: list[dict], xsd_sti: Path) -> dict[str, dict]:
    """Elementer hvis navn starter med cmd, med deres child-elementer og 'command'-attribut."""
    rod = ET.parse(xsd_sti).getroot()
    res: dict[str, dict] = {}
    for e in rod.iter():
        if tag(e) == "element" and (e.get("name") or "").lower().startswith("cmd"):
            navn = e.get("name")
            born = [c.get("name") or c.get("ref") for c in e.iter() if tag(c) == "element" and c is not e]
            attrs = {a.get("name"): (a.get("fixed") or a.get("default") or "") for a in e.iter() if tag(a) == "attribute"}
            res[navn] = {"born": [b for b in born if b], "attributter": attrs,
                         "dok": " ".join((d.text or "").strip() for d in e.iter() if tag(d) == "documentation")}
    return res


def skriv_script(sti: Path, log: Path, model: Path, docx: Path, beregn: bool) -> None:
    dele = ['<?xml version="1.0" encoding="utf-8"?>',
            '<fdscript xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="fdscript.xsd">',
            '<fdscriptheader fContinueOnError="1" fIgnoreParseError="1">',
            "<title>femdoc probe</title><version>2400</version><module>SFRAME</module>",
            f"<logfile>{log}</logfile></fdscriptheader>",
            f'<cmdopen command="; CXL CS2SHELL OPEN"><filename>{model}</filename></cmdopen>']
    if beregn:
        # Samme format som StruSofts Python-API (Analysis.StaticAnalysis): lasttilfaelde og kombinationer
        attrs = {k: "0" for k in ("calcGmax", "calcStage", "calcImpf", "calcStab", "calcFreq", "calcSeis",
                                  "calcFootfall", "calcMovingLoad", "calcThGrounAcc", "calcThExforce",
                                  "calcPeriodicExc", "calcStoreyFreq", "calcBedding", "calcDesign",
                                  "diaphragm", "peaksmoothings")}
        attrs.update(calcCase="1", calcComb="1", elemfine="1")
        a = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        dele.append(f'<cmdcalculation command="; CXL $MODULE CALC"><analysis {a}/></cmdcalculation>')
    dele.append(f'<cmdsavedocx command="$ DOC SAVEDOCX"><filename>{docx}</filename></cmdsavedocx>')
    dele.append("</fdscript>")
    sti.write_text("\n".join(dele), encoding="utf-8")


def koer_fd(fd: Path, script: Path, log: Path, timeout: int) -> tuple[str, str]:
    env = dict(os.environ, FD_NOLOGO="1")
    try:
        p = subprocess.run([str(fd), "/s", str(script)], env=env, timeout=timeout,
                           capture_output=True, text=True, errors="replace")
        status = f"exitkode {p.returncode}"
    except subprocess.TimeoutExpired:
        status = f"TIMEOUT efter {timeout} s (FEM-Design lukkes ikke af sig selv?)"
    except Exception as ex:  # noqa: BLE001
        status = f"fejl: {ex}"
    logtekst = log.read_text(encoding="utf-8", errors="replace") if log.exists() else "(ingen logfil)"
    return status, logtekst


def docx_indhold(docx: Path) -> str:
    if not docx.exists():
        return "docx blev ikke oprettet."
    with zipfile.ZipFile(docx) as z:
        medier = [(i.filename, i.file_size) for i in z.infolist() if i.filename.startswith("word/media/")]
        tekst = z.read("word/document.xml").decode("utf-8", "replace")
    afsnit = re.findall(r"<w:t[^>]*>([^<]+)</w:t>", tekst)
    ud = [f"- størrelse: {docx.stat().st_size / 1024:.0f} kB", f"- billeder i docx: {len(medier)}"]
    ud += [f"  - {n} ({s / 1024:.0f} kB)" for n, s in medier[:30]]
    ud.append(f"- første tekster: {' | '.join(afsnit[:25])}")
    return "\n".join(ud)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fd", help="sti til fd3dstruct.exe (ellers søges automatisk)")
    ap.add_argument("--model", help="egen .struxml i stedet for at hente kontorbygning-eksemplet")
    ap.add_argument("--ud", default=str(Path(__file__).resolve().parent.parent / "femdoc-test"),
                    help="ny mappe til resultater")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--kun-xsd", action="store_true", help="læs kun fdscript.xsd, kør ikke FEM-Design")
    args = ap.parse_args()

    ud = Path(args.ud)
    ud.mkdir(parents=True, exist_ok=True)
    rapport = ["# FEM-Design probe", ""]

    fd = find_fd(args.fd)
    if not fd:
        print("Kunne ikke finde fd3dstruct.exe. Angiv den med --fd.")
        return 2
    rapport.append(f"- FEM-Design: `{fd}`")
    rapport.append(f"- Python: {sys.version.split()[0]} på {sys.platform}")

    # 1) fdscript.xsd og example.fdscript (kun læsning)
    inst = fd.parent
    xsd = next(iter(sorted(inst.rglob("fdscript.xsd"))), None)
    eks = next(iter(sorted(inst.rglob("example.fdscript"))) , None) or next(iter(sorted(inst.rglob("*.fdscript"))), None)
    rapport.append(f"- fdscript.xsd: `{xsd}`")
    rapport.append(f"- eksempelscript: `{eks}`")
    if xsd:
        shutil.copy(xsd, ud / "fdscript.xsd")
        try:
            cmds = kommandoer(laes_xsd(xsd), xsd)
        except ET.ParseError as ex:
            cmds = {}
            rapport.append(f"- kunne ikke parse xsd: {ex}")
        rapport += ["", f"## Scriptkommandoer i fdscript.xsd ({len(cmds)})", "",
                    "| Kommando | `command`-attribut | Underelementer |", "|---|---|---|"]
        for navn, d in sorted(cmds.items()):
            cmdattr = d["attributter"].get("command", "")
            rapport.append(f"| {navn} | {cmdattr} | {', '.join(d['born'][:12])} |")
        interessante = {n: d for n, d in cmds.items()
                        if any(k in (n + " " + d["attributter"].get("command", "") + " " + " ".join(d["born"])).lower()
                               for k in NOEGLEORD)}
        rapport += ["", "### Kommandoer der kan have med views, billeder, snit, eksport eller dokumentation at gøre", ""]
        for navn, d in sorted(interessante.items()):
            rapport.append(f"- **{navn}** `{d['attributter'].get('command', '')}`: {', '.join(d['born'])} {d['dok']}")
    if eks:
        shutil.copy(eks, ud / "example.fdscript")

    if args.kun_xsd:
        (ud / "rapport.md").write_text("\n".join(rapport), encoding="utf-8")
        print(f"Rapport: {ud / 'rapport.md'}")
        return 0

    # 2) modeltest
    model = Path(args.model) if args.model else ud / "kontorbygning.struxml"
    if not model.exists():
        try:
            urllib.request.urlretrieve(MODEL_URL, model)
        except Exception as ex:  # noqa: BLE001
            rapport.append(f"\nKunne ikke hente testmodellen ({ex}). Læg kontorbygning.struxml i {ud} og kør igen.")
            (ud / "rapport.md").write_text("\n".join(rapport), encoding="utf-8")
            return 3
    for navn, beregn in (("uden_beregning", False), ("med_beregning", True)):
        script, log, docx = ud / f"{navn}.fdscript", ud / f"{navn}.log", ud / f"{navn}.docx"
        skriv_script(script, log, model.resolve(), docx, beregn)
        print(f"Kører FEM-Design ({navn}) … (kan tage et par minutter)")
        status, logtekst = koer_fd(fd, script, log, args.timeout)
        rapport += ["", f"## Test: {navn}", "", f"- {status}", "- logfil (uddrag):", "```", logtekst[-4000:], "```",
                    "", "- docx:", docx_indhold(docx)]

    (ud / "rapport.md").write_text("\n".join(rapport), encoding="utf-8")
    zip_sti = ud.with_suffix(".zip")
    with zipfile.ZipFile(zip_sti, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ud.rglob("*"):
            if f.is_file() and f.stat().st_size < 20_000_000:
                z.write(f, f.relative_to(ud))
    print(f"\nFærdig.\n  Rapport: {ud / 'rapport.md'}\n  Zip til at sende tilbage: {zip_sti}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
