// capture-pane -e の出力（SGR つきテキスト）を、行ごとの「スタイル付きの断片」に変換する。
// DOM に依存しない（Node のテストからも読む。tmux/tests/ansi.test.js）。
"use strict";
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.AnsiView = api;
})(typeof self !== "undefined" ? self : this, function () {
  const BASE16 = [
    "#000000", "#cd3131", "#0dbc79", "#e5e510", "#2472c8", "#bc3fbc", "#11a8cd", "#e5e5e5",
    "#666666", "#f14c4c", "#23d18b", "#f5f543", "#3b8eea", "#d670d6", "#29b8db", "#ffffff",
  ];
  const PALETTE = (() => {
    const p = BASE16.slice();
    const level = [0, 95, 135, 175, 215, 255];
    for (let r = 0; r < 6; r++)
      for (let g = 0; g < 6; g++)
        for (let b = 0; b < 6; b++) {
          const hex = (n) => level[n].toString(16).padStart(2, "0");
          p.push("#" + hex(r) + hex(g) + hex(b));
        }
    for (let i = 0; i < 24; i++) p.push("#" + (8 + i * 10).toString(16).padStart(2, "0").repeat(3));
    return p;
  })();
  const DEFAULT_FG = "#d8d2c8";
  const DEFAULT_BG = "#161412";

  const fresh = () => ({ fg: null, bg: null, bold: false, dim: false, italic: false, underline: false, inverse: false });

  function applySgr(st, params) {
    for (let i = 0; i < params.length; i++) {
      const c = params[i];
      if (c === 0) Object.assign(st, fresh());
      else if (c === 1) st.bold = true;
      else if (c === 2) st.dim = true;
      else if (c === 3) st.italic = true;
      else if (c === 4) st.underline = true;
      else if (c === 7) st.inverse = true;
      else if (c === 22) st.bold = st.dim = false;
      else if (c === 23) st.italic = false;
      else if (c === 24) st.underline = false;
      else if (c === 27) st.inverse = false;
      else if (c >= 30 && c <= 37) st.fg = PALETTE[c - 30];
      else if (c >= 90 && c <= 97) st.fg = PALETTE[c - 90 + 8];
      else if (c >= 40 && c <= 47) st.bg = PALETTE[c - 40];
      else if (c >= 100 && c <= 107) st.bg = PALETTE[c - 100 + 8];
      else if (c === 39) st.fg = null;
      else if (c === 49) st.bg = null;
      else if (c === 38 || c === 48) {
        const key = c === 38 ? "fg" : "bg";
        if (params[i + 1] === 5 && i + 2 < params.length) {
          st[key] = PALETTE[params[i + 2]] || null;
          i += 2;
        } else if (params[i + 1] === 2 && i + 4 < params.length) {
          st[key] = "rgb(" + params[i + 2] + "," + params[i + 3] + "," + params[i + 4] + ")";
          i += 4;
        }
      }
    }
  }

  // 値は固定のパレットか、0〜255 に丸めた数値だけから作る（pane の内容が style に入り込まないように）
  function css(st) {
    let fg = st.fg;
    let bg = st.bg;
    if (st.inverse) [fg, bg] = [bg || DEFAULT_BG, fg || DEFAULT_FG];
    const parts = [];
    if (fg) parts.push("color:" + fg);
    if (bg) parts.push("background:" + bg);
    if (st.bold) parts.push("font-weight:700");
    if (st.dim) parts.push("opacity:.6");
    if (st.italic) parts.push("font-style:italic");
    if (st.underline) parts.push("text-decoration:underline");
    return parts.join(";");
  }

  function trimLine(segs) {
    while (segs.length) {
      const last = segs[segs.length - 1];
      const t = last.text.replace(/\s+$/, "");
      if (t === "") segs.pop();
      else {
        last.text = t;
        break;
      }
    }
    return segs;
  }

  // text → 行の配列。各行は { text, style } の配列。スタイルは改行をまたいで引き継ぐ
  function parse(text) {
    const lines = [[]];
    const st = fresh();
    // CSI = ESC [ パラメータ(0-?) 中間(space-/) 終端(@-~)。SGR(m) 以外は読み捨てる
    const re = /\x1b\[([0-?]*)[ -/]*([@-~])|\x1b[^[]?|\n|\r/g;
    let last = 0;
    let m;
    const push = (s) => {
      if (!s) return;
      const line = lines[lines.length - 1];
      const style = css(st);
      const prev = line[line.length - 1];
      if (prev && prev.style === style) prev.text += s;
      else line.push({ text: s, style });
    };
    while ((m = re.exec(text))) {
      push(text.slice(last, m.index));
      last = re.lastIndex;
      if (m[0] === "\n") lines.push([]);
      else if (m[2] === "m") {
        const params = m[1] === "" ? [0] : m[1].split(/[;:]/).map((n) => Math.min(255, parseInt(n, 10) || 0));
        applySgr(st, params);
      }
    }
    push(text.slice(last));
    return lines.map(trimLine);
  }

  const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (s) => s.replace(/[&<>"']/g, (c) => ESC_MAP[c]);

  function toHtml(lines) {
    return lines
      .map((segs) => segs.map((s) => (s.style ? '<span style="' + s.style + '">' + esc(s.text) + "</span>" : esc(s.text))).join(""))
      .join("\n");
  }

  const isWide = (cp) =>
    (cp >= 0x1100 && cp <= 0x115f) || (cp >= 0x2e80 && cp <= 0xa4cf) || (cp >= 0xac00 && cp <= 0xd7a3) ||
    (cp >= 0xf900 && cp <= 0xfaff) || (cp >= 0xfe30 && cp <= 0xfe6f) || (cp >= 0xff00 && cp <= 0xff60) ||
    (cp >= 0xffe0 && cp <= 0xffe6) || (cp >= 0x1f300 && cp <= 0x1faff);

  function cells(str) {
    let n = 0;
    for (const ch of str) n += isWide(ch.codePointAt(0)) ? 2 : 1;
    return n;
  }

  const maxCells = (lines) => lines.reduce((w, segs) => Math.max(w, cells(segs.map((s) => s.text).join(""))), 0);

  return { parse, toHtml, cells, maxCells, esc };
});
