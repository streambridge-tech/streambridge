// ──────────────────────────────────────────────
// PLUGINS — Connector Library
// ──────────────────────────────────────────────

let pluginsCache     = [];
let pluginsFilter    = '';
let pluginsSelected  = null;
let pluginEditId     = null;
let pluginDetailTab  = 'json';

function pluginDescText(s) {
  let t = String(s ?? '').replace(/\r\n/g, '\n').replace(/\t/g, '  ').trim();
  if (t.startsWith('{') || t.startsWith('[')) {
    try { return JSON.stringify(JSON.parse(t), null, 2); } catch {}
  }
  return t;
}

function pluginDescHtml(s) {
  return _esc(pluginDescText(s)).replace(/\n/g, '<br>');
}

function showToast(msg) {
  if (typeof window !== 'undefined' && typeof window._appShowToast === 'function') {
    window._appShowToast(msg);
    return;
  }
  let host = document.getElementById('plugin-toast-host');
  if (!host) {
    host = document.createElement('div');
    host.id = 'plugin-toast-host';
    host.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
    document.body.appendChild(host);
  }
  const el = document.createElement('div');
  el.textContent = msg;
  el.style.cssText = 'background:#111827;color:#fff;padding:10px 14px;border-radius:6px;font-size:13px;box-shadow:0 4px 12px rgba(0,0,0,0.15);opacity:0;transform:translateY(6px);transition:opacity 0.15s,transform 0.15s;';
  host.appendChild(el);
  requestAnimationFrame(() => { el.style.opacity = '1'; el.style.transform = 'translateY(0)'; });
  setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateY(6px)'; setTimeout(() => el.remove(), 200); }, 2200);
}

function _esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function pluginConfigExample(p) {
  if (p.type === 'sink') {
    return {
      's3.bucket.name': '{prod.S3_BUCKET}',
      's3.region': '{prod.S3_REGION}',
      'aws.access.key.id': '{prod.AWS_ACCESS_KEY_ID}',
      'aws.secret.access.key': '{prod.AWS_SECRET_ACCESS_KEY}',
      topics: 'orders',
    };
  }
  return {
    'database.hostname': '{prod.DB_HOST}',
    'database.port': '{prod.DB_PORT}',
    'database.user': '{prod.DB_USER}',
    'database.password': '{prod.DB_PASSWORD}',
    'database.dbname': '{prod.DB_NAME}',
  };
}

function pluginGuideHtml(p) {
  const name = _esc(p.name);
  const fmt = (p.format || 'JSON').toUpperCase();
  const example = JSON.stringify(pluginConfigExample(p), null, 2);
  const guides = {
    'postgres-json': { tag: 'Source · JSON', title: 'Postgres CDC as JSON', lead: 'Debezium captures Postgres changes as JSON. No Schema Registry.' },
    'mysql-json': { tag: 'Source · JSON', title: 'MySQL CDC as JSON', lead: 'Debezium captures MySQL binlog as JSON. No Schema Registry.' },
    's3-json': { tag: 'Sink · JSON', title: 'S3 JSON sink', lead: 'Writes Kafka topics to S3 as JSON objects.' },
  };
  const g = guides[p.name] || {
    tag: `${_esc(p.type)} · ${_esc(fmt)}`,
    title: name,
    lead: 'Reusable Kafka Connect JSON. Select it on Connectors and fill connection keys.',
  };
  return `
    <article class="plugin-doc">
      <span class="docs-intro-tag">${g.tag}</span>
      <h2>${g.title}</h2>
      <p>${g.lead}</p>
      <p>On <a href="/connectors">Connectors</a>, set Plugin to <code>${name}</code>. Keep the template on the JSON tab. Override only these keys with secret tokens.</p>
      <div class="tpl-yaml-wrapper">
        <div class="tpl-yaml-header">
          <span class="tpl-yaml-label">config keys</span>
          <button type="button" class="tpl-copy-inline" onclick="copyPluginConfigExample('${_esc(p.name)}')">Copy</button>
        </div>
        <pre class="tpl-yaml"><code>${_esc(example)}</code></pre>
      </div>
      <p>Create bags on <a href="/connections">Connections</a>, then use <code>{prod.DB_PASSWORD}</code> here. The UI stays masked.</p>
    </article>`;
}

async function pluginsLoad() {
  try {
    const res = await fetch('/api/plugins');
    pluginsCache = await res.json();
    if (!Array.isArray(pluginsCache)) pluginsCache = [];
  } catch (e) {
    pluginsCache = [];
    showToast('Failed to load plugins');
  }
}

async function pluginsApiCreate(payload) {
  const res = await fetch('/api/plugins', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return res;
}

async function pluginsApiUpdate(name, payload) {
  const res = await fetch(`/api/plugins/${name}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return res;
}

async function pluginsApiDelete(name) {
  const res = await fetch(`/api/plugins/${name}`, { method: 'DELETE' });
  return res;
}

function filterPlugins(val) {
  pluginsFilter = val.toLowerCase();
  renderPluginsList();
}

function filteredPlugins() {
  const q = pluginsFilter;
  if (!q) return pluginsCache.slice();
  return pluginsCache.filter(p =>
    p.name.includes(q) ||
    (p.db || '').toLowerCase().includes(q) ||
    (p.format || '').toLowerCase().includes(q) ||
    (p.description || '').toLowerCase().includes(q) ||
    ((p.config && p.config['connector.class']) || '').toLowerCase().includes(q)
  );
}

function renderPluginsList() {
  const body = document.getElementById('pluginsListBody');
  if (!body) return;

  const filtered = filteredPlugins();
  const sources = filtered.filter(p => p.type === 'source');
  const sinks   = filtered.filter(p => p.type === 'sink');

  const group = (label, items) => {
    if (!items.length) return '';
    return `
      <div class="plugin-tree-group">
        <div class="plugin-section-label">${_esc(label)} ${items.length}</div>
        <div class="plugin-tree-items">${items.map((p, i) => pluginListItem(p, i)).join('')}</div>
      </div>`;
  };

  let html = group('source', sources) + group('sink', sinks);
  if (!filtered.length) {
    html = '<div class="plugin-tree-empty">No connectors found.</div>';
  }
  body.innerHTML = html;
}

function pluginListItem(p, i) {
  const isActive = pluginsSelected === p.name ? ' active' : '';
  return `
    <div class="plugin-list-item${isActive}" onclick="selectPlugin('${_esc(p.name)}')">
      <span class="conn-tree-item-num">${i + 1}.</span>
      <span class="plugin-list-name">${_esc(p.name)}</span>
    </div>`;
}

function selectPlugin(name) {
  pluginsSelected = name;
  renderPluginsList();
  const p = pluginsCache.find(x => x.name === name);
  if (p) renderPluginDetail(p);
}

function showPluginLibrary() {
  pluginsSelected = null;
  pluginDetailTab = 'json';
  renderPluginsList();
  renderPluginLanding();
}

function pluginSecretsHint() {
  return `<div class="plugin-secrets-hint">
    <div class="plugin-secrets-hint-title">Secrets</div>
    <p>Create a secret bag on <a href="/connections">Connections</a>, then put tokens in this config like <code>{prod.DB_PASSWORD}</code>. Pipelines compile the real value; the UI stays masked.</p>
  </div>`;
}

function renderPluginLanding() {
  const panel = document.getElementById('pluginDetail');
  if (!panel) return;
  const builtins = pluginsCache.filter(p => p.isBuiltin);
  const cards = (builtins.length ? builtins : pluginsCache).map(pluginLibraryCard).join('');
  panel.innerHTML = `
    <div class="plugin-lib">
      <div class="plugin-lib-kicker">Connector library</div>
      <h2 class="plugin-lib-title">Plugins are reusable Kafka Connect templates</h2>
      <p class="plugin-lib-lead">Pipelines pick one with <code>plugin:</code>. Built-ins stay in this list on every first open. JSON is the default; Avro needs Schema Registry.</p>
      ${pluginSecretsHint()}
      <div class="plugin-lib-grid">${cards || '<p class="plugin-empty-sub">No plugins yet. Use + to add one.</p>'}</div>
    </div>`;
}

function pluginLibraryCard(p) {
  const typeColor = p.type === 'source' ? '#16a34a' : '#ff6b35';
  const typeBg    = p.type === 'source' ? 'rgba(22,163,74,0.1)' : 'rgba(255,107,53,0.1)';
  const fmt = (p.format || 'json').toLowerCase();
  return `
    <button type="button" class="plugin-lib-card" onclick="selectPlugin('${_esc(p.name)}')">
      <div class="plugin-lib-card-top">
        ${pluginDbIcon(p.db || (p.config && p.config['connector.class']) || '')}
        <span class="plugin-type-badge" style="color:${typeColor};background:${typeBg};">${_esc(p.type)}</span>
      </div>
      <div class="plugin-lib-card-name">${_esc(p.name)}</div>
      <div class="plugin-lib-card-desc">${_esc(p.description || '')}</div>
      <div class="plugin-lib-card-meta">
        <span class="plugin-format-badge ${fmt}">${_esc(p.format)}</span>
        ${p.isBuiltin ? '<span class="plugin-builtin-badge">built-in</span>' : '<span class="plugin-custom-badge">custom</span>'}
      </div>
    </button>`;
}

function pluginSyntaxHighlight(obj) {
  const json = JSON.stringify(obj, null, 2);
  return json
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, match => {
      if (/^"/.test(match)) {
        if (/:$/.test(match)) return `<span class="kjson-key">${match}</span>`;
        if (/&lt;[A-Z_]+&gt;/.test(match)) return `<span class="plugin-placeholder">${match}</span>`;
        return `<span class="kjson-str">${match}</span>`;
      }
      if (/true|false/.test(match)) return `<span class="kjson-bool">${match}</span>`;
      if (/null/.test(match))       return `<span class="kjson-null">${match}</span>`;
      return `<span class="kjson-num">${match}</span>`;
    });
}

function pluginDbIcon(db) {
  const t = (db || '').toLowerCase();
  const wrap = (src, bg) => `<div style="width:36px;height:36px;border-radius:9px;background:${bg};display:flex;align-items:center;justify-content:center;flex-shrink:0;"><img src="${src}" width="22" height="22" style="display:block;"></div>`;

  if (t.includes('postgres')) return wrap('https://cdn.simpleicons.org/postgresql/336791', '#e8f0f8');
  if (t.includes('mysql'))    return wrap('https://cdn.simpleicons.org/mysql/4479a1', '#e3eff7');
  if (t.includes('s3') || t.includes('amazon')) return `<div style="width:36px;height:36px;border-radius:9px;background:#fdecea;display:flex;align-items:center;justify-content:center;flex-shrink:0;"><img src="https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/amazons3.svg" width="22" height="22" style="display:block;filter:invert(40%) sepia(80%) saturate(600%) hue-rotate(330deg);"></div>`;
  if (t.includes('mongo'))    return wrap('https://cdn.simpleicons.org/mongodb/13aa52', '#e2f5eb');
  if (t.includes('snowflake'))return wrap('https://cdn.simpleicons.org/snowflake/29b5e8', '#e0f4fb');
  if (t.includes('kafka'))    return wrap('https://cdn.simpleicons.org/apachekafka/231f20', '#e8e8e8');
  if (t.includes('redis'))    return wrap('https://cdn.simpleicons.org/redis/dc382d', '#fdecea');
  if (t.includes('elastic'))  return wrap('https://cdn.simpleicons.org/elasticsearch/f04e98', '#fde8f3');

  return `<div style="width:36px;height:36px;border-radius:9px;background:var(--surface2);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:14px;font-weight:700;color:var(--text2);">${(db||'?')[0].toUpperCase()}</div>`;
}

function setPluginDetailTab(tab) {
  pluginDetailTab = tab === 'howto' ? 'howto' : 'json';
  document.querySelectorAll('[data-plugin-tab]').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-plugin-tab') === pluginDetailTab);
  });
  document.querySelectorAll('[data-plugin-panel]').forEach(el => {
    el.hidden = el.getAttribute('data-plugin-panel') !== pluginDetailTab;
  });
}

function renderPluginDetail(p) {
  const panel = document.getElementById('pluginDetail');
  if (!panel) return;

  const config = p.config || {};
  const highlighted = pluginSyntaxHighlight(config);
  const keyCount = Object.keys(config).length;
  const fmt = (p.format || 'json').toLowerCase();
  const kind = p.isBuiltin ? 'built-in' : 'custom';
  const cls = (config['connector.class'] || '');
  const tab = pluginDetailTab === 'howto' ? 'howto' : 'json';
  const desc = pluginDescText(p.description) || 'No description.';
  const mutBtns = p.isBuiltin ? '' : `
    <button class="plugin-btn-edit" onclick="startPluginPageEdit('${_esc(p.name)}')">Edit</button>
    <button class="plugin-btn-delete" onclick="deletePlugin('${_esc(p.name)}')">Delete</button>`;
  const pencil = p.isBuiltin ? '' : `
    <button type="button" class="plugin-obj-pencil" title="Edit description" onclick="startPluginDescEdit('${_esc(p.name)}')">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
    </button>`;

  panel.innerHTML = `
    <div class="plugin-obj">
      <div class="plugin-obj-head">
        <div class="plugin-obj-head-main">
          <nav class="plugin-obj-crumb">
            <button type="button" onclick="showPluginLibrary()">Library</button>
            <span class="plugin-obj-crumb-sep">/</span>
            <span>${_esc(p.name)}</span>
          </nav>
          <h1 class="plugin-obj-title">${_esc(p.name)}</h1>
          <div class="plugin-obj-meta">${_esc(p.type)} · ${_esc(fmt)} · ${_esc(kind)} · ${keyCount} keys${cls ? ` · ${_esc(cls)}` : ''}</div>
        </div>
        <div class="plugin-obj-actions">
          <button class="plugin-btn-download" onclick="clonePlugin('${_esc(p.name)}')">Clone</button>
          ${mutBtns}
          <button class="plugin-btn-download" onclick="downloadPluginConfig('${_esc(p.name)}')">Download</button>
          <button class="plugin-btn-copy" onclick="copyPluginConfig('${_esc(p.name)}')">Copy</button>
        </div>
      </div>

      <div class="plugin-obj-well" id="pluginDescWell">
        <svg class="plugin-obj-well-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        <div class="plugin-obj-well-body">
          <div class="plugin-obj-well-desc${/^\s*[\[{]/.test(desc) ? ' is-json' : ''}" id="pluginDescView">${pluginDescHtml(desc)}</div>
          <textarea class="plugin-obj-well-edit" id="pluginDescEdit" hidden spellcheck="false">${_esc(pluginDescText(p.description))}</textarea>
          <div class="plugin-obj-well-edit-actions" id="pluginDescActions" hidden>
            <button type="button" class="plugin-btn-copy" onclick="savePluginDesc('${_esc(p.name)}')">Save</button>
            <button type="button" class="plugin-btn-download" onclick="cancelPluginDesc('${_esc(p.name)}')">Cancel</button>
          </div>
        </div>
        ${pencil}
      </div>

      <div class="plugin-obj-tabs" role="tablist">
        <button type="button" class="plugin-obj-tab${tab === 'json' ? ' active' : ''}" data-plugin-tab="json" onclick="setPluginDetailTab('json')">JSON</button>
        <button type="button" class="plugin-obj-tab${tab === 'howto' ? ' active' : ''}" data-plugin-tab="howto" onclick="setPluginDetailTab('howto')">How to use</button>
      </div>

      <div class="plugin-obj-panel" data-plugin-panel="json"${tab === 'json' ? '' : ' hidden'}>
        <div class="pcv-card">
          <div class="pcv-card-header">
            <div class="pcv-filename">${_esc(p.name)}.json</div>
            <span class="pcv-keycount">${keyCount} keys</span>
          </div>
          <div class="pcv-card-body" id="pcv-body-${_esc(p.name)}">
            <pre class="pcv-pre">${highlighted}</pre>
          </div>
          ${p.isBuiltin ? `
          <div class="pcv-card-footer">
            <span style="font-size:11.5px;color:var(--text2);">Built-in template — read only. Clone it to edit JSON on this page.</span>
          </div>` : `
          <div class="pcv-card-footer" id="pcv-view-btns-${_esc(p.name)}">
            <span style="font-size:11.5px;color:var(--text2);">Edit JSON here. Secrets stay as {parent.key} tokens.</span>
            <button class="plugin-btn-edit" onclick="pcvStartEdit('${_esc(p.name)}')">Edit JSON</button>
          </div>
          <div class="pcv-card-footer" id="pcv-edit-btns-${_esc(p.name)}" style="display:none;">
            <span style="font-size:11.5px;color:var(--text2);">Saved to the database on Save</span>
            <div style="display:flex;gap:6px;">
              <button class="plugin-btn-copy" onclick="pcvSaveEdit('${_esc(p.name)}')">Save</button>
              <button class="plugin-btn-download" onclick="pcvCancelEdit('${_esc(p.name)}')">Cancel</button>
            </div>
          </div>`}
        </div>
      </div>

      <div class="plugin-obj-panel" data-plugin-panel="howto"${tab === 'howto' ? '' : ' hidden'}>
        ${pluginGuideHtml(p)}
      </div>
    </div>`;
}

function pcvStartEdit(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (!p) return;
  if (p.isBuiltin) { showToast('Built-in plugins cannot be edited'); return; }
  pluginDetailTab = 'json';
  setPluginDetailTab('json');
  const body     = document.getElementById('pcv-body-' + name);
  const viewBtns = document.getElementById('pcv-view-btns-' + name);
  const editBtns = document.getElementById('pcv-edit-btns-' + name);
  if (!body) return;
  body.innerHTML = `<textarea class="pcv-editor" id="pcv-textarea-${name}" spellcheck="false">${JSON.stringify(p.config, null, 2)}</textarea>`;
  if (viewBtns) viewBtns.style.display = 'none';
  if (editBtns) {
    editBtns.style.display = 'flex';
    editBtns.style.flexDirection = 'row';
  }
  const ta = document.getElementById('pcv-textarea-' + name);
  ta.style.height = ta.scrollHeight + 'px';
  ta.focus();
}

async function pcvSaveEdit(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (p?.isBuiltin) { showToast('Built-in plugins cannot be edited'); return; }
  const ta = document.getElementById('pcv-textarea-' + name);
  if (!ta) return;
  let config;
  try { config = JSON.parse(ta.value); }
  catch(e) { showToast('Invalid JSON — fix errors before saving'); return; }

  const res = await pluginsApiUpdate(name, { config });
  if (!res.ok) {
    const err = await res.json();
    showToast(err.error || 'Save failed'); return;
  }
  const updated = await res.json();
  const idx = pluginsCache.findIndex(x => x.name === name);
  if (idx >= 0) pluginsCache[idx] = updated;
  pluginDetailTab = 'json';
  renderPluginDetail(updated);
  showToast('Config saved');
}

function pcvCancelEdit(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (p) renderPluginDetail(p);
}

function copyPluginConfigExample(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (!p) return;
  navigator.clipboard.writeText(JSON.stringify(pluginConfigExample(p), null, 2))
    .then(() => showToast('Config keys copied'));
}

function uniqueCloneName(base) {
  const taken = new Set(pluginsCache.map(x => x.name));
  let name = `${base}-copy`;
  let n = 2;
  while (taken.has(name)) name = `${base}-copy-${n++}`;
  return name;
}

async function clonePlugin(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (!p) return;
  const newName = uniqueCloneName(p.name);
  const res = await pluginsApiCreate({
    name: newName,
    db: p.db || 'Custom',
    type: p.type,
    format: p.format,
    description: pluginDescText(p.description),
    config: p.config || {},
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    showToast(err.error || 'Clone failed');
    return;
  }
  const created = await res.json();
  pluginsCache.unshift(created);
  pluginDetailTab = 'json';
  renderPluginsList();
  selectPlugin(created.name);
  showToast('Cloned as ' + created.name);
}

function startPluginDescEdit(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (!p || p.isBuiltin) { showToast('Clone this plugin to edit it'); return; }
  const view = document.getElementById('pluginDescView');
  const edit = document.getElementById('pluginDescEdit');
  const actions = document.getElementById('pluginDescActions');
  const pencil = document.querySelector('.plugin-obj-pencil');
  if (!edit) return;
  if (view) view.hidden = true;
  edit.hidden = false;
  if (actions) actions.hidden = false;
  if (pencil) pencil.hidden = true;
  edit.focus();
  edit.style.height = Math.max(56, edit.scrollHeight) + 'px';
}

function cancelPluginDesc(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (p) renderPluginDetail(p);
}

async function savePluginDesc(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (!p || p.isBuiltin) { showToast('Built-in plugins cannot be edited'); return; }
  const edit = document.getElementById('pluginDescEdit');
  if (!edit) return;
  const description = pluginDescText(edit.value);
  const res = await pluginsApiUpdate(name, { description });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    showToast(err.error || 'Save failed');
    return;
  }
  const updated = await res.json();
  const idx = pluginsCache.findIndex(x => x.name === name);
  if (idx >= 0) pluginsCache[idx] = updated;
  renderPluginDetail(updated);
  showToast('Description saved');
}

function startPluginPageEdit(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (!p) return;
  if (p.isBuiltin) { showToast('Clone this plugin to edit it'); return; }
  pluginDetailTab = 'json';
  renderPluginDetail(p);
  startPluginDescEdit(name);
  pcvStartEdit(name);
}

function copyPluginConfig(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (!p) return;
  navigator.clipboard.writeText(JSON.stringify(p.config, null, 2))
    .then(() => showToast('Config copied to clipboard'));
}

function downloadPluginConfig(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (!p) return;
  const blob = new Blob([JSON.stringify(p.config, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${name}.json`;
  a.click();
  showToast('Downloaded ' + name + '.json');
}

async function deletePlugin(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (p?.isBuiltin) { showToast('Built-in plugins cannot be deleted'); return; }
  if (!confirm(`Delete plugin "${name}"? This cannot be undone.`)) return;
  const res = await pluginsApiDelete(name);
  if (!res.ok) {
    const err = await res.json();
    showToast(err.error || 'Delete failed'); return;
  }
  pluginsCache = pluginsCache.filter(x => x.name !== name);
  showPluginLibrary();
  showToast('Plugin deleted');
}

function openPluginModal() {
  pluginEditId = null;
  document.getElementById('pluginModalTitle').textContent    = 'Add Custom Plugin';
  document.getElementById('pluginModalSubtitle').textContent = 'Save a connector config as a reusable plugin';
  document.getElementById('pluginFormName').value    = '';
  document.getElementById('pluginFormName').disabled = false;
  document.getElementById('pluginFormType').value    = 'source';
  document.getElementById('pluginFormFormat').value  = 'JSON';
  document.getElementById('pluginFormDesc').value    = '';
  document.getElementById('pluginFormJson').value    = '';
  document.getElementById('pluginModal').style.display = 'block';
}

function openEditPluginModal(name) {
  const p = pluginsCache.find(x => x.name === name);
  if (!p) return;
  if (p.isBuiltin) { showToast('Built-in plugins cannot be edited'); return; }
  pluginEditId = name;
  document.getElementById('pluginModalTitle').textContent    = 'Edit Plugin';
  document.getElementById('pluginModalSubtitle').textContent = 'Modify connector metadata or update config';
  document.getElementById('pluginFormName').value    = p.name;
  document.getElementById('pluginFormName').disabled = true;
  document.getElementById('pluginFormType').value    = p.type;
  document.getElementById('pluginFormFormat').value  = p.format;
  document.getElementById('pluginFormDesc').value    = p.description || '';
  document.getElementById('pluginFormJson').value    = JSON.stringify(p.config, null, 2);
  document.getElementById('pluginModal').style.display = 'block';
}

function closePluginModal() {
  document.getElementById('pluginModal').style.display = 'none';
}

function pluginModalBgClick(e) {
  if (e.target === document.getElementById('pluginModal')) closePluginModal();
}

async function savePlugin() {
  const rawName = document.getElementById('pluginFormName').value.trim();
  const raw     = document.getElementById('pluginFormJson').value.trim();

  if (!rawName) { showToast('Name is required'); return; }
  if (!raw)     { showToast('Config JSON is required'); return; }

  const name = rawName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
  if (!name) { showToast('Name must contain letters or numbers'); return; }

  let config;
  try { config = JSON.parse(raw); }
  catch(e) { showToast('Invalid JSON — check your config'); return; }

  const type   = document.getElementById('pluginFormType').value;
  const format = document.getElementById('pluginFormFormat').value;
  const desc   = document.getElementById('pluginFormDesc').value.trim() || 'Custom connector plugin.';

  if (pluginEditId) {
    const res = await pluginsApiUpdate(pluginEditId, { type, format, description: desc, config });
    if (!res.ok) { const e = await res.json(); showToast(e.error || 'Update failed'); return; }
    const updated = await res.json();
    const idx = pluginsCache.findIndex(x => x.name === pluginEditId);
    if (idx >= 0) pluginsCache[idx] = updated;
    closePluginModal();
    renderPluginsList();
    selectPlugin(pluginEditId);
    showToast('Plugin updated');
  } else {
    const res = await pluginsApiCreate({ name, type, format, description: desc, config });
    if (!res.ok) { const e = await res.json(); showToast(e.error || 'Create failed'); return; }
    const created = await res.json();
    pluginsCache.unshift(created);
    closePluginModal();
    renderPluginsList();
    selectPlugin(name);
    showToast('Plugin saved');
  }
}

async function renderPluginsView() {
  await pluginsLoad();
  renderPluginsList();
  if (pluginsCache.some(p => p.name === 'postgres-json')) selectPlugin('postgres-json');
  else if (pluginsCache[0]) selectPlugin(pluginsCache[0].name);
  else renderPluginLanding();
}

function initPlugins() {}

document.addEventListener('DOMContentLoaded', () => { if (document.getElementById('view-plugins')?.classList.contains('active')) renderPluginsView(); });
