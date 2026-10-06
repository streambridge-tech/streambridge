
### 0.1 Start Docker Compose Environment

The Compose file uses the external shared network `streambridge-network`.
Create it once before starting the services (skip creation if it already exists):

```sh
docker network create streambridge-network
docker compose up -d
```

Running `docker compose up` starts the following services:

* Zookeeper
* Kafka Broker
* Kafka Connect
* MySQL
* Postgres

### 1. Inspect original rows in `addresses` table of MySQL

`docker compose exec mysql-cdc mysql -u mysqluser -p debezium -e "use inventory; SELECT * FROM addresses;"`

```
$ docker exec -it mysql-container-id bash
# mysql -u mysqluser -p
$ Enter password > mysqlpw
>>> use inventory // change db
>>> select * from addresses;
```


This should result in displaying the data rows contained in the corresponding MySQL table `inventory.addresses`
```
+----+-------------+---------------------------+------------+--------------+-------+----------+
| id | customer_id | street                    | city       | state        | zip   | type     |
+----+-------------+---------------------------+------------+--------------+-------+----------+
| 10 |        1001 | 3183 Moore Avenue         | Euless     | Texas        | 76036 | SHIPPING |
| 11 |        1001 | 2389 Hidden Valley Road   | Harrisburg | Pennsylvania | 17116 | BILLING  |
| 12 |        1002 | 281 Riverside Drive       | Augusta    | Georgia      | 30901 | BILLING  |
| 13 |        1003 | 3787 Brownton Road        | Columbus   | Mississippi  | 39701 | SHIPPING |
| 14 |        1003 | 2458 Lost Creek Road      | Bethlehem  | Pennsylvania | 18018 | SHIPPING |
| 15 |        1003 | 4800 Simpson Square       | Hillsdale  | Oklahoma     | 73743 | BILLING  |
| 16 |        1004 | 1289 University Hill Road | Canehill   | Arkansas     | 72717 | LIVING   |
+----+-------------+---------------------------+------------+--------------+-------+----------+

create users table

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    dob VARCHAR(255) NOT NULL,
    mobile VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL

);

INSERT INTO users (email, dob, mobile, address)
VALUES ('john.doe@example.com', '1990-01-15', '1234567890', '123 Main St, City, Country');

INSERT INTO users (email, dob, mobile, address)
VALUES ('jane.smith@example.com', '1985-05-22', '0987654321', '456 Elm St, City, Country');


```



### 2. Create Debezium Source Connector

Debezium's MySQL source connector is configured together with the `CipherField` SMT to perform log-based change data capture against the MySQL table `inventory.addressess`. The table's `street` column values get encrypted due to the SMT settings.

Run the following command in your host terminal to start the debezium tools container and enter an interactive bash session.

Use the shared network created in step 0.1 for the Debezium tools container:

```
docker run -it --rm \
  --network streambridge-network \
    -v ${PWD}/:/home/ \
    debezium/tooling:1.2 \
    bash
```

_NOTE: All of the following commands are supposed to be executed in the container's bash._

[kcctl](https://github.com/kcctl/kcctl) - a CLI for Apache Kafka Connect - is used to perform any Kafka Connect related operations. First the connect cluster address is set and used as the CLI tool's context. Then the MySQL source connector is created.

```
$ kcctl config set-context default --cluster=http://connect:8083
```

## rest based connector create
```
curl -sS -X POST http://localhost:8083/connectors \
  -H 'Content-Type: application/json' \
  --data-binary /Users/rahulkumar/Desktop/projects/encryption-decryption-datalake/streambridge_connector/mysql_connector_apicurio.json


curl -sS -X POST http://localhost:8083/connectors \
  -H 'Content-Type: application/json' \
  --data-binary /Users/rahulkumar/Desktop/projects/encryption-decryption-datalake/streambridge_connector/mysql_connector_confluent.json
```
