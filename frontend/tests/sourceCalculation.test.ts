import assert from "node:assert/strict";
import test from "node:test";
import * as research from "../src/lib/research.ts";

test("source-calculation display attributes stored operands without recomputing an answer", () => {
  assert.equal(typeof research.sourceCalculationLines, "function");
  const payload = { answer: "-20.00", calculation: { operation: "percent_change", operands: [{ evidence_id: "table_1", quote: "80", value: "80" }, { evidence_id: "table_1", quote: "100", value: "100" }], result: "-20.00", limitations: ["Source relevance is not verified."] } };
  assert.deepEqual(research.sourceCalculationLines(payload), [
    "Operation: percent_change",
    'Operand 1: table_1 · "80" → 80',
    'Operand 2: table_1 · "100" → 100',
    "Stored result: -20.00",
    "Source relevance is not verified.",
  ]);
  assert.deepEqual(research.sourceCalculationLines({ answer: "-20.00" }), []);
  assert.deepEqual(research.sourceCalculationLines(null), []);
  assert.deepEqual(research.sourceCalculationLines({ calculation: { operation: "divide", operands: null } }), []);
});
