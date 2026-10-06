// Generic second sidebar: collapse, dock left/right, drag-resize.
(function () {
  function layoutOf(el) {
    return el && el.closest && el.closest('.conn-tree-layout');
  }

  function sidebarOf(layout) {
    return layout && layout.querySelector('.conn-tree-sidebar');
  }

  function storageKey(layout, kind) {
    const id = (sidebarOf(layout) && sidebarOf(layout).id) || location.pathname;
    return 'streambridge.treePane.' + id + '.' + kind;
  }

  function applySaved(layout) {
    if (!layout) return;
    const dockBtn = layout.querySelector('[data-tree-pane="dock"]');
    if (dockBtn) {
      const dock = localStorage.getItem(storageKey(layout, 'dock'));
      layout.classList.toggle('nav-right', dock === 'right');
      syncDockTitle(layout);
    } else {
      layout.classList.remove('nav-right');
    }
    if (layout.querySelector('[data-tree-pane="collapse"]')) {
      const collapsed = localStorage.getItem(storageKey(layout, 'collapsed')) === '1';
      layout.classList.toggle('nav-collapsed', collapsed);
    }
    const sidebar = sidebarOf(layout);
    const saved = Number(localStorage.getItem(storageKey(layout, 'width')));
    if (sidebar && saved >= 180 && saved <= 560) sidebar.style.width = saved + 'px';
    syncDockTitle(layout);
  }

  function syncDockTitle(layout) {
    const btn = layout.querySelector('[data-tree-pane="dock"]');
    if (!btn) return;
    btn.title = layout.classList.contains('nav-right') ? 'Move list to the left' : 'Move list to the right';
  }

  function toggleCollapse(layout) {
    layout.classList.toggle('nav-collapsed');
    localStorage.setItem(storageKey(layout, 'collapsed'), layout.classList.contains('nav-collapsed') ? '1' : '0');
  }

  function toggleDock(layout) {
    layout.classList.toggle('nav-right');
    localStorage.setItem(storageKey(layout, 'dock'), layout.classList.contains('nav-right') ? 'right' : 'left');
    syncDockTitle(layout);
  }

  function bindResize(handle) {
    if (handle.dataset.bound) return;
    handle.dataset.bound = '1';
    const layout = layoutOf(handle);
    const sidebar = sidebarOf(layout);
    if (!layout || !sidebar) return;
    const clamp = (w) => Math.min(560, Math.max(180, w));
    handle.addEventListener('mousedown', (event) => {
      if (layout.classList.contains('nav-collapsed')) return;
      event.preventDefault();
      const startX = event.clientX;
      const startW = sidebar.getBoundingClientRect().width;
      const fromRight = layout.classList.contains('nav-right');
      handle.classList.add('dragging');
      document.body.classList.add('tree-pane-resizing');
      const onMove = (e) => {
        const dx = e.clientX - startX;
        sidebar.style.width = clamp(fromRight ? startW - dx : startW + dx) + 'px';
      };
      const onUp = () => {
        handle.classList.remove('dragging');
        document.body.classList.remove('tree-pane-resizing');
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        const width = parseInt(sidebar.style.width, 10);
        if (width) localStorage.setItem(storageKey(layout, 'width'), String(width));
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });
  }

  function init() {
    document.querySelectorAll('.conn-tree-layout').forEach(applySaved);
    document.querySelectorAll('[data-tree-pane="collapse"]').forEach((btn) => {
      btn.addEventListener('click', () => toggleCollapse(layoutOf(btn)));
    });
    document.querySelectorAll('[data-tree-pane="dock"]').forEach((btn) => {
      btn.addEventListener('click', () => toggleDock(layoutOf(btn)));
    });
    document.querySelectorAll('.conn-tree-resizer').forEach(bindResize);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
