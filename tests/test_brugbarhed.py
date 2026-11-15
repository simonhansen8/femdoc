"""Tests for fejlbeskeder, talformat, materialer, CLI og projekt.yaml."""
import shutil
from pathlib import Path
import pytest
import yaml
from docx import Document

from femdoc.tal import tal
from femdoc.struxml import laes, StruxmlFejl
from femdoc.config import indlaes, skabelon_yaml, KonfigFejl
from femdoc.__main__ import main
from femdoc import rapport

ROD = Path(__file__).parent.parent
EKS = ROD / "eksempel" / "struxml"


@pytest.mark.parametrize("v, ud", [(3.5, "3,5"), (7.85, "7,85"), (210.0, "210"), (1234.7, "1235"),
                                   (-0.000012, "-1,20e-05"), (0.0, "0"), (None, "–"), (float("nan"), "–"),
                                   (1.0, "1"), (0.45, "0,45"), (33.33333, "33,3")])
def test_tal(v, ud):
    assert tal(v) == ud


def test_materialer_bruger_karakteristisk_e_modul():
    """Biblioteksmaterialer har E_0 = 0; så skal Ek/Ecm bruges i stedet for 0 GPa."""
    mat = {d["Navn"]: d for d in laes(EKS / "kontorbygning.struxml").materiale_data}
    assert mat["S 355"]["E [GPa]"] == 210 and mat["S 355"]["Styrke [MPa]"] == 355
    assert mat["C30/37"]["E [GPa]"] == 33 and mat["C30/37"]["Type"] == "Beton"
    arm = [d for d in laes(EKS / "concrete_beam.struxml").materiale_data if d["Type"] == "Armering"]
    assert arm and arm[0]["E [GPa]"] == 200 and arm[0]["Styrke [MPa]"] == 500


def test_laes_giver_forstaaelige_fejl(tmp_path):
    with pytest.raises(StruxmlFejl, match="findes ikke"):
        laes(tmp_path / "mangler.struxml")
    (tmp_path / "a.struxml").write_text("ikke xml")
    with pytest.raises(StruxmlFejl, match="ikke gyldig XML"):
        laes(tmp_path / "a.struxml")
    (tmp_path / "b.struxml").write_text("<andet/>")
    with pytest.raises(StruxmlFejl, match="ligner ikke"):
        laes(tmp_path / "b.struxml")


def _yaml(tmp_path, d) -> Path:
    f = tmp_path / "projekt.yaml"
    f.write_text(yaml.safe_dump(d, allow_unicode=True), encoding="utf-8")
    return f


@pytest.mark.parametrize("d, besked", [
    ({"projekt": {"navn": "x"}}, "'model' under 'fem_design'"),
    ({"fem_design": {"model": "m.struxml"}}, "'projekt'"),
    ({"projekt": {"navn": "x"}, "fem_design": {"model": "m"},
      "rapport": {"views": [{"type": "snit", "fra": [0, 0]}]}}, "mangler 'til'"),
    ({"projekt": {"navn": "x"}, "fem_design": {"model": "m"},
      "rapport": {"views": [{"type": "perspektiv"}]}}, "skal have type"),
    ({"projekt": {"navn": "x"}, "fem_design": {"model": "m"},
      "rapport": {"sektioner": [{"titel": "t", "bsc": "a.bsc", "graense": 1, "kolone": "x"}]}}, "Ukendt felt kolone"),
])
def test_projekt_yaml_fejl(tmp_path, d, besked):
    with pytest.raises(KonfigFejl, match=besked):
        indlaes(_yaml(tmp_path, d))


def test_cli_fejl_uden_traceback(tmp_path, capsys):
    assert main([str(tmp_path / "mangler.struxml")]) == 1
    assert "findes ikke" in capsys.readouterr().err
    (tmp_path / "x.struxml").write_text("<andet/>")
    assert main([str(tmp_path / "x.struxml")]) == 1
    with pytest.raises(SystemExit):
        main([str(ROD / "README.md")])


def test_cli_struxml_med_projektfelter(tmp_path):
    assert main([str(EKS / "concrete_beam.struxml"), "-o", str(tmp_path), "--nummer", "24-117",
                 "--projekterende", "SIH", "--kontrol", "ABC"]) == 0
    d = Document(str(tmp_path / "24-117_statisk_dokumentation.docx"))
    forside = [c.text for r in d.tables[0].rows for c in r.cells]
    assert "SIH" in forside and "ABC" in forside
    assert "Side" in d.sections[0].footer.paragraphs[0].text


def test_lav_yaml_giver_gyldigt_projekt(tmp_path):
    model = tmp_path / "kontorbygning.struxml"
    shutil.copy(EKS / "kontorbygning.struxml", model)
    assert main([str(model), "--lav-yaml", "--navn", "Kontor \"A\""]) == 0
    p = indlaes(tmp_path / "projekt.yaml")
    assert p.navn == 'Kontor "A"' and p.model == model.resolve()
    assert [v["z"] for v in p.views if v["type"] == "plan"] == [3.5, 7.0]
    assert main([str(model), "--lav-yaml"]) == 1      # overskriver ikke en eksisterende fil
    assert "projekt:" in skabelon_yaml(model)


def test_forkert_kolonne_giver_advarsel(tmp_path):
    (tmp_path / "output" / "tabeller").mkdir(parents=True)
    shutil.copy(ROD / "eksempel/output/tabeller/steel_utilization.csv", tmp_path / "output" / "tabeller")
    f = _yaml(tmp_path, {"projekt": {"navn": "x", "nummer": "1"},
                         "fem_design": {"model": str(EKS / "concrete_beam.struxml")},
                         "rapport": {"views": [], "sektioner": [
                             {"titel": "Stål", "bsc": "steel_utilization.bsc", "kolonne": "Maks", "graense": 1}]}})
    d = Document(str(rapport.byg(indlaes(f))))
    tekst = "\n".join(p.text for p in d.paragraphs)
    assert "Kolonnen 'Maks' findes ikke" in tekst
    assert "KOLONNE MANGLER" in [c.text for c in d.tables[1].rows[1].cells]


def test_lastoversigt_i_rapport(tmp_path):
    d = Document(str(rapport.byg(__import__("femdoc.config", fromlist=["x"]).fra_struxml(
        EKS / "kontorbygning.struxml", tmp_path, views=[]))))
    celler = [c.text for t in d.tables for r in t.rows for c in r.cells]
    assert "2,5 kN/m²" in celler and "−z (nedad)" in celler and "+x" in celler
    assert any("1,5·Nyttelast kat. B" in c for c in celler)
