import {
  alertChannelWarning,
  applyPluginToRecord,
  canDeploy,
  cancelConfigEdit,
  canValidate,
  channelOptions,
  clusterByName,
  clusterOptions,
  configById,
  configByName,
  connectorStatus,
  downstreamOf,
  editorFingerprint,
  isBound,
  isConfigDirty,
  isEditing,
  isEditorDirty,
  needsSave,
  lockEdits,
  normalizeAlertChannels,
  normalizeAlertRules,
  pluginById,
  pluginOptions,
  rememberSaved,
  restoreSaved,
  refreshLiveStatus,
  saveConfig,
  startEdit,
  syncConfigAlert,
  ui,
  upsertNotebook,
  loadNotebookLogs,
  validateNotebook,
  upstreamConnectors,
} from "../store.js";
import { esc, highlightJson, pretty, toast } from "../util.js";
import { hrefFor } from "../router.js";
import { openDeployModal, openDependsModal } from "./modal.js";
import { bindApi, bindLogTable, renderApiPage, renderLogTable } from "./api.js";

function deployBanner(record) {
  if (ui.deployingId === record.id) {
    return `<div class="cfg-banner cfg-banner-info">Deploying — saving config, resolving secrets, then Kafka Connect.</div>`;
  }
  return "";
}

function fmtWhen(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function detailsHtml(record) {
  const st = connectorStatus(record);
  return `<div class="cfg-details">
    <div class="cfg-details-kicker">Details</div>
    <div class="cfg-details-row">
      <span class="cfg-details-label">Connector status</span>
      <span class="cfg-status is-${esc(st)}">${esc(st)}</span>
    </div>
    <div class="cfg-details-row">
      <span class="cfg-details-label">Created at</span>
      <span class="cfg-details-value">${esc(fmtWhen(record.createdAt))}</span>
    </div>
    <div class="cfg-details-row">
      <span class="cfg-details-label">Last modified</span>
      <span class="cfg-details-value">${esc(fmtWhen(record.updatedAt))}</span>
    </div>
  </div>`;
}

function jsonEditorText(record) {
  if (record._draftJson != null && String(record._draftJson).trim() !== "") return record._draftJson;
  return pretty(record.doc || { name: record.name || "", config: {} });
}

function editorDoc(record) {
  if (record._draftJson != null && String(record._draftJson).trim() !== "") {
    try {
      const parsed = JSON.parse(record._draftJson);
      if (parsed && typeof parsed === "object") return parsed;
    } catch {
      /* fall through to the saved doc */
    }
  }
  return record.doc || { name: record.name || "", config: {} };
}

function redact(value) {
  if (Array.isArray(value)) return value.map(redact);
  if (!value || typeof value !== "object") return value;
  const out = {};
  Object.keys(value).forEach((key) => {
    out[key] = /password|passwd|secret|token|credential/i.test(key) ? "••••••••" : redact(value[key]);
  });
  return out;
}

function deployDocument(record) {
  const doc = editorDoc(record);
  const name = doc.name || record.name || "";
  const config = { ...(doc.config || {}) };
  const cluster = clusterByName(record.attachedCluster);
  if (!cluster || cluster.deployment !== "kubernetes") return { name, config };
  const specConfig = { ...config };
  const plugin = specConfig["connector.class"] || "";
  delete specConfig["connector.class"];
  const tasks = specConfig["tasks.max"];
  delete specConfig["tasks.max"];
  delete specConfig.name;
  const tasksMax = Number(tasks || 1);
  return {
    apiVersion: "kafka.strimzi.io/v1",
    kind: "KafkaConnector",
    metadata: {
      name,
      labels: { "strimzi.io/cluster": cluster.cluster || "" },
    },
    spec: {
      class: plugin,
      tasksMax: Number.isFinite(tasksMax) && tasksMax > 0 ? tasksMax : 1,
      state: "running",
      config: specConfig,
    },
  };
}

function yamlScalar(value) {
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  const text = value == null ? "" : String(value);
  if (text === "" || /[:#{}[\],&*!|>'"%@`]|^\s|\s$|\n/.test(text) || /^(true|false|null|yes|no)$/i.test(text) || /^-?\d/.test(text)) {
    return JSON.stringify(text);
  }
  return text;
}

function toYaml(value, indent) {
  const pad = " ".repeat(indent);
  if (Array.isArray(value)) {
    if (!value.length) return "[]";
    return value.map((item) => `${pad}- ${toYaml(item, indent + 2).trimStart()}`).join("\n");
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value);
    if (!keys.length) return "{}";
    return keys.map((key) => {
      const child = value[key];
      if (child && typeof child === "object") {
        const nested = toYaml(child, indent + 2);
        return `${pad}${yamlScalar(key)}:\n${nested}`;
      }
      return `${pad}${yamlScalar(key)}: ${yamlScalar(child)}`;
    }).join("\n");
  }
  return yamlScalar(value);
}

function configBody(record, editConfig) {
  const viewingYaml = ui.configFormat === "yaml";
  if (viewingYaml) {
    return `<pre class="cfg-yaml" id="cfgYaml">${esc(toYaml(redact(deployDocument(record)), 0))}</pre>`;
  }
  const text = editConfig ? jsonEditorText(record) : pretty(redact(deployDocument(record)));
  return `<pre class="cfg-json-hl" id="cfgJsonHl" aria-hidden="true"></pre>
        <textarea class="cfg-editor cfg-editor-job" id="cfgJson" spellcheck="false"${editConfig ? "" : " readonly"}>${esc(text)}</textarea>`;
}

function editBtn(id, locked) {
  if (!locked) return "";
  return `<button type="button" class="cfg-btn cfg-btn-edit" id="${id}">Edit</button>`;
}

function validateBanner() {
  if (!ui.validate) return "";
  if (ui.validate.ok) {
    return `<div class="cfg-banner cfg-banner-ok">✓ ${esc(ui.validate.message)}</div>`;
  }
  return `<div class="cfg-banner cfg-banner-err">✗ ${esc((ui.validate.errors || []).join(" · "))}</div>`;
}

export function currentConfig(sel) {
  return configById(sel.id);
}

function channelPillsHtml(names, canEdit) {
  if (!names.length) return "";
  return names.map((name) => (
    `<span class="cfg-channel-pill">${esc(name)}${canEdit ? `<button type="button" class="cfg-channel-pill-x" data-remove-channel="${esc(name)}" aria-label="Remove ${esc(name)}">×</button>` : ""}</span>`
  )).join("");
}

function paintChannelUi(root, record) {
  const names = record.alertChannels || [];
  const pills = root.querySelector("#cfgChannelPills");
  if (pills) pills.innerHTML = record.alertOnFailed ? channelPillsHtml(names, isEditing(record, "alerts")) : "";
  const label = root.querySelector("#cfgChannelDropLabel");
  if (label) label.textContent = record.alertOnFailed ? (names.length ? `${names.length} selected` : "Select channels") : "Off";
}

function cfgActionOptions(rule, action) {
  const acts = [["pause", "pause"], ["re-trigger", "re-trigger"], ["notify", "notify"]]
    .filter(([v]) => !(rule === "PAUSED" && v === "pause"));
  const cur = rule === "PAUSED" && action === "pause" ? "notify" : action;
  return acts.map(([v, label]) => `<option value="${v}"${v === cur ? " selected" : ""}>${label}</option>`).join("");
}

function cfgRuleRowHtml(rule, action, enabled) {
  const states = ["FAILED", "UNKNOWN", "PAUSED"].map((v) =>
    `<option value="${v}"${v === rule ? " selected" : ""}>${v}</option>`
  ).join("");
  return `<div class="cfg-alert-rule">
    <select class="cfg-select cfg-alert-state"${enabled ? "" : " disabled"}>${states}</select>
    <span class="cfg-alert-then">then</span>
    <select class="cfg-select cfg-alert-action"${enabled ? "" : " disabled"}>${cfgActionOptions(rule, action)}</select>
    <button type="button" class="cfg-alert-del" data-remove-rule ${enabled ? "" : "disabled"}>×</button>
  </div>`;
}

function persist(root, record) {
  const editConfig = isEditing(record, "config");
  const editAlerts = isEditing(record, "alerts");
  const editDocs = isEditing(record, "docs");
  if (editConfig) {
    if (isBound(record)) {
      record.name = record.bound.name;
      record.attachedCluster = record.bound.cluster;
    } else {
      const nameEl = root.querySelector("#cfgName");
      if (nameEl) record.name = nameEl.value.trim() || record.name;
      record.attachedCluster = root.querySelector("#cfgAttach")?.value ?? record.attachedCluster;
    }
    const pluginEl = root.querySelector("#cfgPlugin");
    if (pluginEl) record.pluginId = pluginEl.value;
    const jsonEl = root.querySelector("#cfgJson");
    if (jsonEl && jsonEl.value.trim()) {
      record._draftJson = jsonEl.value;
      try {
        const doc = JSON.parse(jsonEl.value);
        record.doc = doc;
        if (record.name) record.doc.name = record.name;
      } catch {
        /* keep typing */
      }
    }
  }
  if (editAlerts) {
    record.alertOnFailed = Boolean(root.querySelector("#cfgAlert")?.checked);
    record.alertChannels = [...root.querySelectorAll("#cfgAlertChannels [data-channel]:checked")]
      .map((el) => el.getAttribute("data-channel"))
      .filter(Boolean);
    record.alertRules = [...root.querySelectorAll(".cfg-alert-rule")].map((row) => ({
      rule: row.querySelector(".cfg-alert-state")?.value || "FAILED",
      action: row.querySelector(".cfg-alert-action")?.value || "pause",
    }));
    const everyEl = root.querySelector("#cfgAlertEvery");
    if (everyEl) {
      const n = parseInt(everyEl.value, 10);
      record.alertCheckEveryMin = Number.isFinite(n) && n >= 1 ? n : 5;
    }
  }
  if (editDocs) {
    const notesEl = root.querySelector("#cfgNotes");
    if (notesEl) record.notes = notesEl.value;
  }
}

function depHref(dep) {
  if (dep.type !== "connector") return "";
  const found = configByName(dep.name);
  return found ? hrefFor({ kind: "editor", id: found.id }) : "";
}

function lineagePage(record) {
  const downs = downstreamOf(record);
  const ups = upstreamConnectors(record);
  const deps = record.lineage?.dependsOn || [];
  const self = `<span class="cfg-lin-pill is-self">${esc(record.name)}</span>`;
  const upPills = ups.length
    ? ups.map((u) => `<a class="cfg-lin-pill" href="${hrefFor({ kind: "editor", id: u.id })}">${esc(u.name)}</a>`).join("")
    : `<span class="cfg-hint">no upstream</span>`;
  const downPills = downs.length
    ? downs.map((d) => `<a class="cfg-lin-pill" href="${hrefFor({ kind: "editor", id: d.id })}">${esc(d.name)}</a>`).join("")
    : `<span class="cfg-hint">no downstream</span>`;
  const depRows = deps.length
    ? deps.map((dep) => {
      const href = depHref(dep);
      const name = href
        ? `<a class="cfg-lin-pill" href="${href}">${esc(dep.name)}</a>`
        : `<span class="cfg-lin-pill">${esc(dep.name)}</span>`;
      return `<div class="cfg-lin-item">${name}<span class="cfg-hint">${esc(dep.type)}</span></div>`;
    }).join("")
    : `<p class="cfg-hint">No depends-on yet.</p>`;
  const downRows = downs.length
    ? downs.map((d) => `<div class="cfg-lin-item"><a class="cfg-lin-pill" href="${hrefFor({ kind: "editor", id: d.id })}">${esc(d.name)}</a><span class="cfg-hint">${esc(d.pluginId || "connector")}</span></div>`).join("")
    : `<p class="cfg-hint">Nothing depends on this connector.</p>`;
  return `<div class="cfg-job-card">
      <div class="cfg-job-card-title">Lineage</div>
      <div class="cfg-lin-flow">
        <div class="cfg-lin-flow-col">${upPills}</div>
        <span class="cfg-lin-arrow">——▶</span>
        ${self}
        <span class="cfg-lin-arrow">——▶</span>
        <div class="cfg-lin-flow-col">${downPills}</div>
      </div>
      <div class="cfg-lin-cols">
        <div>
          <div class="cfg-side-label" style="margin-bottom:8px">Depends on</div>
          <div class="cfg-lin-list">${depRows}</div>
        </div>
        <div>
          <div class="cfg-side-label" style="margin-bottom:8px">Downstream</div>
          <div class="cfg-lin-list">${downRows}</div>
        </div>
      </div>
      <button type="button" class="cfg-btn" id="cfgAddDep" style="margin-top:16px">+ Add depends-on</button>
    </div>`;
}

export function renderEditor(sel) {
  const record = currentConfig(sel);
  if (!record) {
    return `<div class="cfg-empty"><div class="cfg-empty-title">Connector not found</div><a class="cfg-btn" href="#/">Back</a></div>`;
  }
  const tab = ["config", "api", "rca", "logs", "documents", "lineage"].includes(sel.tab) ? sel.tab : "config";
  const attached = record.attachedCluster || "";
  const clusterOpts = [`<option value="">Detached</option>`, ...clusterOptions(attached).map((name) => `<option value="${esc(name)}"${name === attached ? " selected" : ""}>${esc(name)}</option>`)].join("");
  const pluginOpts = pluginOptions(record.pluginId).map((p) => `<option value="${esc(p.id)}"${p.id === record.pluginId ? " selected" : ""}>${esc(p.name)}</option>`).join("");
  const plugin = pluginById(record.pluginId) || pluginOptions(record.pluginId).find((p) => p.id === record.pluginId);
  const selectedChannels = normalizeAlertChannels(record);
  const channelList = channelOptions(selectedChannels);
  const dropOpen = ui.channelDropOpen && record.alertOnFailed;
  const dropLabel = record.alertOnFailed
    ? (selectedChannels.length ? `${selectedChannels.length} selected` : "Select channels")
    : "Off";
  const on = record.alertOnFailed;
  const editAlerts = isEditing(record, "alerts");
  const channelRows = channelList.length
    ? channelList.map((ch) => `<label class="cfg-channel-opt"><input type="checkbox" data-channel="${esc(ch.name)}" ${selectedChannels.includes(ch.name) ? "checked" : ""}${editAlerts ? "" : " disabled"}><span>${esc(ch.name)}</span>${ch.type ? `<span class="cfg-inspect-hint">${esc(ch.type)}</span>` : ""}</label>`).join("")
    : `<p class="cfg-inspect-hint" style="padding:8px 10px">No channels yet — add one on Connections</p>`;
  const alertRules = normalizeAlertRules(record);
  const alertEvery = record.alertCheckEveryMin || 5;
  const state = record.live?.state || "not_deployed";
  const bound = isBound(record);
  const busy = ui.deployingId === record.id;
  const checking = ui.validatingId === record.id;
  const editConfig = isEditing(record, "config");
  const editDocs = isEditing(record, "docs");
  const showValidate = tab === "config";
  const showDeploy = tab === "config" && (busy || canDeploy(record));
  const pluginMeta = [plugin?.type, plugin?.format].filter(Boolean).join(" · ") || "expert";
  const alertEnabled = on && editAlerts;
  const ruleRows = alertRules.map((r) => cfgRuleRowHtml(r.rule, r.action, alertEnabled)).join("");

  const mainConfig = `<div class="cfg-job-card">
      <div class="cfg-card-head">
        <div class="cfg-job-card-title">Config</div>
        <div class="cfg-card-head-actions">
          <div class="cfg-format">
            <button type="button" data-config-format="json" class="${ui.configFormat === "yaml" ? "" : "is-on"}">JSON</button>
            <button type="button" data-config-format="yaml" class="${ui.configFormat === "yaml" ? "is-on" : ""}">YAML</button>
          </div>
          ${editConfig && record.savedOnce ? `<button type="button" class="cfg-btn cfg-btn-edit" id="cfgCancelConfig">Cancel</button>` : editBtn("cfgEditConfig", record.savedOnce && !editConfig)}
        </div>
      </div>
      ${tab === "config" ? validateBanner() : ""}
      <div class="cfg-json-stack${editConfig && ui.configFormat !== "yaml" ? " is-editing" : ""}">
        ${configBody(record, editConfig)}
      </div>
    </div>`;

  const mainLogs = `<div class="cfg-job-card cfg-kc-card">
      <div class="cfg-kc">
        <div class="cfg-kc-head">
          <div class="cfg-kc-head-copy">
            <div class="cfg-kc-kicker">Logs</div>
            <div class="cfg-kc-title">${esc(record.name)}</div>
          </div>
        </div>
        <div class="cfg-kc-out cfg-kc-out-fill">${renderLogTable(record)}</div>
      </div>
    </div>`;

  const mainRca = `<div class="cfg-job-card">
      <div class="cfg-job-card-title">RCA</div>
      ${state === "failed"
        ? `<p class="cfg-hint">Current failure for this connector (mock).</p>
           <pre class="cfg-live-error">${esc(record.live.error || "Unknown error")}</pre>`
        : `<p class="cfg-hint">No incident. Live is ${esc(state === "not_deployed" ? "not deployed" : state)}.</p>`}
    </div>`;

  const mainDocs = `<div class="cfg-job-card">
      <div class="cfg-card-head">
        <div class="cfg-job-card-title">Documents</div>
        ${editBtn("cfgEditDocs", record.savedOnce && !editDocs)}
      </div>
      <div class="cfg-doc-stack${editDocs ? " is-editing" : ""}">
        <textarea class="cfg-md-editor" id="cfgNotes" spellcheck="true" placeholder="Notes and runbook for this connector."${editDocs ? "" : " readonly"}>${esc(record.notes || "")}</textarea>
      </div>
    </div>`;

  const mainBody = tab === "logs" ? mainLogs
    : tab === "rca" ? mainRca
    : tab === "documents" ? mainDocs
    : tab === "lineage" ? lineagePage(record)
    : tab === "api" ? renderApiPage(record)
    : mainConfig;

  return `<div class="cfg-job">
    <div class="cfg-job-head">
      <div class="cfg-job-head-top">
        <div class="cfg-job-head-lead">
          <div class="cfg-crumb">
            <button type="button" data-href="#/">Connectors</button>
            <span class="cfg-crumb-sep">›</span>
            <button type="button" data-href="#/folder/${encodeURIComponent(record.folder)}">${esc(record.folder)}</button>
          </div>
          <div class="cfg-job-title-row">
            <input class="cfg-job-title" id="cfgName" value="${esc(record.name)}" autocomplete="off"${bound || !editConfig ? " readonly" : ""} title="${bound ? "Name is the Kafka Connect identity and cannot change after deploy." : ""}">
          </div>
        </div>
      </div>
      <div class="cfg-job-tabs-row">
        <div class="cfg-job-tabs">
          <a class="cfg-job-tab${tab === "config" ? " is-on" : ""}" href="${hrefFor({ kind: "editor", id: record.id, tab: "config" })}">Config</a>
          <span class="cfg-job-tab-sep">|</span>
          <a class="cfg-job-tab${tab === "api" ? " is-on" : ""}" href="${hrefFor({ kind: "editor", id: record.id, tab: "api" })}">API</a>
          <span class="cfg-job-tab-sep">|</span>
          <a class="cfg-job-tab${tab === "rca" ? " is-on" : ""}" href="${hrefFor({ kind: "editor", id: record.id, tab: "rca" })}">RCA</a>
          <span class="cfg-job-tab-sep">|</span>
          <a class="cfg-job-tab${tab === "logs" ? " is-on" : ""}" href="${hrefFor({ kind: "editor", id: record.id, tab: "logs" })}">Logs</a>
          <span class="cfg-job-tab-sep">|</span>
          <a class="cfg-job-tab${tab === "documents" ? " is-on" : ""}" href="${hrefFor({ kind: "editor", id: record.id, tab: "documents" })}">Documents</a>
          <span class="cfg-job-tab-sep">|</span>
          <a class="cfg-job-tab${tab === "lineage" ? " is-on" : ""}" href="${hrefFor({ kind: "editor", id: record.id, tab: "lineage" })}">Lineage</a>
        </div>
        <div class="cfg-job-head-actions">
          <button class="cfg-btn" type="button" id="cfgSaveBtn"${needsSave(record) ? "" : " disabled"}>Save</button>
          ${showValidate ? `<button class="cfg-btn${checking ? " is-busy" : ""}" type="button" id="cfgValidateBtn" ${checking || !canValidate(record) ? "disabled" : ""}><span class="cfg-btn-spin" aria-hidden="true"></span>${checking ? "Validating" : "Validate"}</button>` : ""}
          ${showDeploy ? `<button class="cfg-btn cfg-btn-primary${busy ? " is-busy" : ""}" type="button" id="cfgDeployBtn" ${busy ? "disabled" : ""} title="${busy ? "Deploy in progress" : "Deploy this connector to the cluster. It keeps running until you pause or delete it."}"><span class="cfg-btn-spin" aria-hidden="true"></span>${busy ? "Deploying" : "Deploy"}</button>` : ""}
        </div>
      </div>
    </div>
    <div class="cfg-job-split${tab === "api" || tab === "logs" ? " is-api" : ""}">
    <div class="cfg-job-main">
      ${deployBanner(record)}
      ${mainBody}
    </div>
    ${tab === "api" || tab === "logs" ? "" : `<aside class="cfg-job-side">
      <div class="cfg-job-side-body">
        <div class="cfg-inspect">
          ${detailsHtml(record)}
          <div class="cfg-inspect-row">
            <span class="cfg-inspect-label">Plugin</span>
            <div class="cfg-inspect-ctrl">
              <select class="cfg-select" id="cfgPlugin"${editConfig ? "" : " disabled"}>${pluginOpts}</select>
              <span class="cfg-inspect-hint">${esc(pluginMeta)}</span>
            </div>
          </div>
          <div class="cfg-inspect-row">
            <span class="cfg-inspect-label">Attach</span>
            <div class="cfg-inspect-ctrl">
              <select class="cfg-select" id="cfgAttach"${bound || !editConfig ? " disabled" : ""}>${clusterOpts}</select>
              ${bound ? `<span class="cfg-inspect-hint">Locked to this cluster after deploy.</span>` : ""}
            </div>
          </div>
          <div class="cfg-inspect-row">
            <span class="cfg-inspect-label">Alert</span>
            <div class="cfg-inspect-ctrl">
              ${editBtn("cfgEditAlerts", record.savedOnce && !editAlerts)}
              <label class="cfg-inspect-check">
                <input type="checkbox" id="cfgAlert" ${on ? "checked" : ""}${editAlerts ? "" : " disabled"}>
                Alert this connector
              </label>
              <div class="cfg-alert-rules" id="cfgAlertRules">${ruleRows}</div>
              <button type="button" class="cfg-btn" id="cfgAlertAddRule" ${editAlerts && on && alertRules.length < 3 ? "" : "disabled"}>Add rule</button>
              <label class="cfg-inspect-hint">Check every
                <input class="cfg-select" id="cfgAlertEvery" type="number" min="1" step="1" value="${esc(String(alertEvery))}" ${editAlerts && on ? "" : "disabled"} style="height:32px;margin-top:4px">
              </label>
              <div class="cfg-channel-pills" id="cfgChannelPills">${record.alertOnFailed ? channelPillsHtml(selectedChannels, editAlerts) : ""}</div>
              <div class="cfg-channel-drop${dropOpen ? " is-open" : ""}" id="cfgChannelDropWrap">
                <button type="button" class="cfg-select cfg-channel-drop-btn" id="cfgChannelDropBtn" ${editAlerts && record.alertOnFailed ? "" : "disabled"}>
                  <span id="cfgChannelDropLabel">${esc(dropLabel)}</span>
                  <svg class="cfg-channel-drop-chev" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
                </button>
                <div class="cfg-channel-drop-menu" id="cfgAlertChannels">${channelRows}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </aside>`}
    </div>
  </div>`;
}

function paintJson(root) {
  const ta = root.querySelector("#cfgJson");
  const hl = root.querySelector("#cfgJsonHl");
  if (!ta || !hl || ta.dataset.painting === "1") return;
  ta.dataset.painting = "1";
  hl.innerHTML = highlightJson(ta.value) + "\n";
  const stack = ta.closest(".cfg-json-stack");
  const box = Math.max((stack?.clientWidth || 0) - 4, 0);
  ta.style.width = "0px";
  ta.style.height = "auto";
  const contentW = ta.scrollWidth;
  const height = Math.max(ta.scrollHeight, 320);
  const width = Math.max(contentW, box);
  ta.style.height = `${height}px`;
  ta.style.width = `${width}px`;
  hl.style.height = `${height}px`;
  hl.style.width = `${width}px`;
  delete ta.dataset.painting;
}

function watchJsonScroll(root) {
  const stack = root.querySelector(".cfg-json-stack");
  if (!stack || stack.dataset.watch === "1") return;
  stack.dataset.watch = "1";
  const observer = new ResizeObserver(() => paintJson(root));
  observer.observe(stack);
}

function syncActions(root, record) {
  const saveBtn = root.querySelector("#cfgSaveBtn");
  if (saveBtn) saveBtn.disabled = !needsSave(record);
  if (ui.validate?.ok && ui.validatedFp !== editorFingerprint(record)) {
    ui.validate = null;
    ui.validatedFp = null;
    root.querySelector(".cfg-banner")?.remove();
  }
  const valBtn = root.querySelector("#cfgValidateBtn");
  if (valBtn) {
    const checking = ui.validatingId === record.id;
    valBtn.disabled = checking || !canValidate(record);
    valBtn.classList.toggle("is-busy", checking);
  }
  const deploy = root.querySelector("#cfgDeployBtn");
  if (deploy) {
    const busy = ui.deployingId === record.id;
    const ok = !busy && canDeploy(record);
    deploy.disabled = !ok;
    deploy.classList.toggle("is-busy", busy);
    deploy.title = busy
      ? "Deploy in progress"
      : ok
      ? "Deploy this connector to the cluster. It keeps running until you pause or delete it."
      : (record.attachedCluster ? "Validate this connector before deploy" : "Attach a cluster first");
  }
}

export function flushEditor() {
  const root = document.getElementById("cfgDetail");
  const record = configById(ui.selection?.id);
  if (!root || !record || ui.selection?.kind !== "editor") return record;
  persist(root, record);
  return record;
}

export async function saveEditor() {
  const record = flushEditor();
  if (!record) return false;
  const jsonEl = document.querySelector("#cfgJson");
  if (jsonEl && (isConfigDirty(record) || isEditing(record, "config"))) {
    try {
      JSON.parse(jsonEl.value);
    } catch {
      ui.validate = { ok: false, errors: ["JSON is invalid."] };
      toast("Fix JSON before saving");
      window.dispatchEvent(new Event("cfg-render"));
      return false;
    }
  }
  if (!record.name) {
    ui.validate = { ok: false, errors: ["Name is required"] };
    toast("Name is required");
    window.dispatchEvent(new Event("cfg-render"));
    return false;
  }
  const channelWarn = alertChannelWarning(record);
  if (channelWarn) {
    toast(channelWarn);
    window.dispatchEvent(new Event("cfg-render"));
    return false;
  }
  saveConfig(record);
  if (ui.validate?.ok) ui.validatedFp = editorFingerprint(record);
  const err = await upsertNotebook(record);
  if (!err) {
    record.savedOnce = true;
    lockEdits(record);
  }
  const alertMsg = await syncConfigAlert(record);
  if (err) toast(err);
  else if (alertMsg) toast(alertMsg);
  else toast("Connector saved");
  window.dispatchEvent(new Event("cfg-render"));
  return !err;
}

export function discardEditor() {
  const record = configById(ui.selection?.id);
  if (!record) return;
  restoreSaved(record);
  ui.validate = null;
  ui.validatedFp = null;
}

export function bindEditor(root) {
  const sel = ui.selection;
  const record = currentConfig(sel);
  if (!record) return;
  if (sel.tab === "logs") {
    loadNotebookLogs(record).then(() => {
      const box = document.querySelector(".cfg-kc-out-fill");
      if (box && ui.selection?.id === record.id && ui.selection?.tab === "logs") {
        box.innerHTML = renderLogTable(record);
        bindLogTable(document.getElementById("cfgDetail") || document);
      }
    });
  }
  if (!ui.savedClone[record.id]) rememberSaved(record);
  const rerender = () => window.dispatchEvent(new Event("cfg-render"));
  const touch = () => {
    persist(root, record);
    if (ui.validate?.ok && ui.validatedFp !== editorFingerprint(record)) {
      ui.validate = null;
      ui.validatedFp = null;
    }
    syncActions(root, record);
  };

  root.querySelector("#cfgEditConfig")?.addEventListener("click", () => {
    ui.configFormat = "json";
    startEdit(record, "config");
    rerender();
  });
  root.querySelector("#cfgCancelConfig")?.addEventListener("click", () => {
    cancelConfigEdit(record);
    ui.validate = null;
    ui.validatedFp = null;
    rerender();
  });
  root.querySelectorAll("[data-config-format]").forEach((btn) => {
    btn.addEventListener("click", () => {
      persist(root, record);
      ui.configFormat = btn.getAttribute("data-config-format") === "yaml" ? "yaml" : "json";
      rerender();
    });
  });
  root.querySelector("#cfgEditAlerts")?.addEventListener("click", () => {
    startEdit(record, "alerts");
    rerender();
  });
  root.querySelector("#cfgEditDocs")?.addEventListener("click", () => {
    startEdit(record, "docs");
    rerender();
  });

  refreshLiveStatus(record).then(() => {
    if (ui.selection?.kind === "editor" && ui.selection?.id === record.id) {
      const st = connectorStatus(record);
      const el = document.querySelector(".cfg-status");
      if (el) {
        el.className = `cfg-status is-${st}`;
        el.textContent = st;
      }
      const dot = document.querySelector(`[data-config-id="${record.id}"] .cfg-node-dot`);
      if (dot) {
        dot.className = `cfg-node-dot is-${st}`;
        dot.title = st.toUpperCase();
      }
    }
  });

  root.querySelector("#cfgAttach")?.addEventListener("change", () => {
    persist(root, record);
    rerender();
  });
  root.querySelector("#cfgAlert")?.addEventListener("change", () => {
    touch();
    rerender();
  });
  root.querySelector("#cfgAlertEvery")?.addEventListener("input", () => touch());
  root.querySelector("#cfgAlertAddRule")?.addEventListener("click", () => {
    persist(root, record);
    const used = new Set((record.alertRules || []).map((r) => r.rule));
    const next = ["FAILED", "UNKNOWN", "PAUSED"].find((v) => !used.has(v));
    if (!next) return;
    record.alertRules = [...normalizeAlertRules(record), { rule: next, action: next === "PAUSED" ? "notify" : "pause" }];
    rerender();
  });
  root.querySelector("#cfgAlertRules")?.addEventListener("change", (event) => {
    if (event.target.classList.contains("cfg-alert-state")) {
      const row = event.target.closest(".cfg-alert-rule");
      const actionSel = row?.querySelector(".cfg-alert-action");
      if (actionSel) actionSel.innerHTML = cfgActionOptions(event.target.value, actionSel.value);
    }
    touch();
  });
  root.querySelector("#cfgAlertRules")?.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-remove-rule]");
    if (!btn) return;
    persist(root, record);
    if ((record.alertRules || []).length < 2) return;
    btn.closest(".cfg-alert-rule")?.remove();
    touch();
    persist(root, record);
  });
  root.querySelector("#cfgChannelDropBtn")?.addEventListener("click", (event) => {
    event.preventDefault();
    if (root.querySelector("#cfgChannelDropBtn")?.disabled) return;
    const wrap = root.querySelector("#cfgChannelDropWrap");
    const open = !wrap?.classList.contains("is-open");
    wrap?.classList.toggle("is-open", open);
    ui.channelDropOpen = open;
  });
  root.querySelector("#cfgAlertChannels")?.addEventListener("change", () => {
    touch();
    paintChannelUi(root, record);
  });
  root.querySelector("#cfgChannelPills")?.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-remove-channel]");
    if (!btn) return;
    const name = btn.getAttribute("data-remove-channel");
    root.querySelectorAll("#cfgAlertChannels [data-channel]").forEach((box) => {
      if (box.getAttribute("data-channel") === name) box.checked = false;
    });
    touch();
    paintChannelUi(root, record);
  });
  ui._alertDropAbort?.abort();
  ui._alertDropAbort = new AbortController();
  document.addEventListener("mousedown", (event) => {
    const wrap = root.querySelector("#cfgChannelDropWrap");
    if (!wrap?.classList.contains("is-open")) return;
    if (wrap.contains(event.target)) return;
    wrap.classList.remove("is-open");
    ui.channelDropOpen = false;
  }, { signal: ui._alertDropAbort.signal });
  root.querySelector("#cfgName")?.addEventListener("input", () => touch());
  root.querySelector("#cfgNotes")?.addEventListener("input", () => touch());
  root.querySelector("#cfgJson")?.addEventListener("input", () => {
    persist(root, record);
    paintJson(root);
    if (ui.validate?.ok && ui.validatedFp !== editorFingerprint(record)) {
      ui.validate = null;
      ui.validatedFp = null;
    }
    syncActions(root, record);
  });
  root.querySelector("#cfgJson")?.addEventListener("scroll", () => {
    const hl = root.querySelector("#cfgJsonHl");
    const ta = root.querySelector("#cfgJson");
    if (hl && ta) hl.scrollTop = ta.scrollTop;
  });
  paintJson(root);
  watchJsonScroll(root);
  syncActions(root, record);
  bindApi(root, record);
  bindLogTable(root);
  root.querySelector("#cfgPlugin")?.addEventListener("change", () => {
    persist(root, record);
    applyPluginToRecord(record, record.pluginId);
    record.doc.name = record.name;
    record._draftJson = pretty(record.doc);
    ui.validate = null;
    ui.validatedFp = null;
    rerender();
  });

  root.querySelector("#cfgAddDep")?.addEventListener("click", () => openDependsModal(record));

  root.querySelector("#cfgSaveBtn")?.addEventListener("click", () => {
    saveEditor();
  });
  root.querySelector("#cfgValidateBtn")?.addEventListener("click", async () => {
    persist(root, record);
    if (!canValidate(record)) {
      toast(record.attachedCluster ? "Save config before validate" : "Attach a cluster first");
      rerender();
      return;
    }
    const jsonEl = root.querySelector("#cfgJson");
    if (jsonEl) {
      try {
        JSON.parse(jsonEl.value);
      } catch {
        ui.validate = { ok: false, errors: ["JSON is invalid."] };
        ui.validatedFp = null;
        rerender();
        return;
      }
    }
    if (!record.attachedCluster) {
      ui.validate = { ok: false, errors: ["Attach a Kafka Connect cluster first."] };
      ui.validatedFp = null;
      rerender();
      return;
    }
    const fp = editorFingerprint(record);
    const result = await validateNotebook(record);
    ui.validate = result;
    ui.validatedFp = result.ok ? fp : null;
    rerender();
  });
  root.querySelector("#cfgDeployBtn")?.addEventListener("click", () => {
    persist(root, record);
    if (!canDeploy(record)) {
      toast(record.attachedCluster ? "Validate this connector before deploy" : "Attach a cluster first");
      rerender();
      return;
    }
    openDeployModal(record);
  });
}
