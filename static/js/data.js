// ──────────────────────────────────────────────
// DATA
// ──────────────────────────────────────────────
const connections = [
  { id: 2, name: 'kafka-prod-broker', type: 'kafka',   subtype: 'Apache Kafka', host: 'kafka-broker-1:9092',           status: 'live',  usedIn: [] },
  { id: 6, name: 'kafka-dev-broker',  type: 'kafka',   subtype: 'Apache Kafka', host: 'localhost:9092',                status: 'live',  usedIn: [] },
  { id: 7, name: 'connect-prod',      type: 'connect', subtype: 'Kafka Connect',host: 'kafka-connect:8083',            status: 'live',  usedIn: [] },
];

// pipelines are loaded by the Pipelines workbench
const pipelines = [];

// ──────────────────────────────────────────────
// SCHEMA REGISTRY MOCK DATA
// ──────────────────────────────────────────────
const SCHEMA_REGISTRY_DATA = {
  'confluent-schema-registry': {
    url: 'https://psrc-abc123.us-east-2.aws.confluent.cloud',
    subjects: {
      'inventory.public.users-value': {
        schemaType: 'AVRO',
        compatibility: 'BACKWARD',
        versions: [
          {
            version: 1,
            id: 1001,
            schema: {
              type: 'record',
              name: 'users_value',
              namespace: 'inventory.public',
              fields: [
                { name: 'id',         type: 'int',    doc: 'Primary key' },
                { name: 'email',      type: 'string', doc: 'User email address' },
                { name: 'name',       type: 'string', doc: 'Full name' },
                { name: 'created_at', type: 'string', doc: 'ISO 8601 creation timestamp' },
              ],
            },
          },
          {
            version: 2,
            id: 1002,
            schema: {
              type: 'record',
              name: 'users_value',
              namespace: 'inventory.public',
              fields: [
                { name: 'id',         type: 'int',    doc: 'Primary key' },
                { name: 'email',      type: 'string', doc: 'User email address' },
                { name: 'name',       type: 'string', doc: 'Full name' },
                { name: 'plan',       type: ['null','string'], default: null, doc: 'Subscription plan' },
                { name: 'created_at', type: 'string', doc: 'ISO 8601 creation timestamp' },
              ],
            },
          },
          {
            version: 3,
            id: 1003,
            schema: {
              type: 'record',
              name: 'users_value',
              namespace: 'inventory.public',
              fields: [
                { name: 'id',         type: 'int',    doc: 'Primary key' },
                { name: 'email',      type: 'string', doc: 'User email address' },
                { name: 'name',       type: 'string', doc: 'Full name' },
                { name: 'plan',       type: ['null','string'], default: null, doc: 'Subscription plan' },
                { name: 'mfa_enabled',type: 'boolean', default: false, doc: 'Multi-factor auth flag' },
                { name: 'created_at', type: 'string', doc: 'ISO 8601 creation timestamp' },
                { name: 'updated_at', type: 'string', doc: 'ISO 8601 last-update timestamp' },
              ],
            },
          },
        ],
      },
      'inventory.public.orders-value': {
        schemaType: 'AVRO',
        compatibility: 'FULL',
        versions: [
          {
            version: 1,
            id: 1010,
            schema: {
              type: 'record',
              name: 'orders_value',
              namespace: 'inventory.public',
              fields: [
                { name: 'id',          type: 'int',    doc: 'Order ID' },
                { name: 'customer_id', type: 'int',    doc: 'FK → users.id' },
                { name: 'status',      type: 'string', doc: 'Order lifecycle status' },
                { name: 'amount',      type: 'double', doc: 'Total order amount' },
                { name: 'currency',    type: 'string', doc: 'ISO 4217 currency code' },
                { name: 'created_at',  type: 'string', doc: 'ISO 8601 creation timestamp' },
              ],
            },
          },
          {
            version: 2,
            id: 1011,
            schema: {
              type: 'record',
              name: 'orders_value',
              namespace: 'inventory.public',
              fields: [
                { name: 'id',          type: 'int',    doc: 'Order ID' },
                { name: 'customer_id', type: 'int',    doc: 'FK → users.id' },
                { name: 'status',      type: 'string', doc: 'Order lifecycle status' },
                { name: 'amount',      type: 'double', doc: 'Total order amount' },
                { name: 'currency',    type: 'string', doc: 'ISO 4217 currency code' },
                { name: 'warehouse',   type: ['null','string'], default: null, doc: 'Fulfillment warehouse region' },
                { name: 'created_at',  type: 'string', doc: 'ISO 8601 creation timestamp' },
                { name: 'updated_at',  type: 'string', doc: 'ISO 8601 last-update timestamp' },
              ],
            },
          },
        ],
      },
      'analytics.events-value': {
        schemaType: 'JSON',
        compatibility: 'NONE',
        versions: [
          {
            version: 1,
            id: 1020,
            schema: {
              $schema: 'http://json-schema.org/draft-07/schema#',
              title: 'AnalyticsEvent',
              type: 'object',
              required: ['event', 'session_id', 'user_id'],
              properties: {
                event:      { type: 'string',  description: 'Event name' },
                session_id: { type: 'string',  description: 'Browser session identifier' },
                user_id:    { type: 'string',  description: 'FK → users.user_id' },
                page:       { type: 'string',  description: 'URL path where event fired' },
                element:    { type: 'string',  description: 'DOM element identifier (click events)' },
                latency_ms: { type: 'integer', description: 'API call latency in milliseconds' },
                country:    { type: 'string',  description: 'ISO 3166-1 alpha-2 country code' },
              },
            },
          },
        ],
      },
      'ecommerce.public.customers-value': {
        schemaType: 'AVRO',
        compatibility: 'BACKWARD',
        versions: [
          {
            version: 1,
            id: 1030,
            schema: {
              type: 'record',
              name: 'customers_value',
              namespace: 'ecommerce.public',
              fields: [
                { name: 'id',      type: 'int',    doc: 'Customer ID' },
                { name: 'email',   type: 'string', doc: 'Contact email' },
                { name: 'name',    type: 'string', doc: 'Display name' },
                { name: 'tier',    type: 'string', doc: 'bronze | silver | gold' },
                { name: 'country', type: 'string', doc: 'ISO 3166-1 alpha-2' },
              ],
            },
          },
        ],
      },
    },
  },
  'dev-schema-registry': {
    url: 'http://schema-registry.dev.internal:8081',
    subjects: {},
  },
};

// ──────────────────────────────────────────────
// KAFKA TOPICS MOCK DATA
// ──────────────────────────────────────────────
const KAFKA_TOPICS_DATA = {
  'kafka-prod-broker': {
    'ecommerce.public.orders': [
      { partition:0, offset:142, timestamp:'2026-09-02T14:23:01.441Z', key:'"10045"', value:{ id:10045, customer_id:8821, status:'shipped', amount:129.99, currency:'USD', warehouse:'us-east-1', updated_at:'2026-09-02T14:22:59Z' } },
      { partition:0, offset:141, timestamp:'2026-09-02T14:22:58.102Z', key:'"10044"', value:{ id:10044, customer_id:3312, status:'processing', amount:74.50, currency:'USD', warehouse:'us-west-2', updated_at:'2026-09-02T14:22:55Z' } },
      { partition:0, offset:140, timestamp:'2026-09-02T14:22:47.839Z', key:'"10043"', value:{ id:10043, customer_id:9901, status:'delivered', amount:212.00, currency:'USD', warehouse:'eu-west-1', updated_at:'2026-09-02T14:22:45Z' } },
      { partition:0, offset:139, timestamp:'2026-09-02T14:22:31.221Z', key:'"10042"', value:null },
      { partition:0, offset:138, timestamp:'2026-09-02T14:22:18.003Z', key:'"10041"', value:{ id:10041, customer_id:5544, status:'pending', amount:59.99, currency:'USD', warehouse:'us-east-1', updated_at:'2026-09-02T14:22:16Z' } },
      { partition:0, offset:137, timestamp:'2026-09-02T14:21:55.774Z', key:'"10040"', value:{ id:10040, customer_id:7723, status:'shipped', amount:349.00, currency:'USD', warehouse:'us-east-1', updated_at:'2026-09-02T14:21:53Z' } },
      { partition:0, offset:136, timestamp:'2026-09-02T14:21:40.519Z', key:'"10039"', value:{ id:10039, customer_id:1102, status:'refunded', amount:89.99, currency:'USD', warehouse:'us-west-2', updated_at:'2026-09-02T14:21:38Z' } },
      { partition:0, offset:135, timestamp:'2026-09-02T14:21:22.887Z', key:'"10038"', value:{ id:10038, customer_id:6634, status:'delivered', amount:44.00, currency:'USD', warehouse:'eu-west-1', updated_at:'2026-09-02T14:21:20Z' } },
      { partition:0, offset:134, timestamp:'2026-09-02T14:21:09.340Z', key:'"10037"', value:{ id:10037, customer_id:2289, status:'processing', amount:177.50, currency:'USD', warehouse:'us-east-1', updated_at:'2026-09-02T14:21:07Z' } },
      { partition:0, offset:133, timestamp:'2026-09-02T14:20:54.112Z', key:'"10036"', value:{ id:10036, customer_id:4417, status:'shipped', amount:92.00, currency:'USD', warehouse:'ap-southeast-1', updated_at:'2026-09-02T14:20:52Z' } },
    ],
    'ecommerce.public.customers': [
      { partition:0, offset:88, timestamp:'2026-09-02T14:22:44.901Z', key:'"8821"', value:{ id:8821, email:'alex.murphy@example.com', name:'Alex Murphy', tier:'gold', country:'US', updated_at:'2026-09-02T14:22:42Z' } },
      { partition:0, offset:87, timestamp:'2026-09-02T14:22:30.617Z', key:'"3312"', value:{ id:3312, email:'priya.shah@example.com', name:'Priya Shah', tier:'silver', country:'IN', updated_at:'2026-09-02T14:22:28Z' } },
      { partition:0, offset:86, timestamp:'2026-09-02T14:22:15.228Z', key:'"9901"', value:{ id:9901, email:'tom.reeves@example.com', name:'Tom Reeves', tier:'bronze', country:'GB', updated_at:'2026-09-02T14:22:13Z' } },
      { partition:0, offset:85, timestamp:'2026-09-02T14:22:01.443Z', key:'"5544"', value:null },
      { partition:0, offset:84, timestamp:'2026-09-02T14:21:48.092Z', key:'"7723"', value:{ id:7723, email:'sara.kim@example.com', name:'Sara Kim', tier:'gold', country:'KR', updated_at:'2026-09-02T14:21:46Z' } },
      { partition:0, offset:83, timestamp:'2026-09-02T14:21:33.719Z', key:'"1102"', value:{ id:1102, email:'carlos.diaz@example.com', name:'Carlos Diaz', tier:'silver', country:'MX', updated_at:'2026-09-02T14:21:31Z' } },
      { partition:0, offset:82, timestamp:'2026-09-02T14:21:19.004Z', key:'"6634"', value:{ id:6634, email:'nina.wolf@example.com', name:'Nina Wolf', tier:'bronze', country:'DE', updated_at:'2026-09-02T14:21:17Z' } },
      { partition:0, offset:81, timestamp:'2026-09-02T14:21:05.552Z', key:'"2289"', value:{ id:2289, email:'james.osei@example.com', name:'James Osei', tier:'gold', country:'GH', updated_at:'2026-09-02T14:21:03Z' } },
      { partition:0, offset:80, timestamp:'2026-09-02T14:20:51.338Z', key:'"4417"', value:{ id:4417, email:'liu.yan@example.com', name:'Liu Yan', tier:'silver', country:'CN', updated_at:'2026-09-02T14:20:49Z' } },
      { partition:0, offset:79, timestamp:'2026-09-02T14:20:37.891Z', key:'"8801"', value:{ id:8801, email:'fatima.al-farsi@example.com', name:'Fatima Al-Farsi', tier:'bronze', country:'AE', updated_at:'2026-09-02T14:20:35Z' } },
    ],
    'users.cdc.profiles': [
      { partition:0, offset:301, timestamp:'2026-09-02T14:23:10.007Z', key:'"usr_4829"', value:{ user_id:'usr_4829', username:'alex_m', email:'alex.murphy@example.com', plan:'pro', mfa_enabled:true, last_login:'2026-09-02T14:20:00Z' } },
      { partition:0, offset:300, timestamp:'2026-09-02T14:22:59.334Z', key:'"usr_1173"', value:{ user_id:'usr_1173', username:'priya_s', email:'priya.shah@example.com', plan:'free', mfa_enabled:false, last_login:'2026-09-02T13:45:00Z' } },
      { partition:0, offset:299, timestamp:'2026-09-02T14:22:48.112Z', key:'"usr_7744"', value:null },
      { partition:0, offset:298, timestamp:'2026-09-02T14:22:37.889Z', key:'"usr_2291"', value:{ user_id:'usr_2291', username:'tom_r', email:'tom.reeves@example.com', plan:'enterprise', mfa_enabled:true, last_login:'2026-09-02T14:10:00Z' } },
      { partition:0, offset:297, timestamp:'2026-09-02T14:22:26.441Z', key:'"usr_9983"', value:{ user_id:'usr_9983', username:'sara_k', email:'sara.kim@example.com', plan:'pro', mfa_enabled:true, last_login:'2026-09-02T12:30:00Z' } },
      { partition:0, offset:296, timestamp:'2026-09-02T14:22:15.220Z', key:'"usr_3347"', value:{ user_id:'usr_3347', username:'carlos_d', email:'carlos.diaz@example.com', plan:'free', mfa_enabled:false, last_login:'2026-09-01T20:15:00Z' } },
      { partition:0, offset:295, timestamp:'2026-09-02T14:22:04.008Z', key:'"usr_6612"', value:{ user_id:'usr_6612', username:'nina_w', email:'nina.wolf@example.com', plan:'pro', mfa_enabled:true, last_login:'2026-09-02T11:00:00Z' } },
      { partition:0, offset:294, timestamp:'2026-09-02T14:21:53.671Z', key:'"usr_5501"', value:{ user_id:'usr_5501', username:'james_o', email:'james.osei@example.com', plan:'enterprise', mfa_enabled:true, last_login:'2026-09-02T14:05:00Z' } },
      { partition:0, offset:293, timestamp:'2026-09-02T14:21:42.339Z', key:'"usr_8870"', value:{ user_id:'usr_8870', username:'liu_y', email:'liu.yan@example.com', plan:'free', mfa_enabled:false, last_login:'2026-09-02T09:00:00Z' } },
      { partition:0, offset:292, timestamp:'2026-09-02T14:21:31.117Z', key:'"usr_1190"', value:{ user_id:'usr_1190', username:'fatima_af', email:'fatima.al-farsi@example.com', plan:'pro', mfa_enabled:true, last_login:'2026-09-02T13:00:00Z' } },
    ],
    'analytics.events': [
      { partition:0, offset:5521, timestamp:'2026-09-02T14:23:08.771Z', key:'"evt_a1b2"', value:{ event:'page_view', session_id:'s_88cx', user_id:'usr_4829', page:'/dashboard', duration_ms:1240, referrer:'direct' } },
      { partition:0, offset:5520, timestamp:'2026-09-02T14:23:07.334Z', key:'"evt_c3d4"', value:{ event:'button_click', session_id:'s_88cx', user_id:'usr_4829', element:'deploy_btn', page:'/pipelines/orders-cdc' } },
      { partition:0, offset:5519, timestamp:'2026-09-02T14:23:05.990Z', key:'"evt_e5f6"', value:{ event:'api_call', session_id:'s_77bw', user_id:'usr_1173', endpoint:'/api/connections', method:'GET', latency_ms:34 } },
      { partition:0, offset:5518, timestamp:'2026-09-02T14:23:04.441Z', key:'"evt_g7h8"', value:null },
      { partition:0, offset:5517, timestamp:'2026-09-02T14:23:02.118Z', key:'"evt_i9j0"', value:{ event:'page_view', session_id:'s_66av', user_id:'usr_2291', page:'/connections', duration_ms:820, referrer:'/pipelines' } },
      { partition:0, offset:5516, timestamp:'2026-09-02T14:23:00.774Z', key:'"evt_k1l2"', value:{ event:'login', session_id:'s_55zu', user_id:'usr_9983', method:'sso', ip:'203.0.113.42', country:'KR' } },
      { partition:0, offset:5515, timestamp:'2026-09-02T14:22:59.330Z', key:'"evt_m3n4"', value:{ event:'error', session_id:'s_44yt', user_id:'usr_3347', code:'ERR_CONN_TIMEOUT', page:'/pipelines', stack_depth:3 } },
      { partition:0, offset:5514, timestamp:'2026-09-02T14:22:57.881Z', key:'"evt_o5p6"', value:{ event:'page_view', session_id:'s_33xs', user_id:'usr_6612', page:'/docs', duration_ms:3410, referrer:'google.com' } },
      { partition:0, offset:5513, timestamp:'2026-09-02T14:22:56.447Z', key:'"evt_q7r8"', value:{ event:'api_call', session_id:'s_22wr', user_id:'usr_5501', endpoint:'/api/connections', method:'POST', latency_ms:112 } },
      { partition:0, offset:5512, timestamp:'2026-09-02T14:22:55.003Z', key:'"evt_s9t0"', value:{ event:'logout', session_id:'s_11vq', user_id:'usr_8870', duration_s:1842 } },
    ],
  },
  'kafka-dev-broker': {},
};
