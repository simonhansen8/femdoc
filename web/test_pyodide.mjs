// CI-test: kører femdoc i Pyodide (samme kode som websiden) på en eksempelmodel.
import { loadPyodide } from "pyodide";
import { readFile } from "node:fs/promises";
import { installerFemdoc, genererRapport, hentPlan } from "./femdoc-loader.js";

const rod = new URL("../_site/", import.meta.url);
const pyodide = await loadPyodide();
await installerFemdoc(pyodide, (sti) => readFile(new URL(sti, rod), "utf8"), console.log);
const bytes = new Uint8Array(await readFile(new URL("eksempler/kontorbygning.struxml", rod)));
const plan = hentPlan(pyodide, bytes);
console.log("niveauer", plan.niveauer, "stænger", plan.staenger.length);
const res = await genererRapport(pyodide, bytes, { navn: "CI-test", nummer: "0", views: [
  { type: "3d", navn: "Isometri", azim: -60, elev: 25 },
  { type: "oversigt", navn: "Plan" },
  { type: "plan", navn: "Plan kote 3,5", z: plan.niveauer[0] },
  { type: "snit", navn: "A-A", fra: [-1, 5], til: [19, 5], dybde: 1 },
] });
console.log(res.docxNavn, res.docx.length, "bytes,", res.figurer.length, "figurer");
if (res.docx.length < 50000 || res.figurer.length < 4 || plan.niveauer.length !== 2) {
  console.error("Rapporten ser forkert ud"); process.exit(1);
}
