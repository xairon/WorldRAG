#!/bin/bash
# Creates additional databases on first Postgres boot.
# Mounted into /docker-entrypoint-initdb.d/ by docker-compose.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE langfuse;
    GRANT ALL PRIVILEGES ON DATABASE langfuse TO $POSTGRES_USER;
EOSQL
