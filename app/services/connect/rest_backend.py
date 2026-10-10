import requests
from requests import RequestException  # bound at import so a stubbed `requests` keeps it

from app.services.connect.backend import DeploymentBackend

DEFAULT_TIMEOUT = 10  # seconds per request


def verify_ssl(kc_config: dict) -> bool:
    """`verify.ssl` from a Kafka Connect connection. TLS is verified unless it is switched off."""
    raw = str(kc_config.get("verify.ssl", "true")).lower()
    return raw in ("true", "1", "yes", "on")


def request_timeout(kc_config: dict) -> int:
    """`timeout` seconds from a Kafka Connect connection, or the default."""
    try:
        return int(kc_config.get("timeout") or DEFAULT_TIMEOUT)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT


class ConfigValidationError(RuntimeError):
    """Raised when Kafka Connect's /validate endpoint reports one or more field errors.

    Carries a structured list of `{field, value, errors}` so callers (orchestrator,
    API layer) can render them without re-parsing free-form messages.
    """
    def __init__(self, plugin_class: str, field_errors: list[dict]):
        self.plugin_class = plugin_class
        self.field_errors = field_errors
        summary = ", ".join(f"{fe['field']}: {fe['errors'][0]}" for fe in field_errors[:3])
        more = "" if len(field_errors) <= 3 else f" (+{len(field_errors) - 3} more)"
        super().__init__(f"Kafka Connect rejected the '{plugin_class}' config — {summary}{more}")


class RestBackend(DeploymentBackend):
    """Kafka Connect REST API backend.

    Uses `POST /connectors` for new connectors and `PUT /connectors/{name}/config`
    to update existing ones. State comes from `GET /connectors/{name}/status`.
    RUNNING means the connector and every task are RUNNING. Any FAILED task
    makes the overall state FAILED even if the connector itself is RUNNING.
    """

    def __init__(self, kc_config: dict):
        self._url = (kc_config.get("url") or "").rstrip("/")
        self._auth: tuple[str, str] | None = None
        username = kc_config.get("username")
        password = kc_config.get("password")
        if username and password:
            self._auth = (username, password)
        self._verify = verify_ssl(kc_config)
        self._timeout = request_timeout(kc_config)

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Call Connect with the connection's auth, TLS verification and timeout."""
        send = getattr(requests, method)
        return send(
            f"{self._url}{path}",
            auth=self._auth, verify=self._verify, timeout=self._timeout, **kwargs,
        )

    def exists(self, connector_name: str) -> bool:
        resp = self._request("get", f"/connectors/{connector_name}")
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False
        raise RuntimeError(
            f"Kafka Connect returned {resp.status_code} for GET /connectors/{connector_name}: {resp.text}"
        )

    def deploy(self, connector_name: str, config: dict) -> None:
        # Fail-fast on config problems Kafka Connect can already tell us about.
        # We do this before create/update so the caller sees precise field errors
        # instead of a generic 500 from POST /connectors.
        self._validate_or_raise(config, connector_name)
        if self.exists(connector_name):
            resp = self._request("put", f"/connectors/{connector_name}/config", json=config)
        else:
            resp = self._request("post", "/connectors", json={"name": connector_name, "config": config})
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Kafka Connect deploy failed ({resp.status_code}) for '{connector_name}': {resp.text}"
            )

    def _validate_or_raise(self, config: dict, connector_name: str | None = None) -> None:
        plugin_class = config.get("connector.class")
        if not plugin_class:
            return  # let deploy 400 it — nothing to validate against
        try:
            report = self.validate_config(plugin_class, config, connector_name=connector_name)
        except RuntimeError:
            # Plugin not installed or KC rejected the call — surface that on the deploy call instead.
            return
        except RequestException as exc:
            raise RuntimeError(f"Kafka Connect validate failed for '{plugin_class}': {exc}") from exc
        field_errors = _extract_field_errors(report)
        if field_errors:
            raise ConfigValidationError(plugin_class, field_errors)

    def poll_status(self, connector_name: str) -> str:
        resp = self._request("get", f"/connectors/{connector_name}/status")
        if resp.status_code == 404:
            return "UNKNOWN"
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Kafka Connect status failed ({resp.status_code}) for '{connector_name}': {resp.text}"
            )
        return effective_connect_status(resp.json())

    def delete(self, connector_name: str) -> None:
        resp = self._request("delete", f"/connectors/{connector_name}")
        if resp.status_code not in (200, 204, 404):
            raise RuntimeError(
                f"Kafka Connect delete failed ({resp.status_code}) for '{connector_name}': {resp.text}"
            )

    # ── read-only inspection ─────────────────────────────────────────────
    def get_status(self, name: str) -> dict:
        return self._get(f"/connectors/{name}/status")

    def get_config(self, name: str) -> dict:
        return self._get(f"/connectors/{name}/config")

    def get_offsets(self, name: str) -> dict:
        return self._get(f"/connectors/{name}/offsets")

    def list_tasks(self, name: str) -> list:
        return self._get(f"/connectors/{name}/tasks")

    def get_topics(self, name: str) -> dict:
        return self._get(f"/connectors/{name}/topics")

    def get_plugin_config(self, plugin_class: str) -> list:
        return self._get(f"/connector-plugins/{plugin_class}/config")

    # ── lifecycle ────────────────────────────────────────────────────────
    def pause(self, name: str) -> None:
        self._put_no_body(f"/connectors/{name}/pause", ok=(202,))

    def resume(self, name: str) -> None:
        self._put_no_body(f"/connectors/{name}/resume", ok=(202,))

    def restart(self, name: str, include_tasks: bool = False, only_failed: bool = False) -> dict:
        params = {"includeTasks": str(include_tasks).lower(),
                  "onlyFailed":   str(only_failed).lower()}
        resp = self._request("post", f"/connectors/{name}/restart", params=params)
        if resp.status_code not in (200, 202, 204):
            raise RuntimeError(
                f"Kafka Connect restart failed ({resp.status_code}) for '{name}': {resp.text}"
            )
        return resp.json() if resp.text else {}

    def restart_task(self, name: str, task_id: int) -> None:
        resp = self._request("post", f"/connectors/{name}/tasks/{int(task_id)}/restart")
        if resp.status_code not in (200, 204):
            raise RuntimeError(
                f"Kafka Connect restart task {task_id} failed ({resp.status_code}) for '{name}': {resp.text}"
            )

    # ── offset management (KC 3.6+) ──────────────────────────────────────
    def reset_offsets(self, name: str) -> dict:
        resp = self._request("delete", f"/connectors/{name}/offsets")
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Kafka Connect reset offsets failed ({resp.status_code}) for '{name}': {resp.text}"
            )
        return resp.json() if resp.text else {"message": "Offsets reset"}

    # ── validation ───────────────────────────────────────────────────────
    def validate_config(self, plugin_class: str, config: dict, connector_name: str | None = None) -> dict:
        body = dict(config or {})
        name = str(body.get("name") or connector_name or "").strip()
        if name:
            body["name"] = name
        resp = self._request("put", f"/connector-plugins/{plugin_class}/config/validate", json=body)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Kafka Connect validate failed ({resp.status_code}) for '{plugin_class}': {resp.text}"
            )
        return resp.json()

    # ── internal helpers ─────────────────────────────────────────────────
    def _get(self, path: str):
        resp = self._request("get", path)
        if resp.status_code == 404:
            raise RuntimeError(f"Not found: {path}")
        if resp.status_code >= 400:
            raise RuntimeError(f"Kafka Connect GET {path} failed ({resp.status_code}): {resp.text}")
        return resp.json()

    def _put_no_body(self, path: str, ok: tuple):
        resp = self._request("put", path)
        if resp.status_code not in ok and resp.status_code >= 400:
            raise RuntimeError(f"Kafka Connect PUT {path} failed ({resp.status_code}): {resp.text}")


def effective_connect_status(data: dict) -> str:
    """Overall state from GET /connectors/{name}/status.

    RUNNING only if the connector is RUNNING and every available task is RUNNING.
    """
    if not isinstance(data, dict):
        return "UNKNOWN"
    connector = str((data.get("connector") or {}).get("state") or "UNKNOWN").upper()
    task_states = [str((t or {}).get("state") or "UNKNOWN").upper() for t in (data.get("tasks") or [])]
    if connector == "FAILED" or any(s == "FAILED" for s in task_states):
        return "FAILED"
    if connector == "RUNNING" and task_states and all(s == "RUNNING" for s in task_states):
        return "RUNNING"
    if connector == "PAUSED" or any(s == "PAUSED" for s in task_states):
        return "PAUSED"
    if connector == "RUNNING" and not task_states:
        return "UNKNOWN"
    non_running = [s for s in task_states if s != "RUNNING"]
    if non_running:
        return non_running[0]
    return connector or "UNKNOWN"


def _extract_field_errors(validate_report: dict) -> list[dict]:
    """Walk a KC /validate response and return `[{field, value, errors}]` for fields with errors.

    KC 3.x validate response shape:
        {"name": "…", "error_count": N, "groups": [...],
         "configs": [{"definition": {...}, "value": {"name": "x", "value": "y", "errors": [...]}}]}
    """
    if not isinstance(validate_report, dict):
        return []
    if int(validate_report.get("error_count") or 0) == 0:
        return []
    out: list[dict] = []
    for entry in validate_report.get("configs") or []:
        val = (entry or {}).get("value") or {}
        errs = val.get("errors") or []
        if not errs:
            continue
        out.append({
            "field":  val.get("name") or (entry.get("definition") or {}).get("name"),
            "value":  val.get("value"),
            "errors": list(errs),
        })
    return out
