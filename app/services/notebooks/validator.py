from __future__ import annotations

from app.models.connection import Connection
from app.models.connector_notebook import ConnectorNotebook
from app.models.vault import Vault
from app.services.connect.factory import get_backend
from app.services.connect.rest_backend import ConfigValidationError, _extract_field_errors
from app.services.notebooks.logs import STEP_SECRETS, STEP_VALIDATE, CommandLogWriter
from app.services.notebooks.secrets import SecretResolver
from app.utils.logger import get_logger

log = get_logger("app.services.notebooks")


class NotebookValidator:
    """Resolve `{vault.key}` then PUT Kafka Connect /connector-plugins/.../config/validate."""

    def __init__(self, db, get_backend_fn=get_backend):
        self.db = db
        self._get_backend = get_backend_fn

    def validate(self, notebook: ConnectorNotebook) -> dict:
        writer = CommandLogWriter(self.db, notebook.id)
        cluster = (notebook.attached_cluster or "").strip()
        if not cluster:
            return self._fail(writer, "Attach a Kafka Connect cluster first", 400)

        kc = self.db.query(Connection).filter(Connection.name == cluster).first()
        if not kc:
            return self._fail(writer, f"Kafka Connect connection '{cluster}' not found", 404)
        type_ = str(kc.type or "").lower()
        subtype = str(kc.subtype or "").lower()
        if type_ != "connect" and "kafka-connect" not in subtype:
            return self._fail(writer, f"'{cluster}' is not a Kafka Connect connection", 400)

        config = (notebook.doc() or {}).get("config") or {}
        if not isinstance(config, dict):
            return self._fail(writer, "Config must be a JSON object with a config map", 400)
        plugin_class = str(config.get("connector.class") or "").strip()
        if not plugin_class:
            return self._fail(writer, "connector.class is required", 400)

        resolver = SecretResolver(self.db.query(Vault).all())
        try:
            resolved, missing, ref_count = resolver.resolve_config(config)
        except ValueError as exc:
            return self._fail(writer, str(exc), 400, step=STEP_SECRETS)

        if missing:
            return self._fail(writer, f"Missing secrets: {', '.join(missing)}", 400, step=STEP_SECRETS)

        writer.record(
            STEP_SECRETS,
            "ok",
            detail=f"Resolved {ref_count} secret ref(s)" if ref_count else "No secret refs",
        )

        payload = dict(resolved)
        doc = notebook.doc() or {}
        name = (
            str(payload.get("name") or "").strip()
            or str(doc.get("name") or "").strip()
            or str(notebook.name or "").strip()
        )
        if name:
            payload["name"] = name

        try:
            backend = self._get_backend(kc.config or {})
            report = backend.validate_config(plugin_class, payload, connector_name=name)
        except ConfigValidationError as exc:
            errors = _format_field_errors(exc.field_errors)
            return self._fail(writer, str(exc), 400, errors=errors)
        except Exception as exc:
            return self._fail(writer, str(exc), 502)

        field_errors = _extract_field_errors(report)
        if field_errors:
            errors = _format_field_errors(field_errors)
            return self._fail(writer, "Kafka Connect rejected this config", 400, errors=errors)

        detail = f"Kafka Connect accepted {plugin_class}"
        writer.record(STEP_VALIDATE, "ok", detail=detail, http_status=200)
        log.info("Notebook validated  id=%s  connector=%s  cluster=%s", notebook.id, notebook.name, cluster)
        return {"ok": True, "errors": [], "message": detail, "errorCount": 0}

    def _fail(self, writer, message, http_status, errors=None, step=STEP_VALIDATE) -> dict:
        lines = errors or [message]
        writer.record(step, "error", detail="; ".join(lines)[:8000], http_status=http_status)
        log.warning("Notebook validate failed  id=%s  err=%s", writer.notebook_id, message)
        return {
            "ok": False,
            "errors": lines,
            "message": message,
            "errorCount": len(lines),
            "httpStatus": http_status,
        }


def _format_field_errors(field_errors: list[dict]) -> list[str]:
    out = []
    for item in field_errors or []:
        name = item.get("field") or "config"
        msgs = [str(m) for m in (item.get("errors") or []) if m]
        out.append(f"{name}: {'; '.join(msgs)}" if msgs else str(name))
    return out or ["Kafka Connect rejected this config"]
