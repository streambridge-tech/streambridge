"""End-to-end test of MySQL connectors through StreamBridge against the Docker stack.

Deploys 4 connectors via StreamBridge's own API (create notebook -> deploy),
covering Apicurio + Confluent schema registries and 3 SMT/transformation levels.
Does NOT delete anything.

Run: .venv/bin/python sandbox/ec2/e2e/e2e_test.py
Requires: docker-compose stack in sandbox/ec2/schema_registry/connector_with_schema_registry
          and a StreamBridge "docker-connect" connection -> http://localhost:8083.
"""
import json
import time
import requests

SB = "http://localhost:5000"
H = {"Content-Type": "application/json", "Origin": SB}
CLUSTER = "docker-connect"

COMMON = {
    "connector.class": "io.debezium.connector.mysql.MySqlConnector",
    "tasks.max": "1",
    "database.hostname": "mysql",
    "database.port": "3306",
    "database.user": "root",
    "database.password": "debezium",
    "database.whitelist": "inventory",
    "table.whitelist": "inventory.customers",
    "database.history.kafka.bootstrap.servers": "kafka:9092",
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
    "predicates": "isTombstone",
    "predicates.isTombstone.type": "org.apache.kafka.connect.transforms.predicates.RecordIsTombstone",
}
ROUTE = {
    "transforms": "unwrap,route",
    "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
    "transforms.unwrap.drop.tombstones": "false",
    "transforms.unwrap.delete.handling.mode": "drop",
    "transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
    "transforms.route.regex": "(.*)",
    "transforms.route.replacement": "routed_$1",
    "predicates": "isTombstone",
    "predicates.isTombstone.type": "org.apache.kafka.connect.transforms.predicates.RecordIsTombstone",
}

# name -> (server_id, server_name, history_topic, converter, transforms, label)
CONNECTORS = {
    "sb-mysql-apicurio-unwrap":   ("55001", "sbapic",      "sb-apic-hist",      APICURIO_CONV, UNWRAP, "Apicurio Avro + unwrap"),
    "sb-mysql-confluent-unwrap":  ("55002", "sbconf",      "sb-conf-hist",      CONFLUENT_CONV, UNWRAP, "Confluent Avro + unwrap"),
    "sb-mysql-confluent-raw":     ("55003", "sbconfraw",   "sb-confraw-hist",   CONFLUENT_CONV, {},     "Confluent Avro + NO transform (raw envelope)"),
    "sb-mysql-confluent-route":   ("55004", "sbconfroute", "sb-confroute-hist", CONFLUENT_CONV, ROUTE,  "Confluent Avro + unwrap + RegexRouter"),
}


def build_config(server_id, server_name, hist, conv, xform):
    cfg = dict(COMMON)
    cfg["database.server.id"] = server_id
    cfg["database.server.name"] = server_name
    cfg["database.history.kafka.topic"] = hist
    cfg.update(conv)
    cfg.update(xform)
    return cfg


results = {}
for name, (sid, sname, hist, conv, xform, label) in CONNECTORS.items():
    cfg = build_config(sid, sname, hist, conv, xform)
    # create notebook
    r = requests.post(f"{SB}/api/notebooks/", headers=H, json={
        "name": name, "folder": "docker-e2e", "attachedCluster": CLUSTER,
        "doc": {"name": name, "config": cfg},
    })
    if r.status_code not in (200, 201):
        results[name] = {"step": "create", "http": r.status_code, "body": r.text[:200]}
        continue
    nb_id = r.json()["id"]
    # deploy via StreamBridge
    d = requests.post(f"{SB}/api/notebooks/{nb_id}/deploy", headers=H, json={})
    dj = d.json()
    results[name] = {
        "label": label, "notebook": nb_id, "deployHttp": d.status_code,
        "ok": dj.get("ok"), "state": (dj.get("result") or {}).get("state"),
        "error": dj.get("error"),
    }
    print(f"{name:28s} [{label}]")
    print(f"    deploy http={d.status_code} ok={dj.get('ok')} state={(dj.get('result') or {}).get('state')} err={dj.get('error')}")

print("\n=== summary ===")
print(json.dumps(results, indent=1))
