import assert from "node:assert/strict";
import test from "node:test";

import { shortHash } from "../src/design/hashFormat.ts";

test("shortHash keeps head and tail, and tail 0 means head only", () => {
  assert.equal(shortHash("abcdef0123456789", 4, 4), "abcd…6789");
  assert.equal(shortHash("abcdef0123456789", 6, 0), "abcdef…");
  assert.equal(shortHash("short", 6, 4), "short");
});
