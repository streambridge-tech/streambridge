# Pending

Open work for StreamBridge 0.1.0. Pick a number and do that item. Do not start the Later list until the Now list is done.

Status on every item below is open.

## Rough Notes
2. when clone the connector then not showing the save button instantly
2.1 add custom plugin we can more types source and sinks (remove database service ...)
2.2 only give the basic example of the plugin like : filestream connectors, and basic mysql ,postgres..
2.3 diff between kubernets deployment vs normal (rephrase name)
2.4 display the config in yaml and json format both but store in json only

2.5 logging enables

2.6 for streambridge db pass and username set hardcode in profile.yml
2.7 focus on Alerts are wired to the wrong list. A policy is supposed to belong to one connector. The New picker still loads /api/pipelines, and pipelines are parked. A new alert cannot be aimed at the connector you just deployed.


3. check end to end test case
4. remove the secrets any if
5. make the ci/cd with full test run there with all the resoluce install kafka, mysql ,....

6. explore kubernets level api
	exm: apis/kafka.strimzi.io/v1/namespaces
	 kubectl proxy --port=8001 and

3. docs make beautifull
4. add the next items
	rca
	pipelines
	rbac

## Now

1. **Clone does not show Save.** Cloning a connector copies the record and marks it saved at once, so the editor treats it as clean and the Save button stays disabled. The clone should open as unsaved, with Save enabled immediately.
2. **Custom plugins, source and sink only.** A plugin is a source or a sink. Remove the database service type from that flow. Credentials stay in a vault and in the connector config.
3. **Ship only basic plugin examples.** Keep short examples for `FileStreamSourceConnector`, MySQL, and Postgres. Drop the extra variants that are not those basics. The Connect image must already contain the class. These examples do not install the jar.
4. **Show the difference between Kubernetes and Connect.** The stored values are already `kubernetes` and `connect`. `connect` deploys through the Kafka Connect REST URL. `kubernetes` creates or updates a Strimzi `KafkaConnector`. Status, tasks, offsets, and restart stay on the Connect URL for both. The screen should say that difference in plain words. Do not rename them again.
5. **Show JSON and YAML, store JSON only.** The connector screen can display the deploy payload as JSON or YAML. The saved record stays JSON. Confirm a YAML view never becomes the stored document.
6. **Turn logging on for real use.** `profile.yaml` has a log level. Make the running app write useful deploy, test, and alert lines, and keep secret values out of those lines.
7. **Stop hardcoding the StreamBridge database user and password.** Done. `profile.yaml` has PostgreSQL and MySQL fields. A filled value is used. A blank field is read from `STREAMBRIDGE__DATABASE__MYSQL__*` or `STREAMBRIDGE__DATABASE__POSTGRESQL__*`, or from an optional `.env`.
8. **Point alerts at connectors.** Done. A new policy loads `/api/notebooks/` and stores `notebookId`. The checker uses that notebook's name and attached cluster. Pipelines are not the target.
9. **App has no login.** Anyone who can open port 5000 can deploy, pause, delete, and read configs, including a Kubernetes token. Login and roles are the Later item named RBAC. Until that exists, say so in the docs and do not pretend the UI is private.
10. **Secrets are only masked on screen.** Vault values and connector passwords sit in the StreamBridge database. Remove any secret that is still committed: passwords, tokens, keys, and connection strings in the tree and in git history where a current file still has them.
11. **Kubernetes deploy gives up too early.** After a Strimzi create, Connect status stays unknown until the operator reconciles. The wait is about 20 seconds, then the deploy is reported failed even if the connector comes up later. Keep polling until the connector exists or a real error comes back.
12. **The alert checker dies with the Flask process.** It runs inside `main.py`. Stopping the process stops alerts. Two processes can fire the same rule twice.
13. **No audit.** A deploy, pause, or delete does not record who did it.

## Prove it

14. **End-to-end tests.** One path that creates a connection, validates a basic connector, deploys it, reads status, and checks an alert aimed at that connector.
15. **CI that installs the dependencies and runs the tests.** The pipeline should start the services the tests need, including Kafka, Kafka Connect, and MySQL, then run the full test suite. A green unit-test job with nothing running underneath is not this item.

## Kubernetes API

16. **Walk the Kubernetes API StreamBridge already calls.** The resource is the Kubernetes API serving the Strimzi CRD, not a separate Strimzi HTTP server.

    `GET /apis/kafka.strimzi.io/v1/namespaces/{namespace}/kafkaconnectors`

    `kubectl proxy --port=8001` authenticates with the local kubeconfig, so a curl to `http://127.0.0.1:8001` sends no extra token. Write down what create, update, pause, and delete return, and what `401` and `403` mean. Do not add a second product API for this.

## Docs

17. **Make the docs readable.** Installation, features, and the comparison should be scannable: short sections, the two deploy targets, and what this version does not do. No new claims.

## Later

Pick these after the Now list. Order inside this list is not a promise.

18. **RCA.** Its own Phase 2 rail entry. The page stays, and it is not a deploy path.
19. **Pipelines.** Same rail section as RCA. Connectors remain the deploy path until this is chosen.
20. **RBAC.** Login, roles, and who is allowed to deploy or read secrets. This is the real fix for item 9.
