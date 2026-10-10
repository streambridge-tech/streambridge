"""Deploy a connector as a Strimzi KafkaConnector. Status stays on Kafka Connect."""

from __future__ import annotations

import requests

from app.services.connect.backend import DeploymentBackend
from app.services.connect.rest_backend import RestBackend, request_timeout, verify_ssl


_LIFTED = ("connector.class", "tasks.max", "name")


def connector_manifest(name: str, cluster: str, config: dict) -> dict:
    """Build the KafkaConnector body from a Connect config map."""
    raw = dict(config or {})
    plugin = str(raw.pop("connector.class", "") or "")
    tasks = raw.pop("tasks.max", None)
    raw.pop("name", None)
    spec_config = {k: v for k, v in raw.items() if v is not None and k not in _LIFTED}
    try:
        tasks_max = int(tasks) if tasks not in (None, "") else 1
    except (TypeError, ValueError):
        tasks_max = 1
    return {
        "apiVersion": "kafka.strimzi.io/v1",
        "kind": "KafkaConnector",
        "metadata": {
            "name": name,
            "labels": {"strimzi.io/cluster": cluster},
        },
        "spec": {
            "class": plugin,
            "tasksMax": tasks_max,
            "state": "running",
            "config": spec_config,
        },
    }


class KubernetesBackend(DeploymentBackend):
    """Create and update a KafkaConnector. Reads go to the Connect URL."""

    def __init__(self, kc_config: dict):
        self._config = kc_config or {}
        self._rest = RestBackend(self._config)
        self._api = str(self._config.get("api_host") or "").rstrip("/")
        self._namespace = str(self._config.get("namespace") or "").strip()
        self._cluster = str(self._config.get("cluster") or "").strip()
        self._token = str(self._config.get("api_token") or "")
        self._verify = verify_ssl(self._config)
        self._timeout = request_timeout(self._config)

    def _headers(self, content_type: str | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _collection(self) -> str:
        return (
            f"{self._api}/apis/kafka.strimzi.io/v1/namespaces/"
            f"{self._namespace}/kafkaconnectors"
        )

    def _object(self, name: str) -> str:
        return f"{self._collection()}/{name}"

    def _require(self) -> None:
        missing = [
            label for label, value in (
                ("api_host", self._api),
                ("namespace", self._namespace),
                ("cluster", self._cluster),
                ("api_token", self._token),
            ) if not value
        ]
        if missing:
            raise RuntimeError("Kubernetes connection is missing " + ", ".join(missing))

    def _fail(self, resp: requests.Response, action: str) -> None:
        if resp.status_code == 401:
            raise RuntimeError(f"Kubernetes API rejected the token (401) during {action}")
        if resp.status_code == 403:
            raise RuntimeError(
                f"Token cannot {action} connectors in namespace '{self._namespace}' (403)"
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Kubernetes API {action} failed ({resp.status_code}): {resp.text}"
            )

    def exists(self, connector_name: str) -> bool:
        self._require()
        resp = requests.get(
            self._object(connector_name),
            headers=self._headers(),
            timeout=self._timeout,
            verify=self._verify,
        )
        if resp.status_code == 200:
            return True
        if resp.status_code == 404:
            return False
        self._fail(resp, "read")
        return False

    def deploy(self, connector_name: str, config: dict) -> None:
        self._require()
        self._rest._validate_or_raise(config, connector_name)
        manifest = connector_manifest(connector_name, self._cluster, config)
        if self.exists(connector_name):
            resp = requests.patch(
                self._object(connector_name),
                json={"spec": manifest["spec"]},
                headers=self._headers("application/merge-patch+json"),
                timeout=self._timeout,
                verify=self._verify,
            )
            self._fail(resp, "update")
            return
        resp = requests.post(
            self._collection(),
            json=manifest,
            headers=self._headers("application/json"),
            timeout=self._timeout,
            verify=self._verify,
        )
        if resp.status_code == 409:
            resp = requests.patch(
                self._object(connector_name),
                json={"spec": manifest["spec"]},
                headers=self._headers("application/merge-patch+json"),
                timeout=self._timeout,
                verify=self._verify,
            )
            self._fail(resp, "update")
            return
        self._fail(resp, "create")

    def poll_status(self, connector_name: str) -> str:
        return self._rest.poll_status(connector_name)

    def delete(self, connector_name: str) -> None:
        self._require()
        resp = requests.delete(
            self._object(connector_name),
            headers=self._headers(),
            timeout=self._timeout,
            verify=self._verify,
        )
        if resp.status_code in (200, 202, 204, 404):
            return
        self._fail(resp, "delete")

    def _patch_state(self, name: str, state: str) -> None:
        self._require()
        resp = requests.patch(
            self._object(name),
            json={"spec": {"state": state}},
            headers=self._headers("application/merge-patch+json"),
            timeout=self._timeout,
            verify=self._verify,
        )
        self._fail(resp, state)

    def pause(self, name: str) -> None:
        self._patch_state(name, "paused")

    def resume(self, name: str) -> None:
        self._patch_state(name, "running")

    def get_status(self, name: str) -> dict:
        return self._rest.get_status(name)

    def get_config(self, name: str) -> dict:
        return self._rest.get_config(name)

    def get_offsets(self, name: str) -> dict:
        return self._rest.get_offsets(name)

    def list_tasks(self, name: str) -> list:
        return self._rest.list_tasks(name)

    def get_topics(self, name: str) -> dict:
        return self._rest.get_topics(name)

    def get_plugin_config(self, plugin_class: str) -> list:
        return self._rest.get_plugin_config(plugin_class)

    def restart(self, name: str, include_tasks: bool = False, only_failed: bool = False) -> dict:
        return self._rest.restart(name, include_tasks=include_tasks, only_failed=only_failed)

    def restart_task(self, name: str, task_id: int) -> None:
        self._rest.restart_task(name, task_id)

    def reset_offsets(self, name: str) -> dict:
        return self._rest.reset_offsets(name)

    def validate_config(self, plugin_class: str, config: dict, connector_name: str | None = None) -> dict:
        return self._rest.validate_config(plugin_class, config, connector_name=connector_name)
