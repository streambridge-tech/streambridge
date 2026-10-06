// ── ACCESS CONTROL ───────────────────────────────────────────────────────────
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));

  let ME = null;
  let USERS = [];
  let ROLES = [];
  let userFilter = '';
  let roleFilter = '';
  let _pickerItems = [];
  let CATALOG = null;
  let currentRole = null;
  let _privGroup = null;

  function canAdmin(me) {
    if (!me) return false;
    if (me.isAdmin) return true;
    const p = me.permissions || [];
    return p.includes('admin.manage_users') || p.includes('admin.manage_roles');
  }

  const AV_COLORS = ['#ef6c3b', '#2f9e6b', '#3b7ddd', '#9333ea', '#d9772b', '#0ea5a4', '#d6456f', '#5b6ee8'];
  function colorFor(name) {
    let h = 0; for (const c of (name || '')) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    return AV_COLORS[h % AV_COLORS.length];
  }
  function initials(name) {
    const base = (name || '').split('@')[0];
    const parts = base.split(/[._-]+/).filter(Boolean);
    const a = (parts[0] || base || '?')[0] || '?';
    const b = (parts[1] || '')[0] || '';
    return (a + b).toUpperCase();
  }

  async function api(method, url, body) {
    const opt = { method, headers: {} };
    if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body); }
    const res = await fetch(url, opt);
    let data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    if (!res.ok) throw new Error((data && data.error) || `${res.status}`);
    return data;
  }

  // ── init ──
  async function init() {
    try { ME = await api('GET', '/api/auth/me'); } catch (e) { ME = null; }

    // Personal mode (auth disabled): no accounts to manage.
    if (ME && ME.authEnabled === false) { ME = { isAdmin: true, permissions: [] }; }

    if (!canAdmin(ME)) { $('adminNoAccess').style.display = 'flex'; return; }
    $('adminApp').style.display = 'flex';

    wireNav();
    try { ROLES = await api('GET', '/api/admin/roles'); } catch (e) { ROLES = []; }
    renderRoles();
    await loadUsers();
  }

  function wireNav() {
    window.addEventListener('hashchange', applyHashSection);
    applyHashSection();
    $('newUserBtn').addEventListener('click', openNewUser);
    $('userSearch').addEventListener('input', (e) => { userFilter = e.target.value.toLowerCase(); renderUsers(); });
    $('newRoleBtn').addEventListener('click', openNewRole);
    $('roleSearch').addEventListener('input', (e) => { roleFilter = e.target.value.toLowerCase(); renderRoles(); });
    $('roleBack').addEventListener('click', () => {
      $('roleDetail').style.display = 'none';
      $('roleListView').style.display = 'flex';
      reloadRoles();
    });
    document.querySelectorAll('.ac-tab2').forEach((b) => b.addEventListener('click', () => selectRoleTab(b.dataset.rtab)));
    document.addEventListener('click', () => document.querySelectorAll('.ac-kebab-menu.open').forEach((m) => m.classList.remove('open')));
  }

  function applyHashSection() {
    const sec = (window.location.hash || '#users').slice(1) || 'users';
    selectSection(sec === 'roles' ? 'roles' : 'users');
  }

  function selectSection(sec) {
    $('acUsers').style.display = sec === 'users' ? 'flex' : 'none';
    $('acRoles').style.display = sec === 'roles' ? 'flex' : 'none';
  }

  // ── users ──
  async function loadUsers() {
    try { USERS = await api('GET', '/api/admin/users'); } catch (e) { USERS = []; }
    renderUsers();
  }

  function roleChips(u) {
    const chips = [];
    if (u.isAdmin) chips.push('<span class="ac-chip ac-chip-super">Superuser</span>');
    const names = u.roleNames || [];
    const MAX = 3;
    names.slice(0, MAX).forEach((n) => chips.push(`<span class="ac-chip">${esc(n)}</span>`));
    if (names.length > MAX) {
      const rest = names.slice(MAX).join(', ');
      chips.push(`<span class="ac-chip ac-chip-more" title="${esc(rest)}">+${names.length - MAX}</span>`);
    }
    if (!chips.length) chips.push('<span class="ac-chip ac-chip-none">No role</span>');
    return `<div class="ac-role-chips">${chips.join('')}</div>`;
  }

  function renderUsers() {
    const rows = USERS.filter((u) => !userFilter || u.username.toLowerCase().includes(userFilter));
    const tbody = $('userRows');
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text2);padding:28px;">${USERS.length ? 'No users match your search' : 'No users yet'}</td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map((u) => `
      <tr>
        <td>
          <div class="ac-user-cell">
            <span class="ac-avatar" style="background:${colorFor(u.username)}">${esc(initials(u.username))}</span>
            <span class="ac-uname">${esc(u.username)}</span>
          </div>
        </td>
        <td>${roleChips(u)}</td>
        <td><span class="ac-pill ${u.active ? 'ac-pill-on' : 'ac-pill-off'}">${u.active ? 'Active' : 'Disabled'}</span></td>
        <td class="ac-col-actions">
          <span class="ac-row-actions">
            <button class="ac-btn ac-btn-sm" data-act="roles" data-id="${u.id}">Roles</button>
            <button class="ac-btn ac-btn-sm" data-act="pw" data-id="${u.id}">Reset password</button>
            <button class="ac-btn ac-btn-sm" data-act="toggle" data-id="${u.id}">${u.active ? 'Disable' : 'Enable'}</button>
            <button class="ac-btn ac-btn-sm ac-btn-danger" data-act="del" data-id="${u.id}">Delete</button>
          </span>
        </td>
      </tr>`).join('');

    tbody.querySelectorAll('button[data-act]').forEach((btn) => {
      const u = USERS.find((x) => x.id === Number(btn.dataset.id));
      btn.addEventListener('click', () => {
        if (btn.dataset.act === 'roles') openEditRoles(u);
        else if (btn.dataset.act === 'pw') openResetPassword(u);
        else if (btn.dataset.act === 'toggle') toggleActive(u);
        else if (btn.dataset.act === 'del') deleteUser(u);
      });
    });
  }

  // ── modal helpers ──
  function closeModal() { $('adminModalRoot').innerHTML = ''; }

  function modal(title, inner) {
    $('adminModalRoot').innerHTML = `
      <div class="ac-modal-overlay" id="acOverlay">
        <div class="ac-modal">
          <div class="ac-modal-title">${esc(title)}</div>
          ${inner}
          <div class="ac-modal-msg" id="acMsg"></div>
          <div class="ac-modal-actions">
            <button class="ac-btn" id="acCancel">Cancel</button>
            <button class="ac-btn ac-btn-primary" id="acSave">Save</button>
          </div>
        </div>
      </div>`;
    $('acCancel').addEventListener('click', closeModal);
    $('acOverlay').addEventListener('click', (e) => { if (e.target.id === 'acOverlay') closeModal(); });
  }

  function rolePicker(items, selectedIds) {
    _pickerItems = items || [];
    const sel = new Set(selectedIds || []);
    if (!_pickerItems.length) return '<div class="ac-rp-empty">No roles available.</div>';
    return `
      <div class="ac-rp" id="acRolePicker">
        <button type="button" class="ac-rp-trigger" id="acRpTrigger">
          <span id="acRpSummary">${selectedSummary(sel)}</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <div class="ac-rp-panel" id="acRpPanel" style="display:none;">
          <input type="text" class="ac-rp-search" id="acRpSearch" placeholder="Search roles…">
          <div class="ac-rp-list" id="acRpList">
            ${_pickerItems.map((r) => `
              <label class="ac-role-opt" data-name="${esc(r.name.toLowerCase())}">
                <input type="checkbox" value="${r.id}" ${sel.has(r.id) ? 'checked' : ''}>
                <span>${esc(r.name)}</span>
              </label>`).join('')}
          </div>
        </div>
      </div>`;
  }

  function selectedSummary(sel) {
    const chosen = _pickerItems.filter((r) => sel.has(r.id)).map((r) => r.name);
    if (!chosen.length) return '<span class="ac-rp-ph">Select roles…</span>';
    if (chosen.length <= 2) return esc(chosen.join(', '));
    return `${esc(chosen.slice(0, 2).join(', '))} <span class="ac-chip ac-chip-more">+${chosen.length - 2}</span>`;
  }

  function wireRolePicker() {
    const picker = $('acRolePicker');
    if (!picker) return;
    const trigger = $('acRpTrigger');
    const panel = $('acRpPanel');
    const search = $('acRpSearch');

    trigger.addEventListener('click', () => {
      const open = panel.style.display !== 'none';
      panel.style.display = open ? 'none' : 'block';
      if (!open) { search.value = ''; filterOpts(''); search.focus(); }
    });
    search.addEventListener('input', (e) => filterOpts(e.target.value.toLowerCase()));
    picker.querySelectorAll('.ac-role-opt input').forEach((cb) => {
      cb.addEventListener('change', () => { $('acRpSummary').innerHTML = selectedSummary(new Set(pickedRoleIds())); });
    });
    document.addEventListener('click', (e) => { if (!picker.contains(e.target)) panel.style.display = 'none'; });

    function filterOpts(q) {
      picker.querySelectorAll('.ac-role-opt').forEach((o) => {
        o.style.display = o.dataset.name.includes(q) ? '' : 'none';
      });
    }
  }

  function pickedRoleIds() {
    return [...document.querySelectorAll('.ac-rp-list input:checked')].map((i) => Number(i.value));
  }

  // ── new user ──
  function openNewUser() {
    modal('New user', `
      <div class="ac-field"><label class="ac-label">Username</label><input class="ac-input" id="acUsername" placeholder="name@company.com" autocomplete="off"></div>
      <div class="ac-field"><label class="ac-label">Password</label><input class="ac-input" id="acPassword" type="password" placeholder="At least 10 characters" autocomplete="new-password"></div>
      <div class="ac-field"><label class="ac-label">Assign roles</label>${rolePicker(ROLES, [])}</div>
    `);
    wireRolePicker();
    $('acSave').addEventListener('click', async () => {
      const username = $('acUsername').value.trim();
      const password = $('acPassword').value;
      try {
        await api('POST', '/api/admin/users', { username, password, roleIds: pickedRoleIds() });
        closeModal();
        await loadUsers();
      } catch (e) { $('acMsg').textContent = e.message; }
    });
  }

  // ── edit roles ──
  function openEditRoles(u) {
    modal(`Roles — ${u.username}`, `<div class="ac-field"><label class="ac-label">Assign roles</label>${rolePicker(ROLES, u.roleIds)}</div>`);
    wireRolePicker();
    $('acSave').addEventListener('click', async () => {
      try {
        await api('PATCH', `/api/admin/users/${u.id}`, { roleIds: pickedRoleIds() });
        closeModal();
        await loadUsers();
      } catch (e) { $('acMsg').textContent = e.message; }
    });
  }

  // ── reset password ──
  function openResetPassword(u) {
    modal(`Reset password — ${u.username}`, `
      <div class="ac-field"><label class="ac-label">New password</label><input class="ac-input" id="acPassword" type="password" placeholder="At least 10 characters" autocomplete="new-password"></div>
    `);
    $('acSave').addEventListener('click', async () => {
      try {
        await api('POST', `/api/admin/users/${u.id}/reset-password`, { password: $('acPassword').value });
        closeModal();
      } catch (e) { $('acMsg').textContent = e.message; }
    });
  }

  async function toggleActive(u) {
    try { await api('PATCH', `/api/admin/users/${u.id}`, { active: !u.active }); await loadUsers(); }
    catch (e) { alert(e.message); }
  }

  async function deleteUser(u) {
    if (!confirm(`Delete user "${u.username}"? This cannot be undone.`)) return;
    try { await api('DELETE', `/api/admin/users/${u.id}`); await loadUsers(); }
    catch (e) { alert(e.message); }
  }

  // ── roles ──
  const LOCK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>';
  const DOTS_SVG = '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>';

  function roleNameMap() { const m = {}; ROLES.forEach((r) => { m[r.id] = r.name; }); return m; }
  function childrenOf(id) { return ROLES.filter((r) => (r.parents || []).includes(id)).map((r) => r.name); }
  function fmtDate(iso) { if (!iso) return '—'; const d = new Date(iso); return isNaN(d) ? '—' : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }); }
  function relChips(names) {
    if (!names || !names.length) return '<span class="ac-muted">—</span>';
    return `<div class="ac-rel-chips">${names.map((n) => `<span class="ac-rel-chip">${esc(n)}</span>`).join('')}</div>`;
  }

  async function reloadRoles() {
    try { ROLES = await api('GET', '/api/admin/roles'); } catch (e) { ROLES = []; }
    renderRoles();
  }

  function renderRoles() {
    const map = roleNameMap();
    const rows = ROLES.filter((r) => !roleFilter
      || r.name.toLowerCase().includes(roleFilter)
      || (r.description || '').toLowerCase().includes(roleFilter));
    $('roleCount').textContent = `${ROLES.length} role${ROLES.length === 1 ? '' : 's'}`;

    const tbody = $('roleRows');
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text2);padding:28px;">${ROLES.length ? 'No roles match your search' : 'No roles yet'}</td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map((r) => {
      const parents = (r.parents || []).map((id) => map[id]).filter(Boolean);
      const children = childrenOf(r.id);
      const name = `<span class="ac-role-link" data-open="${r.id}">${esc(r.name)}</span>`;
      const actions = r.isBuiltin
        ? `<span class="ac-lock" title="Built-in role">${LOCK_SVG}</span>`
        : `<div class="ac-kebab">
             <button class="ac-kebab-btn" data-kebab="${r.id}">${DOTS_SVG}</button>
             <div class="ac-kebab-menu" id="kebab-${r.id}">
               <button class="ac-kebab-item" data-edit="${r.id}">Edit</button>
               <button class="ac-kebab-item danger" data-del="${r.id}">Delete</button>
             </div>
           </div>`;
      return `<tr>
        <td>${name}</td>
        <td>${r.description ? esc(r.description) : '<span class="ac-muted">—</span>'}</td>
        <td>${relChips(parents)}</td>
        <td>${relChips(children)}</td>
        <td><span class="ac-count-pill">${r.userCount || 0}</span></td>
        <td class="ac-muted">${fmtDate(r.createdAt)}</td>
        <td class="ac-col-actions">${actions}</td>
      </tr>`;
    }).join('');

    tbody.querySelectorAll('[data-edit]').forEach((el) => el.addEventListener('click', (e) => {
      e.stopPropagation(); openEditRole(ROLES.find((x) => x.id === Number(el.dataset.edit)));
    }));
    tbody.querySelectorAll('[data-open]').forEach((el) => el.addEventListener('click', (e) => {
      e.stopPropagation(); openRoleDetail(Number(el.dataset.open));
    }));
    tbody.querySelectorAll('[data-del]').forEach((el) => el.addEventListener('click', (e) => {
      e.stopPropagation(); deleteRole(ROLES.find((x) => x.id === Number(el.dataset.del)));
    }));
    tbody.querySelectorAll('[data-kebab]').forEach((el) => el.addEventListener('click', (e) => {
      e.stopPropagation();
      const menu = $(`kebab-${el.dataset.kebab}`);
      const wasOpen = menu.classList.contains('open');
      document.querySelectorAll('.ac-kebab-menu.open').forEach((m) => m.classList.remove('open'));
      if (!wasOpen) menu.classList.add('open');
    }));
  }

  function openNewRole() {
    modal('Add role', `
      <div class="ac-field"><label class="ac-label">Role name</label><input class="ac-input" id="acRoleName" placeholder="e.g. connector_builder" autocomplete="off"></div>
      <div class="ac-field"><label class="ac-label">Description</label><input class="ac-input" id="acRoleDesc" placeholder="Optional"></div>
      <div class="ac-field"><label class="ac-label">Inherits from</label>${rolePicker(ROLES, [])}</div>
    `);
    wireRolePicker();
    $('acSave').addEventListener('click', async () => {
      try {
        await api('POST', '/api/admin/roles', {
          name: $('acRoleName').value.trim(),
          description: $('acRoleDesc').value.trim(),
          parents: pickedRoleIds(),
        });
        closeModal();
        await reloadRoles();
      } catch (e) { $('acMsg').textContent = e.message; }
    });
  }

  function openEditRole(r) {
    if (!r || r.isBuiltin) return;
    modal(`Edit role — ${r.name}`, `
      <div class="ac-field"><label class="ac-label">Role name</label><input class="ac-input" id="acRoleName" value="${esc(r.name)}"></div>
      <div class="ac-field"><label class="ac-label">Description</label><input class="ac-input" id="acRoleDesc" value="${esc(r.description || '')}"></div>
      <div class="ac-field"><label class="ac-label">Inherits from</label>${rolePicker(ROLES.filter((x) => x.id !== r.id), r.parents || [])}</div>
    `);
    wireRolePicker();
    $('acSave').addEventListener('click', async () => {
      try {
        await api('PATCH', `/api/admin/roles/${r.id}`, {
          name: $('acRoleName').value.trim(),
          description: $('acRoleDesc').value.trim(),
          parents: pickedRoleIds(),
        });
        closeModal();
        await reloadRoles();
      } catch (e) { $('acMsg').textContent = e.message; }
    });
  }

  async function deleteRole(r) {
    if (!r || r.isBuiltin) return;
    if (!confirm(`Delete role "${r.name}"? This cannot be undone.`)) return;
    try { await api('DELETE', `/api/admin/roles/${r.id}`); await reloadRoles(); await loadUsers(); }
    catch (e) { alert(e.message); }
  }

  // ── role detail (Users / Roles / Privileges) ──
  async function openRoleDetail(roleId) {
    try { currentRole = await api('GET', `/api/admin/roles/${roleId}`); }
    catch (e) { alert(e.message); return; }
    if (!CATALOG) { try { CATALOG = await api('GET', '/api/admin/permissions'); } catch (e) { CATALOG = { groups: [] }; } }
    _privGroup = null;
    $('roleListView').style.display = 'none';
    $('roleDetail').style.display = 'flex';
    $('roleDetailName').textContent = currentRole.name + (currentRole.isBuiltin ? '  (built-in)' : '');
    $('roleDetailDesc').textContent = currentRole.description || '';
    selectRoleTab('users');
  }

  function selectRoleTab(tab) {
    document.querySelectorAll('.ac-tab2').forEach((b) => b.classList.toggle('active', b.dataset.rtab === tab));
    ['users', 'roles', 'privileges'].forEach((t) => { $(`rtab-${t}`).style.display = t === tab ? 'flex' : 'none'; });
    if (tab === 'users') renderRoleUsers();
    else if (tab === 'roles') renderRoleParents();
    else renderRolePrivileges();
  }

  // Users tab
  function renderRoleUsers() {
    const rid = currentRole.id;
    const builtin = currentRole.isBuiltin;
    const assigned = USERS.filter((u) => (u.roleIds || []).includes(rid));
    const panel = $('rtab-users');
    panel.innerHTML = `
      <div class="ac-detail-bar">
        ${builtin ? '' : '<button class="ac-btn ac-btn-primary" id="assignUserBtn">Assign user</button>'}
        <span class="ac-count" style="margin-left:auto;">${assigned.length} user${assigned.length === 1 ? '' : 's'}</span>
      </div>
      <div class="ac-table-wrap"><table class="ac-table">
        <thead><tr><th>Username</th>${builtin ? '' : '<th class="ac-col-actions"></th>'}</tr></thead>
        <tbody>${assigned.length ? assigned.map((u) => `
          <tr>
            <td><div class="ac-user-cell"><span class="ac-avatar" style="background:${colorFor(u.username)}">${esc(initials(u.username))}</span><span class="ac-uname">${esc(u.username)}</span></div></td>
            ${builtin ? '' : `<td class="ac-col-actions"><button class="ac-btn ac-btn-sm ac-btn-danger" data-unassign="${u.id}">Unassign</button></td>`}
          </tr>`).join('') : `<tr><td colspan="2" style="text-align:center;color:var(--text2);padding:24px;">No users assigned</td></tr>`}
        </tbody></table></div>`;
    if (!builtin) {
      const ab = $('assignUserBtn'); if (ab) ab.addEventListener('click', openAssignUser);
      panel.querySelectorAll('[data-unassign]').forEach((b) => b.addEventListener('click', () => unassignUser(Number(b.dataset.unassign))));
    }
  }

  async function unassignUser(userId) {
    const u = USERS.find((x) => x.id === userId); if (!u) return;
    const next = (u.roleIds || []).filter((id) => id !== currentRole.id);
    try { await api('PATCH', `/api/admin/users/${userId}`, { roleIds: next }); await loadUsers(); renderRoleUsers(); }
    catch (e) { alert(e.message); }
  }

  function openAssignUser() {
    const rid = currentRole.id;
    const items = USERS.filter((u) => !(u.roleIds || []).includes(rid)).map((u) => ({ id: u.id, name: u.username }));
    modal('Assign users', `<div class="ac-field"><label class="ac-label">Select users</label>${rolePicker(items, [])}</div>`);
    wireRolePicker();
    $('acSave').addEventListener('click', async () => {
      try {
        for (const uid of pickedRoleIds()) {
          const u = USERS.find((x) => x.id === uid);
          await api('PATCH', `/api/admin/users/${uid}`, { roleIds: [...(u.roleIds || []), rid] });
        }
        closeModal(); await loadUsers(); renderRoleUsers();
      } catch (e) { $('acMsg').textContent = e.message; }
    });
  }

  // Roles tab (inherits from)
  function renderRoleParents() {
    const map = roleNameMap();
    const builtin = currentRole.isBuiltin;
    const parents = (currentRole.parents || []).map((id) => ({ id, name: map[id] })).filter((p) => p.name);
    const panel = $('rtab-roles');
    panel.innerHTML = `
      <div class="ac-detail-bar">
        ${builtin ? '' : '<button class="ac-btn ac-btn-primary" id="assignRoleBtn">Assign role</button>'}
        <span class="ac-count" style="margin-left:auto;">${parents.length} role${parents.length === 1 ? '' : 's'}</span>
      </div>
      ${parents.length ? `<div class="ac-table-wrap"><table class="ac-table">
        <thead><tr><th>Inherited role</th>${builtin ? '' : '<th class="ac-col-actions"></th>'}</tr></thead>
        <tbody>${parents.map((p) => `
          <tr><td>${esc(p.name)}</td>${builtin ? '' : `<td class="ac-col-actions"><button class="ac-btn ac-btn-sm ac-btn-danger" data-unassignrole="${p.id}">Unassign</button></td>`}</tr>`).join('')}
        </tbody></table></div>`
        : `<div class="ac-placeholder">No roles assigned to this role.${builtin ? '' : ' Use “Assign role” to inherit another role’s privileges.'}</div>`}`;
    if (!builtin) {
      const ab = $('assignRoleBtn'); if (ab) ab.addEventListener('click', openAssignParent);
      panel.querySelectorAll('[data-unassignrole]').forEach((b) => b.addEventListener('click', () => unassignParent(Number(b.dataset.unassignrole))));
    }
  }

  async function refreshCurrentRole() {
    currentRole = await api('GET', `/api/admin/roles/${currentRole.id}`);
    await reloadRoles();
  }

  async function unassignParent(pid) {
    const next = (currentRole.parents || []).filter((id) => id !== pid);
    try { await api('PATCH', `/api/admin/roles/${currentRole.id}`, { parents: next }); await refreshCurrentRole(); renderRoleParents(); }
    catch (e) { alert(e.message); }
  }

  function openAssignParent() {
    const existing = new Set(currentRole.parents || []);
    const items = ROLES.filter((r) => r.id !== currentRole.id && !existing.has(r.id)).map((r) => ({ id: r.id, name: r.name }));
    modal('Assign role', `<div class="ac-field"><label class="ac-label">Inherit from</label>${rolePicker(items, [])}</div>`);
    wireRolePicker();
    $('acSave').addEventListener('click', async () => {
      try {
        await api('PATCH', `/api/admin/roles/${currentRole.id}`, { parents: [...(currentRole.parents || []), ...pickedRoleIds()] });
        await refreshCurrentRole(); closeModal(); renderRoleParents();
      } catch (e) { $('acMsg').textContent = e.message; }
    });
  }

  // Privileges tab
  async function renderRolePrivileges() {
    const groups = (CATALOG && CATALOG.groups) || [];
    if (!_privGroup && groups.length) _privGroup = groups[0].group;
    let inherited = new Set();
    try {
      const prev = await api('POST', '/api/admin/roles/effective-preview', { parents: currentRole.parents || [], permissions: [] });
      (prev.effective || []).forEach((e) => { if (e.inherited) inherited.add(e.key); });
    } catch (e) { /* ignore */ }
    const own = new Set((currentRole.permissions || []).map((p) => p.key));
    const panel = $('rtab-privileges');
    panel.innerHTML = `
      <div class="ac-priv-layout">
        <div class="ac-priv-groups">${groups.map((g) => `<button class="ac-priv-group-btn ${g.group === _privGroup ? 'active' : ''}" data-group="${esc(g.group)}">${esc(g.group)}</button>`).join('')}</div>
        <div class="ac-priv-perms" id="privPerms"></div>
      </div>`;
    panel.querySelectorAll('[data-group]').forEach((b) => b.addEventListener('click', () => { _privGroup = b.dataset.group; renderRolePrivileges(); }));
    renderPrivPerms(groups.find((g) => g.group === _privGroup), own, inherited);
  }

  function renderPrivPerms(group, own, inherited) {
    const box = $('privPerms');
    if (!group) { box.innerHTML = ''; return; }
    const builtin = currentRole.isBuiltin;
    const navKey = (group.permissions.find((p) => p.key.indexOf('nav.') === 0) || {}).key;
    const opImplied = group.permissions.some((p) => p.key !== navKey && (own.has(p.key) || inherited.has(p.key)));
    box.innerHTML = group.permissions.map((p) => {
      const isNav = p.key === navKey;
      const isInh = inherited.has(p.key) && !own.has(p.key);
      const implied = isNav && opImplied && !own.has(p.key) && !isInh;
      const checked = own.has(p.key) || isInh || implied;
      const disabled = builtin || isInh || implied;
      const tag = isInh ? '<span class="ac-tag ac-tag-inherited">Inherited</span>'
        : implied ? '<span class="ac-tag ac-tag-implied">Implied</span>'
        : (p.sensitive ? '<span class="ac-tag ac-tag-sensitive">Sensitive</span>' : '');
      return `<label class="ac-priv-perm ${isInh || implied ? 'inherited' : ''}">
        <input type="checkbox" data-perm="${esc(p.key)}" ${checked ? 'checked' : ''} ${disabled ? 'disabled' : ''}>
        <span class="ac-priv-label">${esc(p.label)}</span>
        ${tag}
      </label>`;
    }).join('');
    if (!builtin) {
      box.querySelectorAll('input[data-perm]:not(:disabled)').forEach((cb) => cb.addEventListener('change', () => togglePerm(cb.dataset.perm, cb.checked)));
    }
  }

  async function togglePerm(key, on) {
    const own = new Set((currentRole.permissions || []).map((p) => p.key));
    if (on) own.add(key); else own.delete(key);
    const perms = [...own].map((k) => ({ key: k, scopeType: 'global', scopeId: '*' }));
    try {
      await api('PATCH', `/api/admin/roles/${currentRole.id}`, { permissions: perms });
      currentRole = await api('GET', `/api/admin/roles/${currentRole.id}`);
      renderRolePrivileges();
    } catch (e) { alert(e.message); renderRolePrivileges(); }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
