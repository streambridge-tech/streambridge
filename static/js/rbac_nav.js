// Global nav gate: shows/hides rail items by the signed-in user's permissions
// and wires the Account control to logout. No-op in personal mode.
(() => {
  // Global 403 interceptor: surface a clear, highlighted reason for any denied
  // action, regardless of which call site made the request.
  const _origFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const res = await _origFetch(...args);
    if (res.status === 403) {
      res.clone().json().then((body) => {
        // Flagged mid-session: the login page shows the change-password form.
        if (body && body.code === 'must_change_password') window.location.href = '/login';
        if (body && body.error === 'forbidden') {
          showForbiddenBanner(body.message || 'You do not have permission to perform this action.');
        }
      }).catch(() => {});
    }
    return res;
  };

  let _forbTimer = null;
  function showForbiddenBanner(message) {
    let el = document.getElementById('rbacForbidden');
    if (!el) {
      el = document.createElement('div');
      el.id = 'rbacForbidden';
      el.className = 'rbac-forbidden';
      el.innerHTML = '<span class="rbac-forbidden-icon">\u26D4</span>'
        + '<span class="rbac-forbidden-msg"></span>'
        + '<button class="rbac-forbidden-close" aria-label="Dismiss">\u00D7</button>';
      document.body.appendChild(el);
      el.querySelector('.rbac-forbidden-close').addEventListener('click', () => el.classList.remove('show'));
    }
    el.querySelector('.rbac-forbidden-msg').textContent = message;
    el.classList.add('show');
    if (_forbTimer) clearTimeout(_forbTimer);
    _forbTimer = setTimeout(() => el.classList.remove('show'), 7000);
  }

  // rail item id → permission that makes it visible (null = always).
  const RAIL_PERMISSION = {
    'rail-connectors': 'nav.connectors',
    'rail-connections': 'nav.connections',
    'rail-kafka-topics': 'nav.topics',
    'rail-schema-registry': 'nav.registry',
    'rail-plugins': null,
    'rail-alerts': 'nav.alerts',
    'rail-docs': null,
    'rail-admin': '__admin__',
    // 'rail-phase2' intentionally omitted: Phase 2 nav hidden for now (stays display:none).
  };

  const show = (id, on) => { const el = document.getElementById(id); if (el) el.style.display = on ? '' : 'none'; };

  async function run() {
    let status;
    try { status = await (await fetch('/api/auth/status')).json(); } catch { return; }
    if (!status || !status.authEnabled) {
      // Personal mode: no accounts to manage. Phase 2 nav is hidden for now.
      show('rail-admin', false);
      show('rail-phase2', false);
      return;
    }

    let me;
    try { me = await (await fetch('/api/auth/me')).json(); } catch { return; }
    if (!me || !me.authenticated) return;

    const perms = new Set(me.permissions || []);
    const isAdmin = !!me.isAdmin;
    const can = (p) => {
      if (p === null) return true;
      if (p === '__admin__') return isAdmin || perms.has('admin.manage_users') || perms.has('admin.manage_roles');
      return isAdmin || perms.has(p);
    };

    for (const [id, perm] of Object.entries(RAIL_PERMISSION)) {
      show(id, can(perm));
    }

    wireTopAccount(me);
    wireAdminGroup();
    wirePhase2Group();
  }

  function wirePhase2Group() {
    const group = document.getElementById('rail-phase2');
    const hdr = document.getElementById('rail-phase2-hdr');
    if (!group || !hdr) return;
    hdr.addEventListener('click', () => group.classList.toggle('collapsed'));
    const path = window.location.pathname.replace(/\/$/, '');
    if (path === '/pipelines' || path === '/rca') {
      group.classList.remove('collapsed');
      group.querySelectorAll('.rail-subitem').forEach((a) => {
        const href = (a.getAttribute('href') || '').replace(/\/$/, '');
        a.classList.toggle('active', href === path);
      });
    }
  }

  function wireAdminGroup() {
    const group = document.getElementById('rail-admin');
    const hdr = document.getElementById('rail-admin-hdr');
    if (!group || !hdr) return;

    hdr.addEventListener('click', () => group.classList.toggle('collapsed'));

    const onAdminPage = window.location.pathname.replace(/\/$/, '') === '/admin';
    const markActive = () => {
      const sec = (window.location.hash || '#users').slice(1) || 'users';
      group.querySelectorAll('.rail-subitem').forEach((a) => {
        a.classList.toggle('active', a.dataset.sec === sec);
      });
    };
    if (onAdminPage) {
      group.classList.remove('collapsed');
      markActive();
      window.addEventListener('hashchange', markActive);
    }
  }

  function wireTopAccount(me) {
    const btn = document.getElementById('topAccount');
    if (!btn) return;
    const roles = me.roles || [];
    const active = me.activeRoleId != null ? me.activeRoleId : null;
    const activeName = active == null ? 'All roles' : ((roles.find((r) => r.id === active) || {}).name || 'All roles');
    const uname = (me.user && me.user.username) || 'Account';
    const av = document.getElementById('topAcctAvatar');
    const roleLabel = document.getElementById('topAcctRole');
    if (av) av.textContent = ((uname.split('@')[0] || '?')[0] || '?').toUpperCase();
    if (roleLabel) roleLabel.textContent = activeName;
    btn.style.display = 'flex';
    btn.addEventListener('click', (e) => { e.stopPropagation(); toggleTopMenu(btn, me); });
  }

  function toggleTopMenu(btn, me) {
    const existing = document.getElementById('topMenu');
    if (existing) { existing.remove(); return; }
    const roles = me.roles || [];
    const active = me.activeRoleId != null ? me.activeRoleId : null;
    const def = me.defaultRoleId != null ? me.defaultRoleId : null;
    const uname = (me.user && me.user.username) || 'Account';
    const activeName = active == null ? 'All roles' : ((roles.find((r) => r.id === active) || {}).name || 'All roles');

    const opt = (id, name) => {
      const idAttr = id === null ? '' : id;
      const sel = id === active ? ' selected' : '';
      const star = id === def ? ' \u2605' : '';
      return `<option value="${idAttr}"${sel}>${esc(name)}${star}</option>`;
    };

    const menu = document.createElement('div');
    menu.id = 'topMenu';
    menu.className = 'topmenu';
    menu.innerHTML = `
      <div class="topmenu-user">${esc(uname)}</div>
      <div class="topmenu-active">Acting as: ${esc(activeName)}</div>
      <div class="topmenu-label">Active role</div>
      <div class="topmenu-rolepick">
        <select class="topmenu-select" id="tmRoleSelect">
          ${opt(null, 'All roles')}
          ${roles.map((r) => opt(r.id, r.name)).join('')}
        </select>
        <button class="topmenu-star" id="tmDefaultStar" title="Set selected role as default at login"></button>
      </div>
      <div class="topmenu-divider"></div>
      <button class="topmenu-item" id="tmChangePw">Change password</button>
      <button class="topmenu-item topmenu-logout" id="tmLogout">Log out</button>`;
    document.body.appendChild(menu);
    const rect = btn.getBoundingClientRect();
    menu.style.top = (rect.bottom + 6) + 'px';
    menu.style.right = Math.max(8, window.innerWidth - rect.right) + 'px';

    const select = document.getElementById('tmRoleSelect');
    const star = document.getElementById('tmDefaultStar');
    const selectedId = () => (select.value === '' ? null : Number(select.value));
    const syncStar = () => {
      const isDef = selectedId() === def;
      star.textContent = isDef ? '\u2605' : '\u2606';
      star.classList.toggle('on', isDef);
    };
    syncStar();
    select.addEventListener('change', async () => {
      await fetch('/api/auth/active-role', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ roleId: selectedId() }) });
      window.location.reload();
    });
    star.addEventListener('click', async (e) => {
      e.stopPropagation();
      await fetch('/api/auth/default-role', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ roleId: selectedId() }) });
      window.location.reload();
    });
    document.getElementById('tmLogout').addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST' });
      window.location.href = '/login';
    });
    document.getElementById('tmChangePw').addEventListener('click', () => { menu.remove(); openChangePassword(); });

    setTimeout(() => {
      document.addEventListener('click', function onDoc(ev) {
        if (!menu.contains(ev.target) && !btn.contains(ev.target)) { menu.remove(); document.removeEventListener('click', onDoc); }
      });
    }, 0);
  }

  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));

  function openChangePassword() {
    const ov = document.createElement('div');
    ov.className = 'acct-modal-overlay';
    ov.innerHTML = `
      <div class="acct-modal">
        <div class="acct-modal-title">Change password</div>
        <label class="acct-label">Current password</label>
        <input class="acct-input" id="cpCurrent" type="password" autocomplete="current-password">
        <label class="acct-label">New password</label>
        <input class="acct-input" id="cpNew" type="password" autocomplete="new-password" placeholder="At least 10 characters">
        <label class="acct-label">Confirm new password</label>
        <input class="acct-input" id="cpConfirm" type="password" autocomplete="new-password">
        <div class="acct-msg" id="cpMsg"></div>
        <div class="acct-modal-actions">
          <button class="acct-btn" id="cpCancel">Cancel</button>
          <button class="acct-btn acct-btn-primary" id="cpSave">Update password</button>
        </div>
      </div>`;
    document.body.appendChild(ov);
    const close = () => ov.remove();
    ov.addEventListener('click', (e) => { if (e.target === ov) close(); });
    document.getElementById('cpCancel').addEventListener('click', close);
    document.getElementById('cpSave').addEventListener('click', async () => {
      const msg = document.getElementById('cpMsg');
      const cur = document.getElementById('cpCurrent').value;
      const nw = document.getElementById('cpNew').value;
      const cf = document.getElementById('cpConfirm').value;
      if (nw !== cf) { msg.textContent = 'New passwords do not match'; return; }
      try {
        const res = await fetch('/api/auth/change-password', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ currentPassword: cur, newPassword: nw }) });
        const body = await res.json().catch(() => ({}));
        if (res.ok) { msg.style.color = 'var(--green, #16a34a)'; msg.textContent = 'Password updated'; setTimeout(close, 900); }
        else msg.textContent = body.error || 'Could not update password';
      } catch (e) { msg.textContent = 'Network error'; }
    });
  }

  document.addEventListener('DOMContentLoaded', run);
})();
