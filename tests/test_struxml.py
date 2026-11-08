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
