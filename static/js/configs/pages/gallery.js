import { connections, expandFolderPath, generateDoc, recipeById, recipes, ui, insertConfig, insertNotes, insertLineage } from "../store.js";
import { esc, pretty } from "../util.js";
import { go } from "../router.js";

const TABS = [
  { id: "starter", label: "Starter" },
  { id: "production", label: "Production" },
  { id: "advanced", label: "Advanced" },
];

function cardsFor(tab) {
  return recipes.filter((r) => r.levels.includes(tab));
}

function bindSelects(recipe) {
  const binds = recipe?.binds || [];
  const g = ui.galleryBinds;
  const field = (key, label, options) => {
    if (!binds.includes(key)) return "";
    const list = ["", ...options.filter(Boolean)];
    if (g[key] && !list.includes(g[key])) list.splice(1, 0, g[key]);
    const opts = list.map((c) => `<option value="${esc(c)}"${c === g[key] ? " selected" : ""}>${esc(c || "none")}</option>`).join("");
    return `<div class="cfg-field"><label class="cfg-label">${label}</label><select class="cfg-select" data-bind="${key}">${opts}</select></div>`;
  };
  return [
    field("kafka", "Kafka", connections.kafka),
    field("schemaRegistry", "Schema Registry", connections.schemaRegistry),
  ].join("");
}

export function renderGallery(sel) {
  const folder = sel.folder || "default";
  const tab = ui.galleryTab || "advanced";
  const list = cardsFor(tab);
  if (!list.some((c) => c.id === ui.galleryCard)) ui.galleryCard = list[0]?.id || "";
  const selected = recipeById(ui.galleryCard);
  const level = tab;
  const preview = selected ? generateDoc({ recipeId: selected.id, level, binds: ui.galleryBinds, name: "" }) : { name: "", config: {} };
  const notes = selected ? insertNotes(selected.id, level) : "";
  const lineage = selected ? insertLineage(selected.id, level, ui.galleryBinds) : { dependsOn: [] };
  const advanced = level === "advanced" || level === "production";

  const cards = list.map((card) => `<button type="button" class="cfg-card${card.id === ui.galleryCard ? " is-on" : ""}" data-card="${esc(card.id)}">
      <div class="cfg-card-top">
        <strong>${esc(card.name)}</strong>
        <span class="cfg-pill">${esc(card.type)}</span>
        <span class="cfg-pill cfg-pill-muted">${esc(tab)}</span>
      </div>
      <p>${esc(card.blurb)}</p>
    </button>`).join("");

  return `<div class="cfg-pane">
    <header class="cfg-header">
      <div class="cfg-crumb"><button type="button" data-href="#/">Connectors</button> / <button type="button" data-href="#/folder/${encodeURIComponent(folder)}">${esc(folder)}</button> / new</div>
      <div class="cfg-header-row">
        <div>
          <h1 class="cfg-title">New connector in ${esc(folder)}</h1>
          <div class="cfg-sub">One Insert creates one notebook. Source and sink are separate connectors.</div>
        </div>
        <div class="cfg-header-actions">
          <button class="cfg-btn" type="button" data-href="#/folder/${encodeURIComponent(folder)}">Cancel</button>
        </div>
      </div>
    </header>
    <div class="cfg-tabs">
      ${TABS.map((t) => `<button type="button" class="cfg-tab${t.id === tab ? " is-on" : ""}" data-tab="${t.id}">${t.label}</button>`).join("")}
    </div>
    <div class="cfg-pane-scroll">
      <div class="cfg-cards">${cards || `<p class="cfg-hint">No recipes on this tab.</p>`}</div>
      ${selected ? `<div class="cfg-gallery-detail">
        <div class="cfg-sub">Selected: <strong>${esc(selected.name)}</strong> · ${esc(tab)}</div>
        <div class="cfg-form-grid" style="margin-top:12px;">${bindSelects(selected)}</div>
        <div class="cfg-field cfg-field-full">
          <label class="cfg-label">Preview (read-only)</label>
          <pre class="cfg-json">${esc(pretty(preview))}</pre>
        </div>
        ${advanced && notes ? `<p class="cfg-hint">Notes that will be inserted: ${esc(notes.split("\n")[0])}</p>` : ""}
        ${advanced && lineage.dependsOn.length ? `<p class="cfg-hint">Lineage: ${esc(lineage.dependsOn.map((d) => d.name).join(", "))}</p>` : ""}
        <button class="cfg-btn cfg-btn-primary" type="button" id="cfgInsertBtn">Insert</button>
      </div>` : ""}
    </div>
  </div>`;
}

export function bindGallery(root, sel) {
  root.querySelectorAll("[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      ui.galleryTab = btn.getAttribute("data-tab");
      window.dispatchEvent(new Event("cfg-render"));
    });
  });
  root.querySelectorAll("[data-card]").forEach((btn) => {
    btn.addEventListener("click", () => {
      ui.galleryCard = btn.getAttribute("data-card");
      window.dispatchEvent(new Event("cfg-render"));
    });
  });
  root.querySelectorAll("[data-bind]").forEach((el) => {
    el.addEventListener("change", () => {
      ui.galleryBinds[el.getAttribute("data-bind")] = el.value;
      window.dispatchEvent(new Event("cfg-render"));
    });
  });
  root.querySelector("#cfgInsertBtn")?.addEventListener("click", () => {
    const record = insertConfig({
      folder: sel.folder || "default",
      recipeId: ui.galleryCard,
      level: ui.galleryTab || "advanced",
      binds: { ...ui.galleryBinds },
    });
    ui.advancedOpen = (record.level === "advanced" || record.level === "production");
    ui.notesOpen = false;
    expandFolderPath(ui.expanded, record.folder);
    go({ kind: "editor", id: record.id });
  });
}
