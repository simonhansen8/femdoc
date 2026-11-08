// CI-test: kører femdoc i Pyodide (samme kode som websiden) på en eksempelmodel.
import { loadPyodide } from "pyodide";
import { readFile } from "node:fs/promises";
import { installerFemdoc, genererRapport } from "./femdoc-loader.js";

const rod = new URL("../_site/", import.meta.url);
const pyodide = await loadPyodide();
await installerFemdoc(pyodide, (sti) => readFile(new URL(sti, rod), "utf8"), console.log);
const bytes = new Uint8Array(await readFile(new URL("eksempler/sample_slab.struxml", rod)));
const res = await genererRapport(pyodide, bytes, { navn: "CI-test", nummer: "0" });
console.log(res.docxNavn, res.docx.length, "bytes,", res.figurer.length, "figurer");
if (res.docx.length < 50000 || res.figurer.length < 4) {
  console.error("Rapporten ser forkert ud"); process.exit(1);
}
