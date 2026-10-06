# Deploy to Amazon EKS through StreamBridge

Deploy connectors to a Strimzi‑managed Kafka Connect running on **Amazon EKS**, driven
by StreamBridge's **Kubernetes** deploy target. StreamBridge writes a `KafkaConnector`
object to the EKS API; Strimzi reconciles it onto Connect; status/tasks/restart are read
from the Connect REST URL.

This is the same code path proven locally in [local-strimzi/](local-strimzi/)
on Docker Desktop. **It is a template/runbook — not tested against a live EKS here.** The
only real differences from the local run are auth (a long‑lived ServiceAccount token),
TLS trust, and making the Connect REST service reachable.

## Prerequisites

- An **EKS cluster** and `kubectl`/`aws` configured for it (`aws eks update-kubeconfig --name <cluster> --region <region>`).
- The **Strimzi operator** installed, watching a namespace (this runbook uses `kafka`):

  ```bash
  kubectl create namespace kafka
  kubectl create -f 'https://strimzi.io/install/latest?namespace=kafka' -n kafka
  kubectl rollout status deployment/strimzi-cluster-operator -n kafka
  ```

- A **KafkaConnect** cluster with `strimzi.io/use-connector-resources: "true"` so Strimzi
  owns connectors from `KafkaConnector` objects. On EKS, build the Connect plugin image to
  **ECR** (not `ttl.sh`) and ensure the build pod can push to it. Example `spec.build.output`:

  ```yaml
  build:
    output:
      type: docker
      image: <account>.dkr.ecr.<region>.amazonaws.com/streambridge-connect:latest
    plugins:
      - name: debezium-mysql
        artifacts:
          - type: tgz
            url: https://repo1.maven.org/maven2/io/debezium/debezium-connector-mysql/2.5.0.Final/debezium-connector-mysql-2.5.0.Final-plugin.tar.gz
  ```

## 1. Create the ServiceAccount, RBAC, and token

```bash
kubectl apply -f streambridge-eks-rbac.yaml
```

This is a **Kubernetes‑native** credential — it does not go through IAM / `aws-auth`, so
you do not need to map an IAM principal. The token is long‑lived (does not expire like
`aws eks get-token`).

## 2. Collect the connection inputs

```bash
# EKS API server endpoint (https://....eks.amazonaws.com)
aws eks describe-cluster --name <cluster> --region <region> \
  --query 'cluster.endpoint' --output text

# The long-lived ServiceAccount token
kubectl get secret streambridge-token -n kafka -o jsonpath='{.data.token}' | base64 -d; echo

# (optional) the cluster CA, if you terminate TLS through a trusted proxy
aws eks describe-cluster --name <cluster> --region <region> \
  --query 'cluster.certificateAuthority.data' --output text
```

## 3. Make the Connect REST service reachable

Status/tasks/restart come from the Connect REST URL, so StreamBridge must reach it:

- **Testing:** `kubectl port-forward -n kafka svc/<connect-cluster>-connect-api 8084:8083`, then use `http://127.0.0.1:8084`.
- **Production:** expose the Connect service with an **internal LoadBalancer/NLB** or an **ingress**, and use that URL. Keep it private — Connect has no auth of its own.

## 4. Create the Kubernetes connection in StreamBridge

Connections → New → **Kafka Connect**, **Deployment = Kubernetes**:

| Field | Value |
|---|---|
| Connect URL | the reachable Connect REST URL (e.g. `http://127.0.0.1:8084` or your NLB) |
| Kubernetes API host | the EKS endpoint from step 2 (`https://....eks.amazonaws.com`) |
| Namespace | `kafka` |
| Strimzi cluster | your `KafkaConnect` name |
| Token | the ServiceAccount token from step 2 |
| TLS verification | **off** (see the CA note below) |

Or via the API:

```bash
TOKEN=$(kubectl get secret streambridge-token -n kafka -o jsonpath='{.data.token}' | base64 -d)
curl -s -X POST http://localhost:5000/api/connections \
  -H 'Content-Type: application/json' -H 'Origin: http://localhost:5000' \
  -d "{\"name\":\"eks-strimzi\",\"type\":\"connect\",\"subtype\":\"kafka-connect\",
       \"deployment\":\"kubernetes\",
       \"url\":\"http://127.0.0.1:8084\",
       \"api_host\":\"https://<eks-endpoint>\",
       \"namespace\":\"kafka\",
       \"cluster\":\"<connect-cluster-name>\",
       \"api_token\":\"$TOKEN\",
       \"extra\":{\"verify.ssl\": false}}"
```

## 5. Deploy and verify

Author a connector in **Connectors**, attach the `eks-strimzi` connection, **Validate**, then
**Deploy**. StreamBridge writes the `KafkaConnector` object; Strimzi reconciles it. Confirm
both sides:

```bash
kubectl get kafkaconnector -n kafka
curl -s http://127.0.0.1:8084/connectors/<name>/status
```

`READY=True` on the object and `RUNNING` on the REST status mean it works. Editing the
config and re‑deploying updates the same object (a merge patch).

## EKS‑specific notes and current limitations

- **Token.** Use the long‑lived ServiceAccount token above, **not** `aws eks get-token`
  (that expires in ~15 minutes and StreamBridge stores a static token). Rotate the Secret
  periodically per your policy.
- **TLS / CA.** StreamBridge currently supports TLS verification only as on/off — it does
  not yet accept a custom CA bundle, and the EKS API cert is signed by the cluster CA. So
  set **TLS verification off** for now, and keep the API reachable only over a trusted
  network path (VPN / private endpoint / bastion). CA‑bundle support is a planned hardening item.
- **RBAC.** The SA Role here grants only `kafkaconnectors` in one namespace. A `403` means
  the token lacks that verb/namespace; a `401` means the token is wrong or expired.
- **Deploy timeout.** StreamBridge polls the connector up to ~20s after writing the object.
  On EKS, operator reconcile + pod scheduling + image pull can exceed that; a slow first
  deploy may report "failed" even though it comes up shortly after. (Making this timeout
  configurable is a planned change.)
