#!/usr/bin/env python3
"""Build script: assembles per-page standalone dist files.

Each dist file contains:
  - <link rel="stylesheet"> tags for its CSS files  (no inlining)
  - shared sidebar HTML (injected from views/sidebar.html)
  - only the view partials it needs
  - <script src=""> tags for its JS files           (no inlining)

CSS and JS are served directly by Flask from /static/css/ and /static/js/,
so the browser caches them independently of the HTML.

Usage:
    python3 build.py
"""
import pathlib

ROOT   = pathlib.Path(__file__).parent
STATIC = ROOT / 'static'
DIST   = STATIC / 'dist'
DIST.mkdir(exist_ok=True)

NAV = {
    'NAV_PIPELINES':       '/pipelines',
    'NAV_CONNECTIONS':     '/connections',
    'NAV_KAFKA_TOPICS':    '/kafka-topics',
    'NAV_SCHEMA_REGISTRY': '/schema-registry',
    'NAV_CONNECTORS':      '/connectors',
    'NAV_RCA':             '/rca',
    'NAV_PLUGINS':         '/plugins',
    'NAV_ALERTS':          '/alerts',
    'NAV_DOCS':            '/docs',
    'NAV_ADMIN':           '/admin',
}

_SIMPLE_TOPBAR = lambda title: f'<span class="topbar-title">{title}</span>'

# ── Per-page config ──────────────────────────────────────────────────────────
# css:    list of paths under static/  → become <link> tags
# views:  list of HTML partials to inject
# js:     list of paths under static/  → become <script src> tags
# modals: True = include views/modals.html (connection modals)

PAGES = {
    'connections.html': {
        'title':   'Connections',
        'rail_id': 'connections',
        'css':     ['css/base.css', 'css/connections.css', 'css/tree_pane.css'],
        'views':   ['views/connections.html'],
        'js':      ['js/data.js', 'js/secrets.js', 'js/tree_pane.js', 'js/connections.js', 'js/tree_sidebar_toggle.js'],
        'topbar':  _SIMPLE_TOPBAR('Connections'),
        'modals':  True,
    },
    'pipelines.html': {
        'title':   'Pipelines',
        'rail_id': 'pipelines',
        'css':     ['css/base.css', 'css/pipelines.css'],
        'views':   ['views/pipelines.html'],
        'js':      ['js/pipeline_examples.js', 'js/pipelines.js'],
        'topbar':  _SIMPLE_TOPBAR('Pipelines'),
        'modals':  False,
    },
    'kafka_topics.html': {
        'title':   'Kafka Topics',
        'rail_id': 'kafka-topics',
        'css':     ['css/base.css', 'css/connections.css', 'css/tree_pane.css'],
        'views':   ['views/kafka_topics.html'],
        'js':      ['js/data.js', 'js/tree_pane.js', 'js/kafka_topics_display.js', 'js/tree_sidebar_toggle.js'],
        'topbar':  _SIMPLE_TOPBAR('Kafka Topics'),
        'modals':  False,
    },
    'schema_registry.html': {
        'title':   'Schema Registry',
        'rail_id': 'schema-registry',
        'css':     ['css/base.css', 'css/connections.css', 'css/tree_pane.css'],
        'views':   ['views/schema_registry.html'],
        'js':      ['js/data.js', 'js/tree_pane.js', 'js/schema_registry.js', 'js/tree_sidebar_toggle.js'],
        'topbar':  _SIMPLE_TOPBAR('Schema Registry'),
        'modals':  False,
    },
    'connectors.html': {
        'title':   'Connectors',
        'rail_id': 'connectors',
        'css':     ['css/base.css', 'css/configs.css'],
        'views':   ['views/configs.html'],
        'js_classic': ['js/secrets.js'],
        'js':      ['js/configs/app.js'],
        'js_module': True,
        'topbar':  _SIMPLE_TOPBAR('Connectors'),
        'modals':  False,
    },
    'docs.html': {
        'title':   'Documentation',
        'rail_id': 'docs',
        'css':     ['css/base.css', 'css/docs.css'],
        'views':   ['views/docs.html'],
        'js':      ['js/docs.js'],
        'topbar':  _SIMPLE_TOPBAR('Documentation'),
        'modals':  False,
    },
    'rca.html': {
        'title':   'RCA — Incident Tracker',
        'rail_id': 'rca',
        'css':     ['css/base.css', 'css/connections.css', 'css/tree_pane.css'],
        'views':   ['views/rca.html'],
        'js':      ['js/data.js', 'js/tree_pane.js', 'js/rca.js', 'js/tree_sidebar_toggle.js'],
        'topbar':  _SIMPLE_TOPBAR('RCA'),
        'modals':  False,
    },
    'plugins.html': {
        'title':   'Plugins — Connector Library',
        'rail_id': 'plugins',
        'css':     ['css/base.css', 'css/connections.css', 'css/tree_pane.css'],
        'views':   ['views/plugins.html'],
        'js':      ['js/data.js', 'js/tree_pane.js', 'js/plugins.js', 'js/tree_sidebar_toggle.js'],
        'topbar':  _SIMPLE_TOPBAR('Plugins'),
        'modals':  False,
    },
    'alerts.html': {
        'title':   'Alerts',
        'rail_id': 'alerts',
        'css':     ['css/base.css', 'css/alerts.css', 'css/tree_pane.css'],
        'views':   ['views/alerts.html'],
        'js':      ['js/tree_pane.js', 'js/alerts.js', 'js/tree_sidebar_toggle.js'],
        'topbar':  _SIMPLE_TOPBAR('Alerts'),
        'modals':  False,
    },
    'admin.html': {
        'title':   'Access Control',
        'rail_id': 'admin',
        'css':     ['css/base.css', 'css/admin.css'],
        'views':   ['views/admin.html'],
        'js':      ['js/admin.js'],
        'topbar':  _SIMPLE_TOPBAR('Access Control'),
        'modals':  False,
    },
}


def read(path):
    return (STATIC / path).read_text(encoding='utf-8')


def apply_nav(html):
    for key, value in NAV.items():
        html = html.replace(f'<!-- {{{{{key}}}}} -->', value)
    return html


def css_tags(css_files):
    return '\n  '.join(
        f'<link rel="stylesheet" href="/static/{f}">' for f in css_files
    )


def js_tags(js_files, module=False):
    attr = ' type="module"' if module else ''
    return '\n'.join(
        f'<script{attr} src="/static/{f}"></script>' for f in js_files
    )


def all_js_tags(cfg):
    classic = list(cfg.get('js_classic') or [])
    if 'js/tree_icons.js' not in classic:
        classic.insert(0, 'js/tree_icons.js')
    classic_tags = js_tags(classic, False)
    main = js_tags(cfg['js'], cfg.get('js_module'))
    return '\n'.join(part for part in (classic_tags, main) if part)


def build_page(filename, cfg):
    sidebar     = apply_nav(read('views/sidebar.html'))
    views_block = '\n\n'.join(read(f) for f in cfg['views'])
    modals      = read('views/modals.html') if cfg['modals'] else ''

    # Single-view pages: mark the view active (no app.js switchView)
    if len(cfg['views']) == 1:
        views_block = views_block.replace('class="view"', 'class="view active"', 1)

    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>StreamBridge — {cfg['title']}</title>
  <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:ital,opsz,wght@0,14..32,400;0,14..32,500;0,14..32,600;0,14..32,700;1,14..32,400&display=swap" rel="stylesheet">
  {css_tags(cfg['css'])}
</head>
<body>

{sidebar}

<div class="main">
  <header class="topbar">
    {cfg['topbar']}
    <button class="topbar-account" id="topAccount" style="display:none;">
      <span class="topbar-acct-avatar" id="topAcctAvatar">?</span>
      <span class="topbar-acct-role" id="topAcctRole">All roles</span>
      <svg class="topbar-acct-chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </button>
  </header>
  <div class="content">

{views_block}

  </div>
</div>

{modals}
<script src="/static/js/rbac_nav.js"></script>
{all_js_tags(cfg)}

</body>
</html>'''

    # Mark the active rail link
    page = page.replace(
        f'class="rail-item" id="rail-{cfg["rail_id"]}"',
        f'class="rail-item active" id="rail-{cfg["rail_id"]}"',
    )

    return page


for filename, cfg in PAGES.items():
    out = build_page(filename, cfg)
    (DIST / filename).write_text(out, encoding='utf-8')
    lines = out.count('\n')
    print(f'Built dist/{filename:<26} {lines:>4} lines')

print(f'\n  Pages built : {len(PAGES)}')
