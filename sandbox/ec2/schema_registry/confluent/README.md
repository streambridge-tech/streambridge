## Api docs
https://docs.confluent.io/platform/current/schema-registry/develop/using.html#starting-sr

## Register an Avro schema
```bash
curl -X POST \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{
    "schema": "{\"type\":\"record\",\"name\":\"User\",\"fields\":[{\"name\":\"id\",\"type\":\"int\"},{\"name\":\"name\",\"type\":\"string\"}]}"
  }' \
  http://localhost:8081/subjects/users-value/versions
```

## list subjects
```bash
curl http://localhost:8081/subjects
```

## get versions
```bash
curl http://localhost:8081/subjects/users-value/versions
```
## 5. Get the schema
```bash
curl http://localhost:8081/subjects/users-value/versions/1
or
curl http://localhost:8081/subjects/users-value/versions/1/schema
```


```bash
```


```bash
```
