"""S3 sink end-to-end through StreamBridge against a local S3 mock (adobe/s3mock).

Reads an Avro CDC topic and writes JSONL objects to an S3 bucket using the
Aiven S3 sink connector, deployed via StreamBridge. Does NOT delete anything.

Prereqs:
  - docker compose up -d   (includes the `s3mock` service, port 9090)
  - the Aiven S3 plugin mounted into Connect (see sandbox/ec2/e2e/README.md)
  - StreamBridge running with a `docker-connect` connection -> http://localhost:8083
  - a source topic already populated (run e2e_test.py first)

Run: .venv/bin/python sandbox/ec2/e2e/e2e_s3.py
"""
import re
import time
import requests

SB = "http://localhost:5000"
H = {"Content-Type": "application/json", "Origin": SB}
S3 = "http://localhost:9090"
BUCKET = "streambridge-sink"
SOURCE_TOPIC = "sbconf.inventory.customers"
NAME = "sb-s3-sink-confluent"

CONFIG = {
    "connector.class": "io.aiven.kafka.connect.s3.AivenKafkaConnectS3SinkConnector",
    "tasks.max": "1",
    "topics": SOURCE_TOPIC,
    "aws.access.key.id": "foo",
    "aws.secret.access.key": "bar",
    "aws.s3.bucket.name": BUCKET,
    "aws.s3.endpoint": "http://s3mock:9090",
    "aws.s3.region": "us-east-1",
    "aws.s3.prefix": "cdc/",
    "format.output.type": "jsonl",
    "format.output.fields": "value",
    "format.output.envelope": "false",
    "file.max.records": "1",
    "file.compression.type": "none",
    "key.converter": "io.confluent.connect.avro.AvroConverter",
    "key.converter.schema.registry.url": "http://schema-registry:8081",
    "value.converter": "io.confluent.connect.avro.AvroConverter",
    "value.converter.schema.registry.url": "http://schema-registry:8081",
}


def list_objects():
    r = requests.get(f"{S3}/{BUCKET}", params={"list-type": "2", "prefix": "cdc/"})
    return re.findall(r"<Key>(.*?)</Key>", r.text)


# ensure the bucket exists (s3mock)
requests.put(f"{S3}/{BUCKET}")

# create + deploy the sink through StreamBridge
r = requests.post(f"{SB}/api/notebooks/", headers=H, json={
    "name": NAME, "folder": "docker-e2e", "attachedCluster": "docker-connect",
    "doc": {"name": NAME, "config": CONFIG},
})
print("create notebook:", r.status_code)
if r.status_code in (200, 201):
    nb = r.json()["id"]
    d = requests.post(f"{SB}/api/notebooks/{nb}/deploy", headers=H, json={})
    dj = d.json()
    print("deploy:", d.status_code, "ok=", dj.get("ok"),
          "state=", (dj.get("result") or {}).get("state"), "err=", dj.get("error"))
else:
    print("  (already exists?)", r.text[:150])

print("\nWaiting ~65s for the sink's offset flush to write objects...")
time.sleep(65)
keys = list_objects()
print(f"objects in s3://{BUCKET}/cdc/ : {len(keys)}")
for k in keys[:12]:
    print("  ", k)
if keys:
    body = requests.get(f"{S3}/{BUCKET}/{keys[0]}").text
    print("\nsample object content:", body.strip())
