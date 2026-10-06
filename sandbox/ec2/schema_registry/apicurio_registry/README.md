## Managing schema and API artifacts using Apicurio Registry REST API commands
https://www.apicur.io/registry/docs/apicurio-registry/3.3.x/getting-started/assembly-managing-registry-artifacts-api.html

## morw schema example
https://www.apicur.io/blog/2025/11/25/registry-dereference-v3

## Observation to Build generic UI
    1. check what is group
    2. what is subject
    3. what group/subject
    4. what group/subject/versions this is the flow

    levels:
        groups/
            group-1/
                artifacts/
                        artifacts1/ versions

## create schema
```bash
curl -X POST http://localhost:8080/apis/registry/v3/groups/my-group/artifacts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  --data-raw '{
    "artifactId": "share-price",
    "artifactType": "AVRO",
    "firstVersion": {
        "content": {
            "content": "{\"type\":\"record\",\"name\":\" p\",\"namespace\":\"com.example\", \"fields\":[{\"name\":\"symbol\",\"type\":\"string\"},{\"name\":\"price\",\"type\":\"string\"}]}",
            "contentType": "application/json"
        }
    }
}'
```
## Managing schema and API artifact versions using Apicurio Registry REST API commands
```bash
curl -X POST http://localhost:8080/apis/registry/v3/groups/my-group/artifacts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  --data-raw '{
    "artifactId": "my-share-price",
    "artifactType": "AVRO",
    "firstVersion": {
        "version": "1.1.1",
        "content": {
            "content": "{\"type\":\"record\",\"name\":\" p\",\"namespace\":\"com.example\", \"fields\":[{\"name\":\"symbol\",\"type\":\"string\"},{\"name\":\"price\",\"type\":\"string\"}]}",
            "contentType": "application/json"
        }
    }
}'
```

## fetch schema
```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
 http://localhost:8080/apis/registry/v3/groups/my-group/artifacts/share-price/versions/1/content
```

## Retrieve the artifact content from the registry using its artifact ID and version in the API path. In this example, the specified ID is my-share-price and the version is 1.1.1:
```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
    http://localhost:8080/apis/registry/v3/groups/my-group/artifacts/my-share-price/versions/1.1.1/content

```


## Add the ItemId schema artifact that you want to create the nested artifact reference to using the /groups/{groupId}/artifacts operation:
```bash
curl -X POST http://localhost:8080/apis/registry/v3/groups/my-group/artifacts \
   -H "Content-Type: application/json" \
   -H "Authorization: Bearer $ACCESS_TOKEN" \
   --data '{"artifactId":"ItemId","artifactType":"AVRO","firstVersion":{"version":"1.0.0","content":{"content":"{\"namespace\":\"com.example.common\",\"name\":\"ItemId\",\"type\":\"record\",\"fields\":[{\"name\":\"id\",\"type\":\"int\"}]}","contentType":"application/json"}}}'

```

## Add the Item schema artifact that includes the artifact reference to the ItemId schema using the /groups/{groupId}/artifacts operation:
```bash
curl -X POST http://localhost:8080/apis/registry/v3/groups/my-group/artifacts \
-H 'Content-Type: application/json' \
-H "Authorization: Bearer $ACCESS_TOKEN" \
--data-raw '{
	"artifactId": "Item",
	"artifactType": "AVRO",
	"firstVersion": {
		"version": "1.0.0",
		"content": {
			"content": "{\"namespace\":\"com.example.common\",\"name\":\"Item\",\"type\":\"record\",\"fields\":[{\"name\":\"itemId\",\"type\":\"com.example.common.ItemId\"}]}",
			"contentType": "application/json",
			"references": [
				{
					"name": "com.example.common.ItemId",
					"groupId": "my-group",
					"artifactId": "ItemId",
					"version": "1.0.0"
				}
			]
		}
	}
}'
```

## Searching for schema and API artifacts using Apicurio Registry REST API commands
```bash
curl "http://localhost:8080/apis/registry/v3/search/artifacts?artifactId=my-share-price"

curl "http://localhost:8080/apis/registry/v3/search/artifacts?artifactId=*"
curl "http://localhost:8080/apis/registry/v3/search/artifacts?limit=50&skipCount=true"c
```
