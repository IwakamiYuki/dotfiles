// tmux-agent-web の ANSI 変換のテスト。実行: cd tmux/tests && node --test
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const A = require(path.join(__dirname, "..", "assets", "agent-web", "ansi.js"));

const texts = (lines) => lines.map((segs) => segs.map((s) => s.text).join(""));

test("plain text is split into lines", () => {
  assert.deepEqual(texts(A.parse("a\nb\n\nc")), ["a", "b", "", "c"]);
});

test("SGR 16 colors and reset create styled segments", () => {
  const [line] = A.parse("\x1b[31mred\x1b[0m plain");
  assert.equal(line.length, 2);
  assert.match(line[0].style, /color:#cd3131/);
  assert.equal(line[0].text, "red");
  assert.equal(line[1].style, "");
  assert.equal(line[1].text, " plain");
});

test("256-color and truecolor, foreground and background", () => {
  const [line] = A.parse("\x1b[38;5;208mA\x1b[48;2;1;2;3mB");
  assert.match(line[0].style, /color:#ff8700/); // 256 色の 208
  assert.match(line[1].style, /background:rgb\(1,2,3\)/);
  assert.match(line[1].style, /color:#ff8700/); // 前景は続いている
});

test("style carries across newlines until reset", () => {
  const lines = A.parse("\x1b[1mbold\nstill bold\x1b[22m\nnormal");
  assert.match(lines[0][0].style, /font-weight:700/);
  assert.match(lines[1][0].style, /font-weight:700/);
  assert.equal(lines[2][0].style, "");
});

test("inverse swaps foreground and background", () => {
  const [line] = A.parse("\x1b[31;7mX");
  assert.match(line[0].style, /background:#cd3131/);
});

test("trailing whitespace is trimmed, interior kept", () => {
  assert.deepEqual(texts(A.parse("a  b   \x1b[0m   \n   ")), ["a  b", ""]);
});

test("non-SGR escape sequences are dropped, not shown", () => {
  assert.deepEqual(texts(A.parse("\x1b[2Jhello\x1b[?25l!")), ["hello!"]);
});

test("HTML is escaped (pane content is untrusted)", () => {
  const html = A.toHtml(A.parse("<script>alert(1)</script> & \"q\""));
  assert.ok(!html.includes("<script>"));
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(html.includes("&amp;"));
});

test("style values never contain injected markup", () => {
  const html = A.toHtml(A.parse("\x1b[38;2;1;2;\"><img>mX"));
  assert.ok(!html.includes("<img"));
});

test("cells counts CJK as double width and maxCells picks the widest line", () => {
  assert.equal(A.cells("abc"), 3);
  assert.equal(A.cells("日本語"), 6);
  assert.equal(A.maxCells(A.parse("ab\n日本語\nabcd")), 6);
});
