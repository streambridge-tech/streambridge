# Sandbox E2E test — MySQL CDC through StreamBridge

End-to-end test of MySQL source connectors deployed **through StreamBridge** against a
local Docker stack, covering both schema registries and three transformation levels.

## What it proves

| Dimension | Covered |
|---|---|
| Deploy path | Create connector + deploy via StreamBridge's API (`/api/notebooks/.../deploy`) |
| Schema registry | **Apicurio** and **Confluent** |
| Transformation levels | none (raw Debezium envelope), `unwrap` (ExtractNewRecordState), `unwrap + RegexRouter` |
| S3 sink | MySQL CDC topic → **Aiven S3 sink** → S3 bucket (adobe/s3mock) as JSONL |
| Operate path | StreamBridge reads live status/tasks via `/api/kc/...` |
| Live CDC | Insert a MySQL row and confirm each topic / the S3 bucket grows |

Nothing is deleted — the connectors stay deployed so you can inspect them.

## Prerequisites

1. **Docker stack up** (Kafka, Connect, MySQL, Apicurio, Confluent, s3mock):

   ```bash
   cd sandbox/ec2/schema_registry/connector_with_schema_registry
   docker compose up -d
   ```

   Expected host ports: Connect `8083`, Confluent SR `8081`, Apicurio `8080`,
   Kafka `9093`, MySQL `3000→3306`, Kafka UI `9021`, S3 mock `9090`.

2. **Aiven S3 sink plugin** mounted into Connect (for the S3 test). Download it once
   into `debezium_plugins/aiven-s3-sink/`, then recreate Connect:

   ```bash
   cd sandbox/ec2/schema_registry/connector_with_schema_registry/debezium_plugins
   curl -sL -o /tmp/aiven-s3.zip \
     https://github.com/Aiven-Open/s3-connector-for-apache-kafka/releases/download/v2.15.0/s3-connector-for-apache-kafka-2.15.0.zip
   rm -rf aiven-s3-sink && mkdir aiven-s3-sink && unzip -q /tmp/aiven-s3.zip -d /tmp/aiven-s3
   cp /tmp/aiven-s3/*/*.jar aiven-s3-sink/
   cd .. && docker compose up -d --force-recreate connect
   ```

   The compose already mounts `./debezium_plugins/aiven-s3-sink` → `/kafka/connect/aiven-s3-sink`.

3. **StreamBridge running** on `http://localhost:5000`:

   ```bash
   python3 main.py
   ```

4. **A Kafka Connect connection named `docker-connect`** pointing at the stack.
   Create it in the UI (Connections → New → Kafka Connect, Deployment = Connect,
   URL = `http://localhost:8083`), or via the API:

   ```bash
   curl -s -X POST http://localhost:5000/api/connections \
     -H 'Content-Type: application/json' -H 'Origin: http://localhost:5000' \
     -d '{"name":"docker-connect","type":"connect","subtype":"kafka-connect",
          "deployment":"connect","url":"http://localhost:8083","auth_type":"none"}'
   ```

## Run

```bash
.venv/bin/python sandbox/ec2/e2e/e2e_test.py     # create + deploy 4 MySQL source connectors via StreamBridge
.venv/bin/python sandbox/ec2/e2e/e2e_verify.py   # status, topics, message counts, registries
.venv/bin/python sandbox/ec2/e2e/e2e_cdc.py      # schema shape per transform + live CDC insert
.venv/bin/python sandbox/ec2/e2e/e2e_s3.py       # deploy S3 sink -> write CDC topic to the S3 bucket
```

## Connectors it creates (kept after the run)

| Name | Registry | Transform |
|---|---|---|
| `sb-mysql-apicurio-unwrap` | Apicurio | `unwrap` |
| `sb-mysql-confluent-unwrap` | Confluent | `unwrap` |
| `sb-mysql-confluent-raw` | Confluent | none (raw envelope) |
| `sb-mysql-confluent-route` | Confluent | `unwrap` + RegexRouter → `routed_*` |
| `sb-s3-sink-confluent` | — (sink) | reads `sbconf.inventory.customers` → `s3://streambridge-sink/cdc/` as JSONL |

They save into the **docker-e2e** folder on the Connectors page and run live on the
cluster (visible in Kafka UI at `http://localhost:9021`). Inspect written objects with
`curl "http://localhost:9090/streambridge-sink?list-type=2&prefix=cdc/"`.

## Notes

- Container/host names are internal to the Docker network: connector configs use
  `mysql`, `kafka:9092`, `http://registry:8080`, `http://schema-registry:8081`
  (reachable from inside the Connect container), while the scripts talk to the host
  ports above.
- Each connector uses a unique `database.server.id` and history topic. Re-running
  `e2e_test.py` will report name conflicts if the connectors already exist — delete
  them first (`curl -X DELETE http://localhost:8083/connectors/<name>`) or rename.
