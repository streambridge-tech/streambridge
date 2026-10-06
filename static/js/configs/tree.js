import {
  childFolders,
  configById,
  configs,
  configsFor,
  connectorStatus,
  expandFolderPath,
  folderName,
  insertBlank,
  isBound,
  ui,
} from "./store.js";
import { esc } from "./util.js";
import { go, hrefFor } from "./router.js";
import { openCloneModal, openDeleteFolderModal, openDeleteModal, openFolderModal, openMoveModal, openRenameFolderModal } from "./pages/modal.js";

const MORE_ICON = `<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><circle cx="3.5" cy="8" r="1.15"/><circle cx="8" cy="8" r="1.15"/><circle cx="12.5" cy="8" r="1.15"/></svg>`;
const FOLDER_ICON = `<svg class="cfg-type-icon cfg-folder-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" aria-hidden="true"><path d="M2.2 4.2h4l1.1 1.3h6.5c.4 0 .7.3.7.7v6.3c0 .4-.3.7-.7.7H2.2c-.4 0-.7-.3-.7-.7V4.9c0-.4.3-.7.7-.7z"/></svg>`;

function matchesQuery(text) {
  const q = ui.query.trim().toLowerCase();
  if (!q) return true;
  return String(text || "").toLowerCase().includes(q);
}

function folderVisible(path) {
  if (!ui.query.trim()) return true;
  if (matchesQuery(folderName(path)) || matchesQuery(path)) return true;
  if (configsFor(path).some((c) => matchesQuery(c.name))) return true;
  return childFolders(path).some(folderVisible);
}

function renderFolderNode(path, depth) {
  if (!folderVisible(path)) return "";
  const items = configsFor(path);
  const kids = childFolders(path);
  const visibleItems = items.filter((c) => matchesQuery(c.name) || matchesQuery(path));
  const key = `folder:${path}`;
  const open = ui.expanded.has(key) || Boolean(ui.query.trim());
  const sel = ui.selection;
  const folderActive = sel.kind === "folder" && sel.folder === path;
  const inheritActive = sel.kind === "gallery" && sel.folder === path;
  const pad = 8 + depth * 12;
  const filePad = pad + 14;
  const files = (ui.query ? visibleItems : items).map((item, i) => {
    const active = sel.kind === "editor" && sel.id === item.id;
    const st = connectorStatus(item);
    return `<div class="cfg-node cfg-node-item${active ? " is-active" : ""}" style="padding-left:${filePad}px" data-config-id="${esc(item.id)}">
      <a class="cfg-node-link" href="${hrefFor({ kind: "editor", id: item.id })}">
        <span class="cfg-node-num">${i + 1}.</span>
        <span class="cfg-node-name">${esc(item.name)}</span>
        <span class="cfg-node-dot is-${esc(st)}" title="${esc(st.toUpperCase())}"></span>
      </a>
      <button class="cfg-more" type="button" data-menu-config="${esc(item.id)}" title="More" aria-label="Connector menu">${MORE_ICON}</button>
    </div>`;
  }).join("");
  const nested = kids.map((child) => renderFolderNode(child, depth + 1)).join("");
  return `<div class="cfg-group${open ? "" : " is-collapsed"}">
    <div class="cfg-node cfg-node-folder${folderActive || inheritActive ? " is-active" : ""}${open ? "" : " is-collapsed"}" style="padding-left:${pad}px" data-expand="${esc(key)}" data-folder="${esc(path)}">
      <svg class="cfg-chevron" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
      ${FOLDER_ICON}
      <span class="cfg-node-name">${esc(folderName(path))}</span>
      <button class="cfg-more" type="button" data-menu-folder="${esc(path)}" title="More" aria-label="Folder menu">${MORE_ICON}</button>
    </div>
    <div class="cfg-group-children" style="--cfg-indent:${pad + 12}px">${nested}${files}</div>
  </div>`;
}

export function closeTreeMenu() {
  const menu = document.getElementById("cfgTreeMenu");
  if (!menu) return;
  menu.hidden = true;
  menu.innerHTML = "";
}

function placeMenu(button, html) {
  const menu = document.getElementById("cfgTreeMenu");
  if (!menu) return;
  const rect = button.getBoundingClientRect();
  menu.hidden = false;
  menu.innerHTML = html;
  const top = rect.top;
  const left = Math.min(rect.right + 6, window.innerWidth - 200);
  menu.style.top = `${top}px`;
  menu.style.left = `${Math.max(8, left)}px`;
}

export function renderTree() {
  const root = document.getElementById("cfgTreeBody");
  if (!root) return;
  closeTreeMenu();
  const html = childFolders("").map((path) => renderFolderNode(path, 0)).join("");
  root.innerHTML = html || `<div class="cfg-empty-desc" style="padding:16px;">${configs.length ? "No connectors match." : "No connectors yet."}</div>`;
}

export function bindTree() {
  const body = document.getElementById("cfgTreeBody");
  const search = document.getElementById("cfgSearch");
  const menu = document.getElementById("cfgTreeMenu");

  body?.addEventListener("click", (event) => {
    const moreCfg = event.target.closest("[data-menu-config]");
    if (moreCfg) {
      event.preventDefault();
      event.stopPropagation();
      const id = moreCfg.getAttribute("data-menu-config");
      placeMenu(moreCfg, `
        <button type="button" data-act="clone" data-id="${esc(id)}">Clone</button>
        <button type="button" data-act="move" data-id="${esc(id)}">Move</button>
        <button type="button" class="is-danger" data-act="delete" data-id="${esc(id)}">Delete</button>`);
      return;
    }
    const moreFolder = event.target.closest("[data-menu-folder]");
    if (moreFolder) {
      event.preventDefault();
      event.stopPropagation();
      const folder = moreFolder.getAttribute("data-menu-folder");
      placeMenu(moreFolder, `
        <button type="button" data-act="new-config" data-folder="${esc(folder)}">Add File</button>
        <button type="button" data-act="new-folder" data-folder="${esc(folder)}">Add Folder</button>
        <button type="button" data-act="rename-folder" data-folder="${esc(folder)}">Rename</button>
        <button type="button" class="is-danger" data-act="delete-folder" data-folder="${esc(folder)}">Delete</button>`);
      return;
    }
    const file = event.target.closest("[data-config-id]");
    if (file) {
      event.preventDefault();
      go({ kind: "editor", id: file.getAttribute("data-config-id") });
      return;
    }
    const node = event.target.closest("[data-expand]");
    if (!node || event.target.closest("a")) return;
    const key = node.getAttribute("data-expand");
    const folder = node.getAttribute("data-folder");
    if (event.target.closest(".cfg-chevron")) {
      event.preventDefault();
      if (ui.expanded.has(key)) ui.expanded.delete(key);
      else ui.expanded.add(key);
      renderTree();
      return;
    }
    ui.expanded.add(key);
    go({ kind: "folder", folder });
  });

  menu?.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-act]");
    if (!btn) return;
    const act = btn.getAttribute("data-act");
    const folder = btn.getAttribute("data-folder") || "default";
    const id = btn.getAttribute("data-id");
    closeTreeMenu();
    if (act === "new-config") {
      expandFolderPath(ui.expanded, folder);
      const record = insertBlank({ folder, pluginId: "blank" });
      go({ kind: "editor", id: record.id });
      return;
    }
    if (act === "new-folder") {
      expandFolderPath(ui.expanded, folder);
      openFolderModal({ parent: folder });
      return;
    }
    if (act === "rename-folder") {
      openRenameFolderModal(folder);
      return;
    }
    if (act === "delete-folder") {
      openDeleteFolderModal(folder);
      return;
    }
    const record = configById(id);
    if (!record) return;
    if (act === "clone") openCloneModal(record);
    if (act === "move") openMoveModal(record);
    if (act === "delete") openDeleteModal(record);
  });

  document.addEventListener("click", (event) => {
    if (event.target.closest(".cfg-more, #cfgTreeMenu")) return;
    closeTreeMenu();
  });

  search?.addEventListener("input", () => {
    ui.query = search.value;
    renderTree();
  });

  const resizer = document.getElementById("cfgResizer");
  const tree = document.getElementById("cfgTree");
  if (!resizer || !tree) return;
  let dragging = false;
  let startX = 0;
  let startW = 0;
  resizer.addEventListener("mousedown", (event) => {
    dragging = true;
    startX = event.clientX;
    startW = tree.getBoundingClientRect().width;
    resizer.classList.add("is-dragging");
    document.body.classList.add("cfg-resizing");
  });
  document.addEventListener("mousemove", (event) => {
    if (!dragging) return;
    const width = Math.max(200, Math.min(560, startW + (event.clientX - startX)));
    tree.style.width = `${width}px`;
  });
  document.addEventListener("mouseup", () => {
    dragging = false;
    resizer.classList.remove("is-dragging");
    document.body.classList.remove("cfg-resizing");
  });
}

export function selectedFolder() {
  const sel = ui.selection;
  if (sel.kind === "folder" || sel.kind === "gallery") return sel.folder || "default";
  if (sel.kind === "editor") return configById(sel.id)?.folder || "default";
  return "default";
}
