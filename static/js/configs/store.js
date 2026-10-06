/** In-memory connector notebooks until a backend exists. Live state is current, not a run list. */

import { esc } from "./util.js";

export const DEFAULT_FOLDER = "default";

function secretsApi() {
  return (typeof window !== "undefined" && window.StreamBridgeSecrets) || {
    collect: () => [],
    isSecretOnly: () => false,
    resolve: (text) => text,
    listRefs: () => [],
    secretRef: (parent, key) => `{${parent}.${key}}`,
  };
}

export function collectVarKeys(text) {
  return secretsApi().collect(text).map((r) => r.ref);
}

export function isVarOnly(value) {
  return secretsApi().isSecretOnly(value);
}

export function varRef(parent, key) {
  return secretsApi().secretRef(parent, key);
}

export const connections = {
  database: [],
  kafka: [],
  schemaRegistry: [],
};

export const clusters = [];
export const channels = [];

function uniq(list) {
  return [...new Set(list.filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function channelTypeOf(row) {
  const subtype = String(row.subtype || "").toLowerCase();
  const type = String(row.type || row.channelType || "").toLowerCase();
  if (subtype.includes("slack") || type === "slack") return "slack";
  if (subtype.includes("gchat") || type === "gchat") return "gchat";
  if (subtype.includes("pager") || type === "pagerduty") return "pagerduty";
  if (subtype.includes("email") || type === "email") return "email";
  if (subtype.includes("webhook") || type === "webhook") return "webhook";
  if (type === "notification") return subtype.replace(/^notification-/, "") || "notify";
  return type || "";
}

function bindKind(row) {
  const subtype = String(row.subtype || "").toLowerCase();
  const type = String(row.type || "").toLowerCase();
  if (type === "notification" || subtype.startsWith("notification-")) return "channel";
  if (subtype.includes("schema-registry") || subtype.includes("schema_registry")) return "schemaRegistry";
  if (type === "connect" || subtype.includes("kafka-connect")) return "cluster";
  if (type === "kafka" || subtype === "kafka" || (type === "transport" && subtype === "kafka")) return "kafka";
  if (type === "source" || subtype === "postgres" || subtype === "mysql" || subtype === "mongodb") return "database";
  return "";
}

function upsertChannel(name, type) {
  if (!name) return;
  const existing = channels.find((c) => c.name === name);
  if (existing) {
    if (type && !existing.type) existing.type = type;
    return;
  }
  channels.push({ name, type: type || "" });
}

export function applyConnectionCatalog(rows) {
  const database = [];
  const kafka = [];
  const schemaRegistry = [];
  const clusterByNameMap = new Map();
  channels.length = 0;
  (rows || []).forEach((row) => {
    const name = row.name;
    const kind = bindKind(row);
    if (kind === "database") database.push(name);
    if (kind === "kafka") kafka.push(name);
    if (kind === "schemaRegistry") schemaRegistry.push(name);
    if (kind === "cluster") {
      const cfg = row.config || {};
      const url = String(cfg.url || cfg.host || row.host || "").replace(/\/+$/, "");
      const deployment = String(cfg.deployment || "").toLowerCase() === "kubernetes"
        || String(cfg.mode || "").toLowerCase() === "kubernetes"
        ? "kubernetes"
        : "connect";
      clusterByNameMap.set(name, {
        name,
        url,
        deployment,
        namespace: String(cfg.namespace || ""),
        cluster: String(cfg.cluster || ""),
      });
    }
    if (kind === "channel") upsertChannel(name, channelTypeOf(row));
  });
  connections.database = uniq(database);
  connections.kafka = uniq(kafka);
  connections.schemaRegistry = uniq(schemaRegistry);
  clusters.length = 0;
  clusterByNameMap.forEach((row) => clusters.push(row));
  clusters.sort((a, b) => a.name.localeCompare(b.name));
  channels.sort((a, b) => a.name.localeCompare(b.name));
}

export function applyAlertChannels(rows) {
  (rows || []).forEach((row) => {
    upsertChannel(row.channelName || row.channel_name, channelTypeOf(row));
  });
  channels.sort((a, b) => a.name.localeCompare(b.name));
}

export async function loadConnectionCatalog() {
  try {
    const res = await fetch("/api/connections");
    if (res.ok) {
      const payload = await res.json();
      const rows = Array.isArray(payload) ? payload : (payload.connections || payload.items || []);
      applyConnectionCatalog(rows);
    } else {
      applyConnectionCatalog([]);
    }
  } catch (_) {
    applyConnectionCatalog([]);
  }
  try {
    const res = await fetch("/api/alerts");
    if (!res.ok) return;
    const payload = await res.json();
    const rows = Array.isArray(payload) ? payload : (payload.alerts || payload.items || []);
    applyAlertChannels(rows);
    applyConfigAlerts(rows);
  } catch (_) {
    /* keep connection-only channels */
  }
}

export function notebookPayload(record) {
  let doc = record.doc || { name: record.name, config: {} };
  if (record._draftJson != null) {
    try {
      const parsed = JSON.parse(record._draftJson);
      if (parsed && typeof parsed === "object") doc = parsed;
    } catch {
      /* keep last parsed doc */
    }
  }
  if (record.name && doc && typeof doc === "object") doc = { ...doc, name: record.name };
  return {
    id: record.id,
    name: record.name,
    folder: record.folder || DEFAULT_FOLDER,
    attachedCluster: record.attachedCluster || "",
    pluginId: record.pluginId || "blank",
    level: record.level || "starter",
    type: record.type || "expert",
    notes: record.notes || "",
    doc,
    lineage: record.lineage || { dependsOn: [] },
    connections: record.connections || { database: "", kafka: "", schemaRegistry: "" },
  };
}

export function applyNotebookServer(record, dto) {
  if (!record || !dto) return record;
  if (dto.id) record.id = dto.id;
  if (dto.name) record.name = dto.name;
  if (dto.folder) record.folder = dto.folder;
  if ("attachedCluster" in dto) record.attachedCluster = dto.attachedCluster || "";
  if (dto.pluginId) record.pluginId = dto.pluginId;
  if (dto.level) record.level = dto.level;
  if (dto.type) record.type = dto.type;
  if ("notes" in dto) record.notes = dto.notes || "";
  if (dto.doc) record.doc = dto.doc;
  if (dto.lineage) record.lineage = dto.lineage;
  if (dto.connections) record.connections = dto.connections;
  record.lastDeployStatus = dto.lastDeployStatus || record.lastDeployStatus || "never";
  record.lastDeployError = dto.lastDeployError || "";
  record.lastDeployedAt = dto.lastDeployedAt || null;
  if (dto.createdAt) record.createdAt = dto.createdAt;
  if (dto.updatedAt) record.updatedAt = dto.updatedAt;
  if (dto.createdAt || dto.id) record.savedOnce = true;
  if (Array.isArray(dto.logs)) record.logs = dto.logs;
  if (dto.bound && record.attachedCluster) {
    record.bound = { name: record.name, cluster: record.attachedCluster };
  }
  // Live runtime state is authoritative from the last status fetch (persisted in
  // liveState), not the deploy outcome. Deploy status stays as history only.
  if (dto.liveState) {
    record.live = {
      state: dto.liveState,
      error: dto.liveState === "failed" ? (record.lastDeployError || "") : "",
      tasks: dto.liveTasks || record.live?.tasks || "",
    };
  } else if (record.lastDeployStatus === "success" || record.lastDeployStatus === "failed") {
    // Deployed but never polled: unknown until a status fetch runs.
    if (!record.live || record.live.state === "not_deployed") {
      record.live = {
        state: "unknown",
        error: record.lastDeployStatus === "failed" ? (record.lastDeployError || "") : "",
        tasks: record.live?.tasks || "",
      };
    }
  }
  if (record.lastDeployStatus === "success") {
    record.liveDoc = structuredClone(record.doc);
  }
  return record;
}

export async function loadNotebooks() {
  try {
    const res = await fetch("/api/notebooks/");
    if (!res.ok) return;
    const rows = await res.json();
    if (!Array.isArray(rows) || !rows.length) return;
    configs.splice(0, configs.length);
    rows.forEach((dto) => {
      const record = applyNotebookServer({
        alertOnFailed: false,
        alertChannels: [],
        logs: [],
        lastDeployStatus: "never",
        lastDeployError: "",
        createdAt: null,
        updatedAt: null,
        savedOnce: true,
        live: { state: "not_deployed", error: "", tasks: "" },
        liveDoc: null,
      }, dto);
      configs.push(record);
      rememberFolder(record.folder);
      rememberSaved(record);
    });
  } catch (_) {
    /* keep in-memory notebooks */
  }
}

export async function upsertNotebook(record) {
  const body = notebookPayload(record);
  let res = await fetch(`/api/notebooks/${encodeURIComponent(record.id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 404) {
    res = await fetch("/api/notebooks/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    return err.error || "Could not save the connector";
  }
  const dto = await res.json();
  applyNotebookServer(record, dto);
  rememberSaved(record);
  return "";
}

export async function loadNotebookLogs(record) {
  if (!record?.id) return;
  try {
    const res = await fetch(`/api/notebooks/${encodeURIComponent(record.id)}/logs`);
    if (!res.ok) return;
    const payload = await res.json();
    record.logs = payload.items || [];
  } catch (_) {
    /* keep local logs */
  }
}

export async function persistNotebookLog(record, entry) {
  if (!record?.id || !entry) return;
  try {
    await fetch(`/api/notebooks/${encodeURIComponent(record.id)}/logs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    });
  } catch (_) {
    /* local log still shown */
  }
}

export async function deployNotebook(record, retried = false) {
  ui.deployingId = record.id;
  window.dispatchEvent(new Event("cfg-render"));
  let handedOff = false;
  try {
    const res = await fetch(`/api/notebooks/${encodeURIComponent(record.id)}/deploy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(notebookPayload(record)),
    });
    const payload = await res.json().catch(() => ({}));
    const dto = payload.notebook || {};
    if (res.status === 404 && !retried) {
      const created = await fetch("/api/notebooks/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(notebookPayload(record)),
      });
      if (created.ok) {
        applyNotebookServer(record, await created.json());
        handedOff = true;
        return deployNotebook(record, true);
      }
    }
    applyNotebookServer(record, dto);
    if (payload.result?.state) {
      record.live = {
        state: String(payload.result.state).toLowerCase(),
        error: payload.ok === false ? (payload.error || "") : "",
        tasks: "",
      };
    }
    if (payload.ok === false || !res.ok) {
      record.lastDeployStatus = "failed";
      record.lastDeployError = payload.error || record.lastDeployError || "Deploy failed";
      record.live = { state: "failed", error: record.lastDeployError, tasks: "" };
      rememberSaved(record);
      return record.lastDeployError;
    }
    bindIdentity(record);
    rememberSaved(record);
    return "";
  } catch (err) {
    record.lastDeployStatus = "failed";
    record.lastDeployError = String(err.message || err);
    record.live = { state: "failed", error: record.lastDeployError, tasks: "" };
    return record.lastDeployError;
  } finally {
    if (!handedOff) {
      ui.deployingId = null;
      window.dispatchEvent(new Event("cfg-render"));
    }
  }
}

export async function validateNotebook(record, retried = false) {
  ui.validatingId = record.id;
  window.dispatchEvent(new Event("cfg-render"));
  let handedOff = false;
  try {
    const res = await fetch(`/api/notebooks/${encodeURIComponent(record.id)}/validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(notebookPayload(record)),
    });
    const payload = await res.json().catch(() => ({}));
    if (res.status === 404 && !retried) {
      const created = await fetch("/api/notebooks/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(notebookPayload(record)),
      });
      if (created.ok) {
        applyNotebookServer(record, await created.json());
        handedOff = true;
        return validateNotebook(record, true);
      }
    }
    if (payload.notebook) applyNotebookServer(record, payload.notebook);
    const errors = Array.isArray(payload.errors) ? payload.errors.filter(Boolean) : [];
    if (payload.ok) {
      const result = { ok: true, message: payload.message || "Kafka Connect accepted this config." };
      ui.validate = result;
      return result;
    }
    if (!errors.length && payload.error) errors.push(payload.error);
    if (!errors.length) errors.push(payload.message || "Kafka Connect rejected this config.");
    const result = { ok: false, errors };
    ui.validate = result;
    return result;
  } catch (err) {
    const result = { ok: false, errors: [String(err.message || err)] };
    ui.validate = result;
    return result;
  } finally {
    if (!handedOff) {
      ui.validatingId = null;
      window.dispatchEvent(new Event("cfg-render"));
    }
  }
}

function splitChannelNames(value) {
  return String(value || "").split(",").map((s) => s.trim()).filter(Boolean);
}

export function findFailedAlert(alerts, record) {
  const list = Array.isArray(alerts) ? alerts : [];
  if (record?.alertId) {
    const byId = list.find((a) => a.id === record.alertId);
    if (byId) return byId;
  }
  if (record?.id) {
    const byNotebook = list.find((a) => a.notebookId === record.id);
    if (byNotebook) return byNotebook;
  }
  const name = record?.name;
  if (!name) return null;
  return list.find((a) => a.connectorName === name) || null;
}

export function defaultAlertRules() {
  return [{ rule: "FAILED", action: "pause" }];
}

export function normalizeAlertRules(record) {
  if (Array.isArray(record?.alertRules) && record.alertRules.length) {
    const seen = new Set();
    const out = [];
    for (const item of record.alertRules) {
      const rule = String(item?.rule || "FAILED").toUpperCase();
      let action = String(item?.action || "pause").toLowerCase();
      if (action !== "re-trigger" && action !== "notify") action = "pause";
      if (rule === "PAUSED" && action === "pause") action = "notify";
      if (!["FAILED", "UNKNOWN", "PAUSED"].includes(rule) || seen.has(rule)) continue;
      seen.add(rule);
      out.push({ rule, action });
    }
    if (out.length) return out;
  }
  return defaultAlertRules();
}

export function applyConfigAlerts(rows) {
  const alerts = Array.isArray(rows) ? rows : [];
  configs.forEach((record) => {
    if (isEditorDirty(record)) return;
    const hit = findFailedAlert(alerts, record);
    if (!hit) return;
    record.alertId = hit.id;
    record.alertOnFailed = hit.active !== false;
    record.alertChannels = splitChannelNames(hit.channelName);
    record.alertRules = Array.isArray(hit.rules) && hit.rules.length ? hit.rules : defaultAlertRules();
    record.alertCheckEveryMin = hit.checkEveryMin;
    rememberSaved(record);
  });
}

function configAlertPayload(record, names) {
  const first = channelByName(names[0]);
  const plugin = pluginById(record.pluginId);
  const connectorType = plugin?.type === "sink" ? "sink" : "source";
  const rules = normalizeAlertRules(record);
  const head = rules[0] || { rule: "FAILED", action: "pause" };
  const every = parseInt(record.alertCheckEveryMin, 10);
  return {
    name: `${record.name} · ${rules.map((r) => r.rule).join(",")}`,
    notebookId: record.id,
    connectorName: record.name,
    connectorType,
    conditionMetric: "connector_status",
    conditionOp: "eq",
    conditionValue: head.rule,
    severity: "high",
    channelType: first?.type || "slack",
    channelName: names.join(", "),
    action: head.action,
    rules,
    checkEveryMin: Number.isFinite(every) && every >= 1 ? every : 5,
    active: true,
  };
}

export function alertChannelWarning(record) {
  if (!record?.alertOnFailed) return "";
  if (normalizeAlertChannels(record).length) return "";
  if (!channels.length) return "Add a notification channel on Connections before saving this alert.";
  return "Select a notification channel before saving this alert.";
}

export async function syncConfigAlert(record) {
  if (!record?.name) return "";
  let alerts = [];
  try {
    const res = await fetch("/api/alerts");
    if (res.ok) alerts = await res.json();
  } catch (_) {
    return "Could not reach alerts API";
  }
  const existing = findFailedAlert(alerts, record);
  const names = normalizeAlertChannels(record);
  const channelWarn = alertChannelWarning(record);
  if (channelWarn) return channelWarn;

  if (!record.alertOnFailed) {
    if (!existing || existing.active === false) return "";
    const res = await fetch(`/api/alerts/${existing.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: false }),
    });
    if (!res.ok) return "Could not disable the alert";
    record.alertId = existing.id;
    return "";
  }

  const body = configAlertPayload(record, names);
  if (existing) {
    const res = await fetch(`/api/alerts/${existing.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, active: true }),
    });
    if (!res.ok) return "Could not update the alert";
    record.alertId = existing.id;
    return "";
  }
  const res = await fetch("/api/alerts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 409) {
    const err = await res.json().catch(() => ({}));
    if (err.id) {
      const retry = await fetch(`/api/alerts/${err.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...body, active: true }),
      });
      if (!retry.ok) return "Could not update the alert";
      record.alertId = err.id;
      return "";
    }
  }
  if (!res.ok) return "Could not create the alert";
  const saved = await res.json().catch(() => ({}));
  if (saved.id) record.alertId = saved.id;
  return "";
}

export function clusterOptions(attached) {
  const names = clusters.map((c) => c.name);
  if (attached && !names.includes(attached)) names.unshift(attached);
  return names;
}

export function clusterByName(name) {
  return clusters.find((c) => c.name === name) || (name ? { name, url: "" } : null);
}

export const kcActions = [];

export async function loadKcActions() {
  try {
    const res = await fetch("/api/kc/actions");
    if (!res.ok) return;
    const payload = await res.json();
    kcActions.length = 0;
    (payload.actions || []).forEach((row) => {
      if (row?.key) kcActions.push(row);
    });
  } catch (_) {
    /* keep empty; UI uses fallback */
  }
}

export function channelOptions(selected) {
  const wanted = Array.isArray(selected) ? selected.filter(Boolean) : (selected ? [selected] : []);
  const list = channels.map((c) => ({ ...c }));
  wanted.forEach((name) => {
    if (!list.some((c) => c.name === name)) list.unshift({ name, type: "" });
  });
  return list;
}

export function channelByName(name) {
  return channels.find((c) => c.name === name) || null;
}

export function normalizeAlertChannels(record) {
  const names = [];
  if (Array.isArray(record?.alertChannels)) names.push(...record.alertChannels);
  else if (record?.alertChannel) names.push(record.alertChannel);
  return uniq(names);
}

export const plugins = [];

export function applyPluginCatalog(rows) {
  plugins.length = 0;
  (rows || []).forEach((row) => {
    if (!row?.name) return;
    plugins.push({
      name: row.name,
      type: row.type || "",
      format: row.format || "",
      db: row.db || "",
      description: row.description || "",
      config: row.config && typeof row.config === "object" ? row.config : {},
      isBuiltin: Boolean(row.isBuiltin),
    });
  });
  plugins.sort((a, b) => a.name.localeCompare(b.name));
}

export async function loadPluginCatalog() {
  try {
    const res = await fetch("/api/plugins");
    if (!res.ok) return;
    const payload = await res.json();
    applyPluginCatalog(Array.isArray(payload) ? payload : []);
  } catch (_) {
    applyPluginCatalog([]);
  }
}

export function pluginById(id) {
  if (!id || id === "blank") return null;
  return plugins.find((p) => p.name === id) || null;
}

export function pluginOptions(currentId) {
  const list = [{ id: "blank", name: "Blank JSON", type: "expert" }];
  plugins.forEach((p) => list.push({ id: p.name, name: p.name, type: p.type }));
  if (currentId && !list.some((p) => p.id === currentId)) {
    list.push({ id: currentId, name: currentId, type: "" });
  }
  return list;
}

export const recipes = [
  {
    id: "pg-cdc",
    name: "Postgres CDC",
    type: "source",
    levels: ["advanced", "production", "starter"],
    blurb: "Snapshot + stream, Schema Registry, unwrap SMT, heartbeat, DLQ",
    binds: ["kafka", "schemaRegistry"],
    suggestedVars: ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"],
  },
  {
    id: "s3-sink",
    name: "S3 sink",
    type: "sink",
    levels: ["advanced", "production"],
    blurb: "topics, DLQ, S3 bucket and format",
    binds: ["kafka"],
    suggestedVars: ["S3_BUCKET", "S3_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
  },
  {
    id: "file-sink",
    name: "File sink",
    type: "sink",
    levels: ["starter"],
    blurb: "Write one topic to a local file",
    binds: ["kafka"],
    suggestedVars: [],
  },
  {
    id: "blank",
    name: "Blank JSON",
    type: "expert",
    levels: ["starter"],
    blurb: "Empty connector JSON. One class only.",
    binds: [],
    suggestedVars: [],
  },
];

export const REQUIRED_KEYS = {
  "pg-cdc": ["connector.class", "database.hostname", "database.password", "slot.name", "topic.prefix", "plugin.name"],
  "s3-sink": ["connector.class", "topics", "s3.bucket.name", "format.class"],
  "file-sink": ["connector.class", "topics", "file"],
  blank: ["connector.class"],
};

export const ADVANCED_KEYS = {
  "pg-cdc": [
    "heartbeat.interval.ms",
    "transforms",
    "transforms.unwrap.type",
    "errors.deadletterqueue.topic.name",
    "key.converter",
    "value.converter",
  ],
  "s3-sink": ["errors.deadletterqueue.topic.name", "flush.size", "rotate.interval.ms"],
  "file-sink": ["tasks.max"],
  blank: [],
};

export const folders = ["default"];

export const configs = [];

export const ui = {
  query: "",
  expanded: new Set(["folder:default"]),
  selection: { kind: "home" },
  galleryTab: "advanced",
  galleryCard: "pg-cdc",
  galleryBinds: { kafka: "", schemaRegistry: "" },
  advancedOpen: null,
  notesOpen: false,
  notesMode: "preview",
  lineageExpand: false,
  validate: null,
  validatedFp: null,
  savedClone: {},
  topicWarnDismissed: false,
  secretQuery: "",
  apiAction: "status",
  apiGroup: "inspect",
  apiParams: {},
  apiResult: null,
  apiSending: false,
  apiLog: [],
  apiLogOpen: null,
  configFormat: "json",
  deployingId: null,
  validatingId: null,
  editing: {},
};

configs.forEach((c) => {
  c.liveDoc = c.live.state === "not_deployed" ? null : structuredClone(c.doc);
  rememberSaved(c);
});

export function recipeById(id) {
  return recipes.find((r) => r.id === id);
}

export function configById(id) {
  return configs.find((c) => c.id === id);
}

export function configByName(name) {
  return configs.find((c) => c.name === name);
}

export function resolveValue(text, missing) {
  return secretsApi().resolve(text, missing);
}

export function collectDocVarKeys(doc) {
  const keys = [];
  Object.values(doc?.config || {}).forEach((value) => {
    if (typeof value === "string") keys.push(...collectVarKeys(value));
  });
  return [...new Set(keys)];
}

export function resolveConfig(record) {
  const missing = [];
  const used = collectDocVarKeys(record?.doc);
  const doc = structuredClone(record?.doc || { name: "", config: {} });
  doc.config = doc.config || {};
  Object.entries(doc.config).forEach(([key, value]) => {
    if (typeof value === "string") doc.config[key] = resolveValue(value, missing);
  });
  return { doc, used, missing: [...new Set(missing)] };
}

export function listSecretRefs() {
  return secretsApi().listRefs();
}

export function folderName(path) {
  const parts = String(path || "").split("/").filter(Boolean);
  return parts[parts.length - 1] || DEFAULT_FOLDER;
}

export function parentFolder(path) {
  const parts = String(path || "").split("/").filter(Boolean);
  return parts.slice(0, -1).join("/");
}

export function allFolders() {
  const names = new Set([...folders, ...configs.map((c) => c.folder || DEFAULT_FOLDER)]);
  for (const path of [...names]) {
    const parts = String(path).split("/").filter(Boolean);
    let acc = "";
    for (const part of parts) {
      acc = acc ? `${acc}/${part}` : part;
      names.add(acc);
    }
  }
  const list = [...names].sort();
  if (!list.includes(DEFAULT_FOLDER)) list.unshift(DEFAULT_FOLDER);
  else {
    list.splice(list.indexOf(DEFAULT_FOLDER), 1);
    list.unshift(DEFAULT_FOLDER);
  }
  return list;
}

export function childFolders(parent = "") {
  return allFolders().filter((d) => parentFolder(d) === (parent || "")).sort();
}

export function configsFor(folder) {
  return configs.filter((c) => (c.folder || DEFAULT_FOLDER) === folder);
}

export function expandFolderPath(expanded, path) {
  const parts = String(path || "").split("/").filter(Boolean);
  let acc = "";
  for (const part of parts) {
    acc = acc ? `${acc}/${part}` : part;
    expanded.add(`folder:${acc}`);
  }
}

export function rememberFolder(path) {
  const parts = String(path || "").split("/").filter(Boolean);
  let acc = "";
  for (const part of parts) {
    acc = acc ? `${acc}/${part}` : part;
    if (!folders.includes(acc)) folders.push(acc);
  }
  return acc;
}

export function addFolder(name, parent = "") {
  const segment = String(name || "").trim().replace(/[\\/]/g, "-") || "folder";
  const domain = parent ? `${parent}/${segment}` : segment;
  rememberFolder(domain);
  return domain;
}

export async function loadFolders() {
  try {
    const res = await fetch("/api/folders/");
    if (!res.ok) return;
    const rows = await res.json();
    if (!Array.isArray(rows)) return;
    rows.forEach((row) => rememberFolder(row.path || row));
  } catch (_) {
    /* keep folders already on screen */
  }
}

export async function createFolder(name, parent = "") {
  const segment = String(name || "").trim().replace(/[\\/]/g, "-") || "folder";
  const path = parent ? `${parent}/${segment}` : segment;
  try {
    const res = await fetch("/api/folders/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { path: "", error: err.error || "Could not create the folder" };
    }
  } catch (_) {
    return { path: "", error: "Could not reach the folders API" };
  }
  rememberFolder(path);
  return { path, error: "" };
}

export async function renameFolderRemote(from, leaf) {
  const next = String(leaf || "").trim().replace(/[\\/]/g, "-");
  if (!from || !next) return { path: from, error: "Folder name is required" };
  const parent = parentFolder(from);
  const dest = parent ? `${parent}/${next}` : next;
  if (dest === from) return { path: from, error: "" };
  try {
    const res = await fetch("/api/folders/", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from, to: dest }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return { path: from, error: err.error || "Could not rename the folder" };
    }
  } catch (_) {
    return { path: from, error: "Could not reach the folders API" };
  }
  renameFolder(from, next);
  return { path: dest, error: "" };
}

export async function deleteFolderRemote(path) {
  if (!path) return "Folder name is required";
  try {
    const res = await fetch("/api/folders/", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return err.error || "Could not delete the folder";
    }
  } catch (_) {
    return "Could not reach the folders API";
  }
  deleteFolder(path);
  return "";
}

export function renameFolder(from, to) {
  const next = String(to || "").trim().replace(/[\\/]/g, "-");
  if (!from || !next || from === next) return from;
  const parent = parentFolder(from);
  const dest = parent ? `${parent}/${next}` : next;
  configs.forEach((c) => {
    if (c.folder === from) c.folder = dest;
    else if (c.folder.startsWith(`${from}/`)) c.folder = dest + c.folder.slice(from.length);
  });
  for (let i = folders.length - 1; i >= 0; i--) {
    if (folders[i] === from || folders[i].startsWith(`${from}/`)) folders.splice(i, 1);
  }
  addFolder(dest);
  return dest;
}

export function deleteFolder(path) {
  if (!path) return;
  for (let i = configs.length - 1; i >= 0; i--) {
    const folder = configs[i].folder || "";
    if (folder === path || folder.startsWith(`${path}/`)) configs.splice(i, 1);
  }
  for (let i = folders.length - 1; i >= 0; i--) {
    if (folders[i] === path || folders[i].startsWith(`${path}/`)) folders.splice(i, 1);
  }
}

export function uniqueName(base) {
  const root = String(base || "new-connector").trim() || "new-connector";
  if (!configs.some((c) => c.name === root)) return root;
  let n = 2;
  while (configs.some((c) => c.name === `${root}-${n}`)) n += 1;
  return `${root}-${n}`;
}

export function maskSecrets(doc) {
  return structuredClone(doc || { name: "", config: {} });
}

export function generateDoc({ recipeId, level, name, binds }) {
  const recipe = recipeById(recipeId) || recipes[0];
  const advanced = level === "advanced" || level === "production";
  const config = { "connector.class": "", "tasks.max": "1" };
  if (recipe.id === "pg-cdc") {
    config["connector.class"] = "io.debezium.connector.postgresql.PostgresConnector";
    config["database.hostname"] = "{prod.DB_HOST}";
    config["database.port"] = "5432";
    config["database.user"] = "debezium";
    config["database.password"] = "{prod.DB_PASSWORD}";
    config["database.dbname"] = "orders";
    config["topic.prefix"] = "dbserver1";
    config["plugin.name"] = "pgoutput";
    config["slot.name"] = "orders_slot";
    if (advanced) {
      config["heartbeat.interval.ms"] = "10000";
      config.transforms = "unwrap";
      config["transforms.unwrap.type"] = "io.debezium.transforms.ExtractNewRecordState";
      config["errors.deadletterqueue.topic.name"] = "dbserver1.dlq";
      if (binds.schemaRegistry) {
        config["key.converter"] = "io.confluent.connect.avro.AvroConverter";
        config["value.converter"] = "io.confluent.connect.avro.AvroConverter";
      }
    }
  } else if (recipe.id === "s3-sink") {
    config["connector.class"] = "io.confluent.connect.s3.S3SinkConnector";
    config.topics = "dbserver1.public.orders";
    config["s3.bucket.name"] = "cdc-orders";
    config["s3.region"] = "eu-central-1";
    config["format.class"] = "io.confluent.connect.s3.format.json.JsonFormat";
    if (advanced) {
      config["errors.deadletterqueue.topic.name"] = "s3.orders.dlq";
      config["flush.size"] = "1000";
    }
  } else if (recipe.id === "file-sink") {
    config["connector.class"] = "org.apache.kafka.connect.file.FileStreamSinkConnector";
    config.topics = binds.kafka ? `${binds.kafka}.demo` : "demo.topic";
    config.file = "/tmp/out.json";
  } else {
    return { name: name || "", config: {} };
  }
  if (binds.kafka && recipe.type === "sink") config["bootstrap.servers"] = `${binds.kafka}:9092`;
  return maskSecrets({ name: name || uniqueName(recipe.id === "pg-cdc" ? "pg-orders-src" : recipe.id === "s3-sink" ? "s3-orders-sink" : "file-sink"), config });
}

export function insertNotes(recipeId, level) {
  if (level === "starter" || recipeId === "blank") return "";
  if (recipeId === "pg-cdc") return "## Postgres CDC\n\nSource connector only. Pair a **sink** in another notebook.\n\n`slot.name` must be unique on the database.";
  if (recipeId === "s3-sink") return "## S3 sink\n\nConsumes topics from a source notebook. Set lineage depends-on to that source.";
  return "";
}

export function insertLineage(recipeId, level, binds) {
  if (level === "starter" || recipeId === "blank") return { dependsOn: [] };
  const dependsOn = [];
  if (recipeId === "s3-sink") {
    const src = configs.find((c) => c.pluginId === "pg-cdc" && c.folder);
    if (src) dependsOn.push({ type: "connector", name: src.name });
  }
  return { dependsOn };
}

export function classForPlugin(pluginId) {
  if (!pluginId || pluginId === "blank") return "";
  const live = pluginById(pluginId);
  if (live?.config?.["connector.class"]) return live.config["connector.class"];
  const doc = generateDoc({
    recipeId: pluginId,
    level: "starter",
    binds: { kafka: "", schemaRegistry: "" },
    name: "tmp",
  });
  return doc?.config?.["connector.class"] || "";
}

export function applyPluginToRecord(record, pluginId) {
  record.pluginId = pluginId || "blank";
  const live = pluginById(pluginId);
  record.type = live?.type || (pluginId === "blank" ? "expert" : record.type);
  record.doc = record.doc || { name: record.name, config: {} };
  if (!pluginId || pluginId === "blank") {
    record.doc.config = {};
    return;
  }
  if (live?.config) {
    record.doc.config = structuredClone(live.config);
    return;
  }
  const cls = classForPlugin(pluginId);
  record.doc.config = cls ? { "connector.class": cls } : {};
}

export function insertBlank({ folder, pluginId = "blank" }) {
  const name = uniqueName("untitled");
  const record = {
    id: crypto.randomUUID ? crypto.randomUUID() : `cfg-${Date.now()}`,
    name,
    folder: folder || DEFAULT_FOLDER,
    attachedCluster: "",
    pluginId: "blank",
    level: "starter",
    connections: { database: "", kafka: "", schemaRegistry: "" },
    notes: "",
    alertOnFailed: false,
    alertChannels: [],
    doc: { name, config: {} },
    lineage: { dependsOn: [] },
    logs: [],
    lastDeployStatus: "never",
    lastDeployError: "",
    createdAt: null,
    updatedAt: null,
    savedOnce: false,
    live: { state: "not_deployed", error: "", tasks: "" },
    liveDoc: null,
    type: "expert",
  };
  applyPluginToRecord(record, pluginId);
  record.doc.name = name;
  configs.push(record);
  addFolder(record.folder);
  rememberSaved(record);
  return record;
}

export function insertConfig({ folder, recipeId, level, binds }) {
  const recipe = recipeById(recipeId);
  const doc = generateDoc({ recipeId, level, binds, name: "" });
  if (!doc.name) doc.name = uniqueName("new-connector");
  else doc.name = uniqueName(doc.name);
  const record = {
    id: crypto.randomUUID ? crypto.randomUUID() : `cfg-${Date.now()}`,
    name: doc.name,
    folder: folder || DEFAULT_FOLDER,
    attachedCluster: "",
    pluginId: recipeId,
    level,
    connections: { ...binds },
    notes: insertNotes(recipeId, level),
    alertOnFailed: false,
    alertChannels: [],
    doc,
    lineage: insertLineage(recipeId, level, binds),
    logs: [],
    lastDeployStatus: "never",
    lastDeployError: "",
    createdAt: null,
    updatedAt: null,
    savedOnce: false,
    live: { state: "not_deployed", error: "", tasks: "" },
    liveDoc: null,
    type: recipe?.type || "expert",
  };
  configs.push(record);
  addFolder(record.folder);
  rememberSaved(record);
  return record;
}

export function cloneConfig(record, { name, folder }) {
  const nextName = uniqueName(name || `${record.name}-copy`);
  const copy = structuredClone(record);
  copy.id = crypto.randomUUID ? crypto.randomUUID() : `cfg-${Date.now()}`;
  copy.name = nextName;
  copy.folder = folder || record.folder;
  copy.doc = structuredClone(record.doc);
  copy.doc.name = nextName;
  copy.live = { state: "not_deployed", error: "", tasks: "" };
  copy.liveDoc = null;
  copy.bound = null;
  copy.logs = [];
  copy.lastDeployStatus = "never";
  copy.lastDeployError = "";
  copy.createdAt = null;
  copy.updatedAt = null;
  copy.savedOnce = false;
  copy.alertOnFailed = false;
  copy.alertChannels = [];
  copy.alertId = null;
  configs.push(copy);
  addFolder(copy.folder);
  rememberSaved(copy);
  return copy;
}

export function saveConfig(record) {
  record.doc = maskSecrets(record.doc);
  if (record.doc) record.doc.name = record.name;
  const existing = configs.findIndex((c) => c.id === record.id);
  if (existing >= 0) configs[existing] = record;
  else configs.push(record);
  addFolder(record.folder);
  delete record._draftJson;
  rememberSaved(record);
  return record;
}

function packEditor(record) {
  let doc = record.doc;
  let jsonInvalid = false;
  let raw = "";
  if (record._draftJson != null) {
    try {
      doc = JSON.parse(record._draftJson);
    } catch {
      jsonInvalid = true;
      raw = record._draftJson;
    }
  }
  return {
    name: record.name,
    pluginId: record.pluginId,
    attachedCluster: record.attachedCluster || "",
    alertOnFailed: Boolean(record.alertOnFailed),
    alertChannels: normalizeAlertChannels(record),
    alertRules: normalizeAlertRules(record),
    alertCheckEveryMin: record.alertCheckEveryMin || 5,
    notes: record.notes || "",
    doc,
    lineage: record.lineage || { dependsOn: [] },
    jsonInvalid,
    raw,
  };
}

function packConfigSlice(packed) {
  return {
    name: packed.name,
    pluginId: packed.pluginId,
    attachedCluster: packed.attachedCluster,
    doc: packed.doc,
    lineage: packed.lineage,
    jsonInvalid: packed.jsonInvalid,
    raw: packed.raw,
  };
}

function packAlertSlice(packed) {
  return {
    alertOnFailed: packed.alertOnFailed,
    alertChannels: packed.alertChannels,
    alertRules: packed.alertRules,
    alertCheckEveryMin: packed.alertCheckEveryMin,
  };
}

function packDocSlice(packed) {
  return { notes: packed.notes };
}

export function editorFingerprint(record) {
  if (!record) return "";
  return JSON.stringify(packConfigSlice(packEditor(record)));
}

export function rememberSaved(record) {
  if (!record?.id) return;
  ui.savedClone[record.id] = structuredClone(packEditor(record));
}

export function isEditorDirty(record) {
  if (!record?.id) return false;
  const saved = ui.savedClone[record.id];
  if (!saved) return false;
  return JSON.stringify(packEditor(record)) !== JSON.stringify(saved);
}

export function needsSave(record) {
  // Unsaved records (new or just cloned) can be saved immediately; saved ones only when dirty.
  if (!record?.id) return false;
  return !record.savedOnce || isEditorDirty(record);
}

export function isConfigDirty(record) {
  const saved = ui.savedClone[record?.id];
  if (!record?.id || !saved) return false;
  return JSON.stringify(packConfigSlice(packEditor(record))) !== JSON.stringify(packConfigSlice(saved));
}

export function isAlertDirty(record) {
  const saved = ui.savedClone[record?.id];
  if (!record?.id || !saved) return false;
  return JSON.stringify(packAlertSlice(packEditor(record))) !== JSON.stringify(packAlertSlice(saved));
}

export function isDocDirty(record) {
  const saved = ui.savedClone[record?.id];
  if (!record?.id || !saved) return false;
  return JSON.stringify(packDocSlice(packEditor(record))) !== JSON.stringify(packDocSlice(saved));
}

export function isEditing(record, surface) {
  if (!record) return false;
  if (!record.savedOnce) return true;
  return Boolean(ui.editing[record.id]?.[surface]);
}

export function startEdit(record, surface) {
  if (!record?.id) return;
  const cur = ui.editing[record.id] || { config: false, alerts: false, docs: false };
  ui.editing[record.id] = { ...cur, [surface]: true };
}

export function lockEdits(record) {
  if (!record?.id) return;
  ui.editing[record.id] = { config: false, alerts: false, docs: false };
}

export function cancelConfigEdit(record) {
  const saved = ui.savedClone[record?.id];
  if (!record?.id) return;
  if (saved) {
    record.name = saved.name;
    record.pluginId = saved.pluginId;
    record.attachedCluster = saved.attachedCluster;
    record.doc = structuredClone(saved.doc);
    record.lineage = structuredClone(saved.lineage);
    delete record._draftJson;
    if (isBound(record)) {
      record.name = record.bound.name;
      record.attachedCluster = record.bound.cluster;
      if (record.doc) record.doc.name = record.bound.name;
    }
  }
  const cur = ui.editing[record.id] || { config: false, alerts: false, docs: false };
  ui.editing[record.id] = { ...cur, config: false };
}

export function restoreSaved(record) {
  const saved = ui.savedClone[record?.id];
  if (!record || !saved) return;
  const next = structuredClone(saved);
  record.name = next.name;
  record.pluginId = next.pluginId;
  record.attachedCluster = next.attachedCluster;
  record.alertOnFailed = next.alertOnFailed;
  record.alertChannels = Array.isArray(next.alertChannels) ? next.alertChannels : [];
  record.alertRules = Array.isArray(next.alertRules) ? next.alertRules : defaultAlertRules();
  record.alertCheckEveryMin = next.alertCheckEveryMin;
  delete record.alertChannel;
  record.notes = next.notes;
  record.doc = next.doc;
  record.lineage = next.lineage;
  delete record._draftJson;
  if (isBound(record)) {
    record.name = record.bound.name;
    record.attachedCluster = record.bound.cluster;
    if (record.doc) record.doc.name = record.bound.name;
  }
  if (record.savedOnce) lockEdits(record);
}

export function canDeploy(record) {
  if (ui.deployingId && record && ui.deployingId === record.id) return false;
  if (!record?.attachedCluster) return false;
  if (isConfigDirty(record)) return false;
  if (!ui.validate?.ok) return false;
  return ui.validatedFp === editorFingerprint(record);
}

export function canValidate(record) {
  return Boolean(record?.attachedCluster) && record.savedOnce && !isConfigDirty(record);
}

export function deleteConfig(id) {
  const index = configs.findIndex((c) => c.id === id);
  if (index >= 0) configs.splice(index, 1);
  fetch(`/api/notebooks/${encodeURIComponent(id)}`, { method: "DELETE" }).catch(() => {});
}

export function topicsOf(record) {
  const cfg = record?.doc?.config || {};
  const prefix = cfg["topic.prefix"];
  const topics = cfg.topics;
  if (topics) return String(topics).split(",").map((t) => t.trim()).filter(Boolean);
  if (prefix) return [`${prefix}.*`];
  return [];
}

export function downstreamOf(record) {
  if (!record) return [];
  const topics = new Set(topicsOf(record));
  return configs.filter((other) => {
    if (other.id === record.id) return false;
    return (other.lineage?.dependsOn || []).some((dep) => {
      if (dep.type === "connector" && dep.name === record.name) return true;
      if (dep.type === "topic" && topics.has(dep.name)) return true;
      return false;
    });
  });
}

export function upstreamConnectors(record) {
  return (record?.lineage?.dependsOn || [])
    .filter((d) => d.type === "connector")
    .map((d) => configByName(d.name))
    .filter(Boolean);
}

export function liveDot(record) {
  return record?.live?.state || "not_deployed";
}

export function isBound(record) {
  return Boolean(record?.bound?.name && record?.bound?.cluster);
}

export function bindIdentity(record) {
  if (!record?.name || !record?.attachedCluster) return record;
  if (!record.bound) {
    record.bound = { name: record.name, cluster: record.attachedCluster };
  }
  record.name = record.bound.name;
  record.attachedCluster = record.bound.cluster;
  if (record.doc) record.doc.name = record.bound.name;
  return record;
}

export function connectorStatus(record) {
  const live = String(record?.live?.state || "").toLowerCase();
  if (live === "deleted") return "deleted";
  if (live === "failed") return "failed";
  if (live === "paused" || live === "pause") return "pause";
  if (live === "running") return "running";
  if (live === "unknown") return "unknown";
  if (record?.lastDeployStatus === "failed") return "failed";
  if (isBound(record) || record?.lastDeployStatus === "success") return "unknown";
  return "draft";
}

export function identityChipHtml(record) {
  const st = connectorStatus(record);
  return `<span class="cfg-id-chip is-${esc(st)}">${esc(st)}</span>`;
}

function _effectiveLiveState(data) {
  const connector = String((data?.connector || {}).state || "UNKNOWN").toUpperCase();
  const taskStates = (data?.tasks || []).map((t) => String((t || {}).state || "UNKNOWN").toUpperCase());
  if (connector === "FAILED" || taskStates.some((s) => s === "FAILED")) return "failed";
  if (connector === "RUNNING" && taskStates.length && taskStates.every((s) => s === "RUNNING")) return "running";
  if (connector === "PAUSED" || taskStates.some((s) => s === "PAUSED")) return "pause";
  if (connector === "RUNNING" && !taskStates.length) return "unknown";
  const other = taskStates.find((s) => s !== "RUNNING");
  if (other === "FAILED") return "failed";
  if (other) return other.toLowerCase() === "paused" ? "pause" : "unknown";
  return connector === "RUNNING" ? "unknown" : (connector.toLowerCase() || "unknown");
}

export async function refreshLiveStatus(record) {
  if (!record) return;
  const cluster = record.attachedCluster || record.bound?.cluster || "";
  if (!cluster || !record.name) {
    if (!record.live || record.live.state === "not_deployed") {
      record.live = { state: "not_deployed", error: "", tasks: "" };
    }
    return;
  }
  try {
    const res = await fetch(
      `/api/kc/connections/${encodeURIComponent(cluster)}/connectors/${encodeURIComponent(record.name)}/status`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
    );
    const payload = await res.json().catch(() => ({}));
    const err = String(payload.error || "");
    if (!payload.ok) {
      if (/not found/i.test(err) && (isBound(record) || record.lastDeployStatus === "success")) {
        record.live = { state: "deleted", error: "", tasks: "" };
      } else {
        record.live = { state: "unknown", error: err, tasks: record.live?.tasks || "" };
      }
    } else {
      record.live = {
        state: _effectiveLiveState(payload.data || {}),
        error: "",
        tasks: String((payload.data?.tasks || []).length),
      };
    }
  } catch {
    record.live = { state: "unknown", error: "", tasks: record.live?.tasks || "" };
  }
  persistLiveState(record);
}

// Best-effort cache of the observed state to the DB so reloads reflect reality.
async function persistLiveState(record) {
  if (!record?.id || !record.savedOnce || !record.live) return;
  try {
    await fetch(`/api/notebooks/${encodeURIComponent(record.id)}/live`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: record.live.state, tasks: record.live.tasks || "" }),
    });
  } catch {
    /* status cache is non-critical */
  }
}

export function editorVsLive(record) {
  if (!isBound(record) || !record.liveDoc) return "not_deployed";
  try {
    return JSON.stringify(record.doc) === JSON.stringify(record.liveDoc) ? "matches" : "differs";
  } catch {
    return "differs";
  }
}

export function impact(record) {
  const deployed = isBound(record);
  return {
    action: deployed ? "UPDATE" : "CREATE",
    topics: topicsOf(record).length,
    downstream: downstreamOf(record).length,
  };
}

export function validateDoc(record) {
  const errors = [];
  const doc = record?.doc;
  if (!record?.name) errors.push("Name is required.");
  if (!doc?.config?.["connector.class"]) errors.push("connector.class is required.");
  const { used, missing } = resolveConfig(record);
  missing.forEach((key) => errors.push(`{${key}} is missing from Connections secrets.`));
  if (errors.length) return { ok: false, errors };
  return { ok: true, message: `Valid for ${doc.config["connector.class"]}. ${used.length ? `Resolved ${used.length} secret ref(s).` : "No secret refs."}` };
}

export function mockDeploy(record) {
  if (!record.attachedCluster) throw new Error("Attach a Connect cluster first.");
  const { doc, missing } = resolveConfig(record);
  if (missing.length) throw new Error(`Missing secrets: ${missing.join(", ")}`);
  const failed = /s3/i.test(record.name) || /S3Sink/i.test(record.doc?.config?.["connector.class"] || "");
  if (failed) {
    record.live = {
      state: "failed",
      error: "Task 0 FAILED\nConnectException: connector class not found on worker",
      tasks: "0/1",
    };
  } else {
    record.live = { state: "running", error: "", tasks: "1/1" };
  }
  record.liveDoc = doc;
  bindIdentity(record);
  rememberSaved(record);
  return record.live;
}

export function setLiveState(record, state) {
  if (record.live.state === "not_deployed") return record.live;
  if (state === "paused") record.live = { ...record.live, state: "paused", error: "" };
  if (state === "running") record.live = { ...record.live, state: "running", error: "", tasks: "1/1" };
  if (state === "restart") {
    return mockDeploy(record);
  }
  return record.live;
}

export function topicKeyChanged(record, original) {
  const now = record?.doc?.config || {};
  const was = original || {};
  return now["topic.prefix"] !== was["topic.prefix"] || now.topics !== was.topics;
}
