// ──────────────────────────────────────────────
// RCA — Incident Tracker
// ──────────────────────────────────────────────

function showToast(msg) {
  if (typeof window !== 'undefined' && typeof window._appShowToast === 'function') { window._appShowToast(msg); return; }
  let host = document.getElementById('rca-toast-host');
  if (!host) {
    host = document.createElement('div');
    host.id = 'rca-toast-host';
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

let rcaList = [
  {
    id: 'RCA-001',
    title: 'Postgres WAL buildup spike',
    severity: 'critical',
    status: 'open',
    connection: 'postgres-prod',
    date: '2026-09-02',
    error: `ERROR:  replication slot "debezium_slot" exceeded max_slot_wal_keep_size
DETAIL: WAL size 4.2 GB, configured limit 2 GB
HINT:   Drop or recreate the replication slot, or increase max_slot_wal_keep_size`,
    rootCause: 'A long-running transaction on the orders table held the replication slot open for ~4 hours, causing WAL segments to accumulate beyond the configured 2 GB limit. The transaction originated from a batch analytics job that lacked a query timeout.',
    resolution: '1. Identified and terminated idle transaction (PID 8821)\n2. Increased max_slot_wal_keep_size from 2 GB to 8 GB\n3. Set statement_timeout = 30min on the analytics role\n4. Added PagerDuty alert at 70% WAL threshold\n5. Documented in runbook: wiki/postgres-replication',
    timeline: [
      { time: '14:10', event: 'Alert fired — WAL size exceeded 2 GB' },
      { time: '14:23', event: 'Incident created, assigned to @oncall' },
      { time: '15:41', event: 'Root cause identified — idle transaction PID 8821' },
      { time: '16:05', event: 'Fix applied, CDC replication resumed' },
    ],
    aiSuggestion: 'Based on 2 similar past incidents (RCA-003, RCA-005), this pattern is typically caused by unbounded read transactions.\n\nSuggested diagnostic query:\n```sql\nSELECT pid, now() - pg_stat_activity.query_start AS duration, query\nFROM pg_stat_activity\nWHERE state = \'idle in transaction\'\nORDER BY duration DESC;\n```\n\nRecommended permanent fix: set `idle_in_transaction_session_timeout = 10min` in postgresql.conf to auto-terminate stalled transactions.'
  },
  {
    id: 'RCA-002',
    title: 'Kafka consumer group lag surge',
    severity: 'high',
    status: 'investigating',
    connection: 'kafka-prod-broker',
    date: '2026-09-01',
    error: `WARN  KafkaConsumer - Consumer group "cdc-sink-group" lag = 2,847,332
ERROR KafkaConsumer - Partition ecommerce.public.orders-0 offset behind by 2.8M messages
WARN  KafkaConsumer - Broker response time > 5000ms`,
    rootCause: 'Under investigation. Likely caused by a slow sink connector writing to Snowflake — Snowflake ingest API started returning 503s at 23:45 UTC triggering back-pressure on the consumer.',
    resolution: '',
    timeline: [
      { time: '23:50', event: 'Lag alert fired — consumer group lag > 1M' },
      { time: '00:03', event: 'Incident created, on-call paged' },
      { time: '00:18', event: 'Snowflake 503 errors confirmed in sink connector logs' },
    ],
    aiSuggestion: 'Snowflake ingest 503s typically indicate rate limiting or a table lock. Check:\n\n1. Snowflake query history for long-running DML on the target table\n2. Snowflake warehouse auto-suspend — may need to increase size temporarily\n3. Consider adding retry backoff in the sink connector config:\n   `errors.retry.delay.max.ms = 60000`\n   `errors.retry.timeout = 300000`'
  },
  {
    id: 'RCA-003',
    title: 'Schema compatibility check failure',
    severity: 'medium',
    status: 'resolved',
    connection: 'confluent-schema-registry',
    date: '2026-08-30',
    error: `ERROR SchemaRegistry - Schema registration failed for subject "ecommerce.public.orders-value"
io.confluent.kafka.schemaregistry.client.rest.exceptions.RestClientException:
  Schema being registered is incompatible with an earlier schema;
  error code: 409 (BACKWARD compatibility violation)
  Removed field: "discount_code" (was required, non-nullable)`,
    rootCause: 'A developer removed the `discount_code` field from the Avro schema without making it nullable first. BACKWARD compatibility requires that consumers reading old messages can still deserialize them with the new schema — removing a required field breaks this.',
    resolution: '1. Reverted the schema change in the orders service\n2. Made `discount_code` nullable with a null default\n3. Re-registered the schema (passed compatibility check)\n4. Added schema review step to the CDC deployment checklist',
    timeline: [
      { time: '10:05', event: 'Deploy failed — schema registration error' },
      { time: '10:12', event: 'Incident created' },
      { time: '10:34', event: 'Root cause identified — non-nullable field removed' },
      { time: '11:02', event: 'Fix deployed, schema registered successfully' },
      { time: '11:10', event: 'Incident resolved' },
    ],
    aiSuggestion: 'For BACKWARD-compatible schema evolution, always follow this order:\n\n1. Add new fields with defaults (never remove required fields directly)\n2. Make a field nullable before removing it in a future version\n3. Run compatibility check locally before deploying:\n   `curl -X POST .../compatibility/subjects/{subject}/versions/latest`\n\nConsider enforcing schema compatibility in CI with the Confluent Schema Registry Maven plugin.'
  },
  {
    id: 'RCA-004',
    title: 'S3 sink connector timeout',
    severity: 'medium',
    status: 'resolved',
    connection: 's3-data-lake',
    date: '2026-08-28',
    error: `ERROR S3SinkTask - Failed to upload part to S3
com.amazonaws.SdkClientException: Unable to execute HTTP request:
  Read timed out after 30000ms
  Bucket: streambridge-data-lake
  Key: cdc/postgres/orders/2026/08/28/part-00012.parquet`,
    rootCause: 'The S3 sink connector\'s default socket timeout (30s) was too low for large Parquet files being written during peak hours. Files were exceeding 500 MB due to a misconfigured flush size (s3.part.size was set to 512 MB instead of 64 MB).',
    resolution: '1. Reduced s3.part.size from 512 MB to 64 MB\n2. Increased s3.socket.timeout.ms to 120000\n3. Enabled S3 multipart upload\n4. Restarted connector — backfilled missing partitions from DLQ',
    timeline: [
      { time: '02:14', event: 'S3 upload timeout alerts triggered' },
      { time: '02:31', event: 'Incident created' },
      { time: '03:10', event: 'Identified oversized Parquet files' },
      { time: '03:45', event: 'Config updated, connector restarted' },
      { time: '04:00', event: 'Backfill complete, incident resolved' },
    ],
    aiSuggestion: 'For S3 sink connectors writing large files, recommended config:\n\n```\ns3.part.size=67108864          # 64 MB\ns3.socket.timeout.ms=120000\nflush.size=50000\nrotate.interval.ms=600000\n```\n\nAlso enable multipart upload for files > 100 MB to avoid single-request timeouts.'
  },
  {
    id: 'RCA-005',
    title: 'MySQL binlog position gap',
    severity: 'high',
    status: 'closed',
    connection: 'mysql-prod',
    date: '2026-08-25',
    error: `ERROR DebeziumConnector - Connector "mysql-cdc-prod" encountered an error
io.debezium.DebeziumException: The connector is trying to read binlog starting at
  gtid_set=3E11FA47-71CA-11E1-9E33-C80AA9429562:1-28, but this is no longer
  available on the server. Attempting to reconnect...
FATAL: binlog purged before connector could process it`,
    rootCause: 'MySQL\'s binlog retention was set to 24 hours. The CDC connector was paused for 26 hours during a planned maintenance window, causing the binlog position to be purged before the connector resumed. This required a full snapshot restart.',
    resolution: '1. Increased binlog retention: SET GLOBAL binlog_expire_logs_seconds = 604800 (7 days)\n2. Triggered full snapshot resync for affected tables\n3. Updated maintenance runbook — CDC connectors must be stopped gracefully and binlog position noted\n4. Added monitoring for binlog retention headroom',
    timeline: [
      { time: 'Aug 23 09:00', event: 'Planned maintenance started, connector paused' },
      { time: 'Aug 25 11:00', event: 'Maintenance complete, connector resumed' },
      { time: 'Aug 25 11:02', event: 'Binlog gap error — connector failed to start' },
      { time: 'Aug 25 11:30', event: 'Full snapshot triggered' },
      { time: 'Aug 25 18:45', event: 'Snapshot complete, CDC resumed, incident closed' },
    ],
    aiSuggestion: 'To prevent binlog purge gaps:\n\n1. Set binlog retention to at least 7 days:\n   `SET GLOBAL binlog_expire_logs_seconds = 604800;`\n2. Before any maintenance, note the current GTID position:\n   `SHOW MASTER STATUS;`\n3. If a gap occurs, trigger a fresh snapshot:\n   Set `snapshot.mode=initial` in the connector config temporarily\n4. Consider enabling GTID-based replication for easier position tracking'
  }
];

let rcaFilter = '';
let rcaSelectedId = null;
let rcaAiExpanded = false;

function filterRcaList(val) {
  rcaFilter = val.toLowerCase();
  renderRcaList();
}

function renderRcaList() {
  const body = document.getElementById('rcaListBody');
  if (!body) return;

  const severityColor = { critical: '#dc2626', high: '#ff6b35', medium: '#d97706', low: '#6b7280' };
  const statusColor   = { open: '#dc2626', investigating: '#ff6b35', resolved: '#059669', closed: '#6b7280' };

  const groups = [
    { key: 'open',          label: 'Open RCA' },
    { key: 'investigating', label: 'Investigating RCA' },
    { key: 'resolved',      label: 'Resolved RCA' },
    { key: 'closed',        label: 'Closed RCA' },
  ];

  let items = rcaList;
  if (rcaFilter) {
    items = items.filter(r =>
      r.title.toLowerCase().includes(rcaFilter) ||
      r.id.toLowerCase().includes(rcaFilter) ||
      r.connection.toLowerCase().includes(rcaFilter)
    );
  }

  const buckets = Object.fromEntries(groups.map(g => [g.key, []]));
  items.forEach(r => { if (buckets[r.status]) buckets[r.status].push(r); });

  const groupIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';

  let html = '';
  groups.forEach(g => {
    const rows = buckets[g.key];
    if (rows.length === 0) return;
    const groupId = 'rcag-' + g.key;
    const isCollapsed = body.querySelector('#' + groupId + '.collapsed') ? 'collapsed' : '';

    html += `
      <div class="conn-tree-group ${isCollapsed}" id="${groupId}">
        <div class="conn-tree-group-hdr" onclick="toggleConnGroup(this)">
          <svg class="conn-tree-chevron" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
          <div class="conn-tree-group-icon" style="background:${statusColor[g.key]}1a;color:${statusColor[g.key]};">
            ${groupIcon}
          </div>
          <span class="conn-tree-group-name">${g.label}</span>
          <span class="conn-tree-group-count">${rows.length}</span>
        </div>
        <div class="conn-tree-group-items">`;

    rows.forEach(r => {
      const isActive = r.id === rcaSelectedId ? ' active' : '';
      html += `
        <div class="conn-tree-item${isActive}" onclick="selectRca('${r.id}')">
          <span class="conn-tree-item-icon">${window.SB_FILE_ICON}</span>
          <span class="conn-tree-item-name"><span style="font-family:var(--mono);color:var(--text3);margin-right:6px;">${r.id}</span>${r.title}</span>
        </div>`;
    });

    html += `</div></div>`;
  });

  if (!html) {
    html = '<div style="padding:24px 16px;text-align:center;color:var(--text3);font-size:12px;">No incidents found.</div>';
  }
  body.innerHTML = html;
}

function selectRca(id) {
  rcaSelectedId = id;
  rcaAiExpanded = false;
  renderRcaList();
  renderRcaDetail(id);
}

function renderRcaDetail(id) {
  const panel = document.getElementById('rcaDetail');
  if (!panel) return;
  const r = rcaList.find(x => x.id === id);
  if (!r) return;
  r.comments = r.comments || [];

  const severityColor = { critical: '#dc2626', high: '#ff6b35', medium: '#d97706', low: '#6b7280' };
  const severityBg    = { critical: 'rgba(220,38,38,0.10)', high: 'rgba(255,107,53,0.10)', medium: 'rgba(217,119,6,0.10)', low: 'rgba(107,114,128,0.10)' };
  const statusColor   = { open: '#dc2626', investigating: '#ff6b35', resolved: '#059669', closed: '#6b7280' };
  const statusBg      = { open: 'rgba(220,38,38,0.10)', investigating: 'rgba(255,107,53,0.10)', resolved: 'rgba(5,150,105,0.10)', closed: 'rgba(107,114,128,0.10)' };
  const statusLabel   = { open: 'Open', investigating: 'Investigating', resolved: 'Resolved', closed: 'Closed' };
  const priorityIcon  = {
    critical: '<svg viewBox="0 0 24 24" width="12" height="12"><polygon points="12,4 20,16 4,16" fill="currentColor"/></svg>',
    high:     '<svg viewBox="0 0 24 24" width="12" height="12"><polygon points="12,6 19,15 5,15" fill="currentColor"/></svg>',
    medium:   '<svg viewBox="0 0 24 24" width="12" height="12"><rect x="4" y="9" width="16" height="2" rx="1" fill="currentColor"/><rect x="4" y="13" width="16" height="2" rx="1" fill="currentColor"/></svg>',
    low:      '<svg viewBox="0 0 24 24" width="12" height="12"><polygon points="4,8 20,8 12,20" fill="currentColor"/></svg>',
  };

  const statusOptions = ['open','investigating','resolved','closed'].map(s =>
    `<option value="${s}" ${r.status === s ? 'selected' : ''}>${statusLabel[s]}</option>`
  ).join('');

  const reporter = r.reporter || '@oncall';
  const assignee = r.assignee || '@oncall';
  const initial = (assignee.replace('@','')[0] || 'U').toUpperCase();
  const isWatching = rcaWatchSet.has(r.id);

  const feedItems = [
    ...r.timeline.map(t => ({ kind:'event', time:t.time, event:t.event })),
    ...r.comments.map(c => ({ kind:'comment', time:c.time, author:c.author, body:c.body })),
  ];

  const feedHtml = feedItems.length === 0
    ? '<div style="padding:16px;color:var(--text3);font-size:12px;font-style:italic;">No activity yet.</div>'
    : feedItems.map((f, i) => f.kind === 'event' ? `
        <div class="rca-feed-row">
          <div class="rca-feed-dot"></div>
          <div class="rca-feed-content">
            <div class="rca-feed-line"><span class="rca-feed-time">${f.time}</span> <span class="rca-feed-event">${f.event}</span></div>
          </div>
        </div>` : `
        <div class="rca-feed-row rca-feed-row-comment">
          <div class="rca-feed-avatar">${(f.author||'U')[0].toUpperCase()}</div>
          <div class="rca-feed-content">
            <div class="rca-feed-line"><b>${f.author||'You'}</b> <span class="rca-feed-time">${f.time}</span></div>
            <div class="rca-feed-body">${(f.body||'').replace(/</g,'&lt;').replace(/\n/g,'<br>')}</div>
          </div>
        </div>`).join('');

  const aiCodeHighlighted = (r.aiSuggestion || '').replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre class="rca-ai-code">${code.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</pre>`
  );
  const aiTextHtml = aiCodeHighlighted.replace(/\n(?!<pre)/g, '<br>');

  const labels = [r.connection.split('-')[0], 'cdc'].filter(Boolean);
  const labelChips = labels.map(l => `<span class="rca-jira-label">${l}</span>`).join('');

  const pencilSvg = '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';
  const copySvg = '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';

  panel.innerHTML = `
    <div class="conn-detail-inner rca-detail-jira">

      <div class="rca-jira-header">
        <div class="rca-jira-key">${r.id}</div>
        <h1 class="rca-jira-title">${r.title}</h1>
        <div class="rca-jira-actionbar">
          <div class="rca-jira-status-wrap" style="background:${statusBg[r.status]};color:${statusColor[r.status]};border-color:${statusColor[r.status]};">
            <select class="rca-jira-status-select" onchange="updateRcaStatus('${r.id}',this.value)" style="color:${statusColor[r.status]};">${statusOptions}</select>
            <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
          </div>
          <div class="rca-jira-priority" style="color:${severityColor[r.severity]};background:${severityBg[r.severity]};">
            ${priorityIcon[r.severity]}<span>${r.severity.charAt(0).toUpperCase()+r.severity.slice(1)}</span>
          </div>
          <button class="rca-jira-icon-btn" onclick="openRcaModal('${r.id}')" title="Edit">${pencilSvg}</button>
        </div>
      </div>

      <div class="rca-jira-body">

        <div class="rca-jira-main">

          <div class="rca-jira-section">
            <div class="rca-jira-section-hdr">
              <span>Error Log</span>
              <button class="rca-jira-tiny-btn" onclick="rcaCopyText('${r.id}','error')">${copySvg}Copy</button>
            </div>
            <pre class="rca-error-pre">${r.error.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</pre>
          </div>

          <div class="rca-jira-section">
            <div class="rca-jira-section-hdr">
              <span>Root Cause</span>
              <button class="rca-jira-tiny-btn rca-jira-edit-btn" onclick="openRcaModal('${r.id}')">${pencilSvg}Edit</button>
            </div>
            <div class="rca-text-body">${r.rootCause ? r.rootCause.replace(/\n/g,'<br>') : '<span style="color:var(--text3);font-style:italic;">Not yet documented.</span>'}</div>
          </div>

          <div class="rca-jira-section">
            <div class="rca-jira-section-hdr">
              <span>Resolution</span>
              <button class="rca-jira-tiny-btn rca-jira-edit-btn" onclick="openRcaModal('${r.id}')">${pencilSvg}Edit</button>
            </div>
            <div class="rca-text-body">${r.resolution ? r.resolution.replace(/\n/g,'<br>') : '<span style="color:var(--text3);font-style:italic;">No resolution yet.</span>'}</div>
          </div>

          <div class="rca-jira-section rca-ai-card">
            <div class="rca-jira-section-hdr rca-ai-title" onclick="toggleRcaAi()" style="cursor:pointer;">
              <div style="display:flex;align-items:center;gap:8px;">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#7c3aed" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                <span style="color:#7c3aed;">AI Suggestion</span>
              </div>
              <svg class="rca-ai-chevron ${rcaAiExpanded ? 'open' : ''}" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
            <div class="rca-ai-body" id="rcaAiBody" style="display:${rcaAiExpanded ? 'block' : 'none'};">
              <div class="rca-ai-text">${aiTextHtml}</div>
            </div>
          </div>

          <div class="rca-jira-section">
            <div class="rca-jira-section-hdr"><span>Activity</span></div>
            <div class="rca-jira-feed">${feedHtml}</div>

            <div class="rca-jira-comment-box">
              <div class="rca-feed-avatar rca-jira-avatar-me">Y</div>
              <div style="flex:1;min-width:0;">
                <textarea id="rcaCommentInput-${r.id}" class="rca-jira-comment-input" placeholder="Add a comment…" rows="2"></textarea>
                <div class="rca-jira-comment-actions">
                  <button class="btn btn-primary" onclick="addRcaComment('${r.id}')">Save</button>
                  <button class="btn btn-secondary" onclick="document.getElementById('rcaCommentInput-${r.id}').value=''">Cancel</button>
                </div>
              </div>
            </div>
          </div>

        </div>

      </div>

    </div>`;
}

let rcaWatchSet = new Set();
function toggleRcaWatch(id) {
  if (rcaWatchSet.has(id)) rcaWatchSet.delete(id); else rcaWatchSet.add(id);
  renderRcaDetail(id);
}

function addRcaComment(id) {
  const r = rcaList.find(x => x.id === id);
  if (!r) return;
  const ta = document.getElementById('rcaCommentInput-' + id);
  const text = (ta && ta.value || '').trim();
  if (!text) return;
  const now = new Date();
  const time = String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
  r.comments = r.comments || [];
  r.comments.push({ time, author: '@you', body: text });
  renderRcaDetail(id);
}

function toggleRcaAi() {
  rcaAiExpanded = !rcaAiExpanded;
  const body = document.getElementById('rcaAiBody');
  const chevron = document.querySelector('.rca-ai-chevron');
  if (body) body.style.display = rcaAiExpanded ? 'block' : 'none';
  if (chevron) chevron.classList.toggle('open', rcaAiExpanded);
}

function updateRcaStatus(id, newStatus) {
  const r = rcaList.find(x => x.id === id);
  if (!r) return;
  r.status = newStatus;
  renderRcaList();
  renderRcaDetail(id);
  showToast('Status updated to ' + newStatus);
}

function openRcaModal(id) {
  const modal = document.getElementById('rcaModal');
  if (!modal) return;
  if (id) {
    const r = rcaList.find(x => x.id === id);
    if (!r) return;
    document.getElementById('rcaModalTitle').textContent = 'Edit Incident';
    document.getElementById('rcaEditId').value = id;
    document.getElementById('rcaFormTitle').value = r.title;
    document.getElementById('rcaFormSeverity').value = r.severity;
    document.getElementById('rcaFormStatus').value = r.status;
    document.getElementById('rcaFormConnection').value = r.connection;
    document.getElementById('rcaFormError').value = r.error;
    document.getElementById('rcaFormRootCause').value = r.rootCause;
    document.getElementById('rcaFormResolution').value = r.resolution;
  } else {
    document.getElementById('rcaModalTitle').textContent = 'New Incident';
    document.getElementById('rcaEditId').value = '';
    document.getElementById('rcaFormTitle').value = '';
    document.getElementById('rcaFormSeverity').value = 'medium';
    document.getElementById('rcaFormStatus').value = 'open';
    document.getElementById('rcaFormConnection').value = '';
    document.getElementById('rcaFormError').value = '';
    document.getElementById('rcaFormRootCause').value = '';
    document.getElementById('rcaFormResolution').value = '';
  }
  modal.style.display = 'block';
}

function closeRcaModal() {
  const modal = document.getElementById('rcaModal');
  if (modal) modal.style.display = 'none';
}

function rcaModalBgClick(e) {
  if (e.target === document.getElementById('rcaModal')) closeRcaModal();
}

function saveRca() {
  const title = document.getElementById('rcaFormTitle').value.trim();
  if (!title) { showToast('Title is required'); return; }

  const editId = document.getElementById('rcaEditId').value;
  const data = {
    title,
    severity:   document.getElementById('rcaFormSeverity').value,
    status:     document.getElementById('rcaFormStatus').value,
    connection: document.getElementById('rcaFormConnection').value.trim(),
    error:      document.getElementById('rcaFormError').value.trim(),
    rootCause:  document.getElementById('rcaFormRootCause').value.trim(),
    resolution: document.getElementById('rcaFormResolution').value.trim(),
  };

  if (editId) {
    const r = rcaList.find(x => x.id === editId);
    if (r) Object.assign(r, data);
    showToast('Incident updated');
    closeRcaModal();
    renderRcaList();
    renderRcaDetail(editId);
  } else {
    const newId = 'RCA-' + String(rcaList.length + 1).padStart(3, '0');
    const today = new Date().toISOString().slice(0, 10);
    rcaList.unshift({ id: newId, date: today, timeline: [], aiSuggestion: '', ...data });
    showToast('Incident created');
    closeRcaModal();
    renderRcaList();
    selectRca(newId);
  }
}

function rcaCopyText(id, field) {
  const r = rcaList.find(x => x.id === id);
  if (!r) return;
  navigator.clipboard.writeText(r[field] || '').then(() => showToast('Copied'));
}

function renderRcaView() {
  renderRcaList();
}

document.addEventListener('DOMContentLoaded', () => { if (document.getElementById('view-rca')?.classList.contains('active')) renderRcaView(); });
