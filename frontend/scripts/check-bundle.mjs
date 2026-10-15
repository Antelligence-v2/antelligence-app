// Fails the build check if the entry chunk (what every page pays for) grows past budget.
import { readFileSync, readdirSync } from "node:fs";
import { gzipSync } from "node:zlib";

const BUDGET_KB = 170;
// The largest lazy chunk is three.js (3D view); tumor runs open in 3D, so keep it from growing silently.
const LAZY_BUDGET_KB = 520;
const html = readFileSync("dist/index.html", "utf8");
const entry = html.match(/src="[^"]*\/assets\/(index\.[^"]+\.js)"/)?.[1]; // base may be /static/
if (!entry) throw new Error("entry chunk not found in dist/index.html");
const kb = gzipSync(readFileSync(`dist/assets/${entry}`)).length / 1024;
const chunks = readdirSync("dist/assets").filter((f) => f.endsWith(".js")).length;
console.log(`entry ${entry}: ${kb.toFixed(1)} kB gzip (budget ${BUDGET_KB} kB), ${chunks} chunks`);
if (kb > BUDGET_KB) {
  console.error(`Entry chunk is over budget by ${(kb - BUDGET_KB).toFixed(1)} kB; lazy-load the new dependency.`);
  process.exit(1);
}
const [largest, largestKb] = readdirSync("dist/assets")
  .filter((f) => f.endsWith(".js") && f !== entry)
  .map((f) => [f, gzipSync(readFileSync(`dist/assets/${f}`)).length / 1024])
  .sort((a, b) => b[1] - a[1])[0] ?? ["none", 0];
console.log(`largest lazy chunk ${largest}: ${largestKb.toFixed(1)} kB gzip (budget ${LAZY_BUDGET_KB} kB)`);
if (largestKb > LAZY_BUDGET_KB) {
  console.error(`Largest lazy chunk is over budget by ${(largestKb - LAZY_BUDGET_KB).toFixed(1)} kB.`);
  process.exit(1);
}
