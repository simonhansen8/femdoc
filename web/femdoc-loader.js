// Fælles indlæsning af femdoc i Pyodide (bruges af websiden og af CI-testen).
export const MODULER = ["__init__", "config", "fem", "modelrapport", "plots",
  "rapport", "struxml", "tabeller", "web"];
export const PAKKER = ["matplotlib", "lxml", "pyyaml", "micropip", "typing-extensions"];

export async function installerFemdoc(pyodide, hentTekst, status = () => {}) {
  status("Indlæser Python-pakker (matplotlib, lxml) …");
  await pyodide.loadPackage(PAKKER);
  status("Installerer python-docx …");
  const micropip = pyodide.pyimport("micropip");
  await micropip.install("python-docx");
  status("Indlæser femdoc …");
  pyodide.FS.mkdirTree("/app/femdoc");
  for (const m of MODULER) {
    pyodide.FS.writeFile(`/app/femdoc/${m}.py`, await hentTekst(`femdoc/${m}.py`));
  }
  await pyodide.runPythonAsync(`
import sys
if "/app" not in sys.path:
    sys.path.insert(0, "/app")
import matplotlib
matplotlib.use("Agg")
from femdoc.web import generer
`);
}

export async function genererRapport(pyodide, struxmlBytes, felter) {
  pyodide.FS.mkdirTree("/data");
  pyodide.FS.writeFile("/data/model.struxml", struxmlBytes);
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
