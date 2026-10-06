// ── ALERTS PAGE ──────────────────────────────────────────────────────────────

let _alertsData = [];
let _alertsFilter = '';
let _selectedAlertId = null;
let _alertHistPage = {};
let _alertHistPageSize = {};

const _sevColor = { critical:'#dc2626', high:'#ff6b35', medium:'#d97706', low:'#6b7280' };
const _sevBg    = { critical:'rgba(220,38,38,0.08)', high:'rgba(255,107,53,0.08)', medium:'rgba(217,119,6,0.08)', low:'rgba(107,114,128,0.08)' };
const ALERT_BELL_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>';
const _stateLabel = { triggered:'Triggered', ok:'OK', unknown:'Unknown' };

function _alertStateDot(state) {
  if (state === 'triggered') return 'background:#dc2626;box-shadow:0 0 4px #dc2626;animation:pulse-red 1.4s infinite;';
  if (state === 'ok')        return 'background:#16a34a;box-shadow:0 0 4px #16a34a;';
  return 'background:#9ca3af;';
}

async function loadAlerts() {
  try {
    const res = await fetch('/api/alerts');
    _alertsData = await res.json();
  } catch(e) { _alertsData = []; }
  renderAlertsSidebar();
}

function renderAlertsSidebar() {
  const body = document.getElementById('alertsListBody');
  const q = _alertsFilter.toLowerCase();
  const filtered = _alertsData.filter(a => !q || a.name.toLowerCase().includes(q) || a.connectorName.toLowerCase().includes(q));
  if (!filtered.length) {
    body.innerHTML = `<div style="padding:20px 16px;color:var(--text2);font-size:12px;text-align:center;">${_alertsData.length ? 'No alerts match your search' : 'No alerts yet — click + New to create one'}</div>`;
    return;
  }
  const chev = '<svg class="conn-tree-chevron" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>';
  const items = filtered.map((a, i) => `
    <div class="conn-tree-item${a.id === _selectedAlertId ? ' active' : ''}" onclick="selectAlert('${a.id}')">
      <span class="conn-tree-item-num">${i + 1}.</span>
      <span class="conn-tree-item-name">${a.name}</span>
    </div>`).join('');
  body.innerHTML = `
    <div class="al-nav-group${_alertListOpen ? '' : ' collapsed'}">
      <div class="conn-tree-group-hdr" onclick="toggleAlertListGroup()">
        ${chev}
        <div class="conn-tree-group-icon">${ALERT_BELL_ICON}</div>
        <span class="conn-tree-group-name">Alerts</span>
        <span class="conn-tree-group-count">${filtered.length}</span>
      </div>
      <div class="al-nav-group-items">${items}</div>
    </div>`;
}

function filterAlerts(q) { _alertsFilter = q; renderAlertsSidebar(); }

let _alertListOpen = true;
function toggleAlertListGroup() {
  _alertListOpen = !_alertListOpen;
  renderAlertsSidebar();
}

let _alertFavSet = new Set();
let _alertUiState = {}; // { [alertId]: { about:true, latest:true, notif:true, advanced:false, query:false } }

function _alertSectionOpen(id, key, defaultOpen) {
  if (!_alertUiState[id]) _alertUiState[id] = {};
  if (typeof _alertUiState[id][key] === 'undefined') _alertUiState[id][key] = !!defaultOpen;
  return _alertUiState[id][key];
}
function toggleAlertSection(id, key) {
  _alertUiState[id] = _alertUiState[id] || {};
  _alertUiState[id][key] = !_alertUiState[id][key];
  const a = _alertsData.find(x => x.id === id); if (a) selectAlert(id);
}
function toggleAlertFav(id) {
  if (_alertFavSet.has(id)) _alertFavSet.delete(id); else _alertFavSet.add(id);
  selectAlert(id);
}

function _fmtDate(d) {
  const M = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${M[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}
function _fmtDateTime(d) {
  const h = d.getHours(), m = String(d.getMinutes()).padStart(2,'0');
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${_fmtDate(d)}, ${h12}:${m} ${ampm}`;
}
function _fmtHistoryTime(d) {
  if (!(d instanceof Date) || Number.isNaN(d.getTime())) return '—';
  return _fmtDateTime(d);
}

function _channelIconSmall(type) {
  const t = (type || '').toLowerCase();
  if (t === 'email')     return '<svg viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22,6 12,13 2,6"/></svg>';
  if (t === 'slack')     return '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="12" y2="17"/></svg>';
  if (t === 'gchat' || t === 'google-chat' || t === 'googlechat') return '<svg viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="14" rx="2"/><polyline points="2 18 8 14 22 18"/></svg>';
  if (t === 'pagerduty') return '<svg viewBox="0 0 24 24"><path d="M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6l8-4z"/></svg>';
  if (t === 'webhook')   return '<svg viewBox="0 0 24 24"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>';
  return '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/></svg>';
}

let _alertNotifConns = [];
function _alertIsActive(a) {
  return !a || a.active !== false;
}

function setAlertStatus(id, value) {
  fetch(`/api/alerts/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ active: value !== 'disabled' }),
  }).then(async res => {
    if (!res.ok) { alert('Failed to update status'); return; }
    await loadAlerts();
    selectAlert(id);
  });
}

function _policyRules(a) {
  if (a && Array.isArray(a.rules) && a.rules.length) return a.rules.map(r => ({
    rule: String(r.rule || 'FAILED').toUpperCase(),
    action: _normAction(r.action),
  }));
  return [{ rule: _alertRule(a), action: _alertAction(a) }];
}

function _normAction(action) {
  const v = String(action || 'pause').toLowerCase();
  if (v === 're-trigger') return 're-trigger';
  if (v === 'notify') return 'notify';
  return 'pause';
}

function _alertRule(a) {
  const v = String((a && a.conditionValue) || 'FAILED').toUpperCase();
  return (v === 'UNKNOWN' || v === 'PAUSED') ? v : 'FAILED';
}

function _alertAction(a) {
  return _normAction(a && a.action);
}

function _alertRulesLabel(a) {
  return _policyRules(a).map(r => `${r.rule} → ${r.action}`).join(', ') || '—';
}

function _alertDisplayName(connectorName, rules) {
  const labels = (rules || []).map(r => r.rule).join(',');
  return labels ? `${connectorName} · ${labels}` : connectorName;
}

function _systemAlertMessage(connectorName, rule, action) {
  const act = _normAction(action);
  const state = String(rule || 'FAILED').toLowerCase();
  if (act === 'notify') return `${connectorName} was ${state}.`;
  const did = act === 're-trigger' ? 're-triggered it' : 'paused it';
  return `${connectorName} was ${state}. StreamBridge ${did}.`;
}

function _ruleSelectHtml(value) {
  return ['FAILED', 'UNKNOWN', 'PAUSED'].map(v =>
    `<option value="${v}"${v === value ? ' selected' : ''}>${v}</option>`
  ).join('');
}

function _actionSelectHtml(rule, action) {
  const acts = [
    ['pause', 'pause'],
    ['re-trigger', 're-trigger'],
    ['notify', 'notify'],
  ].filter(([v]) => !(rule === 'PAUSED' && v === 'pause'));
  const cur = rule === 'PAUSED' && action === 'pause' ? 'notify' : action;
  return acts.map(([v, label]) =>
    `<option value="${v}"${v === cur ? ' selected' : ''}>${label}</option>`
  ).join('');
}

function _alertRuleRowHtml(rule, action) {
  return `<div class="al-rule-row">
    <div class="pm-select-wrap">
      <select class="pm-select al-rule-state" onchange="onAlertRuleChanged(this)">${_ruleSelectHtml(rule)}</select>
      <svg class="pm-select-arrow" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <span class="al-rule-then">then</span>
    <div class="pm-select-wrap">
      <select class="pm-select al-rule-action">${_actionSelectHtml(rule, action)}</select>
      <svg class="pm-select-arrow" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <button type="button" class="al-rule-del" onclick="removeAlertRuleRow(this)" title="Remove">×</button>
  </div>`;
}

function renderAlertRuleRows(rules) {
  const box = document.getElementById('alertFormRules');
  if (!box) return;
  const rows = (rules && rules.length) ? rules : [{ rule: 'FAILED', action: 'pause' }];
  box.innerHTML = rows.map(r => _alertRuleRowHtml(r.rule, r.action)).join('');
}

function onAlertRuleChanged(sel) {
  const row = sel.closest('.al-rule-row');
  const actionSel = row && row.querySelector('.al-rule-action');
  if (!actionSel) return;
  const keep = actionSel.value;
  actionSel.innerHTML = _actionSelectHtml(sel.value, keep);
}

function addAlertRuleRow() {
  const box = document.getElementById('alertFormRules');
  if (!box) return;
  const used = new Set([...box.querySelectorAll('.al-rule-state')].map(s => s.value));
  const next = ['FAILED', 'UNKNOWN', 'PAUSED'].find(v => !used.has(v));
  if (!next) return;
  box.insertAdjacentHTML('beforeend', _alertRuleRowHtml(next, next === 'PAUSED' ? 'notify' : 'pause'));
}

function removeAlertRuleRow(btn) {
  const box = document.getElementById('alertFormRules');
  if (!box || box.querySelectorAll('.al-rule-row').length < 2) return;
  btn.closest('.al-rule-row')?.remove();
}

function _readAlertFormRules() {
  return [...document.querySelectorAll('#alertFormRules .al-rule-row')].map(row => ({
    rule: row.querySelector('.al-rule-state')?.value || 'FAILED',
    action: row.querySelector('.al-rule-action')?.value || 'pause',
  }));
}

function _alertEveryLabel(mins) {
  const n = parseInt(mins, 10);
  if (!Number.isFinite(n) || n < 1) return '1 min';
  if (n === 1) return '1 min';
  if (n % 60 === 0 && n >= 60) {
    const h = n / 60;
    return h === 1 ? '1 hour' : h + ' hours';
  }
  return n + ' min';
}

function _isNotifConn(c) {
  const t = String((c && c.type) || '').toLowerCase();
  const s = String((c && c.subtype) || '').toLowerCase();
  return t === 'notification' || s.startsWith('notification-');
}

function _alertChannelTypeFromConn(c) {
  const s = String((c && c.subtype) || (c && c.type) || '').toLowerCase();
  if (s.includes('gchat') || s.includes('google-chat')) return 'gchat';
  if (s.includes('slack')) return 'slack';
  if (s.includes('webhook')) return 'webhook';
  if (s.includes('email')) return 'email';
  if (s.includes('pager')) return 'pagerduty';
  return 'slack';
}

function _channelNamesFrom(value) {
  return String(value || '').split(',').map(s => s.trim()).filter(Boolean);
}

function _fillAlertChannelSelect(selectedNames) {
  const menu = document.getElementById('alertFormChannelMenu');
  const dd = document.getElementById('alertFormChannelDd');
  if (!menu) return;
  if (dd) dd.classList.remove('open');
  const picked = new Set(_channelNamesFrom(Array.isArray(selectedNames) ? selectedNames.join(',') : selectedNames));
  const rows = [];
  function addRow(name, type) {
    if (!name || rows.some(r => r.name === name)) return;
    rows.push({ name, type: type || 'slack' });
  }
  _alertNotifConns.forEach(c => addRow(c.name, _alertChannelTypeFromConn(c)));
  _alertsData.forEach(a => {
    _channelNamesFrom(a.channelName).forEach(n => addRow(n, a.channelType));
  });
  picked.forEach(n => addRow(n, 'slack'));
  if (!rows.length) {
    menu.innerHTML = '<div class="al-ch-dd-empty">No Slack or Google Chat connections yet.</div>';
    _syncAlertChannelLabel();
    return;
  }
  menu.innerHTML = rows.map(r => {
    const checked = picked.has(r.name) ? ' checked' : '';
    return `<label class="al-ch-dd-item"><input type="checkbox" value="${r.name}" data-type="${r.type}"${checked} onchange="_syncAlertChannelLabel()"><span>${r.name}</span></label>`;
  }).join('');
  _syncAlertChannelLabel();
}

function _checkedAlertChannels() {
  return [...document.querySelectorAll('#alertFormChannelMenu input:checked')].map(el => ({
    name: el.value,
    type: el.getAttribute('data-type') || 'slack',
  }));
}

function _syncAlertChannelLabel() {
  const label = document.getElementById('alertFormChannelLabel');
  if (!label) return;
  const names = _checkedAlertChannels().map(c => c.name);
  if (!names.length) label.textContent = 'Select channels…';
  else if (names.length === 1) label.textContent = names[0];
  else label.textContent = `${names[0]} +${names.length - 1}`;
}

function closeAlertChannelDd() {
  const dd = document.getElementById('alertFormChannelDd');
  if (dd) dd.classList.remove('open');
}

function toggleAlertChannelDd(e) {
  e.stopPropagation();
  const dd = document.getElementById('alertFormChannelDd');
  if (dd) dd.classList.toggle('open');
}

function selectAlert(id) {
  _selectedAlertId = id;
  renderAlertsSidebar();
  const a = _alertsData.find(x => x.id === id);
  if (!a) return;

  const created = new Date(a.createdAt);
  const lastFired = a.lastFiredAt ? new Date(a.lastFiredAt) : null;
  const state = a.state || 'unknown';
  const isTrig = state === 'triggered';
  const isFav = _alertFavSet.has(id);

  const aboutOpen  = _alertSectionOpen(id, 'about', true);
  const latestOpen = _alertSectionOpen(id, 'latest', true);
  const notifOpen  = _alertSectionOpen(id, 'notif', true);
  const advOpen    = _alertSectionOpen(id, 'advanced', false);

  const historyRows = `<tr><td colspan="3" class="al-history-empty">Loading…</td></tr>`;

  const notifList = (a.channelName || '').split(',').map(s => s.trim()).filter(Boolean);
  const notifHtml = notifList.length
    ? notifList.map(n => `<div class="al-side-notif">${_channelIconSmall(a.channelType)}<span>${n}</span></div>`).join('')
    : '<div style="color:var(--text3);font-size:12px;font-style:italic;">None</div>';

  const chev = '<svg class="al-side-chev" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>';

  document.getElementById('alertDetail').innerHTML = `
    <div class="al-page">

      <div class="al-crumb">Alerts <span class="al-crumb-sep">&nbsp;›</span></div>

      <div class="al-title-row">
        <div class="al-title-block">
          <div class="al-title">
            ${a.name}
            <button class="al-star ${isFav ? 'active' : ''}" onclick="toggleAlertFav('${a.id}')" title="Favorite">
              <svg viewBox="0 0 24 24" fill="${isFav ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
            </button>
          </div>
        </div>
        <div class="al-actions">
          <select class="al-btn al-status-select" onchange="setAlertStatus('${a.id}', this.value)" title="Alert status">
            <option value="active"${_alertIsActive(a) ? ' selected' : ''}>Active</option>
            <option value="disabled"${_alertIsActive(a) ? '' : ' selected'}>Disabled</option>
          </select>
          ${isTrig ? `<button class="al-btn" onclick="silenceAlert('${a.id}')">Silence</button>` : ''}
          <button class="al-btn" id="alTestBtn" onclick="sendTestAlert('${a.id}')">Send test</button>
          <button class="al-btn" onclick="openAlertModal('${a.id}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            Edit
          </button>
          <button class="al-btn al-btn-danger" onclick="deleteAlert('${a.id}')" title="Delete">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>
          </button>
        </div>
      </div>

      <div class="al-body">

        <div class="al-main">

          <div class="al-card">
            <div class="al-card-title">Rules</div>
            <div class="al-cond">
              ${_policyRules(a).map(r => `
                <span class="al-cond-value">${r.rule}</span>
                <span class="al-cond-op">then</span>
                <span class="al-cond-pill">${r.action}</span>
              `).join('<span class="al-cond-op">·</span>')}
            </div>
          </div>

          <div class="al-card">
            <div class="al-card-title">History</div>
            <div class="al-history-filters">
              <select class="al-filter-select" onchange="void 0">
                <option>Status</option>
                <option>Triggered</option>
                <option>OK</option>
              </select>
              <input class="al-filter-date" type="text" placeholder="Start: dd/mm/yyyy, --:--">
              <input class="al-filter-date" type="text" placeholder="End: dd/mm/yyyy, --:--">
            </div>
            <table class="al-history-table">
              <thead>
                <tr>
                  <th>Evaluated</th>
                  <th>Status</th>
                  <th>Logs</th>
                </tr>
              </thead>
              <tbody id="alHistoryBody-${a.id}">${historyRows}</tbody>
            </table>
            <div class="al-history-pager" id="alHistoryPager-${a.id}"></div>
          </div>

        </div>

        <div class="al-side">

          <div class="al-side-section ${aboutOpen ? 'open' : ''}">
            <div class="al-side-hdr" onclick="toggleAlertSection('${a.id}','about')">
              ${chev}<span>About this alert</span>
            </div>
            <div class="al-side-body">
              <div class="al-side-field">
                <span class="al-side-field-label">Kafka Connect</span>
                <span class="al-side-field-val al-side-user">
                  ${(a.kafkaConnectName || '—')}
                </span>
              </div>
              <div class="al-side-field">
                <span class="al-side-field-label">Connector</span>
                <span class="al-side-field-val al-side-field-mono">${a.connectorName}</span>
              </div>
              <div class="al-side-field">
                <span class="al-side-field-label">Type</span>
                <span class="al-side-field-val">${a.connectorType}</span>
              </div>
              <div class="al-side-field">
                <span class="al-side-field-label">Status</span>
                <span class="al-side-field-val">${_alertIsActive(a) ? 'Active' : 'Disabled'}</span>
              </div>
              <div class="al-side-field">
                <span class="al-side-field-label">Rules</span>
                <span class="al-side-field-val">${_alertRulesLabel(a)}</span>
              </div>
              <div class="al-side-field">
                <span class="al-side-field-label">Check every</span>
                <span class="al-side-field-val">${_alertEveryLabel(a.checkEveryMin)}</span>
              </div>
              <div class="al-side-field">
                <span class="al-side-field-label">Created on</span>
                <span class="al-side-field-val">${_fmtDate(created)}</span>
              </div>
            </div>
          </div>

          <div class="al-side-section ${latestOpen ? 'open' : ''}">
            <div class="al-side-hdr" onclick="toggleAlertSection('${a.id}','latest')">
              ${chev}<span>Latest status</span>
            </div>
            <div class="al-side-body">
              <div class="al-side-status">
                ${isTrig
                  ? `<span class="al-history-status-triggered">Triggered</span> <span style="color:var(--text2);">on ${lastFired ? _fmtDateTime(lastFired) : '—'}</span>`
                  : state === 'ok'
                    ? `<span class="al-history-status-ok">OK</span> <span style="color:var(--text2);">as of ${lastFired ? _fmtDateTime(lastFired) : 'now'}</span>`
                    : `<span style="color:var(--text3);">Not yet evaluated</span>`}
              </div>
            </div>
          </div>

          <div class="al-side-section ${notifOpen ? 'open' : ''}">
            <div class="al-side-hdr" onclick="toggleAlertSection('${a.id}','notif')">
              ${chev}<span>Notifications</span>
            </div>
            <div class="al-side-body">
              ${notifHtml}
              <div class="al-side-field">
                <span class="al-side-field-label">Frequency</span>
                <span class="al-side-field-val">${_alertEveryLabel(a.checkEveryMin)}</span>
              </div>
            </div>
          </div>

          <div class="al-side-section ${advOpen ? 'open' : ''}">
            <div class="al-side-hdr" onclick="toggleAlertSection('${a.id}','advanced')">
              ${chev}<span>Advanced</span>
            </div>
            <div class="al-side-body">
              <div class="al-side-field">
                <span class="al-side-field-label">Alert ID</span>
                <span class="al-side-field-val al-side-field-mono">${a.id.slice(0,8)}…</span>
              </div>
              <div class="al-side-field">
                <span class="al-side-field-label">State</span>
                <span class="al-side-field-val">${state}</span>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>`;

  loadAlertHistory(id);
}

function _opSymbol(op) {
  return { eq:'=', gt:'>', lt:'<', gte:'≥', lte:'≤' }[op] || op;
}

function _timeAgo(d) {
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60)     return diff + 's ago';
  if (diff < 3600)   return Math.floor(diff/60) + 'm ago';
  if (diff < 86400)  return Math.floor(diff/3600) + 'h ago';
  if (diff < 604800) return Math.floor(diff/86400) + 'd ago';
  return d.toLocaleDateString();
}

function _channelMeta(type) {
  const t = (type || '').toLowerCase();
  if (t === 'slack') return {
    label: 'Slack', color: '#4A154B', bg: 'rgba(74,21,75,0.10)',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M6 15a2 2 0 0 1-2-2 2 2 0 0 1 2-2h2v2a2 2 0 0 1-2 2m1-4a2 2 0 0 1-2-2c0-1.11.89-2 2-2h5a2 2 0 0 1 2 2 2 2 0 0 1-2 2H7m11-2a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-2v-2c0-1.11.89-2 2-2m-1 4a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-5c-1.11 0-2-.89-2-2s.89-2 2-2h5m-6-1a2 2 0 0 1-2-2 2 2 0 0 1 2-2 2 2 0 0 1 2 2v2h-2m0-11c1.11 0 2 .89 2 2v5a2 2 0 0 1-2 2 2 2 0 0 1-2-2V4a2 2 0 0 1 2-2M6 4a2 2 0 0 1 2 2v2H6a2 2 0 0 1-2-2 2 2 0 0 1 2-2z"/></svg>',
  };
  if (t === 'pagerduty') return {
    label: 'PagerDuty', color: '#06AC38', bg: 'rgba(6,172,56,0.10)',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6l8-4z"/><polyline points="9 12 11 14 15 10"/></svg>',
  };
  if (t === 'email') return {
    label: 'Email', color: '#0073cf', bg: 'rgba(0,115,207,0.10)',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22,6 12,13 2,6"/></svg>',
  };
  if (t === 'webhook') return {
    label: 'Webhook', color: '#ff6b35', bg: 'rgba(255,107,53,0.10)',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>',
  };
  return {
    label: type || 'Unknown', color: '#6b7280', bg: 'rgba(107,114,128,0.10)',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/></svg>',
  };
}

async function deleteAlert(id) {
  if (!confirm('Delete this alert?')) return;
  await fetch(`/api/alerts/${id}`, { method: 'DELETE' });
  _selectedAlertId = null;
  document.getElementById('alertDetail').innerHTML = _alertDetailEmpty();
  await loadAlerts();
}

async function silenceAlert(id) {
  await fetch(`/api/alerts/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ state: 'ok' }),
  });
  await loadAlerts();
  selectAlert(id);
}

async function sendTestAlert(id) {
  const btn = document.getElementById('alTestBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }
  try {
    const res = await fetch(`/api/alerts/${id}/test`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    const channels = Array.isArray(data.channels) ? data.channels : [];
    if (channels.length > 1) {
      const ok = channels.filter(c => c.success).length;
      showToast(data.success
        ? `✓ Delivered to ${ok}/${channels.length} channels`
        : `✗ ${ok}/${channels.length} delivered — ${data.error || 'Delivery failed'}`);
    } else if (data.success) {
      showToast(`✓ Delivered to ${data.channel?.name || 'channel'} in ${data.latencyMs}ms`);
    } else {
      showToast(`✗ ${data.error || 'Delivery failed'}`);
    }
  } catch (e) {
    showToast(`✗ Network error: ${e.message}`);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Send test'; }
  }
  loadAlertHistory(id, 1);
}

async function loadAlertHistory(id, page) {
  const tbody = document.getElementById(`alHistoryBody-${id}`);
  const pager = document.getElementById(`alHistoryPager-${id}`);
  if (!tbody) return;
  const empty = '<tr><td colspan="3" class="al-history-empty">No deliveries yet</td></tr>';
  const size = _alertHistPageSize[id] || 20;
  const wantPage = page == null ? (_alertHistPage[id] || 1) : Math.max(1, parseInt(page, 10) || 1);
  try {
    const res = await fetch(`/api/alerts/${id}/history?page=${wantPage}&pageSize=${size}`);
    const data = await res.json();
    const rows = Array.isArray(data?.items) ? data.items : [];
    const total = data.total || 0;
    const pages = data.pages || 1;
    const cur = data.page || 1;
    _alertHistPage[id] = cur;
    _alertHistPageSize[id] = data.pageSize || size;
    if (pager) pager.innerHTML = _alertHistoryPagerHtml(id, cur, pages, total, _alertHistPageSize[id], rows.length);
    if (!rows.length) {
      tbody.innerHTML = empty;
      return;
    }
    tbody.innerHTML = rows.map(r => {
      const when = _fmtHistoryTime(new Date(r.createdAt));
      const isTest = r.kind === 'test';
      let label = 'Sent';
      if (isTest && r.success) label = 'Test sent';
      else if (isTest && !r.success) label = 'Test failed';
      else if (!r.success) label = 'Failed';
      const status = r.success
        ? `<span class="al-history-status-ok">${label}</span>`
        : `<span class="al-history-status-triggered">${label}</span>`;
      const logFull = r.logText || r.error || r.message || (r.status ? 'State: ' + r.status : 'No connector error.');
      const preview = logFull.split('\n').find(Boolean) || 'No connector error.';
      return `
        <tr class="al-history-row" onclick="expandAlertHistoryRow(this)">
          <td><span class="al-history-when">${when}</span></td>
          <td>${status}</td>
          <td class="al-history-log">
            <span class="al-history-log-preview">${_escHist(preview)}</span>
            <pre class="al-history-log-pre" style="display:none;">${_escHist(logFull)}</pre>
          </td>
        </tr>`;
    }).join('');
  } catch (_) {
    tbody.innerHTML = '<tr><td colspan="3" class="al-history-empty">Could not load history</td></tr>';
    if (pager) pager.innerHTML = '';
  }
}

function _alertHistoryPagerHtml(id, page, pages, total, pageSize, shown) {
  if (!total) return '';
  const from = (page - 1) * pageSize + 1;
  const to = (page - 1) * pageSize + shown;
  const prevDis = page <= 1 ? ' disabled' : '';
  const nextDis = page >= pages ? ' disabled' : '';
  const sizes = [10, 20, 50].map(n =>
    `<option value="${n}"${n === pageSize ? ' selected' : ''}>${n}</option>`
  ).join('');
  return `
    <span>Latest first · ${from}–${to} of ${total}</span>
    <div class="al-history-pager-right">
      <select class="al-filter-select" onchange="setAlertHistoryPageSize('${id}', this.value)" title="Page size">${sizes}</select>
      <button type="button" class="al-btn"${prevDis} onclick="loadAlertHistory('${id}', ${page - 1})">Prev</button>
      <span>${page} / ${pages}</span>
      <button type="button" class="al-btn"${nextDis} onclick="loadAlertHistory('${id}', ${page + 1})">Next</button>
    </div>`;
}

function setAlertHistoryPageSize(id, size) {
  _alertHistPageSize[id] = parseInt(size, 10) || 20;
  loadAlertHistory(id, 1);
}

function expandAlertHistoryRow(tr) {
  const isExpanded = tr.classList.contains('al-history-row-open');
  document.querySelectorAll('.al-history-row').forEach(row => {
    row.classList.remove('al-history-row-open');
    const pre = row.querySelector('.al-history-log-pre');
    const preview = row.querySelector('.al-history-log-preview');
    if (pre) pre.style.display = 'none';
    if (preview) preview.style.display = '';
  });
  if (isExpanded) return;
  tr.classList.add('al-history-row-open');
  const pre = tr.querySelector('.al-history-log-pre');
  const preview = tr.querySelector('.al-history-log-preview');
  if (pre) pre.style.display = 'block';
  if (preview) preview.style.display = 'none';
}

function _escHist(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function openAlertModal(editId) {
  document.getElementById('alertFormId').value = editId || '';
  document.getElementById('alertModalTitle').textContent = editId ? 'Edit Alert' : 'New Alert';

  const sel = document.getElementById('alertFormConnector');
  sel.innerHTML = '<option value="">Select a connector…</option>';
  try {
    const res = await fetch('/api/notebooks/');
    const notebooks = await res.json();
    const rows = Array.isArray(notebooks) ? notebooks : [];
    if (!rows.length) {
      const empty = document.createElement('option');
      empty.value = '';
      empty.disabled = true;
      empty.textContent = 'No connectors yet';
      sel.appendChild(empty);
    }
    rows.forEach(nb => {
      const name = (nb.name || '').trim();
      if (!name || !nb.id) return;
      const opt = document.createElement('option');
      const folder = nb.folder && nb.folder !== 'default' ? nb.folder : '';
      opt.value = JSON.stringify({ name, type: nb.type || 'source', notebookId: nb.id });
      opt.textContent = folder ? `${name} · ${folder}` : name;
      sel.appendChild(opt);
    });
  } catch(e) {}

  function addConnectorOpt(a) {
    const name = a && a.connectorName;
    if (!name) return;
    const exists = [...sel.options].some(o => {
      try {
        const v = JSON.parse(o.value);
        if (a.notebookId && v.notebookId === a.notebookId) return true;
        return !a.notebookId && v.name === name;
      } catch (e) { return false; }
    });
    if (exists) return;
    const opt = document.createElement('option');
    opt.value = JSON.stringify({
      name,
      type: a.connectorType || 'source',
      notebookId: a.notebookId || null,
    });
    opt.textContent = name;
    sel.appendChild(opt);
  }
  _alertsData.forEach(addConnectorOpt);

  _alertNotifConns = [];
  try {
    const res = await fetch('/api/connections');
    const rows = await res.json();
    _alertNotifConns = (Array.isArray(rows) ? rows : []).filter(_isNotifConn);
  } catch(e) {}

  if (editId) {
    const a = _alertsData.find(x => x.id === editId);
    if (a) {
      renderAlertRuleRows(_policyRules(a));
      document.getElementById('alertFormEvery').value = a.checkEveryMin != null ? String(a.checkEveryMin) : '';
      [...sel.options].forEach(o => {
        try {
          const v = JSON.parse(o.value);
          if (a.notebookId && v.notebookId === a.notebookId) sel.value = o.value;
          else if (!a.notebookId && v.name === a.connectorName) sel.value = o.value;
        } catch(e) {}
      });
      _fillAlertChannelSelect(a.channelName);
    }
  } else {
    renderAlertRuleRows([{ rule: 'FAILED', action: 'pause' }]);
    document.getElementById('alertFormEvery').value = '';
    _fillAlertChannelSelect('');
  }

  document.getElementById('alertModal').style.display = 'block';
}

function closeAlertModal() {
  closeAlertChannelDd();
  document.getElementById('alertModal').style.display = 'none';
}

function alertModalBgClick(e) {
  if (e.target === document.getElementById('alertModal')) closeAlertModal();
}

async function saveAlert() {
  closeAlertChannelDd();
  const editId = document.getElementById('alertFormId').value;
  let connectorName = '', connectorType = 'source', notebookId = null;
  try {
    const v = JSON.parse(document.getElementById('alertFormConnector').value);
    connectorName = v.name; connectorType = v.type; notebookId = v.notebookId || null;
  } catch(e) {}

  const rules = _readAlertFormRules();
  const every = parseInt(document.getElementById('alertFormEvery').value, 10);
  const existing = _alertsData.find(x => x.id === editId);
  const active = _alertIsActive(existing);
  const channels = _checkedAlertChannels();
  const channelName = channels.map(c => c.name).join(', ');
  const channelType = channels[0] ? channels[0].type : 'slack';
  const first = rules[0] || { rule: 'FAILED', action: 'pause' };

  const body = {
    name:            _alertDisplayName(connectorName, rules),
    connectorName, connectorType, notebookId,
    conditionMetric: 'connector_status',
    conditionOp:     'eq',
    conditionValue:  first.rule,
    severity:        'high',
    channelType,
    channelName,
    message:         _systemAlertMessage(connectorName, first.rule, first.action),
    active,
    action:          first.action,
    rules,
    checkEveryMin:   every,
  };

  if (!notebookId || !connectorName || !rules.length || !body.channelName || !Number.isFinite(every) || every < 1) {
    alert('Please fill in all required fields.'); return;
  }
  const seen = new Set();
  for (const r of rules) {
    if (seen.has(r.rule)) { alert('Each status can only be used once.'); return; }
    seen.add(r.rule);
    if (r.rule === 'PAUSED' && r.action === 'pause') {
      alert('PAUSED cannot use pause. Use re-trigger or notify.'); return;
    }
  }

  const res = await fetch(editId ? `/api/alerts/${editId}` : '/api/alerts', {
    method: editId ? 'PATCH' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.error || 'Failed to save alert');
    return;
  }
  const saved = await res.json();
  closeAlertModal();
  await loadAlerts();
  selectAlert(saved.id);
}

function _alertDetailEmpty() {
  return `<div class="conn-detail-empty">
    <div class="conn-detail-empty-icon">
      <svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
    </div>
    <p>Select an alert</p>
    <span>Click any alert in the list to view its details</span>
  </div>`;
}

document.addEventListener('DOMContentLoaded', loadAlerts);
document.getElementById('alertModal').addEventListener('mousedown', function (e) {
  const dd = document.getElementById('alertFormChannelDd');
  if (!dd || !dd.classList.contains('open')) return;
  if (dd.contains(e.target)) return;
  dd.classList.remove('open');
});
