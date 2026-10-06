---
name: streambridge-context
description: 'Project context for StreamBridge CDC UI and compile flow. Use when working on Pipelines, static partials, build.py page assembly, yaml_builder.py compile logic, connector validation, or pipeline env rules such as kafka_connect.connection.'
user-invocable: false
---

# StreamBridge Context

## What This Repo Is

StreamBridge is a CDC pipeline configuration app built around Debezium and Kafka Connect.

- Backend: Flask app under `app/`
- Frontend: static HTML, CSS, and JS under `static/`
- Build step: `build.py` assembles source partials into standalone pages under `static/dist/`

## Frontend Layout

- Edit source UI in `static/views/`, `static/js/`, and `static/css/`
- Do not treat `static/dist/` as the source of truth; it is generated output
- `app/routes/pages.py` serves the generated pages from `static/dist/`
- Pipeline YAML authoring lives on `/pipelines` (`static/views/pipelines.html`, `static/js/pipelines.js`)

## Compile And Deploy Flow

- Pipeline build and compile authority: `app/utils/yaml_builder.py`
- Connector-specific compile validation: `app/connectors/source/*.py` and `app/connectors/sink/*.py`
- Build route: `app/routes/pipelines_api.py`
- Connection and plugin models live under `app/models/`

## Working Rules

- Prefer fixing behavior in source files rather than generated dist files
- Keep changes narrow and preserve the current no-framework frontend structure
- When changing page composition, update `build.py` instead of duplicating layout logic in Flask routes
- When changing compile behavior, prefer `yaml_builder.py` as the single source of truth unless connector-specific validation is truly required
