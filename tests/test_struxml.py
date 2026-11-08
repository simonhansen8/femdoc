from pathlib import Path
from docx import Document
from femdoc.struxml import laes
from femdoc.config import fra_struxml
from femdoc import rapport

EKS = Path(__file__).parent.parent / "eksempel" / "struxml"


def test_laes_bjaelke():
    m = laes(EKS / "concrete_beam.struxml")
    assert len(m.stænger) == 1
    b = m.stænger[0]
    assert b.materiale == "C40/50" and abs(b.laengde - 6.0) < 1e-6
    assert [k.navn for k in m.lastkombinationer] == ["ULS_1"]


def test_laes_testmodel():
    m = laes(EKS / "testmodel.struxml")
    assert len(m.stænger) == 15 and len(m.flader) == 15
    assert ("ll", 1.5) in m.lastkombinationer[1].faktorer


def test_rapport_fra_struxml(tmp_path):
    p = fra_struxml(EKS / "sample_slab.struxml", tmp_path, "Test")
    ud = rapport.byg(p)
    d = Document(str(ud))
    overskrifter = [x.text for x in d.paragraphs if x.style.name.startswith("Heading")]
    assert "Modelbeskrivelse" in overskrifter and "Laster" in overskrifter
    assert len(d.inline_shapes) >= 4


def test_kontorbygning():
    m = laes(EKS / "kontorbygning.struxml")
    assert len(m.stænger) == 24 + 34 and len(m.flader) == 2
    assert len(m.understoetninger) == 12 and len(m.lastkombinationer) == 6
    assert {s.tvaersnit for s in m.stænger} == {"HE-B 200", "IPE 300"}


def test_views_snit_og_plan(tmp_path):
    from femdoc.views import tegn, plan_data
    m = laes(EKS / "kontorbygning.struxml")
    assert plan_data(m)["niveauer"] == [3.5, 7.0]
    views = [{"type": "oversigt"}, {"type": "plan", "z": 3.5},
             {"type": "snit", "navn": "A-A", "fra": [-1, 5], "til": [19, 5], "dybde": 1}]
    figurer = tegn(m, views, tmp_path)
    assert [t for _, t in figurer] == ["Plan med snitmarkeringer", "Plan kote 3,5 m", "Snit A-A"]
    assert all(f.stat().st_size > 10_000 for f, _ in figurer)


def test_rapport_med_views(tmp_path):
    p = fra_struxml(EKS / "sample_slab.struxml", tmp_path, "Test",
                    views=[{"type": "snit", "navn": "C-C", "fra": [0, 8], "til": [12, 8], "dybde": 1}])
    d = Document(str(rapport.byg(p)))
    tekster = [x.text for x in d.paragraphs]
    assert any(t.startswith("Figur 1: Snit C-C") for t in tekster)
