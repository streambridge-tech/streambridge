"""
yaml_builder.py — Pipeline YAML Validation & Config Assembly
=============================================================

This module is the single backend authority for everything that happens
between "user clicks Build" and "connector config is ready to deploy".

WHAT IT DOES
------------
Given a raw pipeline YAML string and a selected environment name, it:

  1. PARSES — extracts all structural fields from the YAML using regex
     (pipeline name, source/sink type, connector names, table list,
      slot name, plugin name, transforms, schema registry URL).

  2. VALIDATES — checks that all required fields are present and coherent:
       • pipeline.name, source:, sink:, connector_name on both sides
       • source.type and sink.type are present
       • If the YAML has an env: block, an env must be selected
       • Every {{ var('x') }} resolves to a value (no <x> placeholders left)
       • Every [connection:name] reference exists in the connections table
       • Kafka Connect URL is present (from connection or direct value)
       • If schema.registry.url is referenced, it must not be empty/unset

  3. RESOLVES — substitutes Jinja-style template expressions:
       • {{ var('x') }}     → value from the selected env block or vars: block
       • {{ conn('x') }}    → [connection:x]  (marker, injected at deploy time)
       • {{ env_var('x') }} → $X              (resolved at runtime by the host)
     After substitution, any remaining {{ ... }} is an error.

  4. MERGES CONFIG — builds the final Kafka Connect config dict for each
     connector by layering (lowest → highest priority):
       a. Plugin base config from DB  (connector.class, default keys, format)
       b. YAML source.config / sink.config block  (pipeline-specific overrides)
       c. connector_name → "name" key  (always highest priority)

  5. RETURNS a structured result:
       {
         "ok": true | false,
         "logs": [ {"level": "info|warn|error|success", "text": "..."}, ... ],
         "meta": { "name": "pipeline-name", "env": "dev" },
         "sourceConfig": { ...merged Kafka Connect config... },
         "sinkConfig":   { ...merged Kafka Connect config... },
       }
     Callers (the /api/pipelines/build route) return this directly to the
     frontend, which renders logs[] into the Logs tab.

WHAT IT DOES NOT DO
-------------------
  • Does not call Kafka Connect or any external service
  • Does not write to the database
  • Does not inject actual credential values from connections —
    connection references remain as [connection:name] markers;
    credential injection happens at deploy time in the deploy route

MODULE LAYOUT
-------------
  _extract_env_vars(raw, env)   — parse var assignments from env block
  resolve_yaml(raw, env)        — substitute all {{ }} expressions
  _section_config(raw, section) — extract source.config / sink.config keys
  _parse_conn_refs(resolved)    — extract all [connection:name] markers
  build_pipeline(raw, env, db)  — main entry point, returns result dict
"""

import re
import json
import os

from app.connectors.schemas import SECRET_MASK

_VAR_RE  = re.compile(r"\{\{\s*var\s*\(\s*['\"](\w[\w-]*)['\"]\s*\)\s*\}\}")
_CONN_RE = re.compile(r"\{\{\s*conn\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}")
_ANY_RE  = re.compile(r"\{\{[^}]+\}\}")
_CONN_MARKER_RE    = re.compile(r"\[connection:([^\]]+)\]")
_ENV_VAR_MARKER_RE = re.compile(r'\$([A-Z_][A-Z0-9_]*)')

# Values the seeded plugin configs use for "fill this in" (see seeds/plugins/).
_PLACEHOLDERS = (None, "", "*******", SECRET_MASK)


def _is_placeholder(value) -> bool:
    """True when a config value is an unset/masked placeholder rather than a real value."""
    return value in _PLACEHOLDERS


def _extract_env_block(raw: str, env: str) -> str:
    """Return the raw text under pipeline.env.<env>, or an empty string if missing."""
    if not env:
        return ""
    m = re.search(
        rf'^[ \t]{{4}}{re.escape(env)}\s*:\s*\n((?:[ \t]{{6}}[\s\S]*?\n)+)',
        raw, re.MULTILINE
    )
    return m.group(1) if m else ""


def _extract_top_block(raw: str, section: str) -> str:
    """Return a top-level block (e.g. 'source:' or 'sink:') bounded to the next top-level key."""
    m = re.search(
        rf'^{re.escape(section)}\s*:\s*\n((?:[ \t]+.*\n?|\n)*)',
        raw, re.MULTILINE
    )
    return m.group(0) if m else ""


def _extract_env_vars(raw: str, env: str) -> dict:
    """Return var→value mapping for the selected env block and top-level vars:."""
    vars_ = {}
    env_block = _extract_env_block(raw, env)
    if env_block:
        for km in re.finditer(r'^[ \t]{6}([\w][\w-]*)[ \t]*:[ \t]*(.+)', env_block, re.MULTILINE):
            vars_[km.group(1).strip()] = km.group(2).strip()
    vm = re.search(r'^[ \t]{2}vars:\s*\n((?:[ \t]{4}[\w][\w-]*\s*:[ \t]*\S.*\n)+)', raw, re.MULTILINE)
    if vm:
        for km in re.finditer(r'^[ \t]{4}([\w][\w-]*)[ \t]*:[ \t]*(.+)', vm.group(1), re.MULTILINE):
            vars_.setdefault(km.group(1).strip(), km.group(2).strip())
    return vars_


def _strip_env_block(raw: str) -> str:
    """Remove the entire pipeline.env: block so conn() refs from other envs are never expanded."""
    return re.sub(r'^( {2}env:\s*\n)((?:[ \t]{4}[\s\S]*?\n)*)', '', raw, flags=re.MULTILINE)


def resolve_yaml(raw: str, env: str) -> str:
    """Substitute {{ var() }}, {{ conn() }}, {{ env_var() }} in the raw YAML."""
    vars_ = _extract_env_vars(raw, env)
    # Strip the env: block before conn() expansion so only the selected env's
    # connection refs (already substituted into var() calls) become markers.
    stripped = _strip_env_block(raw)
    out = _VAR_RE.sub(lambda m: vars_.get(m.group(1), f'<{m.group(1)}>'), stripped)
    out = _CONN_RE.sub(lambda m: f'[connection:{m.group(1)}]', out)
    out = re.sub(r"\{\{\s*env_var\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}", lambda m: f'${m.group(1)}', out)
    return out


def _section_config(raw: str, section: str) -> dict:
    """Extract key:value pairs under source.config or sink.config block.

    The search stays inside the section's own block, and the config body ends
    at the first line that is not indented deeper than `config:`.
    """
    m = re.search(
        r'^([ \t]+)config:\s*\n((?:\1[ \t]+[\w.]+[ \t]*:[ \t]*[^\n]*\n?)+)',
        _extract_top_block(raw, section), re.MULTILINE
    )
    if not m:
        return {}
    config = {}
    for km in re.finditer(r'^[ \t]+([\w.]+)[ \t]*:[ \t]*([^\n#]*)', m.group(2), re.MULTILINE):
        val = km.group(2).strip().strip('"').strip("'")
        if val:
            config[km.group(1).strip()] = val
    return config


def _parse_conn_refs(resolved: str) -> list[str]:
    """Return all connection names referenced as [connection:name] markers."""
    return _CONN_MARKER_RE.findall(resolved)


def _parse_env_var_refs(resolved: str) -> list[str]:
    """Return deduplicated list of $VAR names produced by {{ env_var() }} substitution."""
    return list(dict.fromkeys(_ENV_VAR_MARKER_RE.findall(resolved)))


def _plugin_config(plugin) -> dict | None:
    """Return a plugin's stored config, or None when it is not a JSON object."""
    try:
        config = json.loads(plugin.config)
    except (TypeError, ValueError):
        return None
    return config if isinstance(config, dict) else None


def _fail(logs: list, errors: list) -> dict:
    for e in errors:
        logs.append({"level": "error", "text": e})
    logs.append({"level": "error", "text": f"✗ Build failed — {len(errors)} error(s)"})
    return {"ok": False, "logs": logs, "sourceConfig": {}, "sinkConfig": {}}


def build_pipeline(raw: str, env: str, db) -> dict:
    """
    Main entry point. Validate, resolve and merge pipeline YAML.
    Returns { ok, logs, meta, sourceConfig, sinkConfig }.
    """
    from app.models.plugin import Plugin
    from app.models.connection import Connection

    logs = []

    def log(level, text):
        logs.append({"level": level, "text": text})

    log("info", f"Starting build… (env: {env or 'direct'})")

    # ── Parse all fields upfront ──────────────────────────────────────────────
    name_m    = re.search(r'^\s{2}name:\s*(\S+)', raw, re.MULTILINE)
    src_block = _extract_top_block(raw, "source")
    snk_block = _extract_top_block(raw, "sink")
    src_type  = (re.search(r'^\s+type:\s*(\S+)', src_block, re.MULTILINE) or [None,None])[1]
    snk_type  = (re.search(r'^\s+type:\s*(\S+)', snk_block, re.MULTILINE) or [None,None])[1]
    src_name  = (re.search(r'^\s+connector_name:\s*(\S+)', src_block, re.MULTILINE) or [None,None])[1]
    snk_name  = (re.search(r'^\s+connector_name:\s*(\S+)', snk_block, re.MULTILINE) or [None,None])[1]
    src_plugin_name = (re.search(r'^\s+plugin:\s*(\S+)', src_block, re.MULTILINE) or [None,None])[1]
    snk_plugin_name = (re.search(r'^\s+plugin:\s*(\S+)', snk_block, re.MULTILINE) or [None,None])[1]
    schema_m  = re.search(r'schema\.registry\.url\s*:\s*(\S+)', raw)
    env_block = _extract_env_block(raw, env)
    kc_env_m  = re.search(r'^[ \t]{6}kafka[_.]connect\.connection\s*:\s*(\S+)', env_block, re.MULTILINE)
    has_source    = bool(re.search(r'^source\s*:', raw, re.MULTILINE))
    has_sink      = bool(re.search(r'^sink\s*:',   raw, re.MULTILINE))
    has_env_block = bool(re.search(r'^\s{2}env:\s*\n', raw, re.MULTILINE))

    # ── Check 1: pipeline.name ────────────────────────────────────────────────
    log("info", "Checking pipeline.name…")
    if not name_m:
        return _fail(logs, [
            "pipeline.name is missing — add a name: field under pipeline:",
        ])
    pipeline_name = name_m.group(1)
    if len(pipeline_name) > 128:
        return _fail(logs, [
            f'pipeline.name "{pipeline_name[:40]}…" is {len(pipeline_name)} chars — max 128',
            "Fix: shorten the name in your YAML and retry",
        ])
    log("success", f'pipeline.name: "{pipeline_name}"  ✓  ({len(pipeline_name)} chars)')

    # ── Check 2: source: and sink: blocks ────────────────────────────────────
    if not has_source:
        return _fail(logs, ["source: block is missing — add a source: section to your YAML"])
    if not has_sink:
        return _fail(logs, ["sink: block is missing — add a sink: section to your YAML"])

    # ── Check 3: env gate ─────────────────────────────────────────────────────
    log("info", "Checking env selection…")
    if has_env_block and not env:
        return _fail(logs, [
            "Pipeline has env: block — select a target env (e.g. dev / prod) to build",
        ])
    log("success", f'env: "{env}"  ✓' if env else "env: direct (no env: block)  ✓")

    # ── Check 4: connector_name source + sink ────────────────────────────────
    log("info", "Checking source.connector_name…")
    errors = []
    if not src_name:
        errors += [
            "source.connector_name is missing — add connector_name: under source:",
            "Fix: add a unique name e.g.  connector_name: my-postgres-source",
        ]
    elif len(src_name) > 64:
        errors += [
            f'source.connector_name "{src_name[:40]}…" is {len(src_name)} chars — max 64',
            "Fix: shorten connector_name in source: block and retry",
        ]
    else:
        log("success", f'source.connector_name: "{src_name}"  ✓  ({len(src_name)} chars)')

    log("info", "Checking sink.connector_name…")
    if not snk_name:
        errors += [
            "sink.connector_name is missing — add connector_name: under sink:",
            "Fix: add a unique name e.g.  connector_name: my-s3-sink",
        ]
    elif len(snk_name) > 64:
        errors += [
            f'sink.connector_name "{snk_name[:40]}…" is {len(snk_name)} chars — max 64',
            "Fix: shorten connector_name in sink: block and retry",
        ]
    else:
        log("success", f'sink.connector_name: "{snk_name}"  ✓  ({len(snk_name)} chars)')

    # ── Check 5: source.type + sink.type ─────────────────────────────────────
    from app.connectors import _REGISTRY
    _src_types = sorted(s for (t, s) in _REGISTRY if t == "source")
    _snk_types = sorted(s for (t, s) in _REGISTRY if t == "sink")
    if not src_type:
        errors.append(f"source.type is missing — supported: {', '.join(_src_types)}")
    elif src_type.lower() not in _src_types:
        errors.append(f"source.type '{src_type}' is not supported — supported: {', '.join(_src_types)}")
    if not snk_type:
        errors.append(f"sink.type is missing — supported: {', '.join(_snk_types)}")
    elif snk_type.lower() not in _snk_types:
        errors.append(f"sink.type '{snk_type}' is not supported — supported: {', '.join(_snk_types)}")

    # ── Check 6: kafka_connect.connection — must be in env block ─────────────
    log("info", "Checking infra kafka_connect.connection (env-level)…")
    if not kc_env_m:
        env_label = env or "<env>"
        errors += [
            f"pipeline.env.{env_label}.kafka_connect.connection is required — it must be set for the selected build env",
            f"Fix: add  kafka_connect.connection: {{ conn('kafka_connect_{env_label}') }}  under pipeline.env.{env_label}:",
        ]
    else:
        log("success", f'pipeline.env.{env}.kafka_connect.connection: "{kc_env_m.group(1)}"  ✓')

    if errors:
        return _fail(logs, errors)

    log("success", "All checks passed (6/6)")

    # ── Resolve {{ var() }} / {{ conn() }} / {{ env_var() }} ──────────────────
    log("info", "Resolving {{ var() }} and {{ conn() }} expressions…")
    resolved   = resolve_yaml(raw, env or "")
    unresolved = _ANY_RE.findall(resolved)
    if unresolved:
        return _fail(logs, [f"Unresolved expression: {u}" for u in unresolved])
    log("success", "All expressions resolved  ✓")

    # ── Validate env_var() references are set in the host environment ─────────
    env_var_refs = _parse_env_var_refs(resolved)
    if env_var_refs:
        log("info", f"Checking env vars: {', '.join(env_var_refs)}")
        missing_env = [v for v in env_var_refs if v not in os.environ]
        if missing_env:
            return _fail(logs, [
                f"env_var '{v}' is not set in the host environment"
                for v in missing_env
            ])
        log("success", f"env vars present: {', '.join(env_var_refs)}  ✓")

    # ── Validate connection refs exist in DB ──────────────────────────────────
    # Include conn() refs from the env block since it is stripped before resolve
    env_conn_refs  = _CONN_RE.findall(env_block)
    conn_refs      = list(dict.fromkeys(_parse_conn_refs(resolved) + env_conn_refs))
    existing_names = {c.name for c in db.query(Connection.name).all()}
    ref_errors     = []
    if conn_refs:
        log("info", f"Checking connection registry: {', '.join(conn_refs)}")
        for ref in conn_refs:
            if ref not in existing_names:
                ref_errors += [
                    f"Connection not found in registry: '{ref}'",
                    f"Fix: create a connection named '{ref}' in the Connections view",
                ]
            else:
                log("success", f'connection "{ref}"  ✓  exists in registry')
    if ref_errors:
        return _fail(logs, ref_errors)

    # ── Schema registry check (optional) ─────────────────────────────────────
    if schema_m:
        sr_val = schema_m.group(1).strip()
        if not sr_val or sr_val.startswith('<'):
            return _fail(logs, [
                "schema.registry.url is referenced but has no value",
                "Fix: set schema.registry.url to a valid URL or remove it",
            ])
        log("success", f'schema.registry.url: "{sr_val}"  ✓')

    # ── Resolve plugins by name (explicit) or default "{type}-json" ──────────
    def resolve_plugin(side, explicit_name, type_):
        default_name = f"{(type_ or '').lower()}-json"
        name = explicit_name or default_name
        plugin = db.query(Plugin).filter(Plugin.name == name).first()
        return plugin, name

    src_plugin, src_plugin_resolved = resolve_plugin("source", src_plugin_name, src_type)
    snk_plugin, snk_plugin_resolved = resolve_plugin("sink",   snk_plugin_name, snk_type)

    if not src_plugin:
        return _fail(logs, [
            f"source plugin '{src_plugin_resolved}' not found",
            f"Fix: create it in the Plugins view or set  plugin: <existing-plugin>  under source:",
        ])
    if not snk_plugin:
        return _fail(logs, [
            f"sink plugin '{snk_plugin_resolved}' not found",
            f"Fix: create it in the Plugins view or set  plugin: <existing-plugin>  under sink:",
        ])

    log("success", f'plugin (source): "{src_plugin.name}" ({"explicit" if src_plugin_name else "default"}, format={src_plugin.format})  ✓')
    log("success", f'plugin (sink):   "{snk_plugin.name}" ({"explicit" if snk_plugin_name else "default"}, format={snk_plugin.format})  ✓')

    # ── Merge: plugin base ← YAML config: block ──────────────────────────────
    src_base   = _plugin_config(src_plugin)
    snk_base   = _plugin_config(snk_plugin)
    plugin_errors = [
        f"plugin '{plugin.name}' config is not a JSON object — fix it in the Plugins view"
        for plugin, base in ((src_plugin, src_base), (snk_plugin, snk_base))
        if base is None
    ]
    if plugin_errors:
        return _fail(logs, plugin_errors)
    src_yaml   = _section_config(resolved, "source")
    snk_yaml   = _section_config(resolved, "sink")
    src_config = {**src_base, **src_yaml, "name": src_name}
    snk_config = {**snk_base, **snk_yaml, "name": snk_name}

    log("success", f'plugin merged (source):  {len(src_config)} keys  ✓')
    log("success", f'plugin merged (sink):    {len(snk_config)} keys  ✓')

    # ── Detect connection refs per side (bounded to each block) ──────────────
    from app.connectors import get as get_connector
    resolved_src_block = _extract_top_block(resolved, "source")
    resolved_snk_block = _extract_top_block(resolved, "sink")
    src_has_db_conn    = bool(re.search(r'^\s+db\.connection\s*:',              resolved_src_block, re.MULTILINE))
    src_has_kafka_conn = bool(re.search(r'^\s+kafka\.connection\s*:',           resolved_src_block, re.MULTILINE))
    src_has_sr_conn    = bool(re.search(r'^\s+schema_registry\.connection\s*:', resolved_src_block, re.MULTILINE))
    src_has_kc_conn    = bool(kc_env_m)
    snk_has_db_conn    = bool(re.search(r'^\s+storage\.connection\s*:',         resolved_snk_block, re.MULTILINE))
    snk_has_kafka_conn = bool(re.search(r'^\s+kafka\.connection\s*:',           resolved_snk_block, re.MULTILINE))
    snk_has_sr_conn    = bool(re.search(r'^\s+schema_registry\.connection\s*:', resolved_snk_block, re.MULTILINE))
    snk_has_kc_conn    = bool(kc_env_m)

    # ── Derive Kafka topic names from source ──────────────────────────────────
    derived_topics = []
    log("info", "Deriving Kafka topic names from source config…")
    src_validator = get_connector("source", src_type)
    if src_validator:
        prefix_field = src_validator.TOPIC_PREFIX_FIELD or "topic.prefix"
        # Debezium requires a prefix. When it is unset or a plugin placeholder
        # ("", "*******"), deploy with connector_name as the prefix.
        if _is_placeholder(src_config.get(prefix_field)):
            src_config[prefix_field] = src_name
            checked = f'connector_name "{src_name}" (used as {prefix_field})'
        else:
            checked = f'{prefix_field} "{src_config[prefix_field]}"'
        if not re.match(r'^[a-zA-Z0-9._-]+$', src_config[prefix_field]):
            log("warn", f'{checked} contains characters invalid for a Kafka topic prefix')
            log("warn", f'Fix: set  {prefix_field}: <valid-prefix>  explicitly under source.config:')
        else:
            derived_topics = src_validator.derive_topics(src_config)
            if derived_topics:
                for t in derived_topics:
                    log("success", f"  → {t}")
                log("info", f'Suggested sink topics:  topics: {",".join(derived_topics)}')
            else:
                log("warn", f"Cannot derive topic names — set {prefix_field} or table.include.list in source.config")

    # ── Connector-level compile checks — collect ALL errors across both sides ──
    sink_topics  = []
    all_errors   = []
    compile_logs = []

    for side, ctype, subtype, config, has_db, has_kafka, has_kc, has_sr, plugin_format in [
        ("source", "source", src_type, src_config, src_has_db_conn, src_has_kafka_conn, src_has_kc_conn, src_has_sr_conn, src_plugin.format),
        ("sink",   "sink",   snk_type, snk_config, snk_has_db_conn, snk_has_kafka_conn, snk_has_kc_conn, snk_has_sr_conn, snk_plugin.format),
    ]:
        validator = get_connector(ctype, subtype)
        if validator is None:
            compile_logs.append({"level": "info", "text": f"  no compile validator registered for {side} type '{subtype}' — skipping"})
            continue
        result = validator.compile(config, has_db, has_kafka, has_kc, has_sr, plugin_format)
        if isinstance(result, tuple):
            result, topics, regex = result
            if topics:
                sink_topics = topics
            elif regex:
                sink_topics = [regex]
            elif not result.ok() and derived_topics:
                result.logs.append({"level": "error", "text": f"Fix: add  topics: {','.join(derived_topics)}  under sink.config:"})
        compile_logs.extend(result.logs)
        all_errors.extend(result.errors)

    # emit all compile logs first (inline checks)
    logs.extend(compile_logs)

    # if any errors — show summary block at the bottom then fail
    if all_errors:
        logs.append({"level": "error", "text": "─" * 45})
        logs.append({"level": "error", "text": f"Build errors ({len(all_errors)})"})
        logs.append({"level": "error", "text": "─" * 45})
        for e in all_errors:
            logs.append({"level": "error", "text": f"  • {e}"})
        logs.append({"level": "error", "text": f"✗ Build failed — {len(all_errors)} error(s)"})
        return {"ok": False, "logs": logs, "sourceConfig": {}, "sinkConfig": {}}

    log("success", "✓ Build passed — ready to deploy")

    # ── Lineage summary ───────────────────────────────────────────────────────
    if derived_topics or sink_topics:
        log("info", "─" * 45)
        log("info", "Pipeline Lineage")
        log("info", "─" * 45)
        log("info", f"{src_name}  ({src_type})")
        for t in derived_topics:
            log("info", f"  → {t}")
        log("info", f"{snk_name}  ({snk_type})")
        for t in sink_topics:
            log("info", f"  ← {t}")
        log("info", "─" * 45)

    return {
        "ok": True,
        "logs": logs,
        "meta": {
            "name":             pipeline_name,
            "env":              env or "",
            "sourcePluginName": src_plugin.name,
            "sinkPluginName":   snk_plugin.name,
            "sourceFormat":     src_plugin.format,
            "sinkFormat":       snk_plugin.format,
        },
        "sourceConfig": src_config,
        "sinkConfig":   snk_config,
    }
