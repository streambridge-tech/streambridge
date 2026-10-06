import { clusterByName, kcActions, persistNotebookLog, ui } from "../store.js";
import { esc, highlightJson, pretty } from "../util.js";

const EYE = `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;

function fmtStamp(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso || "—";
  const pad = (n, w = 2) => String(n).padStart(w, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`;
}

function inlineBody(text) {
  return String(text || "").replace(/\s+/g, " ").trim().slice(0, 140);
}

export function logsFor(recordOrId) {
  const record = recordOrId && typeof recordOrId === "object" ? recordOrId : null;
  const recordId = record ? record.id : recordOrId;
  const persisted = record?.logs || [];
  const local = (ui.apiLog || []).filter((row) => row.configId === recordId);
  if (!persisted.length) return local;
  const seen = new Set(persisted.map((row) => row.id));
  return [...persisted, ...local.filter((row) => !seen.has(row.id))];
}

export function renderLogTable(record) {
  const rows = logsFor(record);
  if (!rows.length) {
    return `<div class="cfg-log-empty">No history yet. Send a command on the API tab or Deploy this connector. Click a row to expand.</div>`;
  }
  const body = rows.map((row) => {
    const open = ui.apiLogOpen === row.id;
    const ok = row.http >= 200 && row.http < 300;
    return `<tr class="cfg-log-row${open ? " is-open" : ""}" data-log-id="${esc(row.id)}">
      <td class="cfg-log-ts">${esc(fmtStamp(row.at))}</td>
      <td class="cfg-log-cmd">${esc(row.method)} ${esc(row.action)}</td>
      <td class="cfg-log-status"><span class="cfg-log-code ${ok ? "is-ok" : "is-err"}">${esc(row.http)}</span> ${esc(row.statusText || "")}</td>
      <td class="cfg-log-time">${row.timeMs != null ? `${row.timeMs} ms` : "—"}</td>
      <td class="cfg-log-val">
        <span class="cfg-log-inline" ${open ? "style=\"display:none\"" : ""}>${esc(inlineBody(row.bodyText))}</span>
        <div class="cfg-log-detail" ${open ? "" : "style=\"display:none\""}>
          <div class="cfg-log-meta">
            <span><strong>Status</strong> ${esc(row.http)} ${esc(row.statusText || "")}</span>
            <span><strong>Time</strong> ${row.timeMs != null ? `${row.timeMs} ms` : "—"}</span>
          </div>
          <pre class="cfg-log-pre">${highlightJson(row.bodyText || "")}</pre>
        </div>
      </td>
      <td class="cfg-log-eye">${EYE}</td>
    </tr>`;
  }).join("");
  return `<div class="cfg-log-wrap">
    <table class="cfg-log-table">
      <thead>
        <tr>
          <th class="cfg-log-ts">Timestamp</th>
          <th class="cfg-log-cmd">Command</th>
          <th class="cfg-log-status">Status</th>
          <th class="cfg-log-time">Time</th>
          <th class="cfg-log-val">Response</th>
          <th class="cfg-log-eye"></th>
        </tr>
      </thead>
      <tbody>${body}</tbody>
    </table>
  </div>`;
}

export function bindLogTable(root) {
  root.querySelectorAll(".cfg-log-row").forEach((tr) => {
    tr.addEventListener("click", () => {
      const id = tr.getAttribute("data-log-id");
      const closing = tr.classList.contains("is-open");
      root.querySelectorAll(".cfg-log-row").forEach((row) => {
        row.classList.remove("is-open");
        const pre = row.querySelector(".cfg-log-detail");
        const inline = row.querySelector(".cfg-log-inline");
        if (pre) pre.style.display = "none";
        if (inline) inline.style.display = "";
      });
      if (closing) {
        ui.apiLogOpen = null;
        return;
      }
      tr.classList.add("is-open");
      const pre = tr.querySelector(".cfg-log-detail");
      const inline = tr.querySelector(".cfg-log-inline");
      if (pre) pre.style.display = "";
      if (inline) inline.style.display = "none";
      ui.apiLogOpen = id;
    });
  });
}

const FALLBACK_ACTIONS = [
  { key: "status", label: "Get Status", method: "GET", path: "/connectors/{name}/status", group: "inspect", danger: false, params: [] },
  { key: "config", label: "Get Config", method: "GET", path: "/connectors/{name}/config", group: "inspect", danger: false, params: [] },
  { key: "tasks", label: "List Tasks", method: "GET", path: "/connectors/{name}/tasks", group: "inspect", danger: false, params: [] },
  { key: "topics", label: "List Topics", method: "GET", path: "/connectors/{name}/topics", group: "inspect", danger: false, params: [] },
  { key: "pause", label: "Pause", method: "PUT", path: "/connectors/{name}/pause", group: "lifecycle", danger: false, params: [] },
  { key: "resume", label: "Resume", method: "PUT", path: "/connectors/{name}/resume", group: "lifecycle", danger: false, params: [] },
  { key: "restart", label: "Restart Connector", method: "POST", path: "/connectors/{name}/restart", group: "lifecycle", danger: false, params: [
    { name: "includeTasks", label: "Also restart tasks", type: "boolean", default: false },
    { name: "onlyFailed", label: "Only failed tasks", type: "boolean", default: false },
  ] },
  { key: "restart-task", label: "Restart Task", method: "POST", path: "/connectors/{name}/tasks/{taskId}/restart", group: "lifecycle", danger: false, params: [
    { name: "taskId", label: "Task ID", type: "number", required: true, default: 0 },
  ] },
  { key: "offsets", label: "Show Offsets", method: "GET", path: "/connectors/{name}/offsets", group: "offsets", danger: false, params: [] },
  { key: "reset-offsets", label: "Reset Offsets", method: "DELETE", path: "/connectors/{name}/offsets", group: "offsets", danger: true, params: [] },
  { key: "delete", label: "Delete Connector", method: "DELETE", path: "/connectors/{name}", group: "danger", danger: true, params: [] },
];

const GROUPS = [
  { id: "inspect", label: "Inspect" },
  { id: "lifecycle", label: "Control" },
  { id: "offsets", label: "Offsets" },
  { id: "danger", label: "Danger" },
];

const BLURB = {
  status: "Live connector and task state on the worker.",
  config: "Config currently deployed on Kafka Connect.",
  tasks: "Task list and assignments.",
  topics: "Topics this connector is using.",
  "plugin-config": "Plugin config definition from the worker.",
  "validate-config": "Ask Connect to validate this config payload.",
  pause: "Pause the connector without deleting it.",
  resume: "Resume a paused connector.",
  restart: "Restart the connector process.",
  "restart-task": "Restart one task by id.",
  offsets: "Current source offsets.",
  "reset-offsets": "Wipe offsets so the connector restarts from the beginning.",
  delete: "Remove this connector from the Connect cluster.",
};

function actionList() {
  return kcActions.length ? kcActions : FALLBACK_ACTIONS;
}

function actionByKey(key) {
  return actionList().find((a) => a.key === key) || actionList()[0];
}

function fillPath(template, name, params) {
  let path = String(template || "");
  path = path.replaceAll("{name}", encodeURIComponent(name || ""));
  path = path.replaceAll("{taskId}", encodeURIComponent(params.taskId ?? "0"));
  path = path.replaceAll("{class}", encodeURIComponent(params.pluginClass || "connector.class"));
  return path;
}

function queryFromParams(spec, params) {
  const q = new URLSearchParams();
  (spec || []).forEach((p) => {
    if (p.type === "json") return;
    const value = params[p.name];
    if (value === undefined || value === "" || value === false) return;
    q.set(p.name, String(value));
  });
  const s = q.toString();
  return s ? `?${s}` : "";
}

function composedUrl(base, pathTpl, name, spec, params) {
  const host = (base || "{connect}").replace(/\/+$/, "");
  return `${host}${fillPath(pathTpl, name, params)}${queryFromParams(spec, params)}`;
}

function paramValue(spec, params) {
  if (params[spec.name] !== undefined) return params[spec.name];
  if (spec.default !== undefined) return spec.default;
  return spec.type === "boolean" ? false : "";
}

function paramRows(action, params) {
  const spec = action.params || [];
  if (!spec.length) return "";
  return spec.map((p) => {
    const val = paramValue(p, params);
    if (p.type === "boolean") {
      return `<label class="cfg-kc-param"><input type="checkbox" data-api-param="${esc(p.name)}" ${val ? "checked" : ""}><span>${esc(p.label || p.name)}</span></label>`;
    }
    if (p.type === "json") {
      return `<label class="cfg-kc-param cfg-kc-param-block"><span>${esc(p.label || p.name)}</span><textarea data-api-param="${esc(p.name)}" class="cfg-kc-textarea" spellcheck="false">${esc(typeof val === "string" ? val : pretty(val || {}))}</textarea></label>`;
    }
    return `<label class="cfg-kc-param"><span>${esc(p.label || p.name)}</span><input data-api-param="${esc(p.name)}" type="${p.type === "number" ? "number" : "text"}" value="${esc(val)}"></label>`;
  }).join("");
}

export function pushLog(record, action, method, result) {
  const entry = {
    id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    configId: record.id,
    at: new Date().toISOString(),
    action: action.label,
    key: action.key,
    method,
    http: result.http,
    statusText: result.statusText,
    timeMs: result.timeMs,
    bodyText: result.bodyText,
  };
  ui.apiLog = [entry, ...(ui.apiLog || [])].slice(0, 100);
  if (record.logs) record.logs = [entry, ...record.logs].slice(0, 100);
  else record.logs = [entry];
  persistNotebookLog(record, entry);
}

function statusSummary(data) {
  if (!data || typeof data !== "object") return "";
  const conn = data.connector;
  const tasks = Array.isArray(data.tasks) ? data.tasks : null;
  if (!conn || typeof conn.state !== "string" || !tasks) return "";
  const badge = (state) => {
    const s = String(state || "UNKNOWN").toUpperCase();
    const cls = s === "RUNNING" ? "ok" : (s === "PAUSED" ? "warn" : "err");
    return `<span class="cfg-kc-st-badge is-${cls}">${esc(s)}</span>`;
  };
  const taskRows = tasks.map((t) => `
    <div class="cfg-kc-st-task">
      <div class="cfg-kc-st-task-head">
        <span class="cfg-kc-st-task-id">Task ${esc(t.id ?? "?")}</span>
        ${badge(t.state)}
        ${t.worker_id ? `<span class="cfg-kc-st-worker">${esc(t.worker_id)}</span>` : ""}
      </div>
      ${t.trace ? `<pre class="cfg-kc-trace">${esc(t.trace)}</pre>` : ""}
    </div>`).join("");
  return `<div class="cfg-kc-status">
      <div class="cfg-kc-st-row">
        <span class="cfg-kc-st-label">Connector</span>
        ${badge(conn.state)}
        ${conn.worker_id ? `<span class="cfg-kc-st-worker">${esc(conn.worker_id)}</span>` : ""}
      </div>
      <div class="cfg-kc-st-tasks">${taskRows || `<div class="cfg-kc-st-empty">No tasks reported.</div>`}</div>
    </div>`;
}

function responseView(result) {
  if (!result) {
    return `<div class="cfg-kc-empty">Send this command. History is on the Logs tab.</div>`;
  }
  const code = result.http;
  const cls = code >= 200 && code < 300 ? "ok" : "err";
  const body = result.bodyText != null ? result.bodyText : pretty(result.data ?? { error: result.error });
  const summary = statusSummary(result.data);
  return `<div class="cfg-kc-out-bar">
      <span class="cfg-kc-code cfg-kc-code-${cls}">${esc(code)}</span>
      <span class="cfg-kc-out-status">${esc(result.statusText || "")}</span>
      <span class="cfg-kc-out-time">${result.timeMs != null ? `${result.timeMs} ms` : ""}</span>
    </div>
    ${summary}
    <pre class="cfg-kc-out-body">${highlightJson(body)}</pre>`;
}

function withPluginClass(record, params) {
  const next = { ...params };
  if (!next.pluginClass && record.doc?.config?.["connector.class"]) {
    next.pluginClass = record.doc.config["connector.class"];
  }
  return next;
}

export function renderApiPage(record) {
  const attached = record.attachedCluster || "";
  if (!attached) {
    return `<div class="cfg-job-card"><p class="cfg-hint">Attach a Kafka Connect cluster on the Config tab. This API tab fills the REST URL from that connection and this connector name.</p></div>`;
  }
  const cluster = clusterByName(attached);
  const group = GROUPS.some((g) => g.id === ui.apiGroup) ? ui.apiGroup : "inspect";
  const inGroup = actionList().filter((a) => a.group === group);
  let action = actionByKey(ui.apiAction);
  if (!inGroup.some((a) => a.key === action.key)) action = inGroup[0] || action;
  const params = withPluginClass(record, ui.apiParams || {});
  const url = composedUrl(cluster?.url, action.path, record.name, action.params, params);
  const method = (action.method || "GET").toUpperCase();
  const extra = paramRows(action, params);
  const current = ui.apiResult?.configId === record.id ? ui.apiResult : null;

  const segs = GROUPS.filter((g) => actionList().some((a) => a.group === g.id)).map((g) => (
    `<button type="button" class="cfg-kc-seg${g.id === group ? " is-on" : ""}" data-api-group="${esc(g.id)}">${esc(g.label)}</button>`
  )).join("");

  const chips = inGroup.map((a) => (
    `<button type="button" class="cfg-kc-chip${a.key === action.key ? " is-on" : ""}${a.danger ? " is-danger" : ""}" data-api-action="${esc(a.key)}">${esc(a.label)}</button>`
  )).join("");

  return `<div class="cfg-job-card cfg-kc-card">
    <div class="cfg-kc">
      <div class="cfg-kc-head">
        <div class="cfg-kc-head-copy">
          <div class="cfg-kc-kicker">Command console</div>
          <div class="cfg-kc-title">${esc(record.name)} <span>→ ${esc(attached)}</span></div>
        </div>
        <div class="cfg-kc-segs">${segs}</div>
      </div>
      <div class="cfg-kc-chips">${chips}</div>
      <div class="cfg-kc-cmd">
        <div class="cfg-kc-cmd-row">
          <span class="cfg-kc-method cfg-kc-method-${esc(method)}">${esc(method)}</span>
          <div class="cfg-kc-cmd-meta">
            <div class="cfg-kc-cmd-name">${esc(action.label)}</div>
            <div class="cfg-kc-cmd-blurb">${esc(BLURB[action.key] || "Kafka Connect REST call for this connector.")}</div>
          </div>
          <button class="cfg-kc-send${action.danger ? " is-danger" : ""}" type="button" id="cfgApiSend"${ui.apiSending ? " disabled" : ""}>${ui.apiSending ? "Sending…" : "Send"}</button>
        </div>
        <div class="cfg-kc-path">
          <span class="cfg-kc-host">${esc((cluster?.url || "").replace(/\/+$/, "") || "{connect}")}</span>
          <input class="cfg-kc-url" id="cfgApiUrl" readonly spellcheck="false" value="${esc(url)}" title="${esc(url)}">
        </div>
        <div class="cfg-kc-params" id="cfgApiParams">${extra}</div>
      </div>
      <div class="cfg-kc-out" id="cfgApiResp">${responseView(current)}</div>
    </div>
  </div>`;
}

function readParams(root, action) {
  const params = {};
  (action.params || []).forEach((p) => {
    const el = root.querySelector(`[data-api-param="${p.name}"]`);
    if (!el) return;
    if (p.type === "boolean") params[p.name] = el.checked;
    else if (p.type === "json") {
      try { params[p.name] = JSON.parse(el.value || "{}"); }
      catch { params[p.name] = el.value; }
    } else if (p.type === "number") params[p.name] = el.value === "" ? p.default : Number(el.value);
    else params[p.name] = el.value;
  });
  return params;
}

function paintUrl(root, record) {
  const action = actionByKey(ui.apiAction);
  const params = withPluginClass(record, ui.apiParams || {});
  const cluster = clusterByName(record.attachedCluster);
  const urlEl = root.querySelector("#cfgApiUrl");
  if (urlEl) urlEl.value = composedUrl(cluster?.url, action.path, record.name, action.params, params);
}

export function bindApi(root, record) {
  if (!root.querySelector(".cfg-kc")) return;
  const rerender = () => window.dispatchEvent(new Event("cfg-render"));

  root.querySelectorAll("[data-api-group]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const group = btn.getAttribute("data-api-group");
      ui.apiGroup = group;
      const first = actionList().find((a) => a.group === group);
      if (first && actionByKey(ui.apiAction).group !== group) {
        ui.apiAction = first.key;
        ui.apiParams = {};
      }
      rerender();
    });
  });

  root.querySelectorAll("[data-api-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      ui.apiAction = btn.getAttribute("data-api-action");
      ui.apiParams = {};
      rerender();
    });
  });

  const paramsBox = root.querySelector("#cfgApiParams");
  paramsBox?.addEventListener("input", () => {
    ui.apiParams = readParams(root, actionByKey(ui.apiAction));
    paintUrl(root, record);
  });
  paramsBox?.addEventListener("change", () => {
    ui.apiParams = readParams(root, actionByKey(ui.apiAction));
    paintUrl(root, record);
  });

  root.querySelector("#cfgApiSend")?.addEventListener("click", async () => {
    const action = actionByKey(ui.apiAction);
    ui.apiParams = readParams(root, action);
    if (action.danger && !window.confirm(`${action.label} for ${record.name}? This hits Kafka Connect.`)) return;
    const cluster = record.attachedCluster;
    if (!cluster) return;
    ui.apiSending = true;
    rerender();
    const started = performance.now();
    try {
      const body = { ...ui.apiParams };
      if (record.doc?.config) body.config = record.doc.config;
      const res = await fetch(
        `/api/kc/connections/${encodeURIComponent(cluster)}/connectors/${encodeURIComponent(record.name)}/${encodeURIComponent(action.key)}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
      );
      const payload = await res.json().catch(() => ({}));
      const timeMs = Math.round(performance.now() - started);
      ui.apiResult = {
        configId: record.id,
        http: res.status,
        statusText: res.statusText,
        timeMs,
        data: payload.data ?? payload,
        error: payload.error,
        bodyText: pretty(payload.ok ? payload.data : payload),
      };
    } catch (err) {
      ui.apiResult = {
        configId: record.id,
        http: 0,
        statusText: "ERR",
        timeMs: Math.round(performance.now() - started),
        error: String(err),
        bodyText: pretty({ error: String(err) }),
      };
    }
    if (ui.apiResult) pushLog(record, action, (action.method || "GET").toUpperCase(), ui.apiResult);
    ui.apiSending = false;
    rerender();
  });
}
