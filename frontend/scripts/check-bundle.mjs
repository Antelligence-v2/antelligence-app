// Fails the build check if the entry chunk (what every page pays for) grows past budget.
import { readFileSync, readdirSync } from "node:fs";
import { gzipSync } from "node:zlib";

const BUDGET_KB = 170;
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
