// ──────────────────────────────────────────────
// SCHEMA REGISTRY
// ──────────────────────────────────────────────

const _SCHEMA_REGISTRY_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="1" width="6" height="5" rx="1"/><rect x="1" y="14" width="6" height="5" rx="1"/><rect x="9" y="14" width="6" height="5" rx="1"/><rect x="17" y="14" width="6" height="5" rx="1"/><line x1="12" y1="6" x2="12" y2="11"/><line x1="4" y1="11" x2="20" y2="11"/><line x1="4" y1="11" x2="4" y2="14"/><line x1="12" y1="11" x2="12" y2="14"/><line x1="20" y1="11" x2="20" y2="14"/></svg>';
const _SCHEMA_GROUP_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7h7l2 2h9v10a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z"/></svg>';

let schemaTreeFilter = '';
let schemaTreeSelected = null;
let schemaRegistries = [];
let schemaContentCache = {};
let _schemaLoadToken = 0;

function srSyntaxHighlight(val) {
  if (val === null) return '<span class="kjson-null">null</span>';
  if (typeof val === 'string') return _escSchema(val);
  let json;
  try { json = JSON.stringify(val, null, 2); }
  catch (e) { return _escSchema(String(val)); }
  return json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, match => {
      if (/^"/.test(match)) {
        if (/:$/.test(match)) return `<span class="kjson-key">${match}</span>`;
        return `<span class="kjson-str">${match}</span>`;
      }
      if (/true|false/.test(match)) return `<span class="kjson-bool">${match}</span>`;
      if (/null/.test(match)) return `<span class="kjson-null">${match}</span>`;
      return `<span class="kjson-num">${match}</span>`;
    });
}

function _escSchema(value) {
  return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function srJs(value) {
  return JSON.stringify(String(value ?? ''))
    .replace(/&/g, '&amp;')
    .replace(/</g, '\\u003c')
    .replace(/'/g, '&#39;');
}

function srApi(name, path, params) {
  const suffix = path || '';
  const base = name
    ? `/api/schema-registries/${encodeURIComponent(name)}${suffix}`
    : '/api/schema-registries';
  const url = new URL(base, window.location.origin);
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value != null && value !== '') url.searchParams.set(key, value);
  });
  return fetch(url).then(async response => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    return data;
  });
}

function schemaTypeClass(type) {
  const value = String(type || 'AVRO').toUpperCase();
  if (value.includes('JSON') || value.includes('OPENAPI')) return 'json';
  if (value.includes('PROTO')) return 'proto';
  return 'avro';
}

function formatSchemaDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}

function schemaCacheKey(registry, groupId, artifactId, version) {
  return [registry, groupId, artifactId, version].join('\u0000');
}

function srSidebar() {
  return document.getElementById('schemaTreeSidebar');
}

function srRegistryKey(name) {
  return `srr-${name}`;
}

function srGroupKey(name, groupId) {
  return `srg-${name}-${groupId}`;
}

function srExpand(...keys) {
  const sidebar = srSidebar();
  if (!sidebar) return;
  sidebar._expandedGroups = sidebar._expandedGroups || new Set();
  keys.filter(Boolean).forEach(key => sidebar._expandedGroups.add(key));
}

function srCollapse(...keys) {
  const sidebar = srSidebar();
  if (!sidebar || !sidebar._expandedGroups) return;
  keys.filter(Boolean).forEach(key => sidebar._expandedGroups.delete(key));
}

function srIsExpanded(key) {
  const sidebar = srSidebar();
  return !!(sidebar && sidebar._expandedGroups && sidebar._expandedGroups.has(key));
}

function srToggleRegistry(registry) {
  if (!registry) return;
  const key = srRegistryKey(registry.name);
  if (srIsExpanded(key)) {
    srCollapse(key, ...(registry.groups || []).map(group => srGroupKey(registry.name, group.groupId)));
  } else {
    srExpand(key);
  }
}

function srToggleGroup(registryName, groupId) {
  const key = srGroupKey(registryName, groupId);
  if (srIsExpanded(key)) srCollapse(key);
  else srExpand(srRegistryKey(registryName), key);
}

function srResetTree() {
  const sidebar = srSidebar();
  if (sidebar) sidebar._expandedGroups = new Set();
}

function loadSchemaRegistries(force) {
  const body = document.getElementById('schemaTreeBody');
  const token = ++_schemaLoadToken;
  if (force) schemaContentCache = {};
  srResetTree();
  if (body) body.innerHTML = '<div class="sr-nav-empty">Loading registries…</div>';
  if (!schemaTreeSelected) renderSchemaRegistryLanding();
  return srApi().then(rows => {
    if (token !== _schemaLoadToken) return;
    schemaRegistries = (Array.isArray(rows) ? rows : []).map(row => ({
      name: row.name,
      provider: row.provider || 'unknown',
      url: row.url || '',
      status: row.status,
      groups: [],
      error: '',
      loaded: false,
    }));
    if (!schemaRegistries.length) {
      renderSchemaTree();
      renderSchemaRegistryEmpty('Add a Schema Registry connection to browse artifacts and schema content.');
      return Promise.resolve();
    }
    renderSchemaTree();
    return Promise.all(schemaRegistries.map(registry => loadRegistryCatalog(registry, force)));
  }).then(() => {
    if (token !== _schemaLoadToken) return;
    renderSchemaTree();
    if (!schemaTreeSelected) renderSchemaRegistryLanding();
  }).catch(err => {
    if (token !== _schemaLoadToken) return;
    schemaRegistries = [];
    renderSchemaTree();
    renderSchemaRegistryEmpty(err.message || 'Unable to load schema registries.');
  });
}

function loadRegistryCatalog(registry, force) {
  if (registry.loaded && !force) return Promise.resolve(registry);
  registry.error = '';
  return srApi(registry.name, '/catalog').then(data => {
    registry.provider = data.provider || registry.provider;
    registry.url = data.url || registry.url;
    registry.groups = data.groups || [];
    registry.loaded = true;
    return registry;
  }).catch(err => {
    registry.groups = [];
    registry.loaded = true;
    registry.error = err.message || 'Unable to load catalog.';
    return registry;
  });
}

function filterSchemaTree(val) {
  schemaTreeFilter = (val || '').toLowerCase();
  renderSchemaTree();
}

function registryMatches(registry, query) {
  if (!query) return true;
  if ((registry.name || '').toLowerCase().includes(query)) return true;
  if ((registry.provider || '').toLowerCase().includes(query)) return true;
  return (registry.groups || []).some(group => {
    if ((group.groupId || '').toLowerCase().includes(query)) return true;
    return (group.artifacts || []).some(artifact => {
      const haystack = `${artifact.artifactId || ''} ${artifact.name || ''} ${artifact.schemaType || ''}`.toLowerCase();
      return haystack.includes(query);
    });
  });
}

function renderSchemaTree() {
  const body = document.getElementById('schemaTreeBody');
  if (!body) return;
  const query = schemaTreeFilter;
  if (!schemaRegistries.length) {
    body.innerHTML = '<div class="sr-nav-empty">No schema registry connections yet.</div>';
    return;
  }
  const visible = schemaRegistries.filter(registry => registryMatches(registry, query));
  if (!visible.length) {
    body.innerHTML = '<div class="sr-nav-empty">No registries match your search.</div>';
    return;
  }
  body.innerHTML = visible.map(registry => {
    const groups = (registry.groups || []).filter(group => {
      if (!query) return true;
      if ((registry.name || '').toLowerCase().includes(query)) return true;
      if ((group.groupId || '').toLowerCase().includes(query)) return true;
      return (group.artifacts || []).some(artifact => `${artifact.artifactId || ''} ${artifact.name || ''}`.toLowerCase().includes(query));
    });
    const artifactCount = (registry.groups || []).reduce((sum, group) => sum + (group.artifacts || []).length, 0);
    return `<div class="conn-tree-group" id="${_escSchema(srRegistryKey(registry.name))}">
      <div class="conn-tree-group-hdr" onclick='selectSchemaRegistry(${srJs(registry.name)})'>
        <svg class="conn-tree-chevron" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
        <div class="conn-tree-group-icon">${_SCHEMA_REGISTRY_ICON}</div>
        <span class="conn-tree-group-name">${_escSchema(registry.name)}</span>
        <span class="conn-tree-group-count">${artifactCount}</span>
      </div>
      <div class="conn-tree-group-items">
        ${registry.error ? `<div class="sr-nav-empty">${_escSchema(registry.error)}</div>` : ''}
        ${groups.map(group => renderSchemaGroup(registry, group, query)).join('') || (!registry.error ? '<div class="sr-nav-empty">No groups</div>' : '')}
      </div>
    </div>`;
  }).join('');
}

function renderSchemaGroup(registry, group, query) {
  const artifacts = (group.artifacts || []).filter(artifact => {
    if (!query) return true;
    if ((registry.name || '').toLowerCase().includes(query)) return true;
    if ((group.groupId || '').toLowerCase().includes(query)) return true;
    return `${artifact.artifactId || ''} ${artifact.name || ''}`.toLowerCase().includes(query);
  });
  return `<div class="conn-tree-group" id="${_escSchema(srGroupKey(registry.name, group.groupId))}">
    <div class="conn-tree-group-hdr" onclick='selectSchemaGroup(${srJs(registry.name)},${srJs(group.groupId)})'>
      <svg class="conn-tree-chevron" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
      <div class="conn-tree-group-icon">${_SCHEMA_GROUP_ICON}</div>
      <span class="conn-tree-group-name">${_escSchema(group.groupId)}</span>
      <span class="conn-tree-group-count">${group.artifacts?.length || 0}</span>
    </div>
    <div class="conn-tree-group-items">
      ${artifacts.length ? artifacts.map((artifact, i) => {
        const active = schemaTreeSelected?.registry === registry.name
          && schemaTreeSelected?.groupId === group.groupId
          && schemaTreeSelected?.artifactId === artifact.artifactId ? ' active' : '';
        const label = artifact.name && artifact.name !== artifact.artifactId ? artifact.name : artifact.artifactId;
        return `<div class="conn-tree-item${active}" title="${_escSchema(label)}" onclick='selectSchemaArtifact(${srJs(registry.name)},${srJs(group.groupId)},${srJs(artifact.artifactId)})'>
          <span class="conn-tree-item-num">${i + 1}.</span>
          <span class="conn-tree-item-name">${_escSchema(label)}</span>
          <span class="sr-nav-version-count">${_escSchema(artifact.schemaType || '')}</span>
        </div>`;
      }).join('') : '<div class="sr-nav-empty">No artifacts</div>'}
    </div>
  </div>`;
}

function renderSchemaRegistryLanding() {
  const panel = document.getElementById('schemaArtifactDetail');
  if (!panel) return;
  panel.innerHTML = `<div class="sr-pane sr-pane-empty">
    <div class="sr-empty-card">
      <div class="sr-landing-mark">${_SCHEMA_REGISTRY_ICON}</div>
      <h2>Schema Registry</h2>
      <p>Browse a registry from the tree to inspect groups, artifacts, and versioned schema content.</p>
      <div class="sr-landing-path">registry <span>›</span> groups <span>›</span> artifacts <span>›</span> versions</div>
    </div>
  </div>`;
}

function renderSchemaRegistryEmpty(message) {
  const panel = document.getElementById('schemaArtifactDetail');
  if (!panel) return;
  panel.innerHTML = `<div class="sr-pane sr-pane-empty">
    <div class="sr-empty-card">
      <div class="sr-landing-mark">${window.SB_FILE_ICON}</div>
      <h2>Unable to load schema</h2>
      <p>${_escSchema(message)}</p>
      <a class="sr-empty-link" href="/connections?new=schema-registry">Create a Schema Registry connection</a>
    </div>
  </div>`;
}

function srCrumb(parts) {
  return `<nav class="sr-crumb">${parts.map((part, index) => {
    const node = part.action
      ? `<button type="button" class="sr-crumb-link" onclick='${part.action}'>${_escSchema(part.label)}</button>`
      : `<span class="sr-crumb-current">${_escSchema(part.label)}</span>`;
    return index ? `<span class="sr-crumb-sep">/</span>${node}` : node;
  }).join('')}</nav>`;
}

function srStat(label, value) {
  return `<div class="sr-stat"><span>${_escSchema(label)}</span><strong>${_escSchema(value)}</strong></div>`;
}

function renderArtifactList(registry, groups) {
  const rows = groups.flatMap(group => (group.artifacts || []).map(artifact => {
    const label = artifact.name && artifact.name !== artifact.artifactId ? artifact.name : artifact.artifactId;
    return `<button type="button" class="sr-artifact-row" onclick='selectSchemaArtifact(${srJs(registry.name)},${srJs(group.groupId)},${srJs(artifact.artifactId)})'>
      <span class="sr-artifact-row-icon">${window.SB_FILE_ICON}</span>
      <span class="sr-artifact-row-copy">
        <strong>${_escSchema(label)}</strong>
        <small>${_escSchema(group.groupId)}</small>
      </span>
      <span class="sr-type-badge sr-type-${schemaTypeClass(artifact.schemaType)}">${_escSchema(artifact.schemaType || 'AVRO')}</span>
    </button>`;
  })).join('');
  if (!rows) return '<div class="sr-list-empty">No artifacts in this selection.</div>';
  return `<div class="sr-artifact-list">${rows}</div>`;
}

function selectSchemaRegistry(registryName, expandOnly) {
  const registry = schemaRegistries.find(item => item.name === registryName);
  if (!registry) return;
  schemaTreeSelected = { registry: registryName, groupId: null, artifactId: null, version: null };
  if (expandOnly) srExpand(srRegistryKey(registry.name));
  else srToggleRegistry(registry);
  renderSchemaTree();
  const panel = document.getElementById('schemaArtifactDetail');
  if (!panel) return;
  const provider = (registry.provider || 'unknown').toUpperCase();
  const artifactCount = registry.groups.reduce((sum, group) => sum + (group.artifacts || []).length, 0);
  panel.innerHTML = `<div class="sr-pane">
    <header class="sr-pane-head">
      ${srCrumb([{ label: 'Schema Registry' }, { label: registry.name }])}
      <div class="sr-pane-title-row">
        <div class="sr-pane-title">
          <div class="sr-pane-kicker">${_escSchema(provider)}</div>
          <h1>${_escSchema(registry.name)}</h1>
          <p class="sr-pane-url">${_escSchema(registry.url || '—')}</p>
        </div>
      </div>
      <div class="sr-stat-row">
        ${srStat('Provider', provider)}
        ${srStat('Groups', registry.groups.length)}
        ${srStat('Artifacts', artifactCount)}
      </div>
    </header>
    <section class="sr-pane-body">
      ${registry.error ? `<div class="sr-error">${_escSchema(registry.error)}</div>` : `<div class="sr-section-title">Artifacts</div>${renderArtifactList(registry, registry.groups)}`}
    </section>
  </div>`;
}

function selectSchemaGroup(registryName, groupId, expandOnly) {
  const registry = schemaRegistries.find(item => item.name === registryName);
  const group = (registry?.groups || []).find(item => item.groupId === groupId);
  if (!registry || !group) return;
  schemaTreeSelected = { registry: registryName, groupId, artifactId: null, version: null };
  if (expandOnly) srExpand(srRegistryKey(registryName), srGroupKey(registryName, groupId));
  else srToggleGroup(registryName, groupId);
  renderSchemaTree();
  const panel = document.getElementById('schemaArtifactDetail');
  if (!panel) return;
  panel.innerHTML = `<div class="sr-pane">
    <header class="sr-pane-head">
      ${srCrumb([
        { label: registry.name, action: `selectSchemaRegistry(${srJs(registry.name)},true)` },
        { label: group.groupId },
      ])}
      <div class="sr-pane-title-row">
        <div class="sr-pane-title">
          <div class="sr-pane-kicker">Group</div>
          <h1>${_escSchema(group.groupId)}</h1>
          <p class="sr-pane-url">${_escSchema((registry.provider || '').toUpperCase())} · ${_escSchema(registry.name)}</p>
        </div>
      </div>
      <div class="sr-stat-row">
        ${srStat('Artifacts', (group.artifacts || []).length)}
        ${srStat('Provider', (registry.provider || '').toUpperCase())}
      </div>
    </header>
    <section class="sr-pane-body">
      <div class="sr-section-title">Artifacts</div>
      ${renderArtifactList(registry, [group])}
    </section>
  </div>`;
}

function findArtifact(registryName, groupId, artifactId) {
  const registry = schemaRegistries.find(item => item.name === registryName);
  const group = (registry?.groups || []).find(item => item.groupId === groupId);
  const artifact = (group?.artifacts || []).find(item => item.artifactId === artifactId);
  return { registry, group, artifact };
}

function selectSchemaArtifact(registryName, groupId, artifactId, version) {
  const found = findArtifact(registryName, groupId, artifactId);
  if (!found.artifact) return;
  schemaTreeSelected = { registry: registryName, groupId, artifactId, version: version || 'latest' };
  srExpand(srRegistryKey(registryName), srGroupKey(registryName, groupId));
  renderSchemaTree();
  const panel = document.getElementById('schemaArtifactDetail');
  if (panel) panel.innerHTML = '<div class="sr-pane sr-pane-empty"><div class="sr-empty-card"><p>Loading schema…</p></div></div>';
  srApi(registryName, '/versions', { group: groupId, artifact: artifactId })
    .then(data => {
      const versions = data.versions || [];
      const latest = data.latest || (versions.length ? versions[versions.length - 1].version : null);
      const requested = version && version !== 'latest' ? version : latest;
      return loadSchemaContent(registryName, groupId, artifactId, requested || 'latest').then(schema => {
        renderLiveSchemaDetail(found, versions, latest, schema);
      });
    })
    .catch(err => renderSchemaRegistryEmpty(err.message || 'Unable to load schema.'));
}

function loadSchemaContent(registryName, groupId, artifactId, version) {
  const key = schemaCacheKey(registryName, groupId, artifactId, version);
  if (schemaContentCache[key]) return Promise.resolve(schemaContentCache[key]);
  return srApi(registryName, '/content', { group: groupId, artifact: artifactId, version }).then(schema => {
    schemaContentCache[key] = schema;
    return schema;
  });
}

function renderLiveSchemaDetail(found, versions, latest, schema) {
  const panel = document.getElementById('schemaArtifactDetail');
  if (!panel) return;
  const artifact = found.artifact;
  const group = found.group;
  const registry = found.registry;
  const selectedVersion = String(schema.version);
  const type = schema.schemaType || artifact.schemaType || 'AVRO';
  const typeClass = schemaTypeClass(type);
  const options = (versions.length ? versions : [{ version: selectedVersion }]).slice().reverse()
    .map(item => {
      const value = String(item.version);
      const latestLabel = value === String(latest) ? ' (latest)' : '';
      return `<option value="${_escSchema(value)}"${value === selectedVersion ? ' selected' : ''}>${_escSchema(value)}${latestLabel}</option>`;
    }).join('');
  panel.innerHTML = `<div class="sr-pane">
    <header class="sr-pane-head">
      ${srCrumb([
        { label: registry.name, action: `selectSchemaRegistry(${srJs(registry.name)},true)` },
        { label: group.groupId, action: `selectSchemaGroup(${srJs(registry.name)},${srJs(group.groupId)},true)` },
        { label: artifact.artifactId },
      ])}
      <div class="sr-pane-title-row">
        <div class="sr-pane-title">
          <div class="sr-pane-kicker">${_escSchema((registry.provider || '').toUpperCase())} artifact</div>
          <h1>${_escSchema(artifact.name || artifact.artifactId)}</h1>
          <p class="sr-pane-url">${_escSchema(group.groupId)} · ${_escSchema(artifact.artifactId)}</p>
        </div>
        <div class="sr-pane-head-actions">
          <span class="sr-type-badge sr-type-${typeClass}">${_escSchema(type)}</span>
          <label class="sr-version-label">
            Version
            <select class="sr-version-select" onchange='selectSchemaVersion(${srJs(registry.name)},${srJs(group.groupId)},${srJs(artifact.artifactId)},this.value)'>
              ${options}
            </select>
          </label>
          <button class="sr-copy-btn" id="srCopyBtn" type="button" onclick="srCopyCurrentSchema()">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            Copy
          </button>
        </div>
      </div>
      <div class="sr-chip-row">
        <span class="sr-chip">Schema ID <strong>${_escSchema(schema.schemaId ?? 'n/a')}</strong></span>
        <span class="sr-chip">Version <strong>${_escSchema(selectedVersion)}</strong>${schema.latest ? ' <em>latest</em>' : ''}</span>
        <span class="sr-chip">Created <strong>${_escSchema(formatSchemaDate(schema.createdAt || artifact.createdAt))}</strong></span>
        <span class="sr-chip">Updated <strong>${_escSchema(formatSchemaDate(schema.updatedAt || artifact.updatedAt))}</strong></span>
      </div>
    </header>
    <section class="sr-viewer">
      <div class="sr-viewer-bar">
        <span>Schema content</span>
        <span>${_escSchema(type)} · v${_escSchema(selectedVersion)}</span>
      </div>
      <pre class="sr-schema-pre" id="srSchemaPre">${srSyntaxHighlight(schema.content)}</pre>
    </section>
  </div>`;
}

function selectSchemaVersion(registryName, groupId, artifactId, version) {
  schemaTreeSelected = { registry: registryName, groupId, artifactId, version };
  const found = findArtifact(registryName, groupId, artifactId);
  const panel = document.getElementById('schemaArtifactDetail');
  const pre = document.getElementById('srSchemaPre');
  if (pre) pre.textContent = 'Loading version…';
  loadSchemaContent(registryName, groupId, artifactId, version)
    .then(schema => {
      return srApi(registryName, '/versions', { group: groupId, artifact: artifactId }).then(data => {
        renderLiveSchemaDetail(found, data.versions || [], data.latest, schema);
      }).catch(() => renderLiveSchemaDetail(found, [{ version }], version, schema));
    })
    .catch(err => {
      if (panel) renderSchemaRegistryEmpty(err.message || 'Unable to load schema version.');
    });
}

function srCopyCurrentSchema() {
  const pre = document.getElementById('srSchemaPre');
  if (!pre) return;
  const text = pre.textContent || '';
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('srCopyBtn');
    if (!btn) return;
    btn.textContent = '✓ Copied';
    setTimeout(() => {
      btn.innerHTML = '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy';
    }, 1800);
  });
}

function initSchemaSidebarResize() {
  const sidebar = document.getElementById('schemaTreeSidebar');
  const handle = document.getElementById('schemaTreeResizer');
  if (!sidebar || !handle || handle.dataset.bound) return;
  handle.dataset.bound = '1';
  const storageKey = 'streambridge.schemaTreeSidebarWidth';
  const minW = 200;
  const maxW = 560;
  const saved = Number(localStorage.getItem(storageKey));
  if (saved >= minW && saved <= maxW) sidebar.style.width = saved + 'px';

  const clamp = (width) => Math.min(maxW, Math.max(minW, width));
  const onMove = (event) => {
    const next = clamp(event.clientX - sidebar.getBoundingClientRect().left);
    sidebar.style.width = next + 'px';
  };
  const onUp = () => {
    handle.classList.remove('dragging');
    document.body.classList.remove('sr-sidebar-resizing');
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    const width = parseInt(sidebar.style.width, 10);
    if (width) localStorage.setItem(storageKey, String(width));
  };
  handle.addEventListener('mousedown', (event) => {
    event.preventDefault();
    handle.classList.add('dragging');
    document.body.classList.add('sr-sidebar-resizing');
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initSchemaSidebarResize();
  if (document.getElementById('view-schema-registry')?.classList.contains('active')) loadSchemaRegistries();
});
