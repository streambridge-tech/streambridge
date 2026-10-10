"""Deploy two MySQL connectors through StreamBridge and check both registries.

Requires the stack in .github/e2e/docker-compose.yml and StreamBridge on port 5000.
Exits non-zero when a connector does not reach RUNNING or a registry has no schema.
Deletes the connectors it created.
"""
from __future__ import annotations

import sys
import time

import requests

SB = "http://127.0.0.1:5000"
CONNECT = "http://127.0.0.1:8083"
APICURIO = "http://127.0.0.1:8080"
CONFLUENT = "http://127.0.0.1:8081"
CLUSTER = "ci-connect"
HEADERS = {"Content-Type": "application/json", "Origin": SB}

COMMON = {
    "connector.class": "io.debezium.connector.mysql.MySqlConnector",
    "tasks.max": "1",
    "database.hostname": "mysql",
    "database.port": "3306",
    "database.user": "debezium",
    "database.password": "dbz",
    "database.ssl.mode": "disabled",
    "database.include.list": "inventory",
    "table.include.list": "inventory.customers",
    "schema.history.internal.kafka.bootstrap.servers": "kafka:9092",
    "schema.name.adjustment.mode": "avro",
    "include.schema.changes": "false",
}

APICURIO_CONV = {
    "key.converter": "io.apicurio.registry.utils.converter.AvroConverter",
    "key.converter.apicurio.registry.url": "http://registry:8080/apis/registry/v2",
    "key.converter.apicurio.registry.auto-register": "true",
    "key.converter.apicurio.registry.find-latest": "true",
    "value.converter": "io.apicurio.registry.utils.converter.AvroConverter",
    "value.converter.apicurio.registry.url": "http://registry:8080/apis/registry/v2",
    "value.converter.apicurio.registry.auto-register": "true",
    "value.converter.apicurio.registry.find-latest": "true",
}
CONFLUENT_CONV = {
    "key.converter": "io.confluent.connect.avro.AvroConverter",
    "key.converter.schema.registry.url": "http://schema-registry:8081",
    "value.converter": "io.confluent.connect.avro.AvroConverter",
    "value.converter.schema.registry.url": "http://schema-registry:8081",
}
UNWRAP = {
    "transforms": "unwrap",
    "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
    "transforms.unwrap.drop.tombstones": "false",
    "transforms.unwrap.delete.handling.mode": "drop",
}

# name, server id, topic prefix, history topic, extra config, registry check
CONNECTORS = (
    (
        "sb-ci-apicurio",
        "18401",
        "sbciapic",
        "sb-ci-apic-hist",
        {**APICURIO_CONV, **UNWRAP},
        "apicurio",
    ),
    (
        "sb-ci-confluent",
        "18402",
        "sbciconf",
        "sb-ci-conf-hist",
        CONFLUENT_CONV,
        "confluent",
    ),
)

CONNECTOR_CLASS = "io.debezium.connector.mysql.MySqlConnector"


def _fail(message: str) -> None:
    print(f"FAIL {message}", file=sys.stderr)


def _json(response: requests.Response):
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text[:500]}


def setup_workspace() -> None:
    status = requests.get(f"{SB}/api/auth/status", timeout=10)
    status.raise_for_status()
    body = status.json()
    if body.get("mode") == "personal" and not body.get("authEnabled"):
        return
    created = requests.post(
        f"{SB}/api/auth/setup",
        headers=HEADERS,
        json={"mode": "personal", "displayName": "ci"},
        timeout=20,
    )
    if created.status_code not in (200, 201):
        raise RuntimeError(f"workspace setup http={created.status_code} body={_json(created)}")


def create_connection() -> None:
    created = requests.post(
        f"{SB}/api/connections",
        headers=HEADERS,
        json={
            "name": CLUSTER,
            "type": "connect",
            "subtype": "kafka-connect",
            "deployment": "connect",
            "url": CONNECT,
            "auth_type": "none",
        },
        timeout=20,
    )
    if created.status_code == 409:
        return
    if created.status_code not in (200, 201):
        raise RuntimeError(f"connection create http={created.status_code} body={_json(created)}")


def require_plugins() -> None:
    """Connect's plugin list contains connectors, not converters.

    A missing Avro converter still fails here: config validation reports that
    the class could not be found.
    """
    listed = requests.get(f"{CONNECT}/connector-plugins", timeout=20)
    listed.raise_for_status()
    classes = {row.get("class") for row in listed.json()}
    if CONNECTOR_CLASS not in classes:
        raise RuntimeError(f"Connect is missing {CONNECTOR_CLASS}")
    require_converter(
        "io.apicurio.registry.utils.converter.AvroConverter",
        {
            "key.converter.apicurio.registry.url": "http://registry:8080/apis/registry/v2",
            "value.converter.apicurio.registry.url": "http://registry:8080/apis/registry/v2",
            "key.converter.apicurio.registry.auto-register": "true",
            "value.converter.apicurio.registry.auto-register": "true",
        },
    )
    require_converter(
        "io.confluent.connect.avro.AvroConverter",
        {
            "key.converter.schema.registry.url": "http://schema-registry:8081",
            "value.converter.schema.registry.url": "http://schema-registry:8081",
        },
    )


def require_converter(converter: str, extra: dict) -> None:
    config = {
        "connector.class": CONNECTOR_CLASS,
        "key.converter": converter,
        "value.converter": converter,
        **extra,
    }
    response = requests.put(
        f"{CONNECT}/connector-plugins/{CONNECTOR_CLASS}/config/validate",
        json=config,
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(f"validate {converter} http={response.status_code} body={_json(response)}")
    missing = []
    for item in response.json().get("configs") or []:
        value = item.get("value") or {}
        if value.get("name") not in ("key.converter", "value.converter"):
            continue
        for error in value.get("errors") or []:
            if "could not be found" in str(error).lower():
                missing.append(str(error))
    if missing:
        raise RuntimeError(f"{converter} is not loadable: {missing[0]}")
    print(f"converter loadable {converter}")


def deploy(name: str, server_id: str, prefix: str, history: str, extra: dict) -> str:
    config = dict(COMMON)
    config.update({
        "database.server.id": server_id,
        "topic.prefix": prefix,
        "schema.history.internal.kafka.topic": history,
    })
    config.update(extra)
    created = requests.post(
        f"{SB}/api/notebooks/",
        headers=HEADERS,
        json={
            "name": name,
            "folder": "ci-e2e",
            "attachedCluster": CLUSTER,
            "doc": {"name": name, "config": config},
        },
        timeout=20,
    )
    if created.status_code not in (200, 201):
        raise RuntimeError(f"{name} create http={created.status_code} body={_json(created)}")
    notebook_id = created.json()["id"]
    deployed = requests.post(
        f"{SB}/api/notebooks/{notebook_id}/deploy",
        headers=HEADERS,
        json={},
        timeout=90,
    )
    body = _json(deployed)
    state = (body.get("result") or {}).get("state")
    print(f"{name} deploy http={deployed.status_code} ok={body.get('ok')} state={state}")
    if deployed.status_code != 200 or not body.get("ok") or state != "RUNNING":
        raise RuntimeError(f"{name} did not reach RUNNING: {body.get('error') or body}")
    return notebook_id


def wait_for_registry(kind: str, prefix: str) -> None:
    deadline = time.time() + 90
    last = None
    while time.time() < deadline:
        if kind == "apicurio":
            response = requests.get(
                f"{APICURIO}/apis/registry/v2/search/artifacts",
                params={"limit": 50},
                timeout=10,
            )
            if response.ok:
                artifacts = response.json().get("artifacts") or []
                matched = [row for row in artifacts if prefix in str(row)]
                last = artifacts[:5]
                if matched:
                    print(f"apicurio schema registered for {prefix}")
                    return
        else:
            response = requests.get(f"{CONFLUENT}/subjects", timeout=10)
            if response.ok:
                subjects = response.json()
                matched = [name for name in subjects if str(name).startswith(prefix)]
                last = subjects
                if matched:
                    print(f"confluent subjects {matched}")
                    return
        time.sleep(3)
    raise RuntimeError(f"{kind} registry has no schema for {prefix}; last={last}")


def cleanup(names: list[str], notebook_ids: list[str]) -> None:
    for name in names:
        try:
            response = requests.delete(f"{CONNECT}/connectors/{name}", timeout=20)
            print(f"delete connector {name} http={response.status_code}")
        except requests.RequestException as exc:
            print(f"delete connector {name} failed: {exc}", file=sys.stderr)
    for notebook_id in notebook_ids:
        try:
            response = requests.delete(f"{SB}/api/notebooks/{notebook_id}", headers=HEADERS, timeout=20)
            print(f"delete notebook {notebook_id} http={response.status_code}")
        except requests.RequestException as exc:
            print(f"delete notebook {notebook_id} failed: {exc}", file=sys.stderr)


def main() -> int:
    names = [row[0] for row in CONNECTORS]
    notebook_ids: list[str] = []
    try:
        setup_workspace()
        create_connection()
        require_plugins()
        for name, server_id, prefix, history, extra, kind in CONNECTORS:
            notebook_ids.append(deploy(name, server_id, prefix, history, extra))
            wait_for_registry(kind, prefix)
    except Exception as exc:
        _fail(str(exc))
        return 1
    finally:
        cleanup(names, notebook_ids)
    print("end to end ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
