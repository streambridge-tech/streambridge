// Collapses every .conn-tree-group inside .conn-tree-sidebar by default.
// User-opened groups persist across tree re-renders (search / data reload).
// Exposes window.toggleConnGroup(hdr) so per-group header clicks work on every page.
(function () {

  function groupKey(g) {
    return g.id || (g.querySelector('.conn-tree-group-name')?.textContent || '').trim();
  }

  window.toggleConnGroup = function (hdr) {
    const g = hdr && hdr.closest && hdr.closest('.conn-tree-group');
    if (!g) return;
    g.classList.toggle('collapsed');
    const sidebar = g.closest('.conn-tree-sidebar');
    if (!sidebar) return;
    sidebar._expandedGroups = sidebar._expandedGroups || new Set();
    const key = groupKey(g);
    if (g.classList.contains('collapsed')) sidebar._expandedGroups.delete(key);
    else sidebar._expandedGroups.add(key);
  };

  function applyState(sidebar) {
    const expanded = sidebar._expandedGroups || new Set();
    sidebar.querySelectorAll('.conn-tree-group').forEach(g => {
      g.classList.toggle('collapsed', !expanded.has(groupKey(g)));
    });
  }

  function attach(sidebar) {
    if (sidebar.dataset.groupCollapseInit) return;
    sidebar.dataset.groupCollapseInit = '1';
    sidebar._expandedGroups = new Set();

    requestAnimationFrame(() => applyState(sidebar));

    const body = sidebar.querySelector('.conn-tree-body');
    if (body) {
      let pending = false;
      new MutationObserver(() => {
        if (pending) return;
        pending = true;
        requestAnimationFrame(() => { pending = false; applyState(sidebar); });
      }).observe(body, { childList: true, subtree: true });
    }
  }

  function scan() {
    document.querySelectorAll('.conn-tree-sidebar').forEach(attach);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scan);
  } else {
    scan();
  }
})();
