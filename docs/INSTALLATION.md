# Installation

StreamBridge is a local control plane. It does not ship Kafka. You point it at a Kafka Connect cluster you already run, on a VM or on Kubernetes.

Requires Python 3.12 or newer.

## Install

```bash
cd streambridge
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python3 build.py
```

`build.py` writes the pages under `static/dist/`. The app serves those pages.

## Configure

Put the internal database in `profile.yaml`. Set `database.backend` to `sqlite`, `mysql`, or `postgresql`, and fill that backend's host, database, username, and password.

Leave a field blank if you would rather not store it in the file. StreamBridge then reads `STREAMBRIDGE__DATABASE__*` from the environment, or from `.env` when that file exists. A value already written in `profile.yaml` is kept.

`python3 main.py` listens on `server.host` and `server.port`, `127.0.0.1` and `5000` by default. Leave `server.debug` at `false`. It turns on the Werkzeug debugger, which runs any code typed into an error page. In personal mode StreamBridge answers only to `localhost`, `127.0.0.1`, `[::1]`, and `server.host`. Add any other host name you open it by to `server.allowed_hosts`.

`kafka_connect.url` in `profile.yaml` is only a default. Each environment uses the Kafka Connect connection you save in the UI.

## Run

```bash
python3 main.py
```

Open `http://127.0.0.1:5000`.

On startup StreamBridge creates its tables and loads the built-in plugins, including `file-source`.

## First run

The first time you open it, StreamBridge walks you through setup in the browser — no CLI. You choose how the workspace is used:

- **Personal** — just you, no sign-in, straight into the app.
- **Team** — accounts with roles and permissions; you create the first admin here. Team is permanent: it cannot be switched back to personal.

Afterwards, Personal drops you straight in and Team shows a sign-in screen. Locked out of a team workspace? `python3 manage.py admin bootstrap` recovers an admin from the terminal.

## Connect it to Kafka

1. Create a Kafka Connect connection.
2. Choose **Connect** to deploy with the Connect REST API, or **Kubernetes** to deploy a Strimzi `KafkaConnector`.
3. For Kubernetes, set the API host, namespace, Connect cluster name, and a bearer token. The Connect URL is still required. Status, tasks, and offsets are read from that URL.
4. Use **Test** before the first deploy. A Kubernetes `401` means the token was rejected. A `403` means the token cannot change connectors in that namespace.

Strimzi lab notes stay on the machine that ran them. They are not part of this repository.

## Tests

```bash
python -m unittest discover -s tests -t .
```
