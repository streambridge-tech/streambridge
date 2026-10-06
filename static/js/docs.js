const DOC_GROUPS = [
  ['Getting Started', ['overview', 'first-connector']],
  ['Connectors', ['connector-config', 'folders', 'validation']],
  ['Connections & Vaults', ['connections', 'vaults']],
  ['Deployment', ['rest-deploy', 'kubernetes-deploy']],
  ['Connector Operations', ['operations']],
  ['Kafka Topics', ['topics']],
  ['Schema Registry', ['registry']],
  ['Plugins', ['plugins', 'sample-connectors']],
  ['Alerts', ['alerts']],
  ['Troubleshooting', ['troubleshooting']],
  ['Phase 2', ['phase-two']],
];

const MYSQL_EXAMPLE = JSON.stringify({
  name: 'inventory-mysql',
  config: {
    'connector.class': 'io.debezium.connector.mysql.MySqlConnector',
    'tasks.max': '1',
    'database.hostname': '{local.mysql_host}',
    'database.port': '3306',
    'database.user': '{local.mysql_user}',
    'database.password': '{local.mysql_password}',
    'database.server.id': '184054',
    'topic.prefix': 'inventory',
    'database.include.list': 'inventory',
    'table.include.list': 'inventory.customers',
    'schema.history.internal.kafka.bootstrap.servers': 'kafka:9092',
    'schema.history.internal.kafka.topic': 'schemahistory.inventory',
  },
}, null, 2);

function docsEscape(value) {
  return String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
}

function docsCode(label, code) {
  return `<div class="docs-code"><div class="docs-code-bar"><span>${docsEscape(label)}</span><button class="docs-copy" type="button" title="Copy code" aria-label="Copy ${docsEscape(label)}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button></div><pre><code>${docsEscape(code)}</code></pre></div>`;
}

const DOC_CONTENT = {
  overview: {
    title: 'StreamBridge at a glance',
    lead: 'Manage connector configuration and operations. Your Kafka Connect workers do the data movement.',
    body: `<h2>What runs where</h2><p>StreamBridge stores connector configurations, saved connections, vault references, notes, and deployment history. Source and sink plugins run in your Kafka Connect cluster. StreamBridge does not install Kafka, Connect, database replication, or plugin JARs.</p><div class="docs-note">Source database &rarr; source connector &rarr; Kafka topic &rarr; sink connector. StreamBridge manages configuration and observes the Connect cluster; it is not in the record-processing path.</div><h2>Choose the right screen</h2><ul><li><a href="/connectors">Connectors</a>: author, validate, deploy, and organize saved records — and operate live connectors (status, tasks, pause, resume, restart) from each connector's API tab.</li><li><a href="/connections">Connections</a>: save endpoints, test connectivity, and manage vaults.</li><li><a href="/kafka-topics">Kafka Topics</a> and <a href="/schema-registry">Schema Registry</a>: browse messages and schemas.</li><li><a href="/plugins">Plugins</a>: manage configuration templates. <a href="/alerts">Alerts</a>: configure connector policies.</li></ul><h2>Before you start</h2><p>Have a reachable Connect REST API, the required plugin installed on its workers, and a database configured for CDC. For Kubernetes deployments, also provide access to a Strimzi-managed cluster. StreamBridge calls Connect, while the Connect workers connect to the source database and Kafka brokers. Use addresses reachable from the process that needs them.</p>`,
  },
  'first-connector': {
    title: 'Deploy your first connector',
    lead: 'A MySQL example using a saved Connect cluster and a vault, without embedding a password in the document.',
    body: `<h2>Prepare the environment</h2><p>This example targets a modern Debezium MySQL plugin (2.x/3.x). Enable MySQL row-based binlogging and grant the connector user replication and read permissions required by your plugin version. The worker must reach MySQL and Kafka.</p><ol><li>In <a href="/connections">Connections</a>, create a Kafka Connect connection named <code>local-connect</code>, choose the Connect deployment target, enter its REST URL, and test it.</li><li>Create a vault named <code>local</code> with keys <code>mysql_host</code>, <code>mysql_user</code>, and <code>mysql_password</code>. Mark the password as secret.</li><li>In <a href="/connectors">Connectors</a>, create a connector record from the MySQL plugin and attach it to <code>local-connect</code>.</li><li>Edit the JSON configuration using the example below, then save it.</li><li>Click <strong>Validate</strong>. Resolve reported errors, then click <strong>Deploy</strong> and review the result.</li><li>Inspect live status and tasks in the connector's <strong>API</strong> tab, then browse output in <a href="/kafka-topics">Kafka Topics</a>.</li></ol><h2>Example configuration</h2>${docsCode('Debezium MySQL connector JSON', MYSQL_EXAMPLE)}<div class="docs-note">Replace the broker address and vault values with your own. For the repository's Debezium 1.8 sandbox, use the equivalent legacy settings <code>database.server.name</code>, <code>database.history.kafka.bootstrap.servers</code>, and <code>database.history.kafka.topic</code>. Do not mix plugin-version settings.</div><h2>Verify the result</h2><p>Insert or update a row in <code>inventory.customers</code>. With this prefix, the expected data topic is <code>inventory.inventory.customers</code>. Snapshot behavior, event format, topic creation, and latency depend on your database, worker, connector, and Kafka configuration.</p>`,
  },
  'connector-config': {
    title: 'Configuration, notes, and payloads',
    lead: 'A saved record is the authored configuration, not proof that the live connector is healthy.',
    body: `<h2>Document structure</h2><p>The document has a <code>name</code> and a <code>config</code> object. The class identifies the worker plugin. Plugin-specific fields belong inside <code>config</code>.</p>${docsCode('Minimal connector document', JSON.stringify({ name: 'file-demo', config: { 'connector.class': 'org.apache.kafka.connect.file.FileStreamSourceConnector', 'tasks.max': '1', file: '/data/input.txt', topic: 'file-demo' } }, null, 2))}<p>The file must exist on the Connect worker, not on the StreamBridge host. The plugin must be installed; a template alone does not install it.</p><h2>Save and inspect</h2><p>Save changes to persist them. JSON and YAML views show the deployment document; Kubernetes targets show a Strimzi resource instead of a REST request. Sensitive fields are masked in payload previews. Keep operational context in notes and inspect deployment logs after sending a change.</p><h2>Connector identity</h2><p>The name is the connector's identity in Kafka Connect. After deployment, the editor locks it. Create a new record for a separate live identity; avoid accidentally reusing an existing name on the same cluster.</p>`,
  },
  folders: {
    title: 'Folders, Move, and Clone',
    lead: 'Organize saved records independently from the live connectors on your cluster.',
    body: `<h2>Organize records</h2><p>Create folders from the connector tree and use nested folders for related configurations, for example <code>commerce/sources</code> and <code>commerce/sinks</code>. Search the tree to find a record.</p><h2>Move a connector</h2><ol><li>Open the connector tree menu and choose <strong>Move</strong>.</li><li>Select the destination folder and confirm.</li><li>Check the record in that folder; its location should survive a reload.</li></ol><p>Moving a record does not migrate a running connector to another Connect cluster.</p><h2>Clone a connector</h2><ol><li>Choose <strong>Clone</strong> from its menu.</li><li>Give the copy a distinct name such as <code>inventory-mysql-test</code>.</li><li>Review its cluster, table selection, topic prefix, replication identity, and secrets before deploying.</li></ol><div class="docs-note">A clone is a separate saved configuration, not an automatic deployment. Concurrent MySQL connectors need distinct <code>database.server.id</code> values. For PostgreSQL, review replication slots and publications.</div>`,
  },
  validation: {
    title: 'Validate before deployment',
    lead: 'Check configuration against the selected cluster and its installed plugin.',
    body: `<h2>Validation workflow</h2><ol><li>Attach a saved Kafka Connect connection.</li><li>Save valid JSON containing the plugin's <code>connector.class</code>.</li><li>Click <strong>Validate</strong> and read the reported errors.</li><li>Correct missing or incompatible fields, then validate again.</li></ol><h2>Example failure</h2><p>Missing <code>database.hostname</code> may produce a required-field error for a MySQL connector. If the plugin class is unavailable, inspect the worker plugins and install the matching JARs before retrying.</p><div class="docs-note">Validation is not an end-to-end CDC test. A valid config can still fail at runtime due to permissions, network reachability, replication setup, or schema compatibility. Inspect tasks after deploying.</div>`,
  },
  connections: {
    title: 'Save and test connections',
    lead: 'Reusable endpoints for Kafka, Kafka Connect, Schema Registry, Slack, and Google Chat.',
    body: `<h2>Connection types</h2><ul><li><strong>Kafka</strong>: broker addresses and supported security settings for topic browsing.</li><li><strong>Kafka Connect</strong>: REST URL, authentication, and deployment target.</li><li><strong>Schema Registry</strong>: Confluent or Apicurio provider and endpoint.</li><li><strong>Slack / Google Chat</strong>: alert notification destinations.</li></ul><h2>Local example</h2><p>If StreamBridge runs on your host and Connect exposes port 8083, use <code>http://localhost:8083</code>. If StreamBridge runs in Docker on the same network, use the worker service name, such as <code>http://connect:8083</code>. Container-internal and host addresses are not interchangeable.</p><h2>Authentication and testing</h2><p>Connect supports no authentication or HTTP basic. Kubernetes uses a bearer token for its API. Save and test connections before attaching them. A <code>401</code> indicates an authentication problem; a <code>403</code> indicates denied access.</p><div class="docs-note">Source/sink database connection objects are retired. Put database properties in connector configuration and sensitive values in a vault.</div>`,
  },
  vaults: {
    title: 'Vaults and secret references',
    lead: 'Use named value bags in Connections and reference their keys in connector configuration.',
    body: `<h2>Create a vault</h2><p>Create a vault named <code>prod</code>. Add <code>mysql_password</code>, enter its value, mark it secret, and save. References use <code>{bag.key}</code>; names and keys must match saved values.</p>${docsCode('Secret references inside config', JSON.stringify({ 'database.hostname': '{prod.mysql_host}', 'database.user': '{prod.mysql_user}', 'database.password': '{prod.mysql_password}' }, null, 2))}<h2>Resolution and masking</h2><p>StreamBridge resolves vault references for deployment while preserving them in authored JSON. Values are masked in the UI. Saving a stored masked value without replacing it preserves the existing value.</p><h2>Missing values</h2><p>If <code>prod.mysql_password</code> is missing, check the vault name, key spelling, and saved value. Do not put actual passwords in shared notes or examples.</p><div class="docs-note">Masking is display protection, not a claim of external secrets-manager integration. Protect the StreamBridge database and app access. The target receives the resolved configuration required to run the connector.</div>`,
  },
  'rest-deploy': {
    title: 'Deploy to Kafka Connect',
    lead: 'Send saved configuration to the selected Connect REST endpoint.',
    body: `<h2>Select the target</h2><p>Choose the <strong>Connect</strong> deployment target on the Kafka Connect connection and set a reachable REST URL. Attach it to your record, save, validate, and deploy.</p><h2>Payload example</h2>${docsCode('REST deployment document', JSON.stringify({ name: 'file-demo', config: { 'connector.class': 'org.apache.kafka.connect.file.FileStreamSourceConnector', 'tasks.max': '1', file: '/data/input.txt', topic: 'file-demo' } }, null, 2))}<h2>After deployment</h2><p>Read the deploy log and inspect status and tasks. A successful response means the request was accepted, not that every task processes records successfully. Connectors keep running until operated on or deleted; alert polling is not a run schedule.</p><div class="docs-note">Check live names before deployment. Updating configuration may affect a running connector with the same identity.</div>`,
  },
  'kubernetes-deploy': {
    title: 'Deploy with Strimzi',
    lead: 'Manage a KafkaConnector resource and retain the Connect REST URL for operations.',
    body: `<h2>Connection settings</h2><p>Select the <strong>Kubernetes</strong> target. Set the Kubernetes API host, bearer token, namespace, Strimzi cluster name, and Connect REST URL. The operator must watch the namespace, and KafkaConnector resource management must be enabled on the KafkaConnect cluster.</p><h2>Resource example</h2>${docsCode('Generated KafkaConnector YAML', `apiVersion: kafka.strimzi.io/v1
kind: KafkaConnector
metadata:
  name: file-demo
  labels:
    strimzi.io/cluster: my-connect
spec:
  class: org.apache.kafka.connect.file.FileStreamSourceConnector
  tasksMax: 1
  state: running
  config:
    file: /data/input.txt
    topic: file-demo`)}<p>Class and task count come from <code>connector.class</code> and <code>tasks.max</code>; remaining fields become <code>spec.config</code>. The connection determines namespace and cluster association.</p><h2>Verify both paths</h2><p>Check the resource and Strimzi reconciliation, then inspect the connector through Connect REST. Status, tasks, offsets, and restart still use the Connect URL.</p>`,
  },
  operations: {
    title: 'Inspect and operate live connectors',
    lead: "Operate live connectors from each connector's API tab, not only the saved authoring record.",
    body: `<h2>Inspect</h2><p>Open a saved connector on <a href="/connectors">Connectors</a> and use its <strong>API</strong> tab. Inspect status, config, tasks, and topics. Failed tasks contain useful runtime error details.</p><h2>Pause, resume, and restart</h2><p>Pause temporarily stops processing; resume enables it again. Restart supports tasks and failed-only targeting. Individual task restart is also available. Repair bad endpoints or credentials before retrying.</p>${docsCode('Equivalent read-only status request', 'curl http://localhost:8083/connectors/inventory-mysql/status')}<h2>Offsets and deletion</h2><p>Offset reset and deletion are destructive. Check the target identity, confirmation, and worker-version requirements. Reset may replay data; behavior depends on snapshot and connector settings.</p><div class="docs-note">Deleting a live connector does not delete its Kafka topics or source objects. For Strimzi-managed connectors, consider operator reconciliation when making REST-side changes.</div>`,
  },
  topics: {
    title: 'Browse Kafka topics and messages',
    lead: 'Inspect records visible to a saved Kafka connection.',
    body: `<h2>Open a topic</h2><ol><li>Create and test a Kafka connection with brokers reachable from StreamBridge.</li><li>Open <a href="/kafka-topics">Kafka Topics</a>, select the connection, and find the topic.</li><li>Inspect metadata and messages, select a partition if needed, and page through results.</li></ol><h2>CDC example</h2>${docsCode('Illustrative Debezium value (abbreviated)', JSON.stringify({ before: null, after: { id: 1001, first_name: 'Ada' }, op: 'c', source: { db: 'inventory', table: 'customers' } }, null, 2))}<p>Typical envelope operations: <code>c</code> create, <code>u</code> update, <code>d</code> delete, and <code>r</code> snapshot read. Converters and transforms can change the shape; deletes can also produce null tombstones.</p><h2>Schema-aware decoding</h2><p>Select the appropriate registry for schema-based decoding when available. Decode errors can indicate a wrong registry, unavailable schema ID, or incompatible serializer format. Broker connectivity alone does not guarantee decoding.</p>`,
  },
  registry: {
    title: 'Browse schema registries',
    lead: 'Explore Confluent and Apicurio schemas and their versions.',
    body: `<h2>Browse the catalog</h2><ol><li>Create a registry connection with its provider and URL.</li><li>Test it and open <a href="/schema-registry">Schema Registry</a>.</li><li>Expand the catalog, select an artifact/schema, and inspect a version's content.</li></ol><h2>Avro example</h2>${docsCode('Customer value schema', JSON.stringify({ type: 'record', name: 'Customer', namespace: 'inventory', fields: [{ name: 'id', type: 'long' }, { name: 'name', type: ['null', 'string'], default: null }] }, null, 2))}<p>A Confluent subject might be <code>inventory.inventory.customers-value</code>, depending on naming strategy. Apicurio organizes artifacts in groups. IDs and versions are not interchangeable between providers.</p><h2>Scope</h2><p>These screens browse catalogs and versions. Worker converter settings determine which registry receives schemas; browsing a registry does not configure a converter.</p>`,
  },
  plugins: {
    title: 'Plugin configuration templates',
    lead: 'Templates help author configs; executable plugins belong on the workers.',
    body: `<h2>Use a template</h2><p>Open <a href="/plugins">Plugins</a>, select a source/sink template, inspect its config, and use it to create a connector. Replace example endpoints, topics, and credentials.</p><h2>Add a custom plugin</h2><p>Provide a unique lowercase slug, service/database, source or sink type, format, description, and JSON configuration. For example, name a file template <code>file-source-demo</code> and use the FileStream configuration in the configuration guide.</p><h2>Worker installation</h2><p>Install JARs and dependencies into your workers' plugin path using the cluster deployment process. Restart/roll workers as required, confirm class availability, and validate a config that uses it.</p><div class="docs-note">Adding a StreamBridge template does not download a JAR or update a worker image.</div>`,
  },
  'sample-connectors': {
    title: 'Sample connectors (test_*)',
    lead: 'Ready-to-run example templates that mirror the sandbox end-to-end tests: MySQL CDC with two schema registries, three transform levels, an S3 sink, and a Kubernetes file source.',
    body: `<h2>What ships by default</h2><p>The <strong>test_</strong> templates appear in <a href="/plugins">Plugins</a> as built-in source and sink entries. They are copy-ready configurations for the Docker sandbox under <code>sandbox/ec2/schema_registry/connector_with_schema_registry</code> (and, for the file source, a Strimzi/Kubernetes cluster). Every value already points at the sandbox service names, so you can deploy them as-is and watch data move.</p><ul><li><code>test_mysql_cdc_confluent</code> &mdash; Debezium MySQL CDC, <strong>Confluent</strong> Avro, <code>unwrap</code> transform (flattened rows).</li><li><code>test_mysql_cdc_apicurio</code> &mdash; the same CDC source but schemas register to <strong>Apicurio</strong>. Run both to compare registries side by side.</li><li><code>test_mysql_cdc_raw</code> &mdash; Confluent Avro with <strong>no transform</strong>, so topics keep the full Debezium envelope (<code>before</code>/<code>after</code>/<code>op</code>/<code>source</code>).</li><li><code>test_mysql_cdc_router</code> &mdash; <code>unwrap</code> plus a <strong>RegexRouter</strong> that renames topics with a <code>routed_</code> prefix (chained SMTs).</li><li><code>test_s3_sink</code> &mdash; Aiven <strong>S3 sink</strong> that writes a CDC topic to a bucket as JSONL (points at the local s3mock).</li><li><code>test_file_source_k8s</code> &mdash; FileStreamSource for a <strong>Kubernetes</strong> (Strimzi) deployment.</li></ul><h2>How to use one</h2><ol><li>Bring the stack up: from <code>sandbox/ec2/schema_registry/connector_with_schema_registry</code> run <code>docker compose up -d</code>.</li><li>In <a href="/connections">Connections</a>, create a <strong>Kafka Connect</strong> connection to <code>http://localhost:8083</code> (for the file source, use a <strong>Kubernetes</strong> deployment connection instead).</li><li>In <a href="/plugins">Plugins</a>, open a <code>test_</code> template and choose <strong>Create connector</strong>; attach it to that connection.</li><li>Click <strong>Validate</strong> to check the config against the cluster, then <strong>Deploy</strong>.</li><li>Insert a row in MySQL and watch the topic grow in <a href="/kafka-topics">Kafka Topics</a>, or inspect registered schemas in <a href="/schema-registry">Schema Registry</a>.</li></ol>${docsCode('Insert a row to produce CDC events', "docker exec mysql-cdc mysql -uroot -pdebezium -e \\\n  \"INSERT INTO inventory.customers (first_name,last_name,email) \\\n   VALUES ('Sample','Row','sample.row@streambridge.test');\"")}<h2>How the transform levels differ</h2><p>All three MySQL variants read the same table; only the SMT chain changes the topic shape.</p>${docsCode('raw vs. unwrap vs. router (value shape)', JSON.stringify({
  raw: { before: null, after: { id: 1001, first_name: 'Ada' }, op: 'c', source: { db: 'inventory', table: 'customers' } },
  unwrap: { id: 1001, first_name: 'Ada' },
  router: { topic: 'routed_sbconfroute.inventory.customers', value: { id: 1001, first_name: 'Ada' } },
}, null, 2))}<div class="docs-note">These templates carry the sandbox password <code>debezium</code> inline so they run out of the box. For any real database, replace the inline secret with a <a href="/connections">vault</a> reference such as <code>{prod.mysql_password}</code> before deploying.</div><h2>The S3 sink</h2><p><code>test_s3_sink</code> consumes <code>sbconf.inventory.customers</code> (produced by <code>test_mysql_cdc_confluent</code>) and writes one JSONL object per record under <code>cdc/</code>. It targets the sandbox <code>s3mock</code>; browse results at the s3 web UI on port 9092, or point <code>aws.s3.endpoint</code>/<code>region</code>/keys at real AWS S3.</p>${docsCode('Aiven S3 sink essentials', JSON.stringify({
  'connector.class': 'io.aiven.kafka.connect.s3.AivenKafkaConnectS3SinkConnector',
  topics: 'sbconf.inventory.customers',
  'aws.s3.bucket.name': 'streambridge-sink',
  'aws.s3.endpoint': 'http://s3mock:9090',
  'aws.s3.prefix': 'cdc/',
  'format.output.type': 'jsonl',
}, null, 2))}<h2>The Kubernetes file source</h2><p><code>test_file_source_k8s</code> deploys through a <strong>Kubernetes</strong> connection: StreamBridge writes a <code>KafkaConnector</code> object and Strimzi reconciles it onto Connect. The Strimzi Connect image must include <code>FileStreamSourceConnector</code>. See the <a href="/connectors">Deploy with Strimzi</a> guide and the runbooks under <code>sandbox/eks/local-strimzi</code> and <code>sandbox/eks</code>.</p><div class="docs-note">Deploying a template does not install its plugin JAR on the workers. The sandbox images already bundle Debezium, the Confluent/Apicurio Avro converters, the Aiven S3 sink, and FileStream.</div>`,
  },
  alerts: {
    title: 'Connector alert policies',
    lead: 'One policy per connector, with ordered rules and an explicit check interval.',
    body: `<h2>Create a policy</h2><ol><li>Save a Slack or Google Chat connection for notifications.</li><li>Open <a href="/alerts">Alerts</a> and select a connector.</li><li>Add rules, actions, destinations, and a check interval.</li><li>Save and test notification delivery where available.</li></ol><h2>Example policy</h2><ul><li>Connector: <code>inventory-mysql</code>.</li><li>Check every: <strong>5 minutes</strong>.</li><li>First rule: when <code>FAILED</code>, notify the operations channel.</li><li>Optional recovery: use <strong>re-trigger</strong> with an explicit attempt limit after reviewing the failure.</li></ul><h2>Order and actions</h2><p>The first matching rule wins. Actions include pause, re-trigger, and notify. Put specific rules before broad ones. Automatic retries cannot fix persistent bad credentials or missing plugins.</p><div class="docs-note">The interval controls state evaluation, not connector execution. Policies bind to connector records, not Phase 2 pipelines.</div>`,
  },
  troubleshooting: {
    title: 'Troubleshooting checklist',
    lead: 'Find the failed boundary: connectivity, validation, deployment, execution, or decoding.',
    body: `<h2>Cannot reach Connect</h2><p>Test the saved URL from the StreamBridge host/container. Container-local <code>localhost</code> is not another container. Check ports, DNS, firewalls, and shared Docker networks. Distinguish authentication errors (<code>401</code>) from permission errors (<code>403</code>).</p><h2>Plugin class unavailable</h2><p>Match <code>connector.class</code> to an installed plugin. Templates are not installations. Check dependency JARs, plugin path, and worker restarts.</p><h2>Deployment fails</h2><p>Read deploy logs and validate again. Check vault references and permissions. In Kubernetes check namespace, token, cluster label, Strimzi operator, and resource permissions.</p><h2>Failed tasks or no records</h2><p>Inspect task errors. Check database grants, binlog/WAL settings, included tables, snapshot mode, Kafka reachability, and converters. Verify topic prefix and committed database changes.</p><h2>Registry decoding fails</h2><p>Check provider, URL, serializer format, schema IDs, and credentials. JSON without registry framing is not the same as registry-backed Avro.</p><h2>Missing external Docker network</h2><p>The connector-with-schema-registry sandbox requires a shared network. Create it once before Compose startup:</p>${docsCode('Sandbox prerequisite', 'docker network create streambridge-network\ndocker compose up -d')}<p>Skip creation if the network exists. Run Compose from the sandbox directory containing the Compose file.</p>`,
  },
  'phase-two': {
    title: 'Pipelines and RCA: Phase 2',
    lead: 'Separate these screens from the current connector deployment workflow.',
    body: `<h2>Current boundary</h2><p>Pipelines and RCA are labeled <strong>Phase 2</strong>. Use <a href="/connectors">Connectors</a> for authoring, validation, and deployment, and each connector's API tab for live operations.</p><h2>Legacy examples</h2><p>Pipeline YAML/Jinja belongs to a separate model. Do not paste <code>pipeline.env</code>, <code>source</code>, or <code>sink</code> blocks into connector JSON. Current vault references use <code>{bag.key}</code>, not <code>{{ var('key') }}</code>.</p><div class="docs-note">Phase 2 features are not presented as the current end-to-end deploy path.</div>`,
  },
};

const DOC_IDS = DOC_GROUPS.flatMap(([, ids]) => ids);
let currentDoc = '';

function renderDocsNav(query = '') {
  const search = query.trim().toLowerCase();
  let count = 0;
  document.getElementById('docsNav').innerHTML = DOC_GROUPS.map(([group, ids]) => {
    const matches = ids.filter(id => {
      const doc = DOC_CONTENT[id];
      const body = new DOMParser().parseFromString(doc.body, 'text/html').body.textContent;
      return `${group} ${doc.title} ${doc.lead} ${body}`.toLowerCase().includes(search);
    });
    count += matches.length;
    if (!matches.length) return '';
    return `<details class="docs-group" ${search || matches.includes(currentDoc) ? 'open' : ''}><summary>${docsEscape(group)}</summary>${matches.map(id => `<a class="docs-topic" href="#${id}" ${id === currentDoc ? 'aria-current="page"' : ''}>${docsEscape(DOC_CONTENT[id].title)}</a>`).join('')}</details>`;
  }).join('');
  document.getElementById('docsEmpty').hidden = count > 0;
}

function showDoc(id) {
  if (!DOC_CONTENT[id]) id = 'overview';
  currentDoc = id;
  const doc = DOC_CONTENT[id];
  const group = DOC_GROUPS.find(([, ids]) => ids.includes(id))[0];
  const content = document.getElementById('docsContent');
  content.innerHTML = `<div class="docs-breadcrumb">Docs / ${docsEscape(group)}</div><h1 tabindex="-1">${docsEscape(doc.title)}</h1><p class="docs-lead">${docsEscape(doc.lead)}</p>${doc.body}`;
  const headings = [...content.querySelectorAll('h2')];
  headings.forEach((heading, index) => { heading.id = `${id}-section-${index + 1}`; });
  const toc = document.createElement('nav');
  toc.className = 'docs-toc';
  toc.setAttribute('aria-label', 'In this article');
  toc.innerHTML = headings.map(heading => `<a href="#${heading.id}">${docsEscape(heading.textContent)}</a>`).join('');
  content.querySelector('.docs-lead').after(toc);
  const index = DOC_IDS.indexOf(id);
  content.insertAdjacentHTML('beforeend', `<nav class="docs-pagination" aria-label="Adjacent articles">${index > 0 ? `<a href="#${DOC_IDS[index - 1]}">Previous: ${docsEscape(DOC_CONTENT[DOC_IDS[index - 1]].title)}</a>` : '<span></span>'}${index < DOC_IDS.length - 1 ? `<a href="#${DOC_IDS[index + 1]}">Next: ${docsEscape(DOC_CONTENT[DOC_IDS[index + 1]].title)}</a>` : ''}</nav>`);
  document.title = `${doc.title} | StreamBridge Docs`;
  document.getElementById('docsReading').scrollTop = 0;
  document.getElementById('docsStatus').textContent = '';
  renderDocsNav(document.getElementById('docsSearch').value);
}

function routeDoc() {
  const hash = location.hash.slice(1);
  const section = hash.match(/^(.*)-section-\d+$/);
  const requested = section ? section[1] : hash;
  const id = Object.hasOwn(DOC_CONTENT, requested) ? requested : 'overview';
  if (currentDoc !== id) showDoc(id);
  if (section) document.getElementById(hash)?.scrollIntoView({ block: 'start' });
}

document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('view-docs')) return;
  const sidebar = document.querySelector('.docs-sidebar');
  const menu = document.getElementById('docsMenu');
  menu.addEventListener('click', () => {
    const open = sidebar.classList.toggle('is-open');
    menu.setAttribute('aria-expanded', String(open));
  });
  document.getElementById('docsSearch').addEventListener('input', event => {
    if (event.target.value) {
      sidebar.classList.add('is-open');
      menu.setAttribute('aria-expanded', 'true');
    }
    renderDocsNav(event.target.value);
  });
  document.getElementById('docsNav').addEventListener('click', event => {
    if (!event.target.closest('a')) return;
    sidebar.classList.remove('is-open');
    menu.setAttribute('aria-expanded', 'false');
    requestAnimationFrame(() => document.querySelector('#docsContent h1')?.focus({ preventScroll: true }));
  });
  document.getElementById('docsContent').addEventListener('click', async event => {
    const button = event.target.closest('.docs-copy');
    if (!button) return;
    const code = button.closest('.docs-code').querySelector('code').textContent;
    try {
      await navigator.clipboard.writeText(code);
      document.getElementById('docsStatus').textContent = 'Code copied.';
      button.title = 'Copied';
    } catch {
      document.getElementById('docsStatus').textContent = 'Clipboard unavailable. Select the example text to copy it.';
    }
  });
  window.addEventListener('hashchange', routeDoc);
  routeDoc();
});
