// ──────────────────────────────────────────────
// KAFKA TOPICS (live broker browse)
// ──────────────────────────────────────────────

let kafkaTreeFilter = '';
let kafkaTreeSelected = null;
let kafkaBrokers = [];
let kafkaTopicsByBroker = {};
let kafkaRegistries = [];
let kafkaTopicState = {
  tab: 'messages',
  messages: [],
  hasOlder: false,
  cursor: {},
  partitions: [],
  loading: false,
  error: '',
  schema: null,
  schemaError: '',
};
let kafkaQuery = {
  valueFormat: 'auto',
  keyFormat: 'auto',
  registry: '',
  partition: '',
};
let _kafkaLoadToken = 0;

function _escKafka(value) {
  return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function kafkaJs(value) {
  return JSON.stringify(String(value ?? ''))
    .replace(/&/g, '&amp;')
    .replace(/</g, '\\u003c')
    .replace(/'/g, '&#39;');
}

function kafkaApi(path) {
  return fetch(path).then(async response => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.message || `Request failed (${response.status})`);
    return data;
  });
}

function filterKafkaTree(val) {
  kafkaTreeFilter = (val || '').toLowerCase();
  renderKafkaTree();
}

function loadKafkaTopicsPage() {
  initKafkaSidebarResize();
  const body = document.getElementById('kafkaTreeBody');
  if (body) body.innerHTML = '<div class="sr-nav-empty">Loading topics…</div>';
  kafkaTopicsByBroker = {};
  const wanted = new URLSearchParams(window.location.search).get('connection') || '';
  Promise.all([
    kafkaApi('/api/kafka-brokers'),
    kafkaApi('/api/schema-registries').catch(() => []),
  ]).then(([brokers, registries]) => {
    kafkaBrokers = Array.isArray(brokers) ? brokers : [];
    kafkaRegistries = Array.isArray(registries) ? registries : [];
    if (!kafkaQuery.registry && kafkaRegistries[0]) kafkaQuery.registry = kafkaRegistries[0].name;
    renderKafkaTree();
    if (!kafkaBrokers.length) {
      renderKafkaEmpty('No Kafka connections yet. Add a broker to browse topics and messages.');
      return;
    }
    const first = kafkaBrokers.find(item => item.name === wanted) || kafkaBrokers[0];
    return Promise.all(kafkaBrokers.map(broker =>
      kafkaApi(`/api/kafka-brokers/${encodeURIComponent(broker.name)}/topics`)
        .then(data => {
          kafkaTopicsByBroker[broker.name] = data.topics || [];
        })
        .catch(err => {
          kafkaTopicsByBroker[broker.name] = { error: err.message };
        })
    )).then(() => {
      renderKafkaTree();
      if (!kafkaTreeSelected) renderKafkaLanding();
      const sidebar = document.getElementById('kafkaTreeSidebar');
      const group = document.getElementById('kg-' + first.name);
      if (sidebar && group) {
        sidebar._expandedGroups = sidebar._expandedGroups || new Set();
        sidebar._expandedGroups.add(group.id);
        group.classList.remove('collapsed');
      }
    });
  }).catch(err => {
    renderKafkaTree();
    renderKafkaEmpty(err.message);
  });
}

function renderKafkaTree() {
  const body = document.getElementById('kafkaTreeBody');
  if (!body) return;
  const q = kafkaTreeFilter;
  if (!kafkaBrokers.length) {
    body.innerHTML = `
      <div class="sr-nav-empty" style="padding:24px 16px;text-align:center;">
        No Kafka brokers configured.
        <div style="margin-top:10px;">
          <a class="sr-empty-link" href="/connections?new=kafka">Add a Kafka connection</a>
        </div>
      </div>`;
    return;
  }

  body.innerHTML = kafkaBrokers.map(broker => {
    const loaded = kafkaTopicsByBroker[broker.name];
    const error = loaded && loaded.error;
    let topics = Array.isArray(loaded) ? loaded : [];
    if (q) {
      topics = topics.filter(topic =>
        (topic.name || '').toLowerCase().includes(q) || broker.name.toLowerCase().includes(q)
      );
    }
    const groupId = 'kg-' + broker.name;
    return `
      <div class="conn-tree-group" id="${_escKafka(groupId)}">
        <div class="conn-tree-group-hdr" onclick="toggleConnGroup(this)">
          <svg class="conn-tree-chevron" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
          <div class="conn-tree-group-icon" style="background:rgba(59,125,233,0.10);color:var(--blue);">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><line x1="9" y1="7" x2="15" y2="7"/><line x1="9" y1="11" x2="15" y2="11"/><line x1="9" y1="15" x2="13" y2="15"/></svg>
          </div>
          <span class="conn-tree-group-name" title="${_escKafka(broker.name)}">${_escKafka(broker.name)}</span>
          <span class="conn-tree-group-count">${error ? '!' : topics.length}</span>
        </div>
        <div class="conn-tree-group-items">
          ${error ? `<div class="sr-nav-empty">${_escKafka(error)}</div>` : ''}
          ${!error && !topics.length ? `<div class="sr-nav-empty">${loaded ? 'no topics' : 'loading…'}</div>` : ''}
          ${topics.map((topic, i) => {
            const active = kafkaTreeSelected && kafkaTreeSelected.conn === broker.name && kafkaTreeSelected.topic === topic.name ? ' active' : '';
            return `
              <div class="conn-tree-item${active}" title="${_escKafka(topic.name)}" onclick='selectKafkaTopic(${kafkaJs(broker.name)},${kafkaJs(topic.name)})'>
                <span class="conn-tree-item-num">${i + 1}.</span>
                <span class="conn-tree-item-name">${_escKafka(topic.name)}</span>
              </div>`;
          }).join('')}
        </div>
      </div>`;
  }).join('');
}

function selectKafkaTopic(connName, topic) {
  kafkaTreeSelected = { conn: connName, topic };
  kafkaTopicState.tab = 'messages';
  kafkaTopicState.cursor = {};
  kafkaQuery.partition = '';
  renderKafkaTree();
  loadKafkaMessages();
}

function kafkaMessageQuery(before) {
  if (!kafkaTreeSelected) return '';
  const params = new URLSearchParams({
    topic: kafkaTreeSelected.topic,
    limit: '100',
    key_format: kafkaQuery.keyFormat,
    value_format: kafkaQuery.valueFormat,
  });
  if (kafkaQuery.registry) params.set('registry', kafkaQuery.registry);
  if (kafkaQuery.partition !== '') params.set('partition', kafkaQuery.partition);
  if (before && Object.keys(before).length) params.set('before', JSON.stringify(before));
  return `/api/kafka-brokers/${encodeURIComponent(kafkaTreeSelected.conn)}/messages?${params}`;
}

function loadKafkaMessages(opts) {
  const older = !!(opts && opts.older);
  if (!kafkaTreeSelected) return;
  const token = ++_kafkaLoadToken;
  kafkaTopicState.loading = true;
  kafkaTopicState.error = '';
  renderTopicMessages();
  const before = older ? kafkaTopicState.cursor : null;
  kafkaApi(kafkaMessageQuery(before)).then(data => {
    if (token !== _kafkaLoadToken) return;
    kafkaTopicState.loading = false;
    kafkaTopicState.messages = data.messages || [];
    kafkaTopicState.hasOlder = !!data.hasOlder;
    kafkaTopicState.cursor = data.cursor || {};
    kafkaTopicState.partitions = data.partitions || [];
    renderTopicMessages();
  }).catch(err => {
    if (token !== _kafkaLoadToken) return;
    kafkaTopicState.loading = false;
    kafkaTopicState.error = err.message;
    kafkaTopicState.messages = [];
    renderTopicMessages();
  });
}

function kafkaSwitchTab(tab) {
  kafkaTopicState.tab = tab;
  renderTopicMessages();
  if (tab === 'schema') loadKafkaSchema();
}

function kafkaApplyFilters() {
  kafkaQuery.valueFormat = (document.getElementById('kafkaValueFormat') || {}).value || 'auto';
  kafkaQuery.keyFormat = (document.getElementById('kafkaKeyFormat') || {}).value || 'auto';
  kafkaQuery.registry = (document.getElementById('kafkaRegistry') || {}).value || '';
  kafkaQuery.partition = (document.getElementById('kafkaPartition') || {}).value || '';
  kafkaTopicState.cursor = {};
  loadKafkaMessages();
}

function syntaxHighlightJson(val) {
  if (val === null) return '<span class="kjson-null">null</span>';
  let json;
  try { json = typeof val === 'string' ? JSON.stringify(val) : JSON.stringify(val, null, 2); }
  catch (e) { return _escKafka(String(val)); }
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

function kafkaInlineValue(message) {
  if (message.tombstone || message.value === null) return '<span class="kafka-tombstone">tombstone</span>';
  if (message.decodeError) return `<span class="kafka-decode-err">${_escKafka(message.decodeError)}</span>`;
  try { return _escKafka(typeof message.value === 'string' ? message.value : JSON.stringify(message.value)); }
  catch (e) { return _escKafka(String(message.value)); }
}

function kafkaKeyLabel(key) {
  if (key == null) return '—';
  if (typeof key === 'string') return key;
  try { return JSON.stringify(key); } catch (e) { return String(key); }
}

function renderKafkaEmpty(message) {
  const panel = document.getElementById('kafkaTopicDetail');
  if (!panel) return;
  panel.innerHTML = `
    <div class="sr-pane sr-pane-empty">
      <div class="sr-empty-card">
        <h2>Kafka Topics</h2>
        <p>${_escKafka(message)}</p>
        <a class="sr-empty-link" href="/connections?new=kafka">Create a Kafka connection</a>
      </div>
    </div>`;
}

function renderKafkaLanding() {
  const panel = document.getElementById('kafkaTopicDetail');
  if (!panel) return;
  panel.innerHTML = `
    <div class="sr-pane sr-pane-empty">
      <div class="sr-empty-card">
        <h2>Kafka Topics</h2>
        <p>Select a topic to inspect the latest 100 messages. Use a Schema Registry connection to deserialize Avro.</p>
      </div>
    </div>`;
}

function renderTopicMessages() {
  const panel = document.getElementById('kafkaTopicDetail');
  if (!panel || !kafkaTreeSelected) return;
  const topic = kafkaTreeSelected.topic;
  const conn = kafkaTreeSelected.conn;
  const tab = kafkaTopicState.tab;
  const registryOpts = ['<option value="">None</option>'].concat(
    kafkaRegistries.map(item => `<option value="${_escKafka(item.name)}"${item.name === kafkaQuery.registry ? ' selected' : ''}>${_escKafka(item.name)}</option>`)
  ).join('');
  const partitionOpts = ['<option value="">All partitions</option>'].concat(
    (kafkaTopicState.partitions || []).map(part => `<option value="${part}"${String(kafkaQuery.partition) === String(part) ? ' selected' : ''}>${part}</option>`)
  ).join('');
  const formatOpts = (selected) => [
    ['auto', 'Auto'],
    ['string', 'String'],
    ['json', 'JSON'],
    ['avro', 'Avro'],
    ['bytes', 'Bytes'],
  ].map(([fmt, label]) => `<option value="${fmt}"${fmt === selected ? ' selected' : ''}>${label}</option>`).join('');

  const rows = (kafkaTopicState.messages || []).map(message => {
    const expanded = message.tombstone
      ? '<span class="kjson-null">null</span> <em style="color:#999;font-size:11px;">(tombstone)</em>'
      : syntaxHighlightJson(message.value);
    const keyHtml = _escKafka(kafkaKeyLabel(message.key));
    return `
      <tr class="kafka-msg-row" onclick="kafkaExpandRow(this)">
        <td class="kafka-col-ts">${_escKafka(message.timestamp || '—')}</td>
        <td class="kafka-col-offset">${message.offset}</td>
        <td class="kafka-col-part">${message.partition}</td>
        <td class="kafka-col-key" title="${keyHtml}">${keyHtml}</td>
        <td class="kafka-col-val">
          <span class="kafka-inline-val">${kafkaInlineValue(message)}</span>
          <pre class="kafka-expanded-pre" style="display:none;">${expanded}${message.decodeError ? `\n\n<span class="kafka-decode-err">${_escKafka(message.decodeError)}</span>` : ''}</pre>
        </td>
        <td class="kafka-col-eye">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </td>
      </tr>`;
  }).join('');

  const loadingPane = `
    <div class="kafka-loading" role="status" aria-live="polite">
      <div class="kafka-loading-spinner" aria-hidden="true"></div>
      <h3>Fetching latest messages</h3>
      <p>Reading up to 100 records from <strong>${_escKafka(topic)}</strong> on ${_escKafka(conn)}.</p>
      <div class="kafka-loading-bar" aria-hidden="true"><span></span></div>
    </div>`;
  const messagesPane = kafkaTopicState.loading ? loadingPane : `
    <div class="kafka-table-wrap">
      ${kafkaTopicState.error ? `<div class="kafka-error">${_escKafka(kafkaTopicState.error)}</div>` : ''}
      ${!kafkaTopicState.error ? `
      <table class="kafka-msg-table">
        <thead>
          <tr>
            <th class="kafka-col-ts">Timestamp</th>
            <th class="kafka-col-offset">Offset</th>
            <th class="kafka-col-part">Partition</th>
            <th class="kafka-col-key">Key</th>
            <th class="kafka-col-val">Value</th>
            <th class="kafka-col-eye"></th>
          </tr>
        </thead>
        <tbody id="kafkaMsgBody">${rows || '<tr><td colspan="6" class="sr-nav-empty">No messages in this window.</td></tr>'}</tbody>
      </table>` : ''}
    </div>
    <div class="kafka-pager">
      <span>${kafkaTopicState.messages.length} of up to 100</span>
      <button type="button" class="kafka-fetch-latest-btn" ${kafkaTopicState.hasOlder ? '' : 'disabled'} onclick="loadKafkaMessages({older:true})">Older</button>
    </div>`;

  const schemaPane = `
    <div class="kafka-schema-pane">
      ${kafkaTopicState.schemaError ? `<div class="kafka-error">${_escKafka(kafkaTopicState.schemaError)}</div>` : ''}
      ${kafkaTopicState.schema ? `<pre class="kafka-expanded-pre" style="display:block;">${syntaxHighlightJson(kafkaTopicState.schema)}</pre>` : ''}
      ${!kafkaTopicState.schema && !kafkaTopicState.schemaError ? '<div class="sr-nav-empty">Select a Schema Registry to inspect the matching subject.</div>' : ''}
    </div>`;

  panel.innerHTML = `
    <div class="kafka-detail-inner">
      <div class="kafka-detail-padded" style="padding-top:20px;padding-bottom:12px;">
        <div class="kafka-topic-heading">
          <div>
            <h2 class="kafka-topic-name">${_escKafka(topic)}</h2>
            <p class="sr-pane-url">${_escKafka(conn)}</p>
          </div>
          <button class="kafka-fetch-latest-btn" id="kafkaFetchBtn" ${kafkaTopicState.loading ? 'disabled' : ''} onclick="fetchLatestMessages()">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3"/></svg>
            Refresh
          </button>
        </div>
        <div class="kafka-tab-bar">
          <button type="button" class="kafka-tab-btn${tab === 'messages' ? ' active' : ''}" onclick="kafkaSwitchTab('messages')">Messages</button>
          <button type="button" class="kafka-tab-btn${tab === 'schema' ? ' active' : ''}" onclick="kafkaSwitchTab('schema')">Schema</button>
        </div>
        <div class="kafka-filter-bar">
          <label class="kafka-filter-field">
            <span>Key deserializer</span>
            <select class="kafka-filter-select" id="kafkaKeyFormat" aria-label="Key deserializer" onchange="kafkaApplyFilters()">${formatOpts(kafkaQuery.keyFormat)}</select>
          </label>
          <label class="kafka-filter-field">
            <span>Value deserializer</span>
            <select class="kafka-filter-select" id="kafkaValueFormat" aria-label="Value deserializer" onchange="kafkaApplyFilters()">${formatOpts(kafkaQuery.valueFormat)}</select>
          </label>
          <label class="kafka-filter-field">
            <span>Schema Registry</span>
            <select class="kafka-filter-select" id="kafkaRegistry" aria-label="Schema Registry" onchange="kafkaApplyFilters()">${registryOpts}</select>
          </label>
          <label class="kafka-filter-field">
            <span>Partition</span>
            <select class="kafka-filter-select" id="kafkaPartition" aria-label="Partition" onchange="kafkaApplyFilters()">${partitionOpts}</select>
          </label>
        </div>
      </div>
      ${tab === 'schema' ? schemaPane : messagesPane}
    </div>`;
}

function _pickTopicSchema(groups, topic) {
  const wanted = new Set([`${topic}-value`, `${topic}-key`, topic]);
  let fallback = null;
  for (const group of groups || []) {
    const groupId = group.groupId || group.id || 'default';
    for (const artifact of group.artifacts || []) {
      const artifactId = artifact.artifactId || artifact.id || '';
      const name = artifact.name || artifact.subject || artifactId;
      const match = wanted.has(name) || wanted.has(artifactId)
        || (String(artifactId).toLowerCase() === 'value' && groupId === topic);
      if (!match) continue;
      const record = { groupId, artifactId };
      if (name.endsWith('-value') || String(artifactId).toLowerCase() === 'value' || String(artifactId).endsWith('-value')) {
        return record;
      }
      fallback = fallback || record;
    }
  }
  return fallback;
}

function loadKafkaSchema() {
  if (!kafkaTreeSelected) return;
  const registry = kafkaQuery.registry;
  if (!registry) {
    kafkaTopicState.schema = null;
    kafkaTopicState.schemaError = 'Choose a Schema Registry connection to load the topic schema.';
    renderTopicMessages();
    return;
  }
  const topic = kafkaTreeSelected.topic;
  kafkaTopicState.schemaError = '';
  const prefix = `/api/schema-registries/${encodeURIComponent(registry)}`;
  kafkaApi(`${prefix}/catalog`).then(data => {
    const found = _pickTopicSchema(data.groups, topic) || { groupId: 'default', artifactId: `${topic}-value` };
    return kafkaApi(`${prefix}/content?group=${encodeURIComponent(found.groupId)}&artifact=${encodeURIComponent(found.artifactId)}`);
  }).then(data => {
    kafkaTopicState.schema = data.content || data;
    kafkaTopicState.schemaError = '';
    if (kafkaTopicState.tab === 'schema') renderTopicMessages();
  }).catch(err => {
    kafkaTopicState.schema = null;
    kafkaTopicState.schemaError = err.message;
    if (kafkaTopicState.tab === 'schema') renderTopicMessages();
  });
}

function kafkaExpandRow(tr) {
  const isExpanded = tr.classList.contains('kafka-row-expanded');
  document.querySelectorAll('.kafka-msg-row').forEach(row => {
    row.classList.remove('kafka-row-expanded');
    const pre = row.querySelector('.kafka-expanded-pre');
    const inline = row.querySelector('.kafka-inline-val');
    if (pre) pre.style.display = 'none';
    if (inline) inline.style.display = '';
  });
  if (isExpanded) return;
  tr.classList.add('kafka-row-expanded');
  const pre = tr.querySelector('.kafka-expanded-pre');
  const inline = tr.querySelector('.kafka-inline-val');
  if (pre) pre.style.display = 'block';
  if (inline) inline.style.display = 'none';
}

function fetchLatestMessages() {
  kafkaTopicState.cursor = {};
  loadKafkaMessages();
}

function initKafkaSidebarResize() {
  const sidebar = document.getElementById('kafkaTreeSidebar');
  const handle = document.getElementById('kafkaTreeResizer');
  if (!sidebar || !handle || handle.dataset.bound) return;
  handle.dataset.bound = '1';
  const storageKey = 'streambridge.kafkaTreeSidebarWidth';
  const minW = 200;
  const maxW = 560;
  const saved = Number(localStorage.getItem(storageKey));
  if (saved >= minW && saved <= maxW) sidebar.style.width = saved + 'px';
  const clamp = (width) => Math.min(maxW, Math.max(minW, width));
  const onMove = (event) => {
    sidebar.style.width = clamp(event.clientX - sidebar.getBoundingClientRect().left) + 'px';
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
  if (document.getElementById('view-kafka-topics')?.classList.contains('active')) loadKafkaTopicsPage();
});
