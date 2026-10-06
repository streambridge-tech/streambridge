from __future__ import annotations

from app.models.connector_command_log import ConnectorCommandLog
from app.utils.logger import get_logger

log = get_logger("app.services.notebooks")

STEP_SAVE = "save_config"
STEP_SECRETS = "resolve_secrets"
STEP_VALIDATE = "validate_config"
STEP_DEPLOY = "deploy_connector"
STEP_API = "api"

STEP_LABELS = {
    STEP_SAVE: "Saving config",
    STEP_SECRETS: "Resolving the secrets",
    STEP_VALIDATE: "Validating with Kafka Connect",
    STEP_DEPLOY: "Deploying connector",
    STEP_API: "API command",
}


class CommandLogWriter:
    """Persist Logs-tab rows and emit the same event to the app logger."""

    def __init__(self, db, notebook_id: str):
        self.db = db
        self.notebook_id = notebook_id

    def record(
        self,
        step: str,
        status: str,
        *,
        message: str | None = None,
        detail: str | None = None,
        http_status: int | None = None,
        latency_ms: int = 0,
    ) -> ConnectorCommandLog:
        label = message or STEP_LABELS.get(step, step.replace("_", " "))
        row = ConnectorCommandLog(
            notebook_id=self.notebook_id,
            step=step,
            message=label,
            status=status,
            detail=(detail or "")[:8000] or None,
            http_status=http_status,
            latency_ms=max(0, int(latency_ms)),
        )
        self.db.add(row)
        self.db.flush()
        log.info(
            "Notebook step  id=%s  step=%s  status=%s  http=%s  %s",
            self.notebook_id,
            step,
            status,
            http_status if http_status is not None else "-",
            label,
        )
        return row
