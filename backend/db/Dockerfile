FROM postgres:16-alpine

# Default local credentials (override in deployment if needed)
ENV POSTGRES_DB=supportdb \
    POSTGRES_USER=postgres \
    POSTGRES_PASSWORD=postgres

# Seed schema + sample data on first startup
COPY init.sql /docker-entrypoint-initdb.d/01-init.sql

EXPOSE 5432

