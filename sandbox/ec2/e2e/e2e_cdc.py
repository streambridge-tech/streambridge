"""Prove transformation differences via registered Avro schemas, and test live CDC.

Run: .venv/bin/python sandbox/ec2/e2e/e2e_cdc.py
"""
import json
import subprocess
import time
import requests

SR = "http://localhost:8081"
KAFKA_CONTAINER = "connector_with_schema_registry-kafka-1"
MYSQL_CONTAINER = "mysql-cdc"


def value_fields(subject):
    r = requests.get(f"{SR}/subjects/{subject}/versions/latest")
    if r.status_code != 200:
        return None, r.status_code
    sch = json.loads(r.json()["schema"])
    return [f["name"] for f in sch.get("fields", [])], 200


print("=== Transformation shape (Confluent value schemas) ===")
raw_fields, _ = value_fields("sbconfraw.inventory.customers-value")
unwrap_fields, _ = value_fields("sbconf.inventory.customers-value")
route_fields, _ = value_fields("routed_sbconfroute.inventory.customers-value")
print("  RAW (no transform) top-level fields:", raw_fields)
print("  UNWRAP top-level fields           :", unwrap_fields)
print("  ROUTE (unwrap+router) fields      :", route_fields)
print("  => raw has Debezium envelope (before/after/op):",
      bool(raw_fields and {"before", "after", "op"} <= set(raw_fields)))
print("  => unwrap is flattened row (id/first_name...):",
      bool(unwrap_fields and "id" in unwrap_fields and "before" not in unwrap_fields))


def count(topic):
    out = subprocess.run(
        ["docker", "exec", KAFKA_CONTAINER,
         "/kafka/bin/kafka-run-class.sh", "kafka.tools.GetOffsetShell",
         "--broker-list", "kafka:9092", "--topic", topic],
        capture_output=True, text=True, timeout=30)
    return sum(int(l.rsplit(":", 1)[1]) for l in out.stdout.splitlines()
              if l.rsplit(":", 1)[-1].strip().isdigit())


print("\n=== Live CDC: insert a row, expect message counts to grow ===")
topics = {
    "unwrap": "sbconf.inventory.customers",
    "raw": "sbconfraw.inventory.customers",
    "route": "routed_sbconfroute.inventory.customers",
    "apicurio": "sbapic.inventory.customers",
}
before = {k: count(t) for k, t in topics.items()}
print("  before:", before)

ins = subprocess.run(
    ["docker", "exec", MYSQL_CONTAINER, "mysql", "-uroot", "-pdebezium", "-e",
     "INSERT INTO inventory.customers (first_name,last_name,email) "
     "VALUES ('E2E','Tester','e2e.tester@streambridge.test');"],
    capture_output=True, text=True, timeout=30)
print("  insert rc:", ins.returncode, (ins.stderr or "").strip()[:120])

time.sleep(5)
after = {k: count(t) for k, t in topics.items()}
print("  after :", after)
for k in topics:
    print(f"    {k:9s} {before[k]} -> {after[k]}  {'OK (+%d)' % (after[k]-before[k]) if after[k] > before[k] else 'no change'}")
