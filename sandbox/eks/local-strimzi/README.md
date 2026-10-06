# Strimzi on Docker Desktop Kubernetes

A local check of the path StreamBridge would use later: create a connector through the Kubernetes API, then read its status from the Kafka Connect REST API.

This is not wired into StreamBridge. Helm only installs the operator. The connector itself is a `KafkaConnector` on the Kubernetes API.

Strimzi **1.2.0**. Kafka and Connect **4.3.1**. One namespace, `kafka`.

## Before you start

1. Docker Desktop → Settings → Kubernetes → Enable Kubernetes. Wait until it says running.
2. Give Docker Desktop at least **4 CPUs** and **6 GB** RAM. Kafka plus Connect will not schedule on a 2 GB VM.
3. Stop the Compose lab. It already publishes port **8083**, and the port-forward below uses that port.

```bash
kubectl config use-context docker-desktop
kubectl get nodes
```

`kubectl get nodes` should show one node, `Ready`.

## 1. Install the operator

```bash
kubectl create namespace kafka
kubectl create -f 'https://strimzi.io/install/latest?namespace=kafka' -n kafka
kubectl rollout status deployment/strimzi-cluster-operator -n kafka
```

The operator watches the `kafka` namespace it is installed in. Every file below is applied with `-n kafka`. (Prefer Helm? `helm install strimzi-operator oci://quay.io/strimzi-helm/strimzi-kafka-operator --version 1.2.0 -n kafka --create-namespace` installs the same operator.)

## 2. Start Kafka

```bash
kubectl apply -n kafka -f kafka-pool.yaml -f kafka.yaml
kubectl wait kafka/my-cluster --for=condition=Ready -n kafka --timeout=600s
```

The first start pulls the Kafka image and usually takes a few minutes.

## 3. Start Kafka Connect

```bash
kubectl apply -n kafka -f kafka-connect.yaml
kubectl wait kafkaconnect/my-connect-cluster --for=condition=Ready -n kafka --timeout=900s
```

This builds a Connect image that contains `FileStreamSourceConnector` and pushes it to `ttl.sh` (the tag lives 24 hours). The build needs internet from the cluster. `Ready` can take several minutes.

`strimzi.io/use-connector-resources: "true"` is set on this Connect cluster. With that annotation, Strimzi creates the connector from the `KafkaConnector` object. A direct `POST /connectors` gets reconciled back to the object.

## 4. Deploy the connector

```bash
kubectl apply -n kafka -f source-connector.yaml
kubectl wait kafkaconnector/my-source-connector --for=condition=Ready -n kafka --timeout=180s
```

The connector reads `/opt/kafka/LICENSE` inside the Connect pod and writes lines to the topic `my-topic`. It is a built-in file connector, not Debezium. Debezium is a later step, because the stock image does not contain that plugin.

## 5. Check both APIs

The Kubernetes API is the deploy path. This lists the connector object:

```bash
kubectl get --raw /apis/kafka.strimzi.io/v1/namespaces/kafka/kafkaconnectors/my-source-connector
```

`kubectl` authenticates with the Docker Desktop admin user in your kubeconfig. There is no separate Strimzi password. A pod inside the cluster would send `Authorization: Bearer` with its service-account token instead.

The Connect REST API is the status path. The service is inside the cluster, so forward it to the Mac:

```bash
kubectl port-forward -n kafka svc/my-connect-cluster-connect-api 8083:8083
```

In another terminal:

```bash
curl -s http://127.0.0.1:8083/connectors/my-source-connector/status
```

`connector.state` and `tasks[0].state` should be `RUNNING`.

## 6. Create and update through the Kubernetes API

Leave the port-forward on **8083** running. In another terminal, open the Kubernetes API on **8001**. `kubectl proxy` authenticates with your kubeconfig, so these calls send no extra token:

```bash
kubectl proxy --port=8001
```

Create a second connector. `POST` the object. The name is `metadata.name`, and the label must match the Connect cluster:

```bash
curl -s -X POST \
  http://127.0.0.1:8001/apis/kafka.strimzi.io/v1/namespaces/kafka/kafkaconnectors \
  -H 'Content-Type: application/json' \
  -d '{
    "apiVersion": "kafka.strimzi.io/v1",
    "kind": "KafkaConnector",
    "metadata": {
      "name": "license-file",
      "labels": { "strimzi.io/cluster": "my-connect-cluster" }
    },
    "spec": {
      "class": "org.apache.kafka.connect.file.FileStreamSourceConnector",
      "tasksMax": 1,
      "config": {
        "file": "/opt/kafka/LICENSE",
        "topic": "license-topic"
      }
    }
  }'
```

A `201` body is the stored object. Strimzi then calls Connect. After a few seconds the port-forward shows it:

```bash
curl -s http://127.0.0.1:8083/connectors/license-file/status
```

Update the topic with `PATCH`. This merges into `spec.config` and leaves `file` in place:

```bash
curl -s -X PATCH \
  http://127.0.0.1:8001/apis/kafka.strimzi.io/v1/namespaces/kafka/kafkaconnectors/license-file \
  -H 'Content-Type: application/merge-patch+json' \
  -d '{"spec":{"config":{"topic":"license-topic-updated"}}}'
```

Connect picks up the new config on its own. Confirm on the port-forward:

```bash
curl -s http://127.0.0.1:8083/connectors/license-file/config
```

`topic` should be `license-topic-updated`.

Remove only this example connector when you are done:

```bash
curl -s -X DELETE \
  http://127.0.0.1:8001/apis/kafka.strimzi.io/v1/namespaces/kafka/kafkaconnectors/license-file
```

## 7. Deploy through StreamBridge (the wired path)

Sections 1–6 drive the Kubernetes API by hand with your kubeconfig. This section
has **StreamBridge** do the deploy instead — the same path it would use on EKS,
authenticating with a **namespaced ServiceAccount token** rather than kubeconfig.

Apply the ServiceAccount, Role/RoleBinding for `kafkaconnectors`, and a long‑lived token:

```bash
kubectl apply -f streambridge-rbac.yaml
```

Read the API host and the token:

```bash
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'   # e.g. https://127.0.0.1:53354
kubectl get secret streambridge-token -n kafka -o jsonpath='{.data.token}' | base64 -d
```

The Compose lab already uses `8083`, so forward the cluster's Connect REST API to `8084`:

```bash
kubectl port-forward -n kafka svc/my-connect-cluster-connect-api 8084:8083
```

In StreamBridge, create a **Kafka Connect** connection with **Deployment = Kubernetes**:

- **Connect URL:** `http://127.0.0.1:8084` — status, tasks, and restart read from here.
- **Kubernetes API host:** the server URL above (e.g. `https://127.0.0.1:53354`).
- **Namespace:** `kafka`
- **Strimzi cluster:** `my-connect-cluster`
- **Token:** the ServiceAccount token.
- Turn **TLS verification off** — Docker Desktop's API cert isn't in the app's trust store (EKS has the same CA caveat).

Author a connector (`FileStreamSourceConnector`, `file: /opt/kafka/LICENSE`, `topic: sb-k8s-topic`),
**Validate**, then **Deploy**. StreamBridge writes a `KafkaConnector` object and Strimzi
reconciles it onto Connect. Confirm both sides:

```bash
kubectl get kafkaconnector -n kafka
curl -s http://127.0.0.1:8084/connectors/<name>/status
```

`READY` on the object and `RUNNING` on the REST status mean the whole path works.
Editing the config and re‑deploying updates the same object (a merge patch).

> **EKS note.** This is the EKS‑equivalent path. The one real difference is the token:
> EKS's default `aws eks get-token` credential expires in ~15 minutes, so on EKS create a
> **long‑lived ServiceAccount token** (as `streambridge-rbac.yaml` does here) with a
> Role for `kafkaconnectors`, trust the cluster CA (or disable TLS verification), and make
> the Connect REST service reachable (ingress / LoadBalancer / port‑forward).

## If something stays pending

```bash
kubectl get pods -n kafka
kubectl describe pod -n kafka -l strimzi.io/kind=Kafka
```

`Insufficient cpu` or `Insufficient memory` means Docker Desktop needs more CPUs or RAM. Stop other Compose stacks first.

A Connect pod stuck in `Pending` during the image build is the plugin build, not the connector. `kubectl get pods -n kafka` shows a build pod. `kubectl logs` on that pod shows whether the push to `ttl.sh` failed.

## Remove it

```bash
kubectl delete kafkaconnector --all -n kafka
kubectl delete -n kafka -f streambridge-rbac.yaml --ignore-not-found
kubectl delete -n kafka -f kafka-connect.yaml -f kafka.yaml -f kafka-pool.yaml
kubectl delete -f 'https://strimzi.io/install/latest?namespace=kafka' -n kafka
kubectl delete namespace kafka
