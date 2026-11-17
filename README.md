# femdoc – automatisk dokumentation af FEM-Design modeller

Genererer en statisk dokumentation (Word) ud fra en FEM-Design model med få inputs.

## Webside
**https://simonhansen8.github.io/femdoc/** – upload en .struxml og hent rapporten.
Python-koden kører direkte i browseren (Pyodide), så modellen forlader ikke din computer.
Felterne *Projekterende* og *Kontrol* huskes i browseren til næste gang.
Siden udrulles automatisk fra `main` af `.github/workflows/pages.yml`.

### Selvvalgte visninger
Når modellen er indlæst, vises en plan af den. Klik **Tegn snit** og derefter start- og slutpunkt.
Punkterne fanger knuder og modullinjer, og næsten vandrette eller lodrette linjer rettes ind.
Snittet ses mod venstre for tegneretningen (pilene). Det, planen skærer, tegnes kraftigt som snitflader,
og alt bagved tegnes i opstalt (søjler i fuld højde, bjælker, vægge, dæk og understøtninger). Feltet
*Dybde* begrænser, hvor langt bagved der vises; tomt betyder alt bagved.
Man vælger også, hvilke etageplaner (én pr. kote med bjælker eller dæk) og 3D-visninger der skal med.
De samme visninger kan angives under `rapport.views` i `projekt.yaml` (se `eksempel/projekt.yaml`).

## Hurtigt i gang – kun en .struxml
Kræver **ikke** FEM-Design installeret.

```bash
pip install -r requirements.txt
python -m femdoc min_model.struxml --navn "Blok B" --nummer 24-117 --projekterende SIH --kontrol ABC
python -m femdoc --help        # alle muligheder
```

Rapporten indeholder:
* Forside med projektdata og sidefod med projektnummer og "Side x af y"
* Modelbeskrivelse (software, norm, nationalt anneks, antal elementer)
* Modelvisninger tegnet automatisk: isometri fra to sider og plan
* Materialer (E-modul, karakteristisk styrke, densitet), stangelementer samlet pr. tværsnit og materiale
  med samlet længde og en fuld liste, plader/vægge (tykkelse), understøtninger
* Lasttilfælde med en lastoversigt (værdi, enhed, retning) og en lastfigur pr. tilfælde,
  og lastkombinationer med partialkoefficienter

Tal skrives med decimalkomma. Fejl i inputfilen (forkert filtype, ikke en .struxml, fejl i
`projekt.yaml`) giver en kort fejlbesked i stedet for en Python-traceback.

**Begrænsning:** en .struxml indeholder modellen, ikke beregningsresultater.
Resultater (udnyttelse, udbøjning, reaktioner) kræver en kørsel i FEM-Design – se nedenfor.

## Fuld kørsel med resultater – projekt.yaml
Ingeniøren udfylder `projekt.yaml` (se `eksempel/projekt.yaml`). Man kan få en udfyldt start-fil
med standardvisninger og én etageplan pr. kote ud fra modellen:

```bash
python -m femdoc min_model.struxml --lav-yaml    # skriver projekt.yaml ved siden af modellen
```

Fejl i `projekt.yaml` (manglende felter, stavefejl i en sektion, et snit uden `til`) meldes med
præcis placering. Findes en `kolonne` ikke i CSV-filen, står det med rødt i rapporten sammen med de
kolonner, der findes, og sammendraget viser `KOLONNE MANGLER`.

```
projekt.yaml ──► femdoc ──► FEM-Design (StruSofts API, kun Windows)
                   │          ├─ .dsc dokumentationsskabelon ──► FEM-Designs egne views/plots (bilag)
                   │          └─ .bsc listeskabeloner        ──► CSV-tabeller
                   ├─► struxml ──► modelbeskrivelse, figurer, laster
                   └─► forside + sammendrag (OK / IKKE OK) + kritiske rækker ──► rapport.docx
```

```bash
pip install FEM-Design
python -m femdoc eksempel/projekt.yaml          # med FEM-Design installeret
python -m femdoc eksempel/projekt.yaml --toer   # uden FEM-Design: bruger eksisterende CSV
```

Engangsopsætning: lav en `.dsc` dokumentationsskabelon med de faste resultatviews og
`.bsc` listeskabeloner for de tabeller der skal eftervises, og læg dem under `skabeloner/`.

## Undersøg hvad din FEM-Design kan automatisere
`tools/fd_probe.py` er et lille testprogram (kun Pythons standardbibliotek), som du selv kører på en computer med
FEM-Design. Det læser FEM-Designs `fdscript.xsd` (kun læsning), lister alle scriptkommandoer og kører en testmodel
gennem FEM-Design, så vi kan se, hvilke views og snit FEM-Design selv kan eksportere.

```bash
python tools/fd_probe.py            # finder FEM-Design selv; eller: --fd "C:\...\fd3dstruct.exe"
python tools/fd_probe.py --kun-xsd  # kun læsning af fdscript.xsd, kører ikke FEM-Design
```
Resultatet er `femdoc-test/rapport.md` og en zip, som kan sendes tilbage.

## Struktur
| Fil | Indhold |
|---|---|
| `femdoc/struxml.py` | Læser .struxml (geometri, materialer, tværsnit, understøtninger, laster) |
| `femdoc/plots.py` | Modelvisninger og lastfigurer (matplotlib) |
| `femdoc/modelrapport.py` | Rapportafsnit for model og laster |
| `femdoc/fem.py` | Styring af FEM-Design via API'et |
| `femdoc/tabeller.py` | Læser FEM-Designs CSV-lister |
| `femdoc/tal.py` | Talformat med decimalkomma |
| `femdoc/rapport.py` | Samler Word-rapporten |
| `femdoc/web.py`, `web/` | Websiden (Pyodide) |

## Test
```bash
pip install pytest && python -m pytest
```

## Testmodel
`eksempel/struxml/kontorbygning.struxml` er en lille kontorbygning i 2 etager: stålskelet
(HE-B 200 søjler, IPE 300 bjælker, S 355) med 220 mm betondæk (C30/37) på et modulnet på 3 × 6,0 m og 2 × 5,0 m.
Den har charnierlejer, 5 lasttilfælde (egenlast, installationer, nyttelast, sne og vind) og 6 lastkombinationer.
Filen er valideret mod `strusoft.xsd` og genereres med `eksempel/generer_testmodel.py`.

De øvrige eksempelmodeller i `eksempel/struxml/` stammer fra StruSofts
[femdesign-api](https://github.com/strusoft/femdesign-api) (MIT/Apache-2.0).
