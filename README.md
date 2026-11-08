# femdoc – automatisk dokumentation af FEM-Design modeller

Genererer en statisk dokumentation (Word) ud fra en FEM-Design model med få inputs.

## Webside
**https://simonhansen8.github.io/femdoc/** – upload en .struxml og hent rapporten.
Python-koden kører direkte i browseren (Pyodide), så modellen forlader ikke din computer.
Siden udrulles automatisk fra `main` af `.github/workflows/pages.yml`.

## Hurtigt i gang – kun en .struxml
Kræver **ikke** FEM-Design installeret.

```bash
pip install -r requirements.txt
python -m femdoc min_model.struxml --navn "Blok B" --nummer 24-117
```

Rapporten indeholder:
* Modelbeskrivelse (software, norm, antal elementer)
* Modelvisninger tegnet automatisk: isometri fra to sider og plan
* Tabeller over materialer, stangelementer (tværsnit, længde), plader/vægge (tykkelse), understøtninger
* Lasttilfælde med en lastfigur pr. tilfælde og lastkombinationer med partialkoefficienter

**Begrænsning:** en .struxml indeholder modellen, ikke beregningsresultater.
Resultater (udnyttelse, udbøjning, reaktioner) kræver en kørsel i FEM-Design – se nedenfor.

## Fuld kørsel med resultater – projekt.yaml
Ingeniøren udfylder `projekt.yaml` (se `eksempel/projekt.yaml`).

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

## Struktur
| Fil | Indhold |
|---|---|
| `femdoc/struxml.py` | Læser .struxml (geometri, materialer, tværsnit, understøtninger, laster) |
| `femdoc/plots.py` | Modelvisninger og lastfigurer (matplotlib) |
| `femdoc/modelrapport.py` | Rapportafsnit for model og laster |
| `femdoc/fem.py` | Styring af FEM-Design via API'et |
| `femdoc/tabeller.py` | Læser FEM-Designs CSV-lister |
| `femdoc/rapport.py` | Samler Word-rapporten |
| `femdoc/web.py`, `web/` | Websiden (Pyodide) |

## Test
```bash
pip install pytest && python -m pytest
```

Eksempelmodellerne i `eksempel/struxml/` stammer fra StruSofts
[femdesign-api](https://github.com/strusoft/femdesign-api) (MIT/Apache-2.0).
