# End-to-end testing

A case passes only when the platform, the API, and the running connector agree. The StreamBridge screen alone is not enough.

Use two environments.

- **EKS.** The Kafka Connect connection is set to Kubernetes. Deploy writes a Strimzi `KafkaConnector`.
- **EC2.** The same connection is set to Connect. Deploy posts to the Kafka Connect REST API.

Status, tasks, offsets, and restart are read from the Connect URL in both.

Run each connector case once as a source and once as a sink. For every case write four lines: environment, connector name, Connect status, and where the data was checked (topic, registry subject, or S3 object).

## connectors:
    Basic Testing
	1. clone is not working in other folder
	2. move is not working for other folder
	3. yaml coloring is not sufficient when click on yaml then it doesn't showing colors


## API

These do not need a successful deploy, except the deploy rows.

| Case | Do this | Pass when |
|---|---|---|
| Create connector | `POST /api/notebooks/` with name, plugin, folder, and JSON config | `201`, and `GET` returns the same JSON |
| Reject empty name | `POST` with no name | `400` |
| Validate | `POST /api/notebooks/{id}/validate` against a real Connect URL | `connector.class` is accepted by that cluster |
| Validate missing class | Remove `connector.class` and validate | `400`, and nothing is deployed |
| Deploy Connect | Connection mode `connect`, then deploy | `GET /connectors/{name}` on Connect returns the config |
| Deploy Kubernetes | Connection mode `kubernetes`, then deploy | A `KafkaConnector` exists in the namespace, and Connect status still returns |
| Update | Change `tasks.max` and deploy again | The same connector is updated, not a second one |
| Delete | Delete the connector from the platform | It is gone from Connect. On EKS the `KafkaConnector` is gone too |
| Folder | `POST /api/folders/`, refresh, rename, delete | The folder is still there after refresh |
| Alert without a channel | Save an alert with no Slack or Google Chat connection | The save is rejected |
| Alert with a channel | Save one policy on one connector | `GET /api/alerts` shows that connector. A second policy for the same connector is rejected |
| Secrets | Save a password, then load the connector again | The value is masked, and the stored value was not wiped |

## Platform

| Case | Do this | Pass when |
|---|---|---|
| Plugin | Create a connector from MySQL JSON, MySQL Avro, and S3 | The JSON tab opens with that template |
| Connection used by the connector | Point the connector at a saved Kafka Connect connection | Deploy uses that connection |
| JSON and YAML | Switch views, edit, then Cancel | Cancel drops the unsaved edit |
| Validate, then deploy | Validate fails, then try to deploy | Deploy stays unavailable until validate passes |
| Schema Registry screen | Open Apicurio, then Confluent | Subjects from that registry are listed |
| Topics screen | Open the saved Kafka connection | The connector topic is listed after it has produced |
| Alert checkbox | Turn the alert on with no channel | The connector is not saved |
| Two folders | Put two connectors in different folders | Each folder shows only its own connectors |

## EKS

### Apicurio and Confluent

- Deploy one Avro source with `value.converter` pointed at Apicurio. Produce one row. The subject exists in Apicurio, and the Schema Registry screen shows it.
- Deploy a second Avro source with the Confluent converter and the Confluent registry URL. The subject exists in Confluent, not in Apicurio.
- A wrong registry URL fails validate, or the connector task goes `FAILED`. The platform shows that failed status.
- A JSON config with no registry still deploys. No schema subject is created.

### Plain JSON

- `value.converter` is `org.apache.kafka.connect.json.JsonConverter` and `schemas.enable` is `false`.
- Consume the topic. The value is the change record, not Avro bytes.
- Restart the task from the Connect screen. The connector returns to `RUNNING`.

### Several connectors

- Deploy three connectors into the same namespace: two sources and one sink.
- All three `KafkaConnector` objects exist. Deleting one leaves the other two running.
- Deploy the same name again. Strimzi updates that object. There is still one connector with that name.
- Two connectors with the same name in one namespace are rejected.

### The Kubernetes template

After deploy, read the `KafkaConnector` and check:

- `spec.class` is the `connector.class` from the JSON.
- `spec.tasksMax` is `tasks.max`.
- `spec.config` does not contain `connector.class`, `tasks.max`, or `name`.
- The label `strimzi.io/cluster` is the Connect cluster name on the connection.
- A bad token returns `401`. A token without permission returns `403`.
- Pause, restart, and status still come from the Connect URL, not from the Kubernetes API.

## EC2

### Apicurio and Confluent

- Run the same Avro cases as EKS. The connector was created with `POST /connectors`, not as a `KafkaConnector`.
- Changing only the registry URL and deploying again updates the same connector.

### Plain JSON

- Run the same JSON converter case as EKS.
- `GET /connectors/{name}/config` matches the JSON saved in StreamBridge. Secrets stay masked in the platform.

### Transforms

Use one MySQL or Postgres source. Add the transforms in the JSON. Consume the topic after each deploy.

- No transform: the value is the Debezium envelope, with `before`, `after`, and `op`.
- Unwrap (`ExtractNewRecordState`): the value is the row itself, not the envelope.
- Unwrap plus delete handling: a delete produces a tombstone, or the routed tombstone topic receives it. Check the behavior the config is supposed to have.
- A bad transform class makes the task `FAILED`, and the platform shows the failure.
- Removing the transform and deploying again restores the envelope.

### More connectors

- File source, MySQL source, Postgres source, and S3 sink, each created from its plugin.
- Each reaches `RUNNING` with at least one task.
- The S3 sink uses the topic produced by one of the sources. A new row lands in the bucket.
- Pause one connector. The others stay `RUNNING`.
- Deploy a connector whose class is not on the Connect image. The task fails, and no data is written.
