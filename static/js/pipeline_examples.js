/** Mock pipeline YAML samples for the Pipelines workbench. */
window.PL_EXAMPLES = [
  {
    name: "payments-ledger.yaml",
    yaml: `pipeline:
  name: payments-ledger
  stage: all_stages
  stages:
    development:
      vault: dev
    staging:
      vault: staging
    production:
      vault: prod
  common:
    pg_plugin: postgres-json
    s3_plugin: s3-json
    snowflake_plugin: snowflake-json
    topic_prefix: payments
    snapshot_mode: initial
  connector:
    "payments-pg-cdc-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.port: "{pg_port}"
        database.user: "{pg_username}"
        database.password: "{pg_password}"
        database.dbname: "{pg_database}"
        database.include.list: payments,ledger,settlement
        table.include.list: payments.txns,payments.refunds,ledger.entries,ledger.accounts,settlement.batches
        slot.name: "payments_cdc_{stage}"
        publication.name: "payments_pub_{stage}"
        plugin.name: pgoutput
        snapshot.mode: "{snapshot_mode}"
        topic.prefix: "{topic_prefix}"
        schema.history.internal.kafka.bootstrap.servers: "{kafka_bootstrap}"
        heartbeat.interval.ms: "10000"
        decimal.handling.mode: string
      alerts:
        - name: "{connector_name}-failed"
          metric: connector_status
          value: FAILED
          channel: "{finops_slack}"
        - name: "{connector_name}-lag"
          metric: source_record_lag
          op: gt
          value: 30000
          channel: "{finops_pager}"
    "payments-refunds-cdc-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.password: "{pg_password}"
        table.include.list: payments.refunds,payments.chargebacks
        slot.name: "payments_refunds_{stage}"
        topic.prefix: "{topic_prefix}"
    "payments-s3-bronze-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: payments.payments.txns,payments.payments.refunds,payments.ledger.entries
        s3.bucket.name: "{s3_bucket}"
        s3.region: "{s3_region}"
        aws.access.key.id: "{s3_access_key}"
        aws.secret.access.key: "{s3_secret_key}"
        topics.dir: "bronze/{topic_prefix}/{stage}"
        format.class: io.confluent.connect.s3.format.parquet.ParquetFormat
        rotate.interval.ms: "300000"
        flush.size: "10000"
        errors.tolerance: all
        errors.deadletterqueue.topic.name: "payments.dlq.{stage}"
    "payments-s3-silver-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: payments.ledger.accounts,payments.settlement.batches
        s3.bucket.name: "{s3_bucket}"
        topics.dir: "silver/{topic_prefix}/{stage}"
        partitioner.class: io.confluent.connect.storage.partitioner.TimeBasedPartitioner
        path.format: "'year'=YYYY/'month'=MM/'day'=dd"
    "payments-snowflake-{stage}":
      plugin: "{snowflake_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        snowflake.url.name: "{snowflake_url}"
        snowflake.user.name: "{snowflake_user}"
        snowflake.private.key: "{snowflake_private_key}"
        snowflake.database.name: "{snowflake_database}"
        snowflake.schema.name: "PAYMENTS_{stage}"
        topics: payments.payments.txns,payments.ledger.entries
        buffer.count.records: "10000"
        buffer.flush.time: "60"
    "payments-audit-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: payments.payments.chargebacks
        s3.bucket.name: "{s3_audit_bucket}"
        topics.dir: "audit/{topic_prefix}/{stage}"
        s3.compression.type: gzip
`
  },
  {
    name: "inventory-oms.yaml",
    yaml: `pipeline:
  name: inventory-oms
  stage: all_stages
  stages:
    development:
      vault: dev
    production:
      vault: prod
  common:
    mysql_plugin: mysql-json
    pg_plugin: postgres-json
    s3_plugin: s3-json
    es_plugin: elasticsearch-json
    topic_prefix: inventory
  connector:
    "inventory-mysql-catalog-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.port: "{mysql_port}"
        database.user: "{mysql_username}"
        database.password: "{mysql_password}"
        database.include.list: catalog,pricing
        table.include.list: catalog.products,catalog.skus,catalog.categories,pricing.price_list,pricing.promos
        database.server.id: "{mysql_server_id}"
        topic.prefix: "{topic_prefix}"
        snapshot.locking.mode: none
        include.schema.changes: "true"
        schema.history.internal.kafka.bootstrap.servers: "{kafka_bootstrap}"
      alerts:
        - name: "{connector_name}-failed"
          metric: connector_status
          value: FAILED
          channel: "{ops_slack}"
    "inventory-mysql-stock-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.password: "{mysql_password}"
        table.include.list: catalog.stock_levels,catalog.reservations,catalog.transfers
        database.server.id: "{mysql_stock_server_id}"
        topic.prefix: "{topic_prefix}"
    "inventory-pg-warehouse-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.password: "{pg_password}"
        database.dbname: "{pg_database}"
        table.include.list: warehouse.bins,warehouse.locations,warehouse.cycles
        slot.name: "inventory_wh_{stage}"
        topic.prefix: "{topic_prefix}"
    "inventory-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: inventory.catalog.products,inventory.catalog.skus,inventory.catalog.stock_levels
        s3.bucket.name: "{s3_bucket}"
        s3.region: "{s3_region}"
        aws.access.key.id: "{s3_access_key}"
        aws.secret.access.key: "{s3_secret_key}"
        topics.dir: "{topic_prefix}/{stage}"
        format.class: io.confluent.connect.s3.format.json.JsonFormat
        flush.size: "5000"
    "inventory-search-{stage}":
      plugin: "{es_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        connection.url: "{es_url}"
        connection.username: "{es_username}"
        connection.password: "{es_password}"
        topics: inventory.catalog.products,inventory.catalog.skus
        type.name: _doc
        key.ignore: "false"
        schema.ignore: "true"
        behavior.on.null.values: delete
    "inventory-dlq-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: inventory.dlq.{stage}
        s3.bucket.name: "{s3_dlq_bucket}"
        topics.dir: "dlq/{topic_prefix}/{stage}"
`
  },
  {
    name: "clickstream-lake.yaml",
    yaml: `pipeline:
  name: clickstream-lake
  stage: all_stages
  stages:
    development:
      vault: dev
    production:
      vault: prod
  common:
    mysql_plugin: mysql-json
    s3_plugin: s3-json
    iceberg_plugin: iceberg-json
    topic_prefix: clickstream
  connector:
    "click-mysql-sessions-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.user: "{mysql_username}"
        database.password: "{mysql_password}"
        table.include.list: web.sessions,web.pageviews,web.identify
        database.server.id: "{mysql_server_id}"
        topic.prefix: "{topic_prefix}"
        snapshot.mode: schema_only
        tombstones.on.delete: "false"
      alerts:
        - name: "{connector_name}-failed"
          metric: connector_status
          value: FAILED
          channel: "{data_slack}"
    "click-mysql-experiments-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.password: "{mysql_password}"
        table.include.list: web.experiments,web.assignments,web.goals
        database.server.id: "{mysql_exp_server_id}"
        topic.prefix: "{topic_prefix}"
    "click-s3-bronze-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: clickstream.web.sessions,clickstream.web.pageviews,clickstream.web.identify
        s3.bucket.name: "{s3_lake_bucket}"
        s3.region: "{s3_region}"
        aws.access.key.id: "{s3_access_key}"
        aws.secret.access.key: "{s3_secret_key}"
        topics.dir: "bronze/{topic_prefix}/{stage}"
        format.class: io.confluent.connect.s3.format.avro.AvroFormat
        rotate.schedule.interval.ms: "3600000"
        flush.size: "50000"
        s3.compression.type: gzip
    "click-s3-silver-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: clickstream.web.experiments,clickstream.web.assignments
        s3.bucket.name: "{s3_lake_bucket}"
        topics.dir: "silver/{topic_prefix}/{stage}"
        partitioner.class: io.confluent.connect.storage.partitioner.HourlyPartitioner
    "click-iceberg-{stage}":
      plugin: "{iceberg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        iceberg.catalog: "{iceberg_catalog}"
        iceberg.warehouse: "{iceberg_warehouse}"
        iceberg.tables: "lake.click_pageviews,lake.click_sessions"
        iceberg.control.topic: "click.iceberg.control.{stage}"
        topics: clickstream.web.pageviews,clickstream.web.sessions
    "click-identity-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: clickstream.web.identify
        s3.bucket.name: "{s3_pii_bucket}"
        topics.dir: "restricted/{topic_prefix}/{stage}"
        s3.sse.kms.key.id: "{s3_kms_key}"
`
  },
  {
    name: "crm-hub.yaml",
    yaml: `pipeline:
  name: crm-hub
  stage: all_stages
  stages:
    development:
      vault: dev
    production:
      vault: prod
  common:
    pg_plugin: postgres-json
    s3_plugin: s3-json
    jdbc_plugin: jdbc-json
    topic_prefix: crm
  connector:
    "crm-pg-accounts-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.port: "{pg_port}"
        database.user: "{pg_username}"
        database.password: "{pg_password}"
        database.dbname: "{pg_database}"
        table.include.list: crm.accounts,crm.contacts,crm.owners
        slot.name: "crm_accounts_{stage}"
        publication.autocreate.mode: filtered
        topic.prefix: "{topic_prefix}"
        transforms: unwrap
        transforms.unwrap.type: io.debezium.transforms.ExtractNewRecordState
        transforms.unwrap.drop.tombstones: "false"
      alerts:
        - name: "{connector_name}-failed"
          metric: connector_status
          value: FAILED
          channel: "{revops_slack}"
    "crm-pg-pipeline-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.password: "{pg_password}"
        table.include.list: crm.deals,crm.stages,crm.activities,crm.tasks
        slot.name: "crm_deals_{stage}"
        topic.prefix: "{topic_prefix}"
    "crm-pg-marketing-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.password: "{pg_password}"
        table.include.list: crm.campaigns,crm.leads,crm.forms
        slot.name: "crm_mkt_{stage}"
        topic.prefix: "{topic_prefix}"
    "crm-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: crm.crm.accounts,crm.crm.contacts,crm.crm.deals,crm.crm.leads
        s3.bucket.name: "{s3_bucket}"
        s3.region: "{s3_region}"
        aws.access.key.id: "{s3_access_key}"
        aws.secret.access.key: "{s3_secret_key}"
        topics.dir: "{topic_prefix}/{stage}"
        format.class: io.confluent.connect.s3.format.parquet.ParquetFormat
    "crm-warehouse-{stage}":
      plugin: "{jdbc_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        connection.url: "{warehouse_jdbc}"
        connection.user: "{warehouse_user}"
        connection.password: "{warehouse_password}"
        topics: crm.crm.accounts,crm.crm.deals
        insert.mode: upsert
        pk.mode: record_key
        table.name.format: "crm_{stage}"
        batch.size: "2000"
    "crm-audit-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: crm.crm.activities,crm.crm.tasks
        s3.bucket.name: "{s3_audit_bucket}"
        topics.dir: "audit/{topic_prefix}/{stage}"
`
  },
  {
    name: "iot-fleet.yaml",
    yaml: `pipeline:
  name: iot-fleet
  stage: all_stages
  stages:
    development:
      vault: dev
    production:
      vault: prod
  common:
    mysql_plugin: mysql-json
    pg_plugin: postgres-json
    s3_plugin: s3-json
    topic_prefix: iot
  connector:
    "iot-mysql-devices-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.user: "{mysql_username}"
        database.password: "{mysql_password}"
        table.include.list: fleet.devices,fleet.firmware,fleet.sim_cards
        database.server.id: "{mysql_server_id}"
        topic.prefix: "{topic_prefix}"
        include.query: "false"
      alerts:
        - name: "{connector_name}-failed"
          metric: connector_status
          value: FAILED
          channel: "{iot_slack}"
        - name: "{connector_name}-offline"
          metric: source_record_poll_rate
          op: lt
          value: 1
          channel: "{iot_pager}"
    "iot-mysql-trips-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.password: "{mysql_password}"
        table.include.list: fleet.trips,fleet.geofences,fleet.alerts
        database.server.id: "{mysql_trips_server_id}"
        topic.prefix: "{topic_prefix}"
    "iot-pg-telemetry-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.password: "{pg_password}"
        database.dbname: "{pg_database}"
        table.include.list: telemetry.readings,telemetry.heartbeats,telemetry.faults
        slot.name: "iot_tel_{stage}"
        topic.prefix: "{topic_prefix}"
        decimal.handling.mode: double
        time.precision.mode: adaptive
    "iot-s3-hot-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: iot.telemetry.readings,iot.telemetry.heartbeats
        s3.bucket.name: "{s3_hot_bucket}"
        s3.region: "{s3_region}"
        aws.access.key.id: "{s3_access_key}"
        aws.secret.access.key: "{s3_secret_key}"
        topics.dir: "hot/{topic_prefix}/{stage}"
        rotate.interval.ms: "60000"
        flush.size: "20000"
        format.class: io.confluent.connect.s3.format.avro.AvroFormat
    "iot-s3-cold-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: iot.fleet.trips,iot.telemetry.faults
        s3.bucket.name: "{s3_cold_bucket}"
        topics.dir: "cold/{topic_prefix}/{stage}"
        storage.class.override: GLACIER_IR
    "iot-fault-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: iot.fleet.alerts
        s3.bucket.name: "{s3_ops_bucket}"
        topics.dir: "faults/{topic_prefix}/{stage}"
`
  },
  {
    name: "media-catalog.yaml",
    yaml: `pipeline:
  name: media-catalog
  stage: all_stages
  stages:
    development:
      vault: dev
    production:
      vault: prod
  common:
    mysql_plugin: mysql-json
    s3_plugin: s3-json
    search_plugin: opensearch-json
    topic_prefix: media
  connector:
    "media-mysql-titles-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.user: "{mysql_username}"
        database.password: "{mysql_password}"
        table.include.list: catalog.titles,catalog.seasons,catalog.episodes,catalog.genres
        database.server.id: "{mysql_server_id}"
        topic.prefix: "{topic_prefix}"
        snapshot.mode: when_needed
      alerts:
        - name: "{connector_name}-failed"
          metric: connector_status
          value: FAILED
          channel: "{media_slack}"
    "media-mysql-assets-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.password: "{mysql_password}"
        table.include.list: catalog.assets,catalog.captions,catalog.artwork,catalog.audio_tracks
        database.server.id: "{mysql_assets_server_id}"
        topic.prefix: "{topic_prefix}"
    "media-mysql-plays-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.password: "{mysql_password}"
        table.include.list: playback.sessions,playback.heartbeats,playback.errors
        database.server.id: "{mysql_plays_server_id}"
        topic.prefix: "{topic_prefix}"
    "media-s3-catalog-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: media.catalog.titles,media.catalog.seasons,media.catalog.episodes,media.catalog.assets
        s3.bucket.name: "{s3_bucket}"
        s3.region: "{s3_region}"
        aws.access.key.id: "{s3_access_key}"
        aws.secret.access.key: "{s3_secret_key}"
        topics.dir: "{topic_prefix}/catalog/{stage}"
        format.class: io.confluent.connect.s3.format.json.JsonFormat
    "media-s3-playback-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: media.playback.sessions,media.playback.heartbeats
        s3.bucket.name: "{s3_bucket}"
        topics.dir: "{topic_prefix}/playback/{stage}"
        format.class: io.confluent.connect.s3.format.parquet.ParquetFormat
        flush.size: "25000"
    "media-search-{stage}":
      plugin: "{search_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        connection.url: "{opensearch_url}"
        connection.username: "{opensearch_user}"
        connection.password: "{opensearch_password}"
        topics: media.catalog.titles,media.catalog.episodes
        key.ignore: "false"
        schema.ignore: "true"
        behavior.on.malformed.documents: warn
`
  },
  {
    name: "logistics-network.yaml",
    yaml: `pipeline:
  name: logistics-network
  stage: all_stages
  stages:
    development:
      vault: dev
    production:
      vault: prod
  common:
    pg_plugin: postgres-json
    s3_plugin: s3-json
    snowflake_plugin: snowflake-json
    topic_prefix: logistics
  connector:
    "logistics-pg-shipments-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.user: "{pg_username}"
        database.password: "{pg_password}"
        database.dbname: "{pg_database}"
        table.include.list: ops.shipments,ops.parcels,ops.manifests,ops.exceptions
        slot.name: "logistics_ship_{stage}"
        topic.prefix: "{topic_prefix}"
        heartbeat.action.query: "INSERT INTO ops.heartbeat (ts) VALUES (now())"
      alerts:
        - name: "{connector_name}-failed"
          metric: connector_status
          value: FAILED
          channel: "{logistics_slack}"
    "logistics-pg-stops-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.password: "{pg_password}"
        table.include.list: ops.stops,ops.routes,ops.windows
        slot.name: "logistics_stops_{stage}"
        topic.prefix: "{topic_prefix}"
    "logistics-pg-vehicles-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.password: "{pg_password}"
        table.include.list: ops.vehicles,ops.drivers,ops.depots
        slot.name: "logistics_fleet_{stage}"
        topic.prefix: "{topic_prefix}"
    "logistics-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: logistics.ops.shipments,logistics.ops.parcels,logistics.ops.stops,logistics.ops.vehicles
        s3.bucket.name: "{s3_bucket}"
        s3.region: "{s3_region}"
        aws.access.key.id: "{s3_access_key}"
        aws.secret.access.key: "{s3_secret_key}"
        topics.dir: "{topic_prefix}/{stage}"
        locale: en
        timezone: UTC
        path.format: "'dt'=YYYY-MM-dd"
    "logistics-snowflake-{stage}":
      plugin: "{snowflake_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        snowflake.url.name: "{snowflake_url}"
        snowflake.user.name: "{snowflake_user}"
        snowflake.private.key: "{snowflake_private_key}"
        snowflake.database.name: "{snowflake_database}"
        snowflake.schema.name: "LOGISTICS_{stage}"
        topics: logistics.ops.shipments,logistics.ops.exceptions
        buffer.flush.time: "30"
    "logistics-exceptions-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: logistics.ops.exceptions
        s3.bucket.name: "{s3_ops_bucket}"
        topics.dir: "exceptions/{topic_prefix}/{stage}"
`
  },
  {
    name: "lending-core.yaml",
    yaml: `pipeline:
  name: lending-core
  stage: all_stages
  stages:
    development:
      vault: dev
    production:
      vault: prod
  common:
    mysql_plugin: mysql-json
    s3_plugin: s3-json
    jdbc_plugin: jdbc-json
    topic_prefix: lending
  connector:
    "lending-mysql-customers-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.user: "{mysql_username}"
        database.password: "{mysql_password}"
        table.include.list: core.customers,core.kyc,core.addresses
        database.server.id: "{mysql_server_id}"
        topic.prefix: "{topic_prefix}"
        column.exclude.list: core.kyc.ssn_hash,core.customers.tax_id
      alerts:
        - name: "{connector_name}-failed"
          metric: connector_status
          value: FAILED
          channel: "{risk_slack}"
    "lending-mysql-loans-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.password: "{mysql_password}"
        table.include.list: core.loans,core.schedules,core.collaterals,core.rates
        database.server.id: "{mysql_loans_server_id}"
        topic.prefix: "{topic_prefix}"
    "lending-mysql-payments-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.password: "{mysql_password}"
        table.include.list: core.payments,core.nsf,core.collections
        database.server.id: "{mysql_pay_server_id}"
        topic.prefix: "{topic_prefix}"
    "lending-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: lending.core.loans,lending.core.payments,lending.core.customers
        s3.bucket.name: "{s3_bucket}"
        s3.region: "{s3_region}"
        aws.access.key.id: "{s3_access_key}"
        aws.secret.access.key: "{s3_secret_key}"
        topics.dir: "{topic_prefix}/{stage}"
        s3.sse.kms.key.id: "{s3_kms_key}"
        format.class: io.confluent.connect.s3.format.parquet.ParquetFormat
    "lending-warehouse-{stage}":
      plugin: "{jdbc_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        connection.url: "{warehouse_jdbc}"
        connection.user: "{warehouse_user}"
        connection.password: "{warehouse_password}"
        topics: lending.core.loans,lending.core.payments
        insert.mode: upsert
        pk.mode: record_key
        auto.create: "false"
        auto.evolve: "false"
    "lending-audit-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: lending.core.kyc,lending.core.collections
        s3.bucket.name: "{s3_audit_bucket}"
        topics.dir: "audit/{topic_prefix}/{stage}"
        s3.acl.canned: bucket-owner-full-control
`
  },
  {
    name: "healthcare-claims.yaml",
    yaml: `pipeline:
  name: healthcare-claims
  stage: all_stages
  stages:
    development:
      vault: dev
    production:
      vault: prod
  common:
    pg_plugin: postgres-json
    s3_plugin: s3-json
    jdbc_plugin: jdbc-json
    topic_prefix: claims
  connector:
    "claims-pg-members-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.user: "{pg_username}"
        database.password: "{pg_password}"
        database.dbname: "{pg_database}"
        table.include.list: member.members,member.coverage,member.dependents
        slot.name: "claims_members_{stage}"
        topic.prefix: "{topic_prefix}"
        column.exclude.list: member.members.mrn,member.members.ssn
      alerts:
        - name: "{connector_name}-failed"
          metric: connector_status
          value: FAILED
          channel: "{hipaa_ops_slack}"
    "claims-pg-providers-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.password: "{pg_password}"
        table.include.list: network.providers,network.npi,network.contracts
        slot.name: "claims_prov_{stage}"
        topic.prefix: "{topic_prefix}"
    "claims-pg-encounters-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.password: "{pg_password}"
        table.include.list: clinical.encounters,clinical.diagnoses,clinical.procedures
        slot.name: "claims_enc_{stage}"
        topic.prefix: "{topic_prefix}"
    "claims-pg-adjudication-{stage}":
      plugin: "{pg_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{pg_host}"
        database.password: "{pg_password}"
        table.include.list: billing.claims,billing.lines,billing.remits,billing.denials
        slot.name: "claims_adj_{stage}"
        topic.prefix: "{topic_prefix}"
    "claims-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: claims.billing.claims,claims.billing.lines,claims.member.coverage
        s3.bucket.name: "{s3_phi_bucket}"
        s3.region: "{s3_region}"
        aws.access.key.id: "{s3_access_key}"
        aws.secret.access.key: "{s3_secret_key}"
        topics.dir: "{topic_prefix}/{stage}"
        s3.sse.kms.key.id: "{s3_kms_key}"
        format.class: io.confluent.connect.s3.format.parquet.ParquetFormat
    "claims-warehouse-{stage}":
      plugin: "{jdbc_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        connection.url: "{warehouse_jdbc}"
        connection.user: "{warehouse_user}"
        connection.password: "{warehouse_password}"
        topics: claims.billing.claims,claims.billing.denials
        insert.mode: upsert
        pk.mode: record_key
        quote.sql.identifiers: always
    "claims-audit-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: claims.clinical.encounters,claims.billing.remits
        s3.bucket.name: "{s3_audit_bucket}"
        topics.dir: "audit/{topic_prefix}/{stage}"
`
  },
  {
    name: "ads-attribution.yaml",
    yaml: `pipeline:
  name: ads-attribution
  stage: all_stages
  stages:
    development:
      vault: dev
    production:
      vault: prod
  common:
    mysql_plugin: mysql-json
    s3_plugin: s3-json
    jdbc_plugin: jdbc-json
    topic_prefix: ads
  connector:
    "ads-mysql-impressions-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.user: "{mysql_username}"
        database.password: "{mysql_password}"
        table.include.list: ads.impressions,ads.viewability,ads.placements
        database.server.id: "{mysql_server_id}"
        topic.prefix: "{topic_prefix}"
        snapshot.mode: schema_only
      alerts:
        - name: "{connector_name}-failed"
          metric: connector_status
          value: FAILED
          channel: "{growth_slack}"
        - name: "{connector_name}-lag"
          metric: source_record_lag
          op: gt
          value: 15000
          channel: "{growth_pager}"
    "ads-mysql-clicks-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.password: "{mysql_password}"
        table.include.list: ads.clicks,ads.conversions,ads.fraud_flags
        database.server.id: "{mysql_clicks_server_id}"
        topic.prefix: "{topic_prefix}"
    "ads-mysql-campaigns-{stage}":
      plugin: "{mysql_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        database.hostname: "{mysql_host}"
        database.password: "{mysql_password}"
        table.include.list: ads.campaigns,ads.adgroups,ads.creatives,ads.budgets
        database.server.id: "{mysql_camp_server_id}"
        topic.prefix: "{topic_prefix}"
    "ads-s3-events-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: ads.ads.impressions,ads.ads.clicks,ads.ads.conversions
        s3.bucket.name: "{s3_lake_bucket}"
        s3.region: "{s3_region}"
        aws.access.key.id: "{s3_access_key}"
        aws.secret.access.key: "{s3_secret_key}"
        topics.dir: "events/{topic_prefix}/{stage}"
        format.class: io.confluent.connect.s3.format.parquet.ParquetFormat
        flush.size: "40000"
        rotate.schedule.interval.ms: "600000"
    "ads-s3-dim-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: ads.ads.campaigns,ads.ads.adgroups,ads.ads.creatives
        s3.bucket.name: "{s3_lake_bucket}"
        topics.dir: "dims/{topic_prefix}/{stage}"
        format.class: io.confluent.connect.s3.format.json.JsonFormat
    "ads-warehouse-{stage}":
      plugin: "{jdbc_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        connection.url: "{warehouse_jdbc}"
        connection.user: "{warehouse_user}"
        connection.password: "{warehouse_password}"
        topics: ads.ads.conversions,ads.ads.campaigns
        insert.mode: upsert
        pk.mode: record_key
        batch.size: "5000"
    "ads-fraud-s3-{stage}":
      plugin: "{s3_plugin}"
      kafka_connect: "{kafka_connect}"
      config:
        topics: ads.ads.fraud_flags,ads.ads.viewability
        s3.bucket.name: "{s3_ops_bucket}"
        topics.dir: "fraud/{topic_prefix}/{stage}"
`
  }
];
