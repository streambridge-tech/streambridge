"""Verify the deployed connectors end-to-end: StreamBridge status, topics,
schema-registry registration (Apicurio + Confluent), and message counts.

Run: .venv/bin/python sandbox/ec2/e2e/e2e_verify.py
"""
import json
import subprocess
import requests

SB = "http://localhost:5000"
H = {"Content-Type": "application/json", "Origin": SB}
CLUSTER = "docker-connect"
KAFKA_CONTAINER = "connector_with_schema_registry-kafka-1"

CONNECTORS = {
    "sb-mysql-apicurio-unwrap":  "sbapic.inventory.customers",
    "sb-mysql-confluent-unwrap": "sbconf.inventory.customers",
    "sb-mysql-confluent-raw":    "sbconfraw.inventory.customers",
    "sb-mysql-confluent-route":  "routed_sbconfroute.inventory.customers",
}


def sb_status(name):
    r = requests.post(f"{SB}/api/kc/connections/{CLUSTER}/connectors/{name}/status", headers=H, json={})
    d = r.json().get("data", {})
    conn = (d.get("connector") or {}).get("state")
    tasks = [t.get("state") for t in d.get("tasks") or []]
    return conn, tasks


def kafka_topics():
    out = subprocess.run(
        ["docker", "exec", KAFKA_CONTAINER,
         "/kafka/bin/kafka-topics.sh", "--bootstrap-server", "kafka:9092", "--list"],
        capture_output=True, text=True, timeout=30)
    return out.stdout.splitlines()


def topic_count(topic):
    out = subprocess.run(
        ["docker", "exec", KAFKA_CONTAINER,
         "/kafka/bin/kafka-run-class.sh", "kafka.tools.GetOffsetShell",
         "--broker-list", "kafka:9092", "--topic", topic],
        capture_output=True, text=True, timeout=30)
    total = 0
    for line in out.stdout.splitlines():
        parts = line.rsplit(":", 1)
        if len(parts) == 2 and parts[1].strip().isdigit():
            total += int(parts[1].strip())
    return total


print("=== 1) StreamBridge status + tasks (read path) ===")
for name in CONNECTORS:
    conn, tasks = sb_status(name)
    print(f"  {name:28s} connector={conn}  tasks={tasks}")

print("\n=== 2) Topics created ===")
topics = kafka_topics()
for name, topic in CONNECTORS.items():
    present = topic in topics
    n = topic_count(topic) if present else 0
    print(f"  {name:28s} topic={topic}  present={present}  messages={n}")

print("\n=== 3) Confluent Schema Registry subjects ===")
subs = requests.get("http://localhost:8081/subjects").json()
for s in subs:
    print("   ", s)

print("\n=== 4) Apicurio Registry artifacts ===")
try:
    arts = requests.get("http://localhost:8080/apis/registry/v2/search/artifacts?limit=50").json()
    for a in arts.get("artifacts", []):
        print(f"    {a.get('groupId')}/{a.get('id')}  ({a.get('type')})")
except Exception as e:
    print("    apicurio query error:", e)
