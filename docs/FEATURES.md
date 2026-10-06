# Features

StreamBridge is the control plane for Change Data Capture on Apache Kafka Connect. The connector runs in your Connect cluster. StreamBridge stores the config, the secret refs, and the deploy target.

## In this release

- **Connectors.** Write the connector config, validate it against the Connect cluster, and deploy it. One connector record keeps its config, notes, and deploy log.
- **Two deploy targets.** `connect` posts the config to the Kafka Connect REST API. `kubernetes` creates or updates a Strimzi `KafkaConnector` in the namespace you name. Status, tasks, offsets, and restart stay on the Connect URL either way.
- **Connections.** Kafka, Kafka Connect, Schema Registry, Slack, and Google Chat. A Kubernetes connection stores two hosts: the cluster API and the Connect API.
- **Authentication.** Connect accepts no auth or HTTP basic. Kubernetes uses a bearer token. Test reports `401` and `403` separately.
- **Vaults.** Secret values can be masked. A later save does not wipe a masked value that was already stored.
- **JSON and YAML.** The connector screen shows the payload that deploy will send. On a Kubernetes connection that payload is the `KafkaConnector` document. Secret fields are masked in that view.
- **Plugins.** Built-in plugin configs, including `file-source` (`FileStreamSourceConnector`). The Connect image must already contain the plugin class.
- **Kafka topics and Schema Registry.** Browse topics and registry artifacts from the connections you saved.
- **Alerts.** One policy per connector. The first matching rule wins. A rule can pause, re-trigger, or notify. The poll interval is the alert check, not the connector schedule.

## Phase 2

Pipelines and RCA are marked on screen and are not the deploy path. Deploy from Connectors.

Source and sink connection objects are retired. Database credentials belong in a vault and in the connector config, not in a second connection type.
