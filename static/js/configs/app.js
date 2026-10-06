import { configById, expandFolderPath, insertBlank, isEditorDirty, loadConnectionCatalog, loadFolders, loadKcActions, loadNotebooks, loadPluginCatalog, ui } from "./store.js";
import { bindRouter, go } from "./router.js";
import { bindTree, renderTree } from "./tree.js";
import { renderDetail } from "./detail.js";
import { openFolderModal, openUnsavedModal } from "./pages/modal.js";
import { discardEditor, flushEditor, saveEditor } from "./pages/editor.js";

function expandSelection() {
  const sel = ui.selection;
  if (sel.folder) expandFolderPath(ui.expanded, sel.folder);
  if (sel.kind === "editor") {
    const record = configById(sel.id);
    if (record?.folder) expandFolderPath(ui.expanded, record.folder);
  }
}

function createConfig(folder) {
  const record = insertBlank({ folder: folder || "default", pluginId: "blank" });
  expandFolderPath(ui.expanded, record.folder);
  go({ kind: "editor", id: record.id });
}

function render() {
  const sel = ui.selection;
  if (sel.kind === "new" || sel.kind === "gallery") {
    createConfig(sel.folder);
    return;
  }
  const editorId = sel.kind === "editor" ? sel.id : "";
  if (ui._editorId !== editorId) {
    ui.validate = null;
    ui.validatedFp = null;
    ui._editorId = editorId;
  }
  expandSelection();
  renderTree();
  renderDetail();
}

function bindChrome() {
  document.getElementById("cfgAddFolderBtn")?.addEventListener("click", () => {
    openFolderModal({ parent: "" });
  });
  document.getElementById("cfgRefreshBtn")?.addEventListener("click", async () => {
    await Promise.all([loadConnectionCatalog(), loadPluginCatalog(), loadKcActions(), loadNotebooks(), loadFolders()]);
    render();
  });
}

async function init() {
  if (window.StreamBridgeSecrets?.refresh) {
    try { await window.StreamBridgeSecrets.refresh(); } catch (_) { /* keep empty until API is up */ }
  }
  if (!document.getElementById("view-configs")) return;
  await Promise.all([loadConnectionCatalog(), loadPluginCatalog(), loadKcActions(), loadNotebooks(), loadFolders()]);
  bindTree();
  bindChrome();
  window.addEventListener("cfg-render", render);
  bindRouter(render, {
    flush: flushEditor,
    save: saveEditor,
    discard: discardEditor,
    onDirtyNav: openUnsavedModal,
  });
  document.addEventListener("click", (event) => {
    const el = event.target.closest("a[href]");
    if (!el) return;
    const href = el.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("javascript:")) return;
    if (ui.selection?.kind !== "editor") return;
    flushEditor();
    const record = configById(ui.selection.id);
    if (!record || !isEditorDirty(record)) return;
    event.preventDefault();
    event.stopPropagation();
    openUnsavedModal({
      onSave: () => {
        const result = saveEditor();
        if (result && typeof result.then === "function") {
          result.then((ok) => { if (ok !== false) window.location.href = href; });
          return true;
        }
        if (result === false) return false;
        window.location.href = href;
        return true;
      },
      onDiscard: () => {
        discardEditor();
        window.location.href = href;
      },
    });
  }, true);
  window.addEventListener("beforeunload", (event) => {
    if (ui.selection?.kind !== "editor") return;
    flushEditor();
    const record = configById(ui.selection.id);
    if (!record || !isEditorDirty(record)) return;
    event.preventDefault();
    event.returnValue = "";
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
