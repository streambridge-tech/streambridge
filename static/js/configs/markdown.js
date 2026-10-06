import { esc } from "./util.js";

function inline(text) {
  let html = esc(text);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return html;
}

function table(lines) {
  const rows = lines
    .map((line) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim()))
    .filter((cells) => cells.length && !cells.every((c) => /^[-:]+$/.test(c)));
  if (!rows.length) return "";
  const [head, ...body] = rows;
  const th = head.map((c) => `<th>${inline(c)}</th>`).join("");
  const tr = body.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("");
  return `<table class="cfg-md-table"><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
}

function list(lines) {
  const items = lines.map((line) => `<li>${inline(line.replace(/^([-*]|\d+\.)\s+/, ""))}</li>`).join("");
  const ordered = /^\d+\./.test(lines[0].trim());
  return ordered ? `<ol>${items}</ol>` : `<ul>${items}</ul>`;
}

export function renderMarkdown(src) {
  const text = String(src || "").replace(/\r\n/g, "\n");
  if (!text.trim()) {
    return `<p class="cfg-md-empty">Notes about this connector. Headings, bold, lists, and tables are supported.</p>`;
  }
  return text.split(/\n{2,}/).map((block) => {
    const lines = block.split("\n").filter((line) => line.length);
    if (!lines.length) return "";
    if (lines.every((line) => /^\|.+\|/.test(line.trim()))) return table(lines);
    if (lines.every((line) => /^([-*]|\d+\.)\s/.test(line.trim()))) return list(lines);
    const heading = lines[0].match(/^(#{1,3})\s+(.*)$/);
    if (heading && lines.length === 1) {
      const level = heading[1].length;
      return `<h${level}>${inline(heading[2])}</h${level}>`;
    }
    return `<p>${lines.map(inline).join("<br>")}</p>`;
  }).join("");
}
