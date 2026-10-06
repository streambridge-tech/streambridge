import { configById, isEditorDirty, ui } from "./store.js";

const TABS = ["config", "api", "rca", "logs", "documents", "lineage"];

export function readRoute() {
  const raw = (location.hash || "#/").replace(/^#/, "") || "/";
  const [path, queryString] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  const params = new URLSearchParams(queryString || "");
  if (!parts.length) return { kind: "home" };
  if (parts[0] === "folder" && parts[1]) {
    return { kind: "folder", folder: decodeURIComponent(parts.slice(1).join("/")) };
  }
  if (parts[0] === "new") {
    return { kind: "new", folder: params.get("folder") || "default" };
  }
  if (parts[0] === "c" && parts[1]) {
    const tab = TABS.includes(parts[2]) ? parts[2] : "config";
    return {
      kind: "editor",
      id: decodeURIComponent(parts[1]),
      tab,
      expandLineage: params.get("expand") === "lineage",
    };
  }
  return { kind: "home" };
}

export function hrefFor(sel) {
  if (!sel || sel.kind === "home") return "#/";
  if (sel.kind === "folder") return `#/folder/${encodeURIComponent(sel.folder)}`;
  if (sel.kind === "new" || sel.kind === "gallery") {
    return sel.folder ? `#/new?folder=${encodeURIComponent(sel.folder)}` : "#/new";
  }
  if (sel.kind === "editor") {
    const tab = sel.tab && sel.tab !== "config" ? `/${sel.tab}` : "";
    const q = sel.expandLineage ? "?expand=lineage" : "";
    return `#/c/${encodeURIComponent(sel.id)}${tab}${q}`;
  }
  return "#/";
}

export function go(sel) {
  const next = hrefFor(sel);
  if (location.hash === next) {
    ui.selection = sel;
    window.dispatchEvent(new Event("cfg-render"));
    return;
  }
  location.hash = next;
}

function leavingEditor(prev, next) {
  if (!prev || prev.kind !== "editor") return false;
  if (next.kind === "editor" && next.id === prev.id) return false;
  return true;
}

export function bindRouter(onChange, hooks = {}) {
  let lastHash = location.hash || "#/";
  const apply = () => {
    const nextHash = location.hash || "#/";
    const next = readRoute();
    if (ui.navForce) {
      ui.navForce = false;
      lastHash = nextHash;
      ui.selection = next;
      onChange();
      return;
    }
    if (ui.navSuppress) {
      ui.navSuppress = false;
      lastHash = nextHash;
      return;
    }
    const prev = ui.selection;
    if (prev?.kind === "editor") hooks.flush?.();
    if (leavingEditor(prev, next)) {
      const record = configById(prev.id);
      if (record && isEditorDirty(record)) {
        const pending = nextHash;
        ui.navSuppress = true;
        location.hash = lastHash;
        hooks.onDirtyNav?.({
          onSave: () => {
            const result = hooks.save?.();
            const proceed = () => {
              ui.navForce = true;
              location.hash = pending;
            };
            if (result && typeof result.then === "function") {
              result.then((ok) => { if (ok !== false) proceed(); });
              return true;
            }
            if (result === false) return false;
            proceed();
            return true;
          },
          onDiscard: () => {
            hooks.discard?.();
            ui.navForce = true;
            location.hash = pending;
          },
          onCancel: () => {},
        });
        return;
      }
    }
    lastHash = nextHash;
    ui.selection = next;
    onChange();
  };
  window.addEventListener("hashchange", apply);
  apply();
}
