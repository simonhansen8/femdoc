// Fælles indlæsning af femdoc i Pyodide (bruges af websiden og af CI-testen).
export const PAKKER = ["matplotlib", "lxml", "pyyaml", "micropip", "typing-extensions"];

export async function installerFemdoc(pyodide, hentTekst, status = () => {}) {
  status("Indlæser Python-pakker (matplotlib, lxml) …");
  await pyodide.loadPackage(PAKKER);
  status("Installerer python-docx …");
  const micropip = pyodide.pyimport("micropip");
  await micropip.install("python-docx");
  status("Indlæser femdoc …");
  pyodide.FS.mkdirTree("/app/femdoc");
  // moduler.json skrives af byg_side.sh, så nye moduler kommer automatisk med
  const moduler = JSON.parse(await hentTekst("femdoc/moduler.json"));
  for (const m of moduler) {
    pyodide.FS.writeFile(`/app/femdoc/${m}`, await hentTekst(`femdoc/${m}`));
  }
  await pyodide.runPythonAsync(`
import sys
if "/app" not in sys.path:
    sys.path.insert(0, "/app")
import matplotlib
matplotlib.use("Agg")
from femdoc.web import generer, plan
`);
}

function skrivModel(pyodide, struxmlBytes) {
  pyodide.FS.mkdirTree("/data");
  pyodide.FS.writeFile("/data/model.struxml", struxmlBytes);
}

// Geometri til den interaktive plan (bjælker, søjler, dæk, niveauer, knuder)
export function hentPlan(pyodide, struxmlBytes) {
  skrivModel(pyodide, struxmlBytes);
  const f = pyodide.globals.get("plan");
  try { return JSON.parse(f("/data/model.struxml")); } finally { f.destroy(); }
}

// felter.views: liste af view-definitioner (se femdoc/views.py) eller undefined = standard
export async function genererRapport(pyodide, struxmlBytes, felter) {
  skrivModel(pyodide, struxmlBytes);
  const { views, ...rest } = felter;
  felter = { ...rest, ...(views ? { views: JSON.stringify(views) } : {}) };
  const ud = "/tmp/femdoc_" + Date.now();
  const generer = pyodide.globals.get("generer");
  const res = generer.callKwargs({ struxml: "/data/model.struxml", output: ud, ...felter });
  const js = res.toJs({ dict_converter: Object.fromEntries });
  res.destroy(); generer.destroy();
  return {
    docx: pyodide.FS.readFile(js.docx),
    docxNavn: js.docx.split("/").pop(),
    figurer: js.figurer.map((f) => ({ navn: f.split("/").pop(), data: pyodide.FS.readFile(f) })),
  };
}
