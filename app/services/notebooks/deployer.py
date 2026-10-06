from __future__ import annotations

import time
from datetime import datetime, timezone

from app.models.connection import Connection
from app.models.connector_notebook import ConnectorNotebook
from app.models.vault import Vault
from app.services.connect.factory import get_backend
from app.services.notebooks.logs import STEP_DEPLOY, STEP_SAVE, STEP_SECRETS, CommandLogWriter
from app.services.notebooks.secrets import SecretResolver
from app.utils.logger import get_logger

log = get_logger("app.services.notebooks")

_OK_STATES = {"RUNNING", "PAUSED"}


class NotebookDeployError(Exception):
    def __init__(self, step: str, message: str):
        super().__init__(message)
        self.step = step
        self.message = message


class NotebookDeployer:
    """Save → resolve secrets → Kafka Connect deploy, with persisted step logs."""

    def __init__(self, db, get_backend_fn=get_backend, sleep=time.sleep, poll_timeout=20, poll_interval=1):
        self.db = db
        self._get_backend = get_backend_fn
        self._sleep = sleep
        self._poll_timeout = poll_timeout
        self._poll_interval = poll_interval

    def deploy(self, notebook: ConnectorNotebook) -> dict:
        writer = CommandLogWriter(self.db, notebook.id)
        started = time.perf_counter()
        writer.record(STEP_SAVE, "ok", detail=f"Saved notebook '{notebook.name}'")

        cluster = (notebook.attached_cluster or "").strip()
        if not cluster:
            raise self._abort(notebook, writer, STEP_DEPLOY, "Attach a Kafka Connect cluster first", 400)

        kc = self.db.query(Connection).filter(Connection.name == cluster).first()
        if not kc:
            raise self._abort(notebook, writer, STEP_DEPLOY, f"Kafka Connect connection '{cluster}' not found", 404)
        type_ = str(kc.type or "").lower()
        subtype = str(kc.subtype or "").lower()
        if type_ != "connect" and "kafka-connect" not in subtype:
            raise self._abort(notebook, writer, STEP_DEPLOY, f"'{cluster}' is not a Kafka Connect connection", 400)

        resolver = SecretResolver(self.db.query(Vault).all())
        config = (notebook.doc() or {}).get("config") or {}
        if not isinstance(config, dict):
            raise self._abort(notebook, writer, STEP_SECRETS, "Config must be a JSON object with a config map", 400)

        try:
            resolved, missing, ref_count = resolver.resolve_config(config)
        except ValueError as exc:
            raise self._abort(notebook, writer, STEP_SECRETS, str(exc), 400) from exc

        if missing:
            raise self._abort(notebook, writer, STEP_SECRETS, f"Missing secrets: {', '.join(missing)}", 400)

        writer.record(
            STEP_SECRETS,
            "ok",
            detail=f"Resolved {ref_count} secret ref(s)" if ref_count else "No secret refs",
        )

        name = notebook.name
        try:
            backend = self._get_backend(kc.config or {})
            backend.deploy(name, resolved)
            state = self._poll(backend, name)
        except NotebookDeployError:
            raise
        except Exception as exc:
            raise self._abort(notebook, writer, STEP_DEPLOY, str(exc), 502) from exc

        latency = int((time.perf_counter() - started) * 1000)
        ok = state in _OK_STATES
        status = "ok" if ok else "error"
        detail = f"Kafka Connect state {state}"
        writer.record(STEP_DEPLOY, status, detail=detail, http_status=200 if ok else 502, latency_ms=latency)
        if ok:
            self._mark(notebook, "success", None)
            notebook.bound = True
            log.info("Notebook deployed  id=%s  connector=%s  cluster=%s  state=%s", notebook.id, name, cluster, state)
        else:
            self._mark(notebook, "failed", detail)
            raise NotebookDeployError(STEP_DEPLOY, detail)
        return {"state": state, "cluster": cluster, "name": name, "status": "success"}

    def _poll(self, backend, name: str) -> str:
        deadline = time.time() + self._poll_timeout
        state = "UNKNOWN"
        while True:
            state = str(backend.poll_status(name) or "UNKNOWN").upper()
            if state in _OK_STATES or state == "FAILED":
                return state
            if time.time() >= deadline:
                return state
            self._sleep(self._poll_interval)

    def _abort(self, notebook, writer, step, message, http_status) -> NotebookDeployError:
        writer.record(step, "error", detail=message, http_status=http_status)
        self._mark(notebook, "failed", message)
        return NotebookDeployError(step, message)

    def _mark(self, notebook: ConnectorNotebook, status: str, error: str | None) -> None:
        notebook.last_deploy_status = status
        notebook.last_deploy_error = (error or "")[:2000] or None
        notebook.last_deployed_at = datetime.now(timezone.utc)
