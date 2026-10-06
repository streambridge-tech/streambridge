import { childFolders, configsFor, folderName, identityChipHtml, parentFolder } from "../store.js";
import { esc } from "../util.js";
import { hrefFor } from "../router.js";

function crumb(folder) {
  const parts = String(folder || "").split("/").filter(Boolean);
  let acc = "";
  const links = parts.map((part, index) => {
    acc = acc ? `${acc}/${part}` : part;
    if (index === parts.length - 1) return esc(part);
    return `<button type="button" data-href="${hrefFor({ kind: "folder", folder: acc })}">${esc(part)}</button>`;
  });
  return `<div class="cfg-crumb"><button type="button" data-href="#/">Connectors</button> / ${links.join(" / ")}</div>`;
}

function liveLabel(item) {
  return identityChipHtml(item);
}

export function renderFolder(sel) {
  const rows = configsFor(sel.folder);
  const nested = childFolders(sel.folder);
  const label = folderName(sel.folder);
  const body = rows.map((item) => `<tr data-href="${hrefFor({ kind: "editor", id: item.id })}">
      <td>${esc(item.name)}</td>
      <td>${esc(item.attachedCluster || item.bound?.cluster || "Detached")}</td>
      <td>${liveLabel(item)}</td>
    </tr>`).join("");
  const nestedRows = nested.map((path) => `<tr data-href="${hrefFor({ kind: "folder", folder: path })}">
      <td>${esc(folderName(path))}</td>
      <td>folder</td>
      <td>—</td>
    </tr>`).join("");

  return `<div class="cfg-pane">
    <header class="cfg-header">
      ${crumb(sel.folder)}
      <div class="cfg-header-row">
        <div>
          <h1 class="cfg-title">${esc(label)}</h1>
          <div class="cfg-sub">${rows.length} connector${rows.length === 1 ? "" : "s"}${nested.length ? ` · ${nested.length} folder${nested.length === 1 ? "" : "s"}` : ""}${parentFolder(sel.folder) ? ` · in ${esc(parentFolder(sel.folder))}` : ""}</div>
        </div>
        <div class="cfg-header-actions">
          <button class="cfg-btn" type="button" data-new-folder="${esc(sel.folder)}">New folder</button>
          <button class="cfg-btn cfg-btn-primary" type="button" data-new-config="${esc(sel.folder)}">New connector</button>
        </div>
      </div>
    </header>
    <div class="cfg-pane-scroll">
      ${nestedRows || rows.length ? `<table class="cfg-table">
        <thead><tr><th>Name</th><th>Attached</th><th>Status</th></tr></thead>
        <tbody>${nestedRows}${body}</tbody>
      </table>` : `<div class="cfg-empty" style="min-height:240px;">
        <div class="cfg-empty-title">No connectors in ${esc(label)}</div>
        <div class="cfg-empty-actions"><button class="cfg-btn cfg-btn-primary" type="button" data-new-config="${esc(sel.folder)}">New connector</button></div>
      </div>`}
    </div>
  </div>`;
}
