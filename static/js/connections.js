// Per-subtype tree-row icons (small line SVGs)
const _CONN_ICONS = {
  db:        '<svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5"/><path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6"/></svg>',
  nosql:     '<svg viewBox="0 0 24 24"><path d="M12 2C8 2 6 4 6 7v10c0 3 2 5 6 5s6-2 6-5V7c0-3-2-5-6-5z"/><path d="M6 12c0 2 2 3 6 3s6-1 6-3"/><path d="M12 2v20"/></svg>',
  warehouse: '<svg viewBox="0 0 24 24"><polygon points="12 3 21 7 12 11 3 7 12 3"/><polyline points="3 12 12 16 21 12"/><polyline points="3 17 12 21 21 17"/></svg>',
  storage:   '<svg viewBox="0 0 24 24"><path d="M5 7h14l-1.5 13a2 2 0 0 1-2 1.8h-7A2 2 0 0 1 6.5 20L5 7z"/><path d="M4 7c0-1.66 3.58-3 8-3s8 1.34 8 3"/></svg>',
  kafka:     '<svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><line x1="9" y1="7" x2="15" y2="7"/><line x1="9" y1="11" x2="15" y2="11"/><line x1="9" y1="15" x2="13" y2="15"/></svg>',
  connect:   '<svg viewBox="0 0 24 24"><path d="M15 7h2a4 4 0 0 1 0 8h-2"/><path d="M9 7H7a4 4 0 0 0 0 8h2"/><line x1="8" y1="12" x2="16" y2="12"/></svg>',
  search:    '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
  webhook:   '<svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>',
  slack:     '<svg viewBox="0 0 24 24"><path fill="#e01e5a" d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z"/><path fill="#36c5f0" d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z"/><path fill="#2eb67d" d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312z"/><path fill="#ecb22e" d="M15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/></svg>',
  gchat:     '<svg viewBox="0 0 24 24"><path fill="#00a67d" d="M22 4H2c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16l4 4V6c0-1.1-.9-2-2-2zm-2 12H6l-2 2V6h16v10z"/><circle cx="9" cy="11" r="1.4" fill="#fff"/><circle cx="13" cy="11" r="1.4" fill="#fff"/><circle cx="17" cy="11" r="1.4" fill="#fff"/></svg>',
  socket:    '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="9" cy="10" r="1.2"/><circle cx="15" cy="10" r="1.2"/><path d="M8 15h8"/></svg>',
};
function _connSubtypeIcon(subtype) {
  const s = (subtype || '').toLowerCase();
  if (['postgres','postgresql','mysql','mariadb','sqlserver','mssql','oracle'].includes(s)) return _CONN_ICONS.db;
  if (['mongodb','mongo','dynamodb','cassandra','couchbase'].includes(s))                   return _CONN_ICONS.nosql;
  if (['snowflake','bigquery','redshift','databricks','clickhouse','synapse'].includes(s))  return _CONN_ICONS.warehouse;
  if (['s3','gcs','azureblob','azure-blob','minio'].includes(s))                            return _CONN_ICONS.storage;
  if (s === 'kafka')                                                                        return _CONN_ICONS.kafka;
  if (s === 'kafka-connect')                                                                return _CONN_ICONS.connect;
  if (s === 'elasticsearch' || s === 'opensearch')                                          return _CONN_ICONS.search;
  if (s === 'notification-slack')                                                            return _CONN_ICONS.slack;
  if (s === 'notification-gchat')                                                            return _CONN_ICONS.gchat;
  if (s === 'notification-webhook' || s === 'webhook' || s === 'http')                       return _CONN_ICONS.webhook;
  return _CONN_ICONS.socket;
}

function _isRetiredSourceSink(c) {
  const type = String(c.type || '').toLowerCase();
  const subtype = String(c.subtype || '').toLowerCase();
  return type === 'source' || type === 'sink' || ['postgres', 'mysql', 's3'].includes(subtype);
}

const connectorTypes = [
  // ── Kafka ──
  { id:'kafka',         group:'transport',  name:'Apache Kafka',    sub:'Message Broker · Streaming',      color:'#231f20', bg:'#e8e8e8',
    icon:'<img src="https://cdn.simpleicons.org/apachekafka/231f20" alt="Kafka">' },
  { id:'kafka-connect', group:'transport',  name:'Kafka Connect',   sub:'Connector Framework · REST API',  color:'#8a8a8a', bg:'#f3f4f6',
    icon:'<svg viewBox="0 0 100 100" width="28" height="28" fill="none" stroke="#8a8a8a" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="50" cy="50" r="45"/><path d="M32 36 L20 50 L32 64 L48 64 L60 50 L48 36 Z"/><path d="M52 36 L40 50 L52 64 L68 64 L80 50 L68 36 Z"/></svg>' },
  { id:'schema-registry', group:'transport', name:'Schema Registry', sub:'Confluent · Apicurio · Avro / Protobuf / JSON Schema', color:'#0073cf', bg:'#d9eeff',
    icon:'<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#0073cf" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5c0-1.1 3.6-2 8-2s8 0.9 8 2v14c0 1.1-3.6 2-8 2s-8-0.9-8-2V5z"/><path d="M4 5c0 1.1 3.6 2 8 2s8-0.9 8-2"/><path d="M4 10c0 1.1 3.6 2 8 2s8-0.9 8-2"/><path d="M4 15c0 1.1 3.6 2 8 2s8-0.9 8-2"/></svg>' },
  // { id:'confluent',     group:'kafka',      name:'Confluent Cloud', sub:'Managed Kafka · Cloud',           color:'#0066cc', bg:'#ddeeff',
  //   icon:'<svg viewBox="0 0 24 24" width="24" height="24"><circle cx="12" cy="12" r="10" fill="#0066cc"/><path d="M7 12c0-2.76 2.24-5 5-5s5 2.24 5 5-2.24 5-5 5" stroke="white" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M9 12c0-1.66 1.34-3 3-3s3 1.34 3 3-1.34 3-3 3" stroke="white" stroke-width="1.5" fill="none"/><circle cx="12" cy="12" r="1.5" fill="white"/></svg>' },

  // ── Notification Channels ──
  { id:'notification-slack',     group:'notification', name:'Slack',        sub:'Incoming Webhook', color:'#4a154b', bg:'#f3e9f5',
    icon:'<svg viewBox="0 0 24 24" width="24" height="24"><path fill="#e01e5a" d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z"/><path fill="#36c5f0" d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z"/><path fill="#2eb67d" d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312z"/><path fill="#ecb22e" d="M15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/></svg>' },
  { id:'notification-gchat',     group:'notification', name:'Google Chat',  sub:'Space Webhook',    color:'#00a67d', bg:'#e0f5ee',
    icon:'<img src="https://cdn.simpleicons.org/googlechat/00a67d" alt="Google Chat">' },
];

// ── Per-connector field definitions ──────────────────────────────────────────
// label       : display name shown in detail + edit rows
// cfgKey      : the Debezium / connector config key stored in the DB
// formKey     : the form field name sent to the API  (matches backend _FORM_MAP)
// inputId     : DOM id used in the inline-edit form
// type        : 'text' | 'password' | 'number'
// placeholder : hint text
// defaultVal  : pre-fill value in edit form (optional)
const CONNECTOR_FIELD_MAP = {
  kafka: [
    { label:'Bootstrap Servers', cfgKey:'bootstrap.servers',  formKey:'bootstrap_servers', inputId:'ieH',    type:'text',     placeholder:'broker1:9092,broker2:9092' },
    { label:'Security Protocol', cfgKey:'security.protocol',  formKey:'security_protocol', inputId:'ieP',    type:'text',     placeholder:'SASL_SSL' },
    { label:'Username',          cfgKey:'sasl.username',       formKey:'username',          inputId:'ieU',    type:'text',     placeholder:'kafka-user' },
    { label:'Password',          cfgKey:'sasl.password',       formKey:'password',          inputId:'iePass', type:'password', placeholder:'••••••••' },
  ],
  'kafka-connect': [
    { label:'REST API URL', cfgKey:'url',           formKey:'url',      inputId:'ieH',    type:'text',     placeholder:'http://kafka-connect:8083' },
    { label:'Username',     cfgKey:'username',      formKey:'username', inputId:'ieU',    type:'text',     placeholder:'(optional)' },
    { label:'Password',     cfgKey:'password',      formKey:'password', inputId:'iePass', type:'password', placeholder:'••••••••' },
  ],
  'schema-registry': [
    { label:'Registry Type', cfgKey:'provider',  formKey:'provider',  inputId:'ieProv', type:'text',     placeholder:'confluent' },
    { label:'Registry URL',  cfgKey:'url',       formKey:'url',       inputId:'ieH',    type:'text',     placeholder:'http://schema-registry:8081' },
    { label:'Authentication',cfgKey:'auth_type', formKey:'auth_type', inputId:'ieAuth', type:'text',     placeholder:'none' },
    { label:'Username',      cfgKey:'username',  formKey:'username',  inputId:'ieU',    type:'text',     placeholder:'API key or username' },
    { label:'Password',      cfgKey:'password',  formKey:'password',  inputId:'iePass', type:'password', placeholder:'••••••••' },
    { label:'Bearer Token',  cfgKey:'token',     formKey:'token',     inputId:'ieTok',  type:'password', placeholder:'••••••••' },
  ],
  'notification-slack': [
    { label:'Webhook URL', cfgKey:'host',     formKey:'host',     inputId:'ieH',    type:'text',     placeholder:'https://hooks.slack.com/services/T00/B00/xxx' },
    { label:'Token',       cfgKey:'password', formKey:'password', inputId:'iePass', type:'password', placeholder:'••••••••' },
  ],
  'notification-gchat': [
    { label:'Webhook URL', cfgKey:'host',     formKey:'host',     inputId:'ieH',    type:'text',     placeholder:'https://chat.googleapis.com/v1/spaces/AAA/messages?key=...&token=...' },
    { label:'Token',       cfgKey:'password', formKey:'password', inputId:'iePass', type:'password', placeholder:'••••••••' },
  ],
};

const cmGroups = [
  { key:'transport',    label:'Kafka / Streaming', icon:'⚡' },
  { key:'notification', label:'Notifications', icon:'🔔' },
];

let cmActiveFilter = 'all';
let cmSearchVal = '';
let cmActiveType = null;
let cmActiveSchema = null;         // schema loaded for current form, or null → fall back to buildFormFields
let cmEditId = null;               // connection ID being edited, or null when creating
const connectorSchemaCache = {};   // subtype → schema JSON

/* ───────── Schema-driven form rendering (Phase D) ─────────
 * Fetches the schema for a subtype and renders inputs directly from field defs.
 * Falls back to buildFormFields() for connectors without a registered schema.
 * All inputs carry data-field="<field.id>" so collectSchemaForm() can gather
 * them into a flat {field.id: value} payload the backend already understands.
 */
function fetchConnectorSchema(subtype) {
  if (connectorSchemaCache[subtype] !== undefined) {
    return Promise.resolve(connectorSchemaCache[subtype]);
  }
  return fetch('/api/connector-schemas/' + encodeURIComponent(subtype))
    .then(r => r.ok ? r.json() : null)
    .catch(() => null)
    .then(schema => { connectorSchemaCache[subtype] = schema; return schema; });
}

function toggleSecretField(btn) {
  const input = btn.previousElementSibling;
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  btn.textContent = show ? 'Hide' : 'Show';
}

function _escAttr(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function _schemaFieldList(schema) {
  if (!schema) return [];
  return [].concat(schema.required || [], schema.recommended || [], schema.advanced || [], schema.fields || []);
}

const _ENUM_LABELS = {
  none: 'None',
  basic: 'HTTP Basic',
  bearer: 'Bearer token',
  connect: 'Connect',
  kubernetes: 'Kubernetes',
  confluent: 'Confluent',
  apicurio: 'Apicurio',
};

function _enumOptionLabel(value) {
  return _ENUM_LABELS[value] || value;
}

function _inferAuthType(values) {
  const raw = String(values.auth_type || '').toLowerCase();
  if (raw === 'none' || raw === 'basic' || raw === 'bearer') return raw;
  if (values.token || values.bearer_token) return 'bearer';
  if (values.username && values.password) return 'basic';
  return 'none';
}

function _isHiddenFormGroup(el) {
  const group = el && el.closest ? el.closest('.cm-form-group') : null;
  return !!(group && group.style.display === 'none');
}

function _fieldVisible(field, values) {
  const when = field.visibleWhen || field.visible_when;
  if (!when || !when.field) return true;
  const current = String(values[when.field] == null ? '' : values[when.field]);
  return (when.in || []).map(String).includes(current);
}

function _stripAuthPayload(payload) {
  if (!payload || payload.auth_type === undefined && !payload.username && !payload.token && !payload.bearer_token) {
    return payload;
  }
  const auth = _inferAuthType(payload);
  payload.auth_type = auth;
  if (auth === 'none') {
    delete payload.username;
    delete payload.password;
    delete payload.token;
    delete payload.bearer_token;
  } else if (auth === 'basic') {
    delete payload.token;
    delete payload.bearer_token;
  } else if (auth === 'bearer') {
    delete payload.username;
    delete payload.password;
  }
  return payload;
}

function _renderSchemaField(field, existingValue) {
  const rawVal   = existingValue == null ? (field.default == null ? '' : field.default) : existingValue;
  const val      = rawVal;
  const inputId  = 'cmFld_' + field.id;
  const dataAttr = `data-field="${_escAttr(field.id)}"`;
  const isReq    = field.importance === 'required';
  const reqMark  = isReq ? ' <span>*</span>' : ' <span class="cm-form-label-optional">(optional)</span>';
  const doc      = field.doc ? `<div class="cm-form-hint">${field.doc}</div>` : '';
  const ph       = _escAttr(field.placeholder || '');

  let inputHtml = '';
  if (field.type === 'enum' && Array.isArray(field.options) && field.options.length) {
    const opts = field.options.map(o =>
      `<option value="${_escAttr(o)}"${String(val) === String(o) ? ' selected' : ''}>${_escAttr(_enumOptionLabel(o))}</option>`
    ).join('');
    inputHtml = `<select class="cm-form-select" id="${inputId}" ${dataAttr}>${opts}</select>`;
  } else if (field.type === 'boolean') {
    const isOn = String(val).toLowerCase() === 'true' || val === true;
    // Render as inline checkbox — label+control combined
    return `
      <div class="cm-form-group">
        <label class="cm-form-checkbox">
          <input type="checkbox" id="${inputId}" ${dataAttr} data-bool="1"${isOn ? ' checked' : ''}>
          <span>${_escAttr(field.label)}${isReq ? ' <span style="color:var(--red);">*</span>' : ''}</span>
        </label>
        ${doc}
      </div>`;
  } else {
    const isSecret = field.secret || field.type === 'password';
    const inputType = isSecret ? 'password' : (field.type === 'number' ? 'number' : 'text');
    const monoClass = isSecret || /url|host|servers|bucket/.test(field.id) ? ' mono' : '';
    const inputEl = `<input class="cm-form-input${monoClass}" id="${inputId}" ${dataAttr} type="${inputType}" placeholder="${ph}" value="${_escAttr(val)}">`;
    inputHtml = isSecret
      ? `<div class="cm-form-secret-wrap">${inputEl}<button type="button" class="cm-secret-toggle" onclick="toggleSecretField(this)">Show</button></div>`
      : inputEl;
  }
  const when = field.visibleWhen || field.visible_when;
  const visAttrs = when && when.field
    ? ` data-visible-when-field="${_escAttr(when.field)}" data-visible-when-in="${_escAttr((when.in || []).join(','))}"`
    : '';
  return `
    <div class="cm-form-group"${visAttrs}>
      <label class="cm-form-label" for="${inputId}">${_escAttr(field.label)}${reqMark}</label>
      ${inputHtml}
      ${doc}
    </div>`;
}

function _renderSchemaFieldGroup(fields, existing) {
  // group by field.group (default "connection") in insertion order
  const groups = new Map();
  fields.forEach(f => {
    const g = f.group || 'connection';
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(f);
  });
  const GROUP_LABELS = {
    connection: null,    // no section header for the primary group
    auth:       'Authentication',
    kubernetes: 'Kubernetes',
    tls:        'TLS / SSL',
    tuning:     'Tuning',
    endpoint:   'S3-Compatible Endpoint',
  };
  let html = '';
  groups.forEach((groupFields, groupKey) => {
    const label = GROUP_LABELS[groupKey];
    if (label) html += `<div class="cm-form-section">${label}</div>`;
    groupFields.forEach(f => {
      const v = existing && existing[f.id] != null ? existing[f.id] : undefined;
      html += _renderSchemaField(f, v);
    });
  });
  return html;
}

// Subtype-specific info banner shown at the top of the create/edit form.
// Only Kafka needs one right now — pattern extends cleanly to any subtype.
function _subtypeNotice(subtype) {
  const NOTICES = {
    kafka: {
      kind: 'info',
      title: 'Testing this connection may take a few seconds',
      body: `Kafka brokers with SASL_SSL (Aiven, Confluent Cloud, MSK) can take
             <strong>up to 15\u201330 seconds</strong> for the first TLS handshake and
             SASL negotiation. If the Test button spins, wait for the real broker
             response \u2014 don\u2019t assume it\u2019s hung.
             Common causes of failure: wrong <em>SSL CA Bundle</em> path,
             blocked outbound port, wrong <em>SASL Mechanism</em> (Aiven uses PLAIN, not SCRAM).`,
    },
  };
  const n = NOTICES[subtype];
  if (!n) return '';
  return `
    <div class="cm-form-notice cm-form-notice-${n.kind}">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      <div>
        <div class="cm-form-notice-title">${n.title}</div>
        <div class="cm-form-notice-body">${n.body}</div>
      </div>
    </div>`;
}

function bindSchemaForm(root) {
  if (!root) return;
  const apply = () => {
    const values = {};
    root.querySelectorAll('[data-field]').forEach(el => {
      values[el.getAttribute('data-field')] = el.dataset.bool ? (el.checked ? 'true' : 'false') : (el.value || '');
    });
    if (values.auth_type !== undefined) values.auth_type = _inferAuthType(values);
    root.querySelectorAll('[data-visible-when-field]').forEach(group => {
      const field = group.getAttribute('data-visible-when-field');
      const allowed = (group.getAttribute('data-visible-when-in') || '').split(',').filter(Boolean);
      group.style.display = allowed.includes(String(values[field] || '')) ? '' : 'none';
    });
    root.querySelectorAll('.cm-form-section').forEach(section => {
      let any = false;
      let node = section.nextElementSibling;
      while (node && !node.classList.contains('cm-form-section') && !node.classList.contains('cm-form-advanced')) {
        if (node.classList.contains('cm-form-group') && node.style.display !== 'none') any = true;
        node = node.nextElementSibling;
      }
      section.style.display = any ? '' : 'none';
    });
    const url = root.querySelector('[data-field="url"]');
    const provider = root.querySelector('[data-field="provider"]');
    if (url && provider) {
      url.placeholder = provider.value === 'apicurio' ? 'http://localhost:8080' : 'http://schema-registry:8081';
    }
  };
  root.querySelectorAll('[data-field]').forEach(el => {
    el.addEventListener('change', apply);
    el.addEventListener('input', apply);
  });
  apply();
}

function renderSchemaForm(schema, connection) {
  cmActiveSchema = schema;
  const fields = _schemaFieldList(schema);

  // Subtype-specific notices shown at the top of the form.
  const notice = _subtypeNotice(schema.subtype);

  const nameVal = _escAttr(connection ? connection.name || '' : '');
  const nameField = `
    <div class="cm-form-group">
      <label class="cm-form-label" for="cmFldName">Connection Name <span>*</span></label>
      <input class="cm-form-input" id="cmFldName" type="text" placeholder="e.g. ${_escAttr(schema.subtype)}-prod" value="${nameVal}">
    </div>`;

  const topFields = fields.filter(f => f.importance !== 'advanced');
  const advFields = fields.filter(f => f.importance === 'advanced');

  // Reverse-map stored kc-config back onto field.id so edit-mode pre-fills correctly.
  const existing = {};
  if (connection && connection.config) {
    fields.forEach(f => {
      const kc = f.kcKey || f.kc_key;
      if (kc && connection.config[kc] != null) existing[f.id] = connection.config[kc];
    });
  }
  if (fields.some(f => f.id === 'auth_type')) {
    existing.auth_type = _inferAuthType(existing);
  }

  let html = notice + nameField + _renderSchemaFieldGroup(topFields, existing);

  if (advFields.length) {
    const setCount = advFields.filter(f => existing[f.id] != null && existing[f.id] !== '' && existing[f.id] !== f.default).length;
    const openCls = setCount > 0 ? ' open' : '';
    html += `
      <div class="cm-form-advanced${openCls}" id="cmAdvanced">
        <button type="button" class="cm-form-advanced-toggle" onclick="this.parentElement.classList.toggle('open')">
          <span>Advanced parameters
            <span class="cm-form-advanced-count">${advFields.length}</span>
          </span>
          <svg class="caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
        <div class="cm-form-advanced-body">
          ${_renderSchemaFieldGroup(advFields, existing)}
        </div>
      </div>`;
  }
  return html;
}

/* Collect a schema-driven form into a flat {field.id: value} object suitable
 * for POST /api/connections and /api/connections/test. Empty strings are dropped
 * so backend defaults can win. */
function collectSchemaForm() {
  const out = {};
  const root = document.getElementById('connModalFormBody');
  if (!root) return out;
  root.querySelectorAll('[data-field]').forEach(el => {
    if (_isHiddenFormGroup(el)) return;
    const key = el.getAttribute('data-field');
    let val;
    if (el.dataset.bool) {
      val = el.checked ? 'true' : 'false';
    } else {
      val = (el.value || '').trim();
      if (val === '') return;  // let backend default win
    }
    out[key] = val;
  });
  return _stripAuthPayload(out);
}


function connIconSvg(ct) {
  return ct.icon;
}

function loadConnectionsFromApi() {
  const secretsP = window.StreamBridgeSecrets?.refresh
    ? window.StreamBridgeSecrets.refresh().catch(function () {})
    : Promise.resolve();
  fetch('/api/connections')
    .then(r => r.json())
    .then(async data => {
      await secretsP;
      // map API response to the shape the UI expects
      connections.length = 0;
      data.forEach(c => {
        if (_isRetiredSourceSink(c)) return;
        const cfg = c.config || {};
        const fieldDefs = CONNECTOR_FIELD_MAP[c.subtype] || [];
        // resolve display host from config using the connector's field map
        const hostDef = fieldDefs.find(f => f.formKey === 'host');
        const portDef = fieldDefs.find(f => f.formKey === 'port');
        const hostVal = hostDef ? (cfg[hostDef.cfgKey] || '') : '';
        const portVal = portDef ? (cfg[portDef.cfgKey] || '') : '';
        connections.push({
          id:        c.id,
          name:      c.name,
          type:      c.type,
          subtype:   c.subtype,          // keep raw lowercase — "postgres", "mysql", etc.
          config:    cfg,
          host:      hostVal + (portVal ? ':' + portVal : ''),
          status:    c.status,
          usedIn:    c.usedIn || [],
          createdAt: c.createdAt,
          updatedAt: c.updatedAt,
        });
      });
      renderConnTree();
      renderCmConnTable();
    })
    .catch(err => console.warn('Could not load connections from API:', err));
}

function renderConnectionsMarket() {
  loadConnectionsFromApi();
}

/* ── CONNECTIONS TREE ── */
let connTreeFilter = '';
let connTreeSelected = null;

function renderConnTree() {
  const body = document.getElementById('connTreeBody');
  if (!body) return;

  const q = connTreeFilter.toLowerCase();

  // Group connections by subtype. Collapse all notification-* subtypes into a
  // single synthetic "__alert__" group so alerts show up under one header.
  const groups = {};
  connections.forEach(c => {
    const ct = connectorTypes.find(t => t.id === c.subtype);
    const key = (ct && ct.group === 'notification') ? '__alert__' : (c.subtype || c.type || 'Other');
    if (!groups[key]) groups[key] = [];
    groups[key].push(c);
  });

  const ALERT_GROUP_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 12a5 5 0 0 1 5-5v0a5 5 0 0 1 5 5v6H7v-6Z"/><path d="M5 20a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v2H5v-2Z"/><path d="M21 12h1"/><path d="M18.5 4.5 18 5"/><path d="M2 12h1"/><path d="M12 2v1"/><path d="M5.5 4.5 6 5"/></svg>';

  let html = '';

  const secrets = (window.StreamBridgeSecrets && window.StreamBridgeSecrets.bags) || [];
  const secretQ = secrets.filter(b => !q || String(b.name).toLowerCase().includes(q));
  if (!q || secretQ.length) {
    const SECRET_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="1.8" stroke-linecap="round"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>';
    html += `
      <div class="conn-tree-group cg-secrets" id="cg-secrets">
        <div class="conn-tree-group-hdr" onclick="toggleConnGroup(this)">
          <svg class="conn-tree-chevron" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
          <div class="conn-tree-group-icon" style="background:#f3f4f6;">${SECRET_ICON}</div>
          <span class="conn-tree-group-name">Secrets</span>
          <span class="conn-tree-group-count">${secretQ.length}</span>
          <button type="button" class="conn-tree-icon-btn" style="width:22px;height:22px;margin-left:4px;" title="New secret bag" onclick="event.stopPropagation();openNewSecretBag()">+</button>
        </div>
        <div class="conn-tree-group-items">`;
    secretQ.forEach((bag, i) => {
      const sid = 'secret:' + bag.name;
      const isActive = connTreeSelected === sid ? ' active' : '';
      html += `
          <div class="conn-tree-item${isActive}" onclick="selectSecretBag('${bag.name.replace(/'/g, "\\'")}')">
            <span class="conn-tree-item-num">${i + 1}.</span>
            <span class="conn-tree-item-name">${bag.name}</span>
          </div>`;
    });
    if (!secretQ.length) {
      html += `<div style="padding:8px 16px;color:var(--text3);font-size:12px;">No secret bags yet.</div>`;
    }
    html += `</div></div>`;
  }

  Object.entries(groups).forEach(([subtype, items]) => {
    const isAlertGroup = subtype === '__alert__';
    const ct = isAlertGroup ? null : (connectorTypes.find(t => t.id === subtype) || connectorTypes.find(t => t.name === subtype));
    const iconHtml = isAlertGroup ? ALERT_GROUP_ICON : (ct ? ct.icon : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="3"/></svg>`);
    const iconBg = isAlertGroup ? 'rgba(220,38,38,0.10)' : (ct ? ct.bg : '#f3f4f6');
    const groupName = isAlertGroup ? 'Notification Channels' : ((ct && ct.name) || subtype);

    const filtered = q ? items.filter(c => c.name.toLowerCase().includes(q)) : items;
    if (!filtered.length) return;

    const groupId = 'cg-' + subtype.replace(/\s+/g,'-').toLowerCase();
    const isOpen = !body.querySelector('.' + groupId + '.collapsed');
    html += `
      <div class="conn-tree-group ${groupId}" id="${groupId}">
        <div class="conn-tree-group-hdr" onclick="toggleConnGroup(this)">
          <svg class="conn-tree-chevron" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
          <div class="conn-tree-group-icon" style="background:${iconBg};">${iconHtml}</div>
          <span class="conn-tree-group-name">${groupName}</span>
          <span class="conn-tree-group-count">${filtered.length}</span>
        </div>
        <div class="conn-tree-group-items">`;
    filtered.forEach((c, i) => {
      const isActive = connTreeSelected === c.id ? ' active' : '';
      html += `
          <div class="conn-tree-item${isActive}" onclick="selectConnTreeItem(${c.id})">
            <span class="conn-tree-item-num">${i + 1}.</span>
            <span class="conn-tree-item-name">${c.name}</span>
          </div>`;
    });
    html += `</div></div>`;
  });

  if (!html) {
    html = '<div style="padding:24px 16px;text-align:center;color:var(--text3);font-size:12px;">No connections found.</div>';
  }

  body.innerHTML = html;

  if (typeof connTreeSelected === 'string' && connTreeSelected.startsWith('secret:')) {
    renderSecretDetail(connTreeSelected.slice(7));
  } else if (connTreeSelected) {
    renderConnDetail(connTreeSelected);
  } else {
    document.getElementById('connTreeDetail').innerHTML = connDetailEmpty();
  }
}

function toggleConnGroup(hdr) {
  hdr.closest('.conn-tree-group').classList.toggle('collapsed');
}

function filterConnTree(val) {
  connTreeFilter = val;
  renderConnTree();
}

function selectConnTreeItem(id) {
  connTreeSelected = id;
  renderConnTree();
}

function selectSecretBag(name) {
  connTreeSelected = 'secret:' + name;
  renderConnTree();
}

function closeSecretModal() {
  const root = document.getElementById('connSecretModal');
  if (!root) return;
  root.hidden = true;
  root.innerHTML = '';
}

function openNewSecretBag() {
  const root = document.getElementById('connSecretModal');
  if (!root) return;
  root.hidden = false;
  root.innerHTML = `
    <div class="conn-secret-modal">
      <div class="conn-secret-modal-kicker">Secrets</div>
      <h2>New secret bag</h2>
      <p class="conn-secret-modal-hint">Parent name used in JSON as <code>{prod.xyz}</code></p>
      <label class="conn-secret-modal-label" for="connSecretBagName">Name</label>
      <input class="conn-secret-modal-input" id="connSecretBagName" placeholder="prod" autocomplete="off" spellcheck="false">
      <div class="conn-secret-modal-actions">
        <button class="conn-secret-btn-ghost" type="button" id="connSecretBagCancel">Cancel</button>
        <button class="conn-secret-btn-ok" type="button" id="connSecretBagOk">Create</button>
      </div>
    </div>`;
  const input = root.querySelector('#connSecretBagName');
  input?.focus();
  const create = () => {
    const raw = (input?.value || '').trim();
    if (!raw) {
      input?.focus();
      return;
    }
    const api = window.StreamBridgeSecrets;
    if (!api) return;
    const ok = root.querySelector('#connSecretBagOk');
    if (ok) { ok.disabled = true; ok.textContent = 'Saving…'; }
    api.insert(raw).then((bag) => {
      closeSecretModal();
      selectSecretBag(bag.name);
    }).catch((err) => {
      if (ok) { ok.disabled = false; ok.textContent = 'Create'; }
      alert(err.message || 'Could not create secret bag');
    });
  };
  root.querySelector('#connSecretBagCancel').onclick = closeSecretModal;
  root.querySelector('#connSecretBagOk').onclick = create;
  input?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') create();
    if (event.key === 'Escape') closeSecretModal();
  });
  root.onclick = (event) => { if (event.target === root) closeSecretModal(); };
}

function bagHasSecrets(bag) {
  return (bag?.vars || []).some((row) => String(row.key || '').trim() || row.hasValue);
}

function deleteSecretBag(name) {
  const bag = window.StreamBridgeSecrets?.byName(name);
  if (bagHasSecrets(bag)) {
    alert('Remove all secrets from this bag before deleting it.');
    return;
  }
  if (!confirm('Delete secret bag ' + name + '?')) return;
  window.StreamBridgeSecrets.remove(name).then(() => {
    connTreeSelected = null;
    renderConnTree();
  }).catch((err) => {
    alert(err.message || 'Could not delete secret bag');
  });
}

function renderSecretDetail(name, notice) {
  const panel = document.getElementById('connTreeDetail');
  const api = window.StreamBridgeSecrets;
  const bag = api?.byName(name);
  if (!panel || !bag) return;
  const canDelete = !bagHasSecrets(bag);
  const rows = (bag.vars?.length ? bag.vars : [{ key: '', value: '', secret: false }]).map((row, i) => {
    const locked = Boolean(row.secret && row.hasValue && !row.replacing);
    const valueType = row.secret || locked ? 'password' : 'text';
    const valueHtml = locked
      ? `<input class="conn-secret-input is-locked" data-secret-field="value" type="password" value="" placeholder="••••••••" disabled autocomplete="off">`
      : `<input class="conn-secret-input" data-secret-field="value"${row.replacing ? ' data-replacing="1"' : ''} type="${valueType}" value="${_escAttr(row.replacing ? '' : (row.value || ''))}" placeholder="${row.replacing ? 'new value' : 'value'}" autocomplete="off" spellcheck="false">`;
    const maskHtml = locked
      ? `<span class="conn-secret-mask is-on" title="Masked — value cannot be viewed or edited">Masked</span>`
      : `<label class="conn-secret-mask-toggle"><input type="checkbox" data-secret-field="secret"${row.secret ? ' checked' : ''}> Mask</label>`;
    const actionHtml = locked
      ? `<button type="button" class="conn-secret-replace" onclick="replaceSecretRow('${_escAttr(name)}', ${i})">Replace</button>`
      : `<button type="button" class="conn-secret-remove" onclick="removeSecretRow('${_escAttr(name)}', ${i})" title="Remove">×</button>`;
    return `
    <tr data-secret-row="${i}" class="${locked ? 'is-locked' : ''}">
      <td><input class="conn-secret-input" data-secret-field="key" value="${_escAttr(row.key)}" placeholder="KEY" autocomplete="off" spellcheck="false"></td>
      <td>${valueHtml}</td>
      <td class="conn-secret-secret">${maskHtml}</td>
      <td class="conn-secret-row-act">${actionHtml}</td>
    </tr>`;
  }).join('');
  panel.innerHTML = `
    <div class="conn-detail-inner">
      <div class="conn-detail-hero">
        <div>
          <div class="conn-detail-hero-name">${_escAttr(bag.name)}</div>
          <div class="conn-detail-hero-sub">JSON ref <code>{${_escAttr(bag.name)}.xyz}</code> · masked values cannot be revealed</div>
        </div>
        <div class="conn-detail-hero-actions">
          <span class="conn-secret-save-msg" id="connSecretSaveMsg">${notice ? _escAttr(notice) : ''}</span>
          <button class="conn-detail-edit-btn" type="button" id="connSecretSave" onclick="saveSecretBag('${_escAttr(name)}')">Save</button>
          <button class="conn-detail-del-btn" type="button" ${canDelete ? '' : 'disabled '}title="${canDelete ? 'Delete empty bag' : 'Remove all secrets before deleting this bag'}" onclick="deleteSecretBag('${_escAttr(name)}')">Delete</button>
        </div>
      </div>
      <div class="conn-detail-card conn-secret-card">
        <div class="conn-detail-card-title">Variables</div>
        <table class="conn-secret-table">
          <thead><tr><th>Key</th><th>Value</th><th>Mask</th><th></th></tr></thead>
          <tbody id="connSecretBody">${rows}</tbody>
        </table>
        <div class="conn-secret-foot">
          <button class="conn-secret-add" type="button" onclick="addSecretRow('${_escAttr(name)}')">+ Add variable</button>
        </div>
      </div>
    </div>`;
  panel.querySelector('#connSecretBody')?.addEventListener('input', () => persistSecretBagFromDom(name));
  panel.querySelector('#connSecretBody')?.addEventListener('change', (event) => {
    persistSecretBagFromDom(name);
    if (event.target.getAttribute('data-secret-field') === 'secret') renderSecretDetail(name);
  });
  panel.querySelector('#connSecretBody')?.addEventListener('focusout', (event) => {
    if (event.target.getAttribute('data-replacing') !== '1') return;
    persistSecretBagFromDom(name);
    const bag = window.StreamBridgeSecrets?.byName(name);
    const index = Number(event.target.closest('[data-secret-row]')?.getAttribute('data-secret-row'));
    if (bag?.vars?.[index]?.value) {
      bag.vars[index].replacing = false;
      renderSecretDetail(name);
    }
  });
}

function persistSecretBagFromDom(name) {
  const bag = window.StreamBridgeSecrets?.byName(name);
  const body = document.getElementById('connSecretBody');
  if (!bag || !body) return;
  const prev = bag.vars || [];
  bag.vars = [...body.querySelectorAll('[data-secret-row]')].map((tr, i) => {
    const old = prev[i] || { key: '', value: '', secret: false };
    const valueEl = tr.querySelector('[data-secret-field="value"]');
    const locked = Boolean(valueEl?.disabled);
    const replacing = valueEl?.getAttribute('data-replacing') === '1';
    const typed = valueEl?.value || '';
    return {
      key: tr.querySelector('[data-secret-field="key"]')?.value || '',
      value: locked ? old.value : typed,
      secret: locked ? true : Boolean(tr.querySelector('[data-secret-field="secret"]')?.checked),
      hasValue: locked ? true : Boolean(typed),
      replacing,
    };
  });
  const del = document.querySelector('#connSecretSave')?.parentElement?.querySelector('.conn-detail-del-btn');
  if (del) {
    const empty = !bagHasSecrets(bag);
    del.disabled = !empty;
    del.title = empty ? 'Delete empty bag' : 'Remove all secrets before deleting this bag';
  }
}

function saveSecretBag(name) {
  persistSecretBagFromDom(name);
  const btn = document.getElementById('connSecretSave');
  const msg = document.getElementById('connSecretSaveMsg');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
  if (msg) msg.textContent = '';
  window.StreamBridgeSecrets.persist(name).then(() => {
    renderSecretDetail(name, 'Saved');
  }).catch((err) => {
    if (btn) { btn.disabled = false; btn.textContent = 'Save'; }
    if (msg) msg.textContent = err.message || 'Save failed';
  });
}

function addSecretRow(name) {
  persistSecretBagFromDom(name);
  const bag = window.StreamBridgeSecrets?.byName(name);
  if (!bag) return;
  bag.vars = bag.vars || [];
  bag.vars.push({ key: '', value: '', secret: false });
  renderSecretDetail(name);
}

function replaceSecretRow(name, index) {
  persistSecretBagFromDom(name);
  const bag = window.StreamBridgeSecrets?.byName(name);
  if (!bag?.vars?.[index]) return;
  bag.vars[index].replacing = true;
  bag.vars[index].secret = true;
  renderSecretDetail(name);
}

function removeSecretRow(name, index) {
  persistSecretBagFromDom(name);
  const bag = window.StreamBridgeSecrets?.byName(name);
  if (!bag) return;
  bag.vars.splice(index, 1);
  if (!bag.vars.length) bag.vars.push({ key: '', value: '', secret: false });
  renderSecretDetail(name);
}

function renderConnDetail(id) {
  const c = connections.find(x => x.id === id);
  const panel = document.getElementById('connTreeDetail');
  if (!c || !panel) return;

  const ct = connectorTypes.find(t => t.id === c.subtype) || connectorTypes.find(t => t.group === c.type);
  const iconHtml = ct ? ct.icon : '';
  const iconBg = ct ? ct.bg : '#f3f4f6';

  // Kick off a schema fetch — if not cached yet, re-render once it lands so the
  // "Additional parameters" rows can use human labels instead of raw kcKeys.
  if (c.subtype && connectorSchemaCache[c.subtype] === undefined) {
    fetchConnectorSchema(c.subtype).then(() => {
      if (connTreeSelected === id) renderConnDetail(id);
    });
  }


  const usedIn = c.usedIn && c.usedIn.length
    ? c.usedIn.map(p => `<span style="background:var(--surface2);color:var(--text2);padding:3px 9px;border-radius:10px;font-size:11px;font-weight:500;">${p}</span>`).join('')
    : '<span style="color:var(--text3);font-size:12px;">Not used in any pipeline</span>';

  panel.innerHTML = `
    <div class="conn-detail-inner">
      <div class="conn-detail-hero">
        <div class="conn-detail-hero-icon" style="background:${iconBg};">${iconHtml}</div>
        <div>
          <div class="conn-detail-hero-name">${c.name}</div>
          <div class="conn-detail-hero-sub">${(ct && ct.name) || c.subtype || c.type} · ${c.host || '—'}</div>
        </div>
        <div class="conn-detail-hero-actions">
          ${(c.type === 'notification' || (c.subtype || '').startsWith('notification-')) ? `
          <button class="conn-detail-del-btn" id="cnRunNowBtn-${c.id}" onclick="runConnNow(${c.id})" onmouseover="this.style.borderColor='var(--blue)';this.style.color='var(--blue)';" onmouseout="this.style.borderColor='';this.style.color='';">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            Run now
          </button>` : `
          <button class="conn-detail-del-btn" id="cnTestBtn-${c.id}" onclick="testConnFromDetail(${c.id})" onmouseover="this.style.borderColor='var(--blue)';this.style.color='var(--blue)';" onmouseout="this.style.borderColor='';this.style.color='';">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            Test Connection
          </button>`}
          ${c.subtype === 'kafka' ? `
          <button class="conn-detail-del-btn" onclick="window.location.href='/kafka-topics?connection=' + encodeURIComponent('${c.name}')" onmouseover="this.style.borderColor='var(--blue)';this.style.color='var(--blue)';" onmouseout="this.style.borderColor='';this.style.color='';">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
            Open in Kafka UI
          </button>` : ''}
          <button class="conn-detail-del-btn" onclick="deleteConn(${c.id})">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
            Delete
          </button>
          <button class="conn-detail-edit-btn" onclick="openConnInlineEdit(${c.id})">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            Edit
          </button>
        </div>
      </div>

      <div id="cnTestResult-${c.id}" class="conn-detail-test-result"></div>

      ${(function() {
        const cfg = c.config || {};
        const tid = c.subtype || '';
        const schema = connectorSchemaCache[tid];

        const GROUP_LABELS = { connection: null, auth: 'Authentication', tls: 'TLS / SSL', tuning: 'Tuning', endpoint: 'S3-Compatible Endpoint' };

        // Read-only field rendered in the same cm-form-group style as the edit form
        const roField = (label, val, isSecret) => {
          if (val === undefined || val === null || val === '') return '';
          const display = _escAttr(String(val));
          const uid = 'det_' + Math.random().toString(36).slice(2);
          const valEl = isSecret
            ? `<div class="cm-form-secret-wrap">
                <div class="cm-form-input mono" style="pointer-events:none;background:var(--surface2);" id="${uid}">••••••••</div>
                <button type="button" class="cm-secret-toggle" onclick="
                  var s=document.getElementById('${uid}');
                  if(s.dataset.shown){s.textContent='••••••••';delete s.dataset.shown;this.textContent='Show';}
                  else{s.textContent='${display}';s.dataset.shown=1;this.textContent='Hide';}
                ">Show</button>
               </div>`
            : `<div class="cm-form-input" style="pointer-events:none;background:var(--surface2);color:var(--text);">${display}</div>`;
          return `<div class="cm-form-group"><label class="cm-form-label">${_escAttr(label)}</label>${valEl}</div>`;
        };

        // Render a list of fields grouped by field.group
        const renderGrouped = (fields, values) => {
          const groups = new Map();
          fields.forEach(f => {
            const g = f.group || 'connection';
            if (!groups.has(g)) groups.set(g, []);
            groups.get(g).push(f);
          });
          let html = '';
          groups.forEach((gFields, gKey) => {
            const visible = gFields.filter(f => _fieldVisible(f, values));
            if (!visible.length) return;
            const label = GROUP_LABELS[gKey];
            if (label) html += `<div class="cm-form-section">${label}</div>`;
            visible.forEach(f => {
              const kc = f.kcKey || f.kc_key;
              const val = kc ? cfg[kc] : undefined;
              html += roField(f.label, val, f.secret);
            });
          });
          return html;
        };

        let topHtml = '', advHtml = '';

        if (schema) {
          const allFields = _schemaFieldList(schema);
          const values = {};
          allFields.forEach(f => {
            const kc = f.kcKey || f.kc_key;
            if (kc && cfg[kc] != null) values[f.id] = cfg[kc];
          });
          values.auth_type = _inferAuthType(values);
          topHtml = renderGrouped(allFields.filter(f => f.importance !== 'advanced'), values);
          advHtml = renderGrouped(allFields.filter(f => f.importance === 'advanced'), values);
        } else {
          const defs = CONNECTOR_FIELD_MAP[tid] || [];
          const synth = defs.map(f => ({
            id: f.formKey, label: f.label, kcKey: f.cfgKey, secret: f.type === 'password', group: 'connection',
          }));
          const values = {};
          defs.forEach(f => { if (cfg[f.cfgKey] != null) values[f.formKey] = cfg[f.cfgKey]; });
          values.auth_type = _inferAuthType(values);
          topHtml = renderGrouped(synth, values);
          // also check top-level host for notifications
          if (!topHtml && c.host) topHtml = roField('URL', c.host, false);
        }

        const metaHtml = [
          roField('Created', c.createdAt ? c.createdAt.slice(0,10) : '', false),
          roField('Updated', c.updatedAt ? c.updatedAt.slice(0,10) : '', false),
        ].join('');

        const advSection = advHtml ? `
          <div class="cm-form-advanced" id="detAdvanced-${c.id}">
            <button type="button" class="cm-form-advanced-toggle" onclick="this.parentElement.classList.toggle('open')">
              <span>Advanced parameters</span>
              <svg class="caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
            </button>
            <div class="cm-form-advanced-body">${advHtml}</div>
          </div>` : '';

        return `
        <div class="conn-detail-card">
          <div class="conn-detail-card-title">Connection Details</div>
          <div style="padding:14px 16px;display:flex;flex-direction:column;gap:14px;">
            ${roField('Connection Name', c.name, false)}
            ${topHtml || '<span style="color:var(--text3);font-size:12px;">No details available.</span>'}
            ${metaHtml}
          </div>
          ${advSection}
        </div>`;
      })()}
    </div>`;
}

// Test Connection from the connection detail hero button.
// Uses the already-saved config so users see the same result as the create modal Test.
function testConnFromDetail(connId) {
  const c = connections.find(x => x.id === connId);
  if (!c) return;
  const btn  = document.getElementById(`cnTestBtn-${connId}`);
  const slot = document.getElementById(`cnTestResult-${connId}`);
  if (!slot) return;

  slot.className = 'conn-detail-test-result testing';
  slot.innerHTML = `
    <div class="cn-test-banner">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      <div>
        <strong>This test connects from StreamBridge, not from Kafka Connect.</strong>
        It validates credentials and network reachability from your app server.
        A passing test does not guarantee Kafka Connect can reach the target or has CDC permissions —
        verify with a deploy in dev first.
      </div>
    </div>
    <div class="cn-test-status">Testing…</div>`;
  if (btn) btn.disabled = true;

  const cfg = c.config || {};
  const typeMap = { 'kafka-connect': 'connect' };
  const payload = {
    id:      connId,
    type:    typeMap[c.subtype] || c.type,
    subtype: c.subtype,
  };
  (CONNECTOR_FIELD_MAP[c.subtype] || []).forEach(f => {
    const v = cfg[f.cfgKey];
    if (v !== undefined && v !== null && v !== '') payload[f.formKey] = v;
  });
  const schema = connectorSchemaCache[c.subtype];
  if (schema) {
    [].concat(_schemaFieldList(schema)).forEach(f => {
      const kc = f.kcKey;
      if (kc && cfg[kc] !== undefined && cfg[kc] !== null && cfg[kc] !== '' && payload[f.id] === undefined) {
        payload[f.id] = cfg[kc];
      }
    });
  }

  _stripAuthPayload(payload);

  fetch('/api/connections/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
    .then(r => r.json())
    .then(data => {
      if (btn) btn.disabled = false;
      slot.className = 'conn-detail-test-result ' + (data.success ? 'ok' : 'err');
      const status = slot.querySelector('.cn-test-status');
      status.className = 'cn-test-status ' + (data.success ? 'ok' : 'err');
      status.textContent = `${data.success ? '✓' : '✗'} ${data.message || (data.success ? 'Connection successful' : 'Connection failed')}`;
    })
    .catch(err => {
      if (btn) btn.disabled = false;
      slot.className = 'conn-detail-test-result err';
      const status = slot.querySelector('.cn-test-status');
      status.className = 'cn-test-status err';
      status.textContent = `✗ ${err.message}`;
    });
}

const _SECRET_KEY_RE = /(password|passwd|secret|token|apikey|api[._-]?key|access[._-]?key|private[._-]?key|bearer|auth|credential)/i;

function _maskSecrets(obj) {
  if (obj === null || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(_maskSecrets);
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    if (_SECRET_KEY_RE.test(k) && v !== '' && v !== null && v !== undefined) {
      out[k] = '••••••••';
    } else if (v && typeof v === 'object') {
      out[k] = _maskSecrets(v);
    } else {
      out[k] = v;
    }
  }
  return out;
}

function connDetailEmpty() {
  return `
    <div class="conn-detail-empty">
      <div class="conn-detail-empty-icon">
        <svg viewBox="0 0 24 24"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
      </div>
      <p>Select a connection</p>
      <span>Click any connection in the tree to view its details</span>
    </div>`;
}

function buildInlineEditRows(ct, c) {
  const h = c.host || '';
  const hostPart = h.includes(':') && !h.startsWith('http') && !h.startsWith('s3') ? h.split(':')[0] : h;
  const portPart = h.includes(':') && !h.startsWith('http') && !h.startsWith('s3') ? h.split(':')[1] : '';
  const inp = (id, val, placeholder) =>
    `<input class="conn-detail-prop-input" id="${id}" value="${(val||'').replace(/"/g,'&quot;')}" placeholder="${placeholder||''}">`;
  const sel = (id, opts, val) =>
    `<select class="conn-detail-prop-select" id="${id}">${opts.map(o=>`<option${val===o?' selected':''}>${o}</option>`).join('')}</select>`;
  const row = (key, inputHtml) =>
    `<div class="conn-detail-prop"><span class="conn-detail-prop-key">${key}</span>${inputHtml}</div>`;

  const rows = [];
  rows.push(row('Name', inp('ieN', c.name, 'Connection name')));

  const tid = ct.id;
  const cfg = c.config || {};
  if (CONNECTOR_FIELD_MAP[tid]) {
    CONNECTOR_FIELD_MAP[tid].forEach(f => {
      const currentVal = f.type === 'password' ? '' : (cfg[f.cfgKey] || f.defaultVal || '');
      if (f.type === 'password') {
        rows.push(row(f.label, `<input class="conn-detail-prop-input" id="${f.inputId}" type="password" value="" placeholder="${f.placeholder||''}">`));
      } else {
        rows.push(row(f.label, inp(f.inputId, currentVal, f.placeholder || '')));
      }
    });
  } else {
    rows.push(row('Host / URL', inp('ieH', h, '')));
  }
  return rows.join('');
}

function openConnInlineEdit(id) {
  const c = connections.find(x => x.id === id);
  if (!c) return;
  const ct = connectorTypes.find(t => t.id === c.subtype) || connectorTypes.find(t => t.group === c.type);
  if (!ct) return;
  const isNotif = c.type === 'notification' || (c.subtype || '').startsWith('notification-');
  const iconBg = ct.bg || '#f3f4f6';
  const iconHtml = ct.icon || '';
  const panel = document.getElementById('connTreeDetail');


  panel.innerHTML = `
    <div class="conn-detail-inner">
      <div class="conn-detail-hero">
        <div class="conn-detail-hero-icon" style="background:${iconBg};">${iconHtml}</div>
        <div>
          <div class="conn-detail-hero-name">${c.name}</div>
          <div class="conn-detail-hero-sub">${(ct && ct.name) || c.subtype || c.type} · ${c.host || '—'}</div>
        </div>
        <div class="conn-detail-hero-actions">
          <button class="conn-detail-cancel-btn" onclick="selectConnTreeItem(${c.id})">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            Cancel
          </button>
        </div>
      </div>

      <div class="conn-detail-card">
        <div class="conn-detail-card-title">Connection Details</div>
        <div id="ieFormBody" style="padding:14px 16px;display:flex;flex-direction:column;gap:14px;">
          <div class="cm-form-group">
            <label class="cm-form-label" for="ieName">Connection Name <span>*</span></label>
            <input class="cm-form-input" id="ieName" type="text" value="${_escAttr(c.name)}" placeholder="Connection name">
          </div>
          <div id="ieSchemaFields" style="display:contents;"><div style="padding:8px 0;color:var(--text3);font-size:12px;">Loading fields…</div></div>
        </div>
      </div>

      <div class="conn-inline-edit-actions">
        <button class="conn-inline-test-btn" onclick="testConnInline(this)">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          Test Connection
        </button>
        <span class="conn-inline-test-result" id="connInlineTestResult"></span>
        <button class="conn-inline-save-btn" onclick="saveConnInlineEdit(${c.id})">Save Changes</button>
      </div>
    </div>`;

  // Fetch schema and render proper form fields into #ieSchemaFields.
  // Falls back to CONNECTOR_FIELD_MAP for connectors without a backend schema (e.g. notifications).
  fetchConnectorSchema(c.subtype).then(schema => {
    const container = document.getElementById('ieSchemaFields');
    if (!container) return;
    container.style = '';

    if (!schema) {
      // No backend schema — synthesize fields from CONNECTOR_FIELD_MAP
      const defs = CONNECTOR_FIELD_MAP[c.subtype] || [];
      if (!defs.length) {
        container.innerHTML = '<div style="color:var(--text3);font-size:12px;">No configurable fields.</div>';
        return;
      }
      const syntheticFields = defs.map(f => ({
        id:         f.formKey,
        label:      f.label,
        type:       f.type === 'password' ? 'password' : 'text',
        secret:     f.type === 'password',
        importance: 'required',
        placeholder: f.placeholder || '',
        default:    null,
        doc:        null,
        group:      'connection',
        options:    null,
      }));
      // Pre-fill values from saved config using cfgKey
      const existing = {};
      defs.forEach(f => {
        const v = c.config ? c.config[f.cfgKey] : (c[f.formKey] || '');
        if (v != null && v !== '') existing[f.formKey] = v;
      });
      // Also check top-level connection fields (host, password)
      if (c.host && !existing['host']) existing['host'] = c.host;
      container.innerHTML = _renderSchemaFieldGroup(syntheticFields, existing);
      return;
    }

    const allFields = _schemaFieldList(schema);
    const existing = {};
    if (c.config) {
      allFields.forEach(f => {
        const kc = f.kcKey || f.kc_key;
        if (kc && c.config[kc] != null) existing[f.id] = c.config[kc];
      });
    }
    if (allFields.some(f => f.id === 'auth_type')) {
      existing.auth_type = _inferAuthType(existing);
    }
    const topFields = allFields.filter(f => f.importance !== 'advanced');
    const advFields = allFields.filter(f => f.importance === 'advanced');

    let html = _renderSchemaFieldGroup(topFields, existing);

    if (advFields.length) {
      const setCount = advFields.filter(f => existing[f.id] != null && existing[f.id] !== '' && existing[f.id] !== f.default).length;
      const openCls = setCount > 0 ? ' open' : '';
      html += `
        <div class="cm-form-advanced${openCls}">
          <button type="button" class="cm-form-advanced-toggle" onclick="this.parentElement.classList.toggle('open')">
            <span>Advanced parameters <span class="cm-form-advanced-count">${advFields.length}</span></span>
            <svg class="caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
          </button>
          <div class="cm-form-advanced-body">${_renderSchemaFieldGroup(advFields, existing)}</div>
        </div>`;
    }

    container.innerHTML = html;
    container._schema = schema;
    bindSchemaForm(container);
  }).catch(() => {
    const container = document.getElementById('ieSchemaFields');
    if (container) container.innerHTML = '<div style="color:var(--red);font-size:12px;">Failed to load fields</div>';
  });
}

function saveConnInlineEdit(id) {
  const c = connections.find(x => x.id === id);
  if (!c) return;

  const nameEl = document.getElementById('ieName');
  const name = nameEl ? nameEl.value.trim() : c.name;
  if (!name) { alert('Connection name is required.'); return; }

  // Collect all schema-driven [data-field] inputs from the inline form
  const fields = {};
  const root = document.getElementById('ieSchemaFields');
  if (root) {
    root.querySelectorAll('[data-field]').forEach(el => {
      if (_isHiddenFormGroup(el)) return;
      const key = el.getAttribute('data-field');
      let val;
      if (el.dataset.bool) {
        val = el.checked ? 'true' : 'false';
      } else {
        val = (el.value || '').trim();
        if (val === '') return;
      }
      fields[key] = val;
    });
  }
  _stripAuthPayload(fields);

  const payload = {
    name,
    subtype: c.subtype,
    type:    c.type,
    ...fields,
  };

  fetch(`/api/connections/${id}`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  })
  .then(r => r.json())
  .then(data => {
    if (data.error) { alert('Save failed: ' + data.error); return; }
    loadConnectionsFromApi();
    showToast('Connection saved ✓');
  })
  .catch(err => alert('Save failed: ' + err.message));
}

function testConnInline(btn) {
  const res = document.getElementById('connInlineTestResult');
  if (!res || !connTreeSelected) return;
  const c = connections.find(x => x.id === connTreeSelected);
  if (!c) return;
  btn.disabled = true;
  btn.textContent = 'Testing…';
  res.className = 'conn-inline-test-result';
  res.textContent = '';

  // Build a form-keyed payload from the schema-driven inline form fields.
  const cfg = c.config || {};
  const typeMap = { 'kafka-connect': 'connect' };
  const payload = { id: c.id, type: typeMap[c.subtype] || c.type, subtype: c.subtype };

  // Read currently-entered values from the inline edit form
  const ieRoot = document.getElementById('ieSchemaFields');
  if (ieRoot) {
    ieRoot.querySelectorAll('[data-field]').forEach(el => {
      if (_isHiddenFormGroup(el)) return;
      const key = el.getAttribute('data-field');
      const val = el.dataset.bool ? (el.checked ? 'true' : 'false') : (el.value || '').trim();
      if (val !== '') payload[key] = val;
    });
  }

  // Fill any missing fields from saved config (reverse-map kc keys via schema)
  const schema = connectorSchemaCache[c.subtype];
  if (schema) {
    [].concat(_schemaFieldList(schema)).forEach(f => {
      if (payload[f.id] !== undefined) return;
      const kc = f.kcKey || f.kc_key;
      if (kc && cfg[kc] !== undefined && cfg[kc] !== null && cfg[kc] !== '') {
        payload[f.id] = cfg[kc];
      }
    });
  }

  _stripAuthPayload(payload);

  fetch('/api/connections/test', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  })
  .then(r => r.json())
  .then(data => {
    btn.disabled = false;
    btn.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> Test Connection';
    if (data.success) {
      res.className = 'conn-inline-test-result success';
      res.textContent = '✓ ' + data.message;
    } else {
      res.className = 'conn-inline-test-result error';
      res.textContent = '✗ ' + data.message;
    }
  })
  .catch(err => {
    btn.disabled = false;
    res.className = 'conn-inline-test-result error';
    res.textContent = '✗ ' + err.message;
  });
}

function runConnNow(id) {
  const c = connections.find(x => x.id === id);
  if (!c) return;
  const btn = document.getElementById('cnRunNowBtn-' + id);
  const original = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }

  fetch('/api/connections/test', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ id: c.id, type: c.type, subtype: c.subtype, ...(c.config || {}) }),
  })
  .then(r => r.json().then(data => ({ ok: r.ok, data })))
  .then(({ ok, data }) => {
    if (btn) { btn.disabled = false; btn.innerHTML = original; }
    if (ok && data.success) {
      _connShowToast(`✓ ${data.message}`, 'success');
    } else {
      _connShowToast(`✗ ${data.message || 'Test failed'}`, 'error');
    }
  })
  .catch(err => {
    if (btn) { btn.disabled = false; btn.innerHTML = original; }
    _connShowToast(`✗ ${err.message}`, 'error');
  });
}

function _connShowToast(msg, kind) {
  if (typeof window.showToast === 'function') { window.showToast(msg); return; }
  let host = document.getElementById('conn-toast-host');
  if (!host) {
    host = document.createElement('div');
    host.id = 'conn-toast-host';
    host.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
    document.body.appendChild(host);
  }
  const el = document.createElement('div');
  el.textContent = msg;
  const bg = kind === 'error' ? '#7f1d1d' : '#111827';
  el.style.cssText = `background:${bg};color:#fff;padding:10px 14px;border-radius:6px;font-size:13px;box-shadow:0 4px 12px rgba(0,0,0,0.15);opacity:0;transform:translateY(6px);transition:opacity 0.15s,transform 0.15s;max-width:420px;`;
  host.appendChild(el);
  requestAnimationFrame(() => { el.style.opacity = '1'; el.style.transform = 'translateY(0)'; });
  setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateY(6px)'; setTimeout(() => el.remove(), 200); }, 3200);
}

function deleteConn(id) {
  const c = connections.find(x => x.id === id);
  if (!c) return;
  if (!confirm('Delete connection "' + c.name + '"? This cannot be undone.')) return;
  fetch(`/api/connections/${id}`, { method: 'DELETE' })
    .then(r => r.json())
    .then(data => {
      if (data.error) { alert('Delete failed: ' + data.error); return; }
      connTreeSelected = null;
      document.getElementById('connTreeDetail').innerHTML = connDetailEmpty();
      loadConnectionsFromApi();
    })
    .catch(err => alert('Delete failed: ' + err.message));
}

function openConnTypeModal() {
  document.getElementById('connTypeModal').style.display = 'block';
  document.body.style.overflow = 'hidden';
  document.getElementById('connModalStep1').style.display = 'block';
  document.getElementById('connModalStep2').style.display = 'none';
  renderCmCards();
}

function closeConnTypeModal() {
  document.getElementById('connTypeModal').style.display = 'none';
  document.body.style.overflow = '';
  cmEditId = null;
}

function connModalBack() {
  document.getElementById('connModalStep1').style.display = 'block';
  document.getElementById('connModalStep2').style.display = 'none';
}

function connModalTestConn() {
  const btn = document.getElementById('connModalTestBtn');
  const res = document.getElementById('connModalTestResult');
  if (!cmActiveType) return;
  btn.disabled = true;
  res.className = 'cm-test-result testing';
  res.textContent = 'Testing…';
  const typeMap = { 'kafka-connect': 'connect' };
  let payload = {
    type:    typeMap[cmActiveType.id] || cmActiveType.group,
    subtype: cmActiveType.id,
  };
  try {
    if (cmActiveSchema) {
      Object.assign(payload, collectSchemaForm());
    } else {
      payload.host     = (document.getElementById('cmFldHost')  || {}).value || '';
      payload.port     = (document.getElementById('cmFldPort')  || {}).value || '';
      payload.database = (document.getElementById('cmFldDb')    || {}).value || '';
      payload.username = (document.getElementById('cmFldUser')  || {}).value || '';
      payload.password = (document.getElementById('cmFldPass')  || {}).value || '';
    }
  } catch (err) {
    btn.disabled = false;
    res.className = 'cm-test-result error';
    res.textContent = '✗ ' + err.message;
    return;
  }
  fetch('/api/connections/test', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  })
  .then(r => r.json())
  .then(data => {
    btn.disabled = false;
    if (data.success) {
      res.className = 'cm-test-result success';
      res.textContent = '✓ ' + data.message;
    } else {
      res.className = 'cm-test-result error';
      res.textContent = '✗ ' + (data.message || 'Connection failed');
    }
  })
  .catch(err => {
    btn.disabled = false;
    res.className = 'cm-test-result error';
    res.textContent = '✗ ' + err.message;
  });
}

function connModalSave() {
  const ct = cmActiveType;
  if (!ct) return;
  const name = (document.getElementById('cmFldName') || {}).value?.trim() || '';
  if (!name) { alert('Please enter a connection name.'); return; }

  const g = (id) => (document.getElementById(id) || {}).value || '';
  const typeMap = { 'kafka-connect': 'connect' };
  let payload = {
    name:    name,
    type:    typeMap[ct.id] || ct.group,
    subtype: ct.id,
  };

  if (cmActiveSchema) {
    // Schema-driven path: flat {field.id: value} — backend runs build_kc_config(SCHEMA, form)
    Object.assign(payload, collectSchemaForm());
    payload.extra = {};  // schema covers everything; keep key for backend compat
  } else {
    const host = (document.getElementById('cmFldHost') || {}).value?.trim() || '';
    const extraRaw = (document.getElementById('cmFldExtra') || {}).value?.trim() || '{}';
    let extra = {};
    try { extra = JSON.parse(extraRaw); } catch(e) { alert('Extra field contains invalid JSON:\n' + e.message); return; }
    payload.extra = extra;

    if (ct.id === 'kafka') {
      payload.bootstrap_servers = g('cmFldBoot');
      payload.security_protocol = g('cmFldSec');
      payload.username          = g('cmFldUser');
      payload.password          = g('cmFldPass');
    } else if (ct.id === 'kafka-connect') {
      payload.url      = g('cmFldUrl');
      payload.username = g('cmFldUser');
      payload.password = g('cmFldPass');
    } else if (ct.id === 'schema-registry') {
      payload.url      = g('cmFldUrl');
      payload.username = g('cmFldUser');
      payload.password = g('cmFldPass');
    } else if (ct.group === 'notification') {
      payload.host     = host;
      payload.password = g('cmFldPass');
    } else {
      payload.host     = host;
      payload.port     = g('cmFldPort');
      payload.database = g('cmFldDb');
      payload.username = g('cmFldUser');
      payload.password = g('cmFldPass');
    }
  }

  const isEdit = cmEditId != null;

  const url    = isEdit ? `/api/connections/${cmEditId}` : '/api/connections';
  const method = isEdit ? 'PUT' : 'POST';

  fetch(url, {
    method,
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  })
  .then(r => r.json().then(data => ({ ok: r.ok, data })))
  .then(({ ok, data }) => {
    if (!ok) { alert('Save failed: ' + (data.error || 'Unknown error')); return; }
    closeConnTypeModal();
    loadConnectionsFromApi();
  })
  .catch(err => alert('Save failed: ' + err.message));
}

function connTypeModalBgClick(e) {
  if (e.target === document.getElementById('connTypeModal')) closeConnTypeModal();
}

function setCmFilter(f, el) {
  cmActiveFilter = f;
  document.querySelectorAll('.cm-filter-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  renderCmCards();
}

function filterCmCards() {
  const inp = document.getElementById('cmModalSearch') || document.getElementById('cmSearch');
  cmSearchVal = inp ? inp.value.toLowerCase() : '';
  renderCmCards();
}

function renderCmCards() {
  const body = document.getElementById('cmBody');
  if (!body) return;
  const q = cmSearchVal;
  const f = cmActiveFilter;

  const groups = cmGroups.filter(g => f === 'all' || f === g.key);
  let html = '';
  groups.forEach(g => {
    const types = connectorTypes.filter(ct => ct.group === g.key && (!q || ct.name.toLowerCase().includes(q) || ct.sub.toLowerCase().includes(q)));
    if (!types.length) return;

    const myConns = connections.filter(c => {
      const ct = connectorTypes.find(t => t.id === c.subtype.toLowerCase().replace(/\s+/g,'-').replace(/\./g,'').replace('amazon-','') || t.name === c.subtype);
      return ct && ct.group === g.key;
    });

    html += `<div>
      <div class="cm-group-label">${g.icon} ${g.label} <span class="cm-group-count">${types.length}</span></div>
      <div class="cm-cards">`;
    types.forEach(ct => {
      html += `
        <div class="cm-card" onclick="openConnPanel('${ct.id}')">
          <div class="cm-card-icon">${ct.icon}</div>
          <div>
            <div class="cm-card-name">${ct.name}</div>
            <div class="cm-card-sub">${ct.sub}</div>
          </div>
        </div>`;
    });
    html += `</div></div>`;
  });

  body.innerHTML = html || '<div style="padding:40px;text-align:center;color:var(--text3);">No connector types match your filter.</div>';
}

function renderCmConnTable() {
  const tbody = document.getElementById('cmConnTableBody');
  const countEl = document.getElementById('cmYourCount');
  if (!tbody) return;

  const typeMap = {};
  connectorTypes.forEach(ct => { typeMap[ct.name] = ct; typeMap[ct.id] = ct; });

  const pillClass = { source:'pill-source', sink:'pill-sink', kafka:'pill-kafka', connect:'pill-connect', notification:'pill-notification' };
  const pillLabel = { source:'Source', sink:'Sink', kafka:'Kafka', connect:'Connect', notification:'Notify' };
  const pillDot   = { source:'#3b5fe2', sink:'#059669', kafka:'#9ca3af', connect:'#2563eb', notification:'#9333ea' };

  tbody.innerHTML = connections.map(c => {
    const ct = connectorTypes.find(t => t.name === c.subtype) || connectorTypes.find(t => c.type && t.group === c.type);
    const iconSvg = ct ? ct.icon : '';
    const iconBg  = ct ? ct.bg : '#f3f4f6';
    const pClass  = pillClass[c.type] || 'pill-kafka';
    const pLabel  = pillLabel[c.type] || c.type;
    const pColor  = pillDot[c.type]   || '#9ca3af';


    const usedIn = c.usedIn && c.usedIn.length
      ? c.usedIn.map(p => `<span style="background:#f0f1f5;color:var(--text2);padding:2px 7px;border-radius:10px;font-size:10.5px;font-weight:500;">${p}</span>`).join(' ')
      : `<span style="color:var(--text3);font-size:12px;">—</span>`;

    return `
      <tr onclick="openConnPanelEdit(${c.id})">
        <td style="width:38%;">
          <div style="display:flex;align-items:center;gap:10px;padding:10px 14px 10px 16px;">
            <div class="conn-icon-wrap" style="background:${iconBg};">${iconSvg}</div>
            <div>
              <div class="conn-name-text">${c.name}</div>
              <div class="conn-host-text">${c.host || '—'}</div>
            </div>
          </div>
        </td>
        <td style="width:14%;">
          <span class="conn-type-pill ${pClass}">
            <span style="width:5px;height:5px;border-radius:50%;background:${pColor};flex-shrink:0;"></span>
            ${c.subtype}
          </span>
        </td>
        <td style="width:34%;">${usedIn}</td>
        <td style="width:14%;padding-right:12px;">
          <div class="conn-row-actions">
            <button class="conn-act-btn" title="Edit" onclick="openConnPanelEdit(${c.id});event.stopPropagation()">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button class="conn-act-btn delete" title="Delete" onclick="event.stopPropagation()">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
            </button>
          </div>
        </td>
      </tr>`;
  }).join('');

  if (countEl) countEl.textContent = connections.length;
}

function openConnPanel(typeId) {
  cmActiveType = connectorTypes.find(t => t.id === typeId);
  if (!cmActiveType) return;
  const ct = cmActiveType;
  cmEditId = null;  // creating, not editing

  document.getElementById('connModalIcon').innerHTML = `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:${ct.bg};border-radius:8px;">${ct.icon}</div>`;
  document.getElementById('connModalTitle').textContent = 'New ' + ct.name + ' Connection';
  document.getElementById('connModalSub').textContent = ct.sub;
  document.getElementById('connModalTestResult').className = 'cm-test-result';
  document.getElementById('connModalTestResult').textContent = '';

  document.getElementById('connModalStep1').style.display = 'none';
  document.getElementById('connModalStep2').style.display = 'block';

  cmActiveSchema = null;
  // Render fallback synchronously so panel isn't blank while the schema loads
  document.getElementById('connModalFormBody').innerHTML = buildFormFields(ct.id, null);
  fetchConnectorSchema(ct.id).then(schema => {
    if (!schema || cmActiveType !== ct) return;
    document.getElementById('connModalFormBody').innerHTML = renderSchemaForm(schema, null);
    bindSchemaForm(document.getElementById('connModalFormBody'));
  });
}

function openConnPanelEdit(id) {
  const c = connections.find(x => x.id === id);
  if (!c) return;
  const ct = connectorTypes.find(t => t.id === c.subtype) || connectorTypes.find(t => t.group === c.type);
  if (!ct) return;
  cmActiveType = ct;
  cmEditId = id;  // track which connection we're editing

  document.getElementById('connModalIcon').innerHTML = `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:${ct.bg};border-radius:8px;">${ct.icon}</div>`;
  document.getElementById('connModalTitle').textContent = 'Edit: ' + c.name;
  document.getElementById('connModalSub').textContent = ct.sub;
  document.getElementById('connModalTestResult').className = 'cm-test-result';
  document.getElementById('connModalTestResult').textContent = '';

  document.getElementById('connModalStep1').style.display = 'none';
  document.getElementById('connModalStep2').style.display = 'block';
  document.getElementById('connTypeModal').style.display = 'block';
  document.body.style.overflow = 'hidden';

  cmActiveSchema = null;
  document.getElementById('connModalFormBody').innerHTML = buildFormFields(ct.id, c);
  fetchConnectorSchema(ct.id).then(schema => {
    if (!schema || cmActiveType !== ct) return;
    document.getElementById('connModalFormBody').innerHTML = renderSchemaForm(schema, c);
    bindSchemaForm(document.getElementById('connModalFormBody'));
  });
}

function closeConnPanel() {
  document.getElementById('cmBackdrop').classList.remove('open');
  document.getElementById('cmPanel').classList.remove('open');
  cmActiveType = null;
  cmActiveSchema = null;
}

function buildFormFields(typeId, c) {
  const v = (field, fallback) => c ? (c[field] || fallback || '') : (fallback || '');
  const h = c ? c.host : '';
  const hostPart = h.includes(':') ? h.split(':')[0] : h;
  const portPart = h.includes(':') ? h.split(':')[1] : '';

  const fld = (label, inputHtml, hint, optional) => `
    <div class="cm-form-group">
      <label class="cm-form-label">${label}${optional ? ' <span style="color:var(--text3);font-weight:400;">(optional)</span>' : ' <span>*</span>'}</label>
      ${inputHtml}
      ${hint ? `<div class="cm-form-hint">${hint}</div>` : ''}
    </div>`;
  const inp = (id, placeholder, val, type, extraClass) =>
    `<input class="cm-form-input${extraClass ? ' '+extraClass : ''}" id="${id}" type="${type||'text'}" placeholder="${placeholder}" value="${val||''}">`;
  const sel = (id, opts, val) =>
    `<select class="cm-form-select" id="${id}">${opts.map(o => `<option${val===o?' selected':''}>${o}</option>`).join('')}</select>`;
  const row2 = (a, b) => `<div class="cm-form-row">${a}${b}</div>`;

  const connName = fld('Connection Name', inp('cmFldName', 'e.g. kafka-prod', v('name')));
  const user = fld('Username', inp('cmFldUser', 'debezium', 'debezium'));
  const pass = fld('Password', inp('cmFldPass', '••••••••', '', 'password'));
  const hostPort = (defPort) => row2(
    fld('Host', inp('cmFldHost', 'e.g. db.internal', hostPart)),
    fld('Port', inp('cmFldPort', defPort, portPart || defPort))
  );

  const extraPlaceholder = typeId === 'kafka'
    ? '{"ssl.truststore.location":"/etc/kafka/ssl/truststore.jks","sasl.mechanism":"SCRAM-SHA-256"}'
    : typeId === 'kafka-connect'
    ? '{"ssl.truststore.location":"/etc/kafka/ssl/truststore.jks","worker.id":"connect-1"}'
    : '{}';
  const extra = fld('Extra',
    `<textarea class="cm-form-input mono" id="cmFldExtra" rows="4" placeholder='${extraPlaceholder}'></textarea>`,
    'Optional — JSON key/value pairs for additional connector parameters', true);

  if (typeId === 'kafka') {
    return connName +
      fld('Bootstrap Servers', inp('cmFldBoot', 'broker1:9092,broker2:9092', h, 'text', 'mono')) +
      fld('Security Protocol', sel('cmFldSec', ['PLAINTEXT','SASL_SSL','SSL','SASL_PLAINTEXT'], 'SASL_SSL')) +
      fld('Username', inp('cmFldUser', 'kafka-user', ''), '', true) +
      fld('Password', inp('cmFldPass', '••••••••', '', 'password'), '', true) +
      extra;
  }
  if (typeId === 'confluent') {
    return connName +
      fld('Bootstrap Servers', inp('cmFldBoot', 'pkc-xxxx.us-east-1.aws.confluent.cloud:9092', h, 'text', 'mono')) +
      row2(
        fld('Cluster API Key', inp('cmFldKey', 'ABCDEF123456', '', 'text', 'mono')),
        fld('Cluster API Secret', inp('cmFldSecret', '••••••••', '', 'password'))
      ) +
      fld('Schema Registry URL', inp('cmFldSr', 'https://psrc-xxxx.us-east-2.aws.confluent.cloud', '', 'text', 'mono'), '', true);
  }
  if (typeId === 'kafka-connect') {
    return connName +
      fld('REST API URL', inp('cmFldUrl', 'http://kafka-connect:8083', h, 'text', 'mono')) +
      fld('Username', inp('cmFldUser', '', ''), '', true) +
      fld('Password', inp('cmFldPass', '••••••••', '', 'password'), '', true) +
      extra;
  }
  if (typeId === 'schema-registry') {
    return connName +
      fld('Registry Type', sel('cmFldProvider', ['confluent','apicurio'], 'confluent')) +
      fld('Registry URL', inp('cmFldUrl', 'http://schema-registry:8081', h, 'text', 'mono')) +
      fld('Authentication', sel('cmFldAuth', ['none','basic','bearer'], 'none'), '', true) +
      fld('Username', inp('cmFldUser', 'API key or username', ''), '', true) +
      fld('Password', inp('cmFldPass', '••••••••', '', 'password'), '', true) +
      fld('Bearer Token', inp('cmFldToken', '••••••••', '', 'password'), '', true);
  }
  if (typeId === 'notification-slack') {
    const slackName = fld('Connection Name', inp('cmFldName', 'e.g. cdc-alerts-channel', v('name')));
    return slackName +
      fld('Webhook URL', inp('cmFldHost', 'https://hooks.slack.com', '', 'text', 'mono'), 'Base URL only — the token goes in the field below') +
      fld('Token', inp('cmFldPass', '/services/T0000/B000/xxx', '', 'text', 'mono'), 'Slack App > Incoming Webhooks — copy the path segment after hooks.slack.com');
  }
  if (typeId === 'notification-gchat') {
    const gchatName = fld('Connection Name', inp('cmFldName', 'e.g. gchat-oncall-space', v('name')));
    return gchatName +
      fld('Webhook URL', inp('cmFldHost', 'https://chat.googleapis.com', '', 'text', 'mono'), 'Base URL only — the token goes in the field below') +
      fld('Token', inp('cmFldPass', '/v1/spaces/AAAAAA/messages?key=...&token=...', '', 'text', 'mono'), 'Google Chat space > Manage webhooks — copy the path after chat.googleapis.com');
  }
  return connName + `<div style="color:var(--text2);font-size:12.5px;padding:8px 0;">Configure your ${cmActiveType ? cmActiveType.name : ''} connection.</div>`;
}

function testConnPanel() {
  const btn = document.getElementById('cmTestBtn');
  const res = document.getElementById('cmTestResult');
  btn.textContent = 'Testing…';
  btn.disabled = true;
  res.className = 'cm-test-result';
  res.textContent = '';
  setTimeout(() => {
    btn.textContent = 'Test Connection';
    btn.disabled = false;
    res.className = 'cm-test-result success';
    res.textContent = '✓ Connection successful — latency 12ms';
  }, 1400);
}

function saveConnPanel() {
  closeConnPanel();
  showToast('Connection saved ✓');
  renderCmConnTable();
}

// ──────────────────────────────────────────────
// CONNECTIONS TABLE (legacy, kept for pipeline canvas)
// ──────────────────────────────────────────────
let connFilter = 'all';
let connSearch = '';
let selectedConnId = null;

const typeLabels = { source: 'Source', sink: 'Sink', kafka: 'Kafka', connect: 'Kafka Connect' };
const typeBadgeClass = { source: 'badge-source', sink: 'badge-sink', kafka: 'badge-kafka', connect: 'badge-connect' };
const typeIcons = { source: '🗄️', sink: '🏔️', kafka: '📨', connect: '🔌' };

const subtypeLogoMap = {
  'PostgreSQL':      { url:'https://cdn.simpleicons.org/postgresql/336791',             bg:'#e8f0f8' },
  'MySQL':           { url:'https://cdn.simpleicons.org/mysql/4479a1',                  bg:'#e3eff7' },
  'MongoDB':         { url:'https://cdn.simpleicons.org/mongodb/13aa52',                bg:'#e2f5eb' },
  'Oracle':          { url:'https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/oracle.svg', filter:'invert(15%) sepia(90%) saturate(700%) hue-rotate(340deg)', bg:'#fee2e2' },
  'SQL Server':      { url:'https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/microsoftsqlserver.svg', filter:'invert(20%) sepia(80%) saturate(700%) hue-rotate(330deg)', bg:'#f7e5e5' },
  'Cassandra':       { url:'https://cdn.simpleicons.org/apachecassandra/1287b1',        bg:'#ddf0f8' },
  'Kafka Broker':    { url:'https://cdn.simpleicons.org/apachekafka/231f20',            bg:'#e8e8e8' },
  'Kafka Connect':   { url:'', bg:'#f3f4f6', svg:'<svg viewBox="0 0 100 100" width="18" height="18" fill="none" stroke="#8a8a8a" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="50" cy="50" r="45"/><path d="M32 36 L20 50 L32 64 L48 64 L60 50 L48 36 Z"/><path d="M52 36 L40 50 L52 64 L68 64 L80 50 L68 36 Z"/></svg>' },
  'Schema Registry': { url:'', bg:'#d9eeff', svg:'<svg viewBox="0 0 24 24" width="18" height="18" fill="#0073cf"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/><circle cx="12" cy="12" r="3" fill="none" stroke="#0073cf" stroke-width="1.5"/></svg>' },
  'Confluent Cloud': { url:'', bg:'#ddeeff', svg:'<svg viewBox="0 0 24 24" width="18" height="18"><circle cx="12" cy="12" r="10" fill="#0066cc"/><path d="M7 12c0-2.76 2.24-5 5-5s5 2.24 5 5-2.24 5-5 5" stroke="white" stroke-width="2" fill="none" stroke-linecap="round"/><circle cx="12" cy="12" r="1.5" fill="white"/></svg>' },
  'Snowflake':       { url:'https://cdn.simpleicons.org/snowflake/29b5e8',              bg:'#d9f2fb' },
  'BigQuery':        { url:'https://cdn.simpleicons.org/googlebigquery/4285f4',         bg:'#e3edff' },
  'Amazon S3':       { url:'https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/amazons3.svg', filter:'invert(40%) sepia(80%) saturate(600%) hue-rotate(330deg)', bg:'#fde8e5' },
  'Elasticsearch':   { url:'https://cdn.simpleicons.org/elasticsearch/f04e98',          bg:'#fde8f3' },
  'ClickHouse':      { url:'https://cdn.simpleicons.org/clickhouse/e8b422',             bg:'#fef9e0' },
  'Databricks':      { url:'https://cdn.simpleicons.org/databricks/ff3621',             bg:'#ffe8e5' },
  'Slack':           { url:'https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/slack.svg', filter:'invert(10%) sepia(60%) saturate(800%) hue-rotate(270deg)', bg:'#f3e9f5' },
  'Email':           { url:'https://cdn.simpleicons.org/gmail/3b7de9',                  bg:'#deeaff' },
  'PagerDuty':       { url:'https://cdn.simpleicons.org/pagerduty/06ac38',              bg:'#e0f7e9' },
  'MS Teams':        { url:'https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/microsoftteams.svg', filter:'invert(30%) sepia(70%) saturate(500%) hue-rotate(210deg)', bg:'#eaebfa' },
  'Webhook':         { url:'', bg:'#f3f4f6', svg:'<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>' },
};

function connLogoCell(subtype) {
  const m = subtypeLogoMap[subtype] || subtypeLogoMap[Object.keys(subtypeLogoMap).find(k => subtype && subtype.toLowerCase().includes(k.toLowerCase()))];
  if (!m) return `<div style="width:24px;height:24px;border-radius:5px;background:var(--surface2);"></div>`;
  const inner = m.svg
    ? m.svg
    : `<img src="${m.url}" style="width:16px;height:16px;object-fit:contain;${m.filter ? 'filter:' + m.filter + ';' : ''}" onerror="this.style.display='none'">`;
  return `<div style="width:24px;height:24px;border-radius:5px;background:${m.bg};display:flex;align-items:center;justify-content:center;flex-shrink:0;">${inner}</div>`;
}

function renderConnections() {
  const tbody = document.getElementById('connTableBody');
  if (!tbody) return;
  const filtered = connections.filter(c => {
    const matchType = connFilter === 'all' || c.type === connFilter;
    const matchSearch = !connSearch || c.name.includes(connSearch) || c.subtype.toLowerCase().includes(connSearch) || c.host.includes(connSearch);
    return matchType && matchSearch;
  });

  tbody.innerHTML = filtered.map(c => `
    <tr class="${selectedConnId === c.id ? 'selected' : ''}" onclick="selectConn(${c.id})">
      <td><div style="display:flex;align-items:center;gap:8px;">${connLogoCell(c.subtype)}<span class="conn-name">${c.name}</span></div></td>
      <td><span class="conn-type-badge ${typeBadgeClass[c.type]}">${c.subtype}</span></td>
      <td style="font-family:var(--mono);font-size:11.5px;color:var(--text2)">${c.host}</td>
      <td style="font-size:11.5px;color:var(--text2)">${c.usedIn.length ? c.usedIn.map(p => `<span class="chip">${p}</span>`).join(' ') : '—'}</td>
      <td>
        <div class="conn-actions">
          <button class="btn-icon tooltip" data-tip="Edit" onclick="selectConn(${c.id});event.stopPropagation()"><svg viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
          <button class="btn-icon tooltip" data-tip="Delete" onclick="event.stopPropagation()"><svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg></button>
        </div>
      </td>
    </tr>
  `).join('');
}

function filterByType(type, el) {
  connFilter = type;
  document.querySelectorAll('.type-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  renderConnections();
}

function filterConnections() {
  connSearch = document.getElementById('connSearch').value.toLowerCase();
  renderConnections();
}

function selectConn(id) {
  selectedConnId = id;
  renderConnections();
  const c = connections.find(x => x.id === id);
  if (!c) return;

  const panel = document.getElementById('connSidePanel');
  panel.classList.remove('hidden');

  const fieldsByType = {
    kafka: `
      <div class="form-group"><label class="form-label">Connection Name</label><input class="form-input" value="${c.name}"></div>
      <div class="form-group"><label class="form-label">Bootstrap Servers</label><input class="form-input mono" value="${c.host}"></div>
      <div class="form-group"><label class="form-label">Security Protocol</label>
        <select class="form-select"><option>SASL_SSL</option><option>PLAINTEXT</option><option>SSL</option></select>
      </div>
      <div class="form-group"><label class="form-label">SASL Mechanism</label>
        <select class="form-select"><option>SCRAM-SHA-512</option><option>PLAIN</option><option>GSSAPI</option></select>
      </div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Username</label><input class="form-input" value="kafka-user"></div>
        <div class="form-group"><label class="form-label">Password</label><input class="form-input" type="password" value="••••••••"></div>
      </div>
      <div class="form-group"><label class="form-label">Schema Registry URL</label><input class="form-input mono" value="http://schema-registry:8081"></div>
    `,
    connect: `
      <div class="form-group"><label class="form-label">Connection Name</label><input class="form-input" value="${c.name}"></div>
      <div class="form-group"><label class="form-label">REST API URL</label><input class="form-input mono" value="${c.host}"></div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Username</label><input class="form-input" value="admin"></div>
        <div class="form-group"><label class="form-label">Password</label><input class="form-input" type="password" value="••••••••"></div>
      </div>
      <div class="form-group"><label class="form-label">TLS/SSL</label>
        <select class="form-select"><option>Enabled</option><option>Disabled</option></select>
      </div>
    `,
  };

  panel.innerHTML = `
    <div class="side-panel-header">
      <div>
        <div class="side-panel-title">${typeIcons[c.type]} ${c.name}</div>
        <div class="side-panel-sub">${c.subtype}</div>
      </div>
      <button class="btn-icon" style="margin-left:auto" onclick="closePanel()">
        <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>
    <div class="side-panel-body">${fieldsByType[c.type] || ''}</div>
    <div class="side-panel-footer">
      <button class="btn btn-secondary" style="flex:1" onclick="testConn()">Test</button>
      <button class="btn btn-primary" style="flex:1" onclick="showToast('Saved ✓')">Save</button>
    </div>
  `;
}

function closePanel() {
  selectedConnId = null;
  document.getElementById('connSidePanel').classList.add('hidden');
  renderConnections();
}

// ──────────────────────────────────────────────
// MODAL
// ──────────────────────────────────────────────
let selectedConnType = 'kafka';

function openModal() {
  document.getElementById('connModal').classList.add('open');
  renderConnTypeFields();
}

function closeModal() {
  document.getElementById('connModal').classList.remove('open');
}

function selectConnType(type, el) {
  selectedConnType = type;
  document.querySelectorAll('.conn-type-opt').forEach(o => o.classList.remove('selected'));
  el.classList.add('selected');
  renderConnTypeFields();
}

function renderConnTypeFields() {
  const fields = {
    kafka: `
      <div class="form-group"><label class="form-label">Connection Name</label><input class="form-input" placeholder="e.g. kafka-prod"></div>
      <div class="form-group"><label class="form-label">Bootstrap Servers</label><input class="form-input mono" placeholder="broker1:9092,broker2:9092"></div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Security Protocol</label>
          <select class="form-select"><option>SASL_SSL</option><option>PLAINTEXT</option><option>SSL</option></select>
        </div>
        <div class="form-group"><label class="form-label">SASL Mechanism</label>
          <select class="form-select"><option>SCRAM-SHA-512</option><option>PLAIN</option><option>GSSAPI</option></select>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Username</label><input class="form-input" placeholder="kafka-user"></div>
        <div class="form-group"><label class="form-label">Password</label><input class="form-input" type="password" placeholder="••••••••"></div>
      </div>
      <div class="form-group"><label class="form-label">Schema Registry URL</label><input class="form-input mono" placeholder="http://schema-registry:8081"></div>
    `,
    connect: `
      <div class="form-group"><label class="form-label">Connection Name</label><input class="form-input" placeholder="e.g. connect-prod"></div>
      <div class="form-group"><label class="form-label">REST API URL</label><input class="form-input mono" placeholder="http://kafka-connect:8083"></div>
      <div class="form-row">
        <div class="form-group"><label class="form-label">Username</label><input class="form-input" placeholder="admin"></div>
        <div class="form-group"><label class="form-label">Password</label><input class="form-input" type="password" placeholder="••••••••"></div>
      </div>
      <div class="form-group"><label class="form-label">TLS</label>
        <select class="form-select"><option>Enabled</option><option>Disabled</option></select>
      </div>
    `,
  };
  document.getElementById('connTypeFields').innerHTML = fields[selectedConnType] || '';
}

function testConn() {
  showToast('Testing connection…');
  setTimeout(() => showToast('Connection successful ✓'), 1200);
}

function saveConn() {
  closeModal();
  showToast('Connection saved ✓');
}

const _connModal = document.getElementById('connModal');
if (_connModal) {
  _connModal.addEventListener('click', (e) => {
    if (e.target === _connModal) closeModal();
  });
}

// Kafka and Schema Registry logic lives in kafka.js and schema_registry.js




document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('view-connections')?.classList.contains('active')) return;
  renderConnectionsMarket();

  const params = new URLSearchParams(window.location.search);
  const createType = params.get('new');
  if (createType !== 'schema-registry' && createType !== 'kafka') return;

  openConnTypeModal();
  const transportTab = Array.from(document.querySelectorAll('.cm-filter-tab'))
    .find(tab => tab.textContent.trim() === 'Transport');
  if (transportTab) setCmFilter('transport', transportTab);
  if (createType === 'kafka') openConnPanel('kafka');
  if (createType === 'schema-registry') openConnPanel('schema-registry');
});
