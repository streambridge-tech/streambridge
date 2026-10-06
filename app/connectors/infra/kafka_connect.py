import requests

from app.connectors.base import BaseConnector
from app.connectors.schemas import build_kc_config, defaults_kc_config
from app.connectors.schemas.kafka_connect import KAFKA_CONNECT_SCHEMA
from app.services.connect.factory import deployment_of
from app.utils.logger import get_logger

log = get_logger(__name__)


class KafkaConnectConnector(BaseConnector):

    SUBTYPE = "kafka-connect"
    TYPE    = "connect"  # API type sent by frontend
    SCHEMA  = KAFKA_CONNECT_SCHEMA

    REQUIRED_FIELDS = [
        "url",
    ]

    OPTIONAL_FIELDS = [
        "username",
        "password",
    ]

    def validate(self, data: dict) -> list[str]:
        errors = []
        for field in self.REQUIRED_FIELDS:
            if not data.get(field):
                errors.append(f"'{field}' is required")
        if str(data.get("auth_type") or "").lower() == "basic":
            if not data.get("username"):
                errors.append("'username' is required")
            if not data.get("password"):
                errors.append("'password' is required")
        if deployment_of(data) == "kubernetes":
            for field in ("api_host", "namespace", "cluster", "api_token"):
                if not data.get(field):
                    errors.append(f"'{field}' is required")
        return errors

    def build_config(self, form: dict, extra: dict) -> dict:
        config = defaults_kc_config(self.SCHEMA)
        config.update(build_kc_config(self.SCHEMA, form))
        config.update({k: str(v) for k, v in (extra or {}).items() if v != ""})
        # Older forms send a username and password without an auth type.
        if not (form or {}).get("auth_type") and config.get("username") and config.get("password"):
            config["auth_type"] = "basic"
        return config

    def test_connection(self, config: dict) -> dict:
        connect = _test_connect(config)
        if deployment_of(config) != "kubernetes":
            return connect
        kubernetes = _test_kubernetes(config)
        if not kubernetes["success"]:
            return kubernetes
        if not connect["success"]:
            return {"success": False, "message": "Kubernetes API ok. " + connect["message"]}
        return {"success": True, "message": "Kubernetes API and Kafka Connect are reachable"}


def _verify(config: dict) -> bool:
    raw = str(config.get("verify.ssl", "true")).lower()
    return raw in ("true", "1", "yes", "on")


def _timeout(config: dict) -> int:
    try:
        return int(config.get("timeout") or 10)
    except (TypeError, ValueError):
        return 10


def _auth(config: dict):
    kind = str(config.get("auth_type") or "").lower()
    username = config.get("username") or ""
    password = config.get("password") or ""
    if kind == "none" or not username or not password:
        return None
    if kind in ("", "basic"):
        return (username, password)
    return None


def _test_connect(config: dict) -> dict:
    url = str(config.get("url") or "").rstrip("/")
    log.info("Testing Kafka Connect REST API  url=%s", url)
    if not url:
        return {"success": False, "message": "Connect URL is required"}
    try:
        resp = requests.get(
            url + "/connectors",
            auth=_auth(config),
            timeout=_timeout(config),
            verify=_verify(config),
        )
    except requests.RequestException as exc:
        return {"success": False, "message": str(exc)}
    if resp.status_code == 401:
        return {"success": False, "message": f"Kafka Connect rejected the username or password (401) at {url}"}
    if resp.status_code >= 400:
        return {"success": False, "message": f"Kafka Connect returned {resp.status_code} at {url}"}
    return {"success": True, "message": f"Kafka Connect reachable at {url}"}


def _test_kubernetes(config: dict) -> dict:
    host = str(config.get("api_host") or "").rstrip("/")
    namespace = str(config.get("namespace") or "").strip()
    token = str(config.get("api_token") or "")
    if not host or not namespace or not token:
        return {"success": False, "message": "Kubernetes API host, namespace, and bearer token are required"}
    url = f"{host}/apis/kafka.strimzi.io/v1/namespaces/{namespace}/kafkaconnectors"
    log.info("Testing Kubernetes API  namespace=%s", namespace)
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=_timeout(config),
            verify=_verify(config),
        )
    except requests.RequestException as exc:
        return {"success": False, "message": str(exc)}
    if resp.status_code == 401:
        return {"success": False, "message": "Kubernetes API rejected the token (401)"}
    if resp.status_code == 403:
        return {"success": False, "message": f"Token cannot list connectors in namespace '{namespace}' (403)"}
    if resp.status_code >= 400:
        return {"success": False, "message": f"Kubernetes API returned {resp.status_code}"}
    return {"success": True, "message": f"Kubernetes API reachable in namespace {namespace}"}
