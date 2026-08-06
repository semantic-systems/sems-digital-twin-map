# Servers
This file explains the different services and containers used in the project. For more information, see `docker-compose.yaml` and the respective Dockerfiles.

## backend
The FastAPI backend. Serves all data to the frontend via a REST API and handles per-user state. It is accessible by default under [http://localhost:8052/](http://localhost:8052/), with Swagger UI at [http://localhost:8052/docs](http://localhost:8052/docs). On first start, the backend automatically creates all required database tables. Source code is in `backend/`.

The backend also enforces the report retention window: once an hour it deletes every report older than `REPORT_RETENTION_DAYS` days (default 7, set in `.env`; 0 disables the purge) along with the per-user state belonging to it. Implementation in `src/data/retention.py`.

## frontend
The React (Vite) frontend. Serves the interactive map UI. It is accessible by default under [http://localhost:8050/](http://localhost:8050/). Source code is in `frontend/`.

## postgis
A PostgreSQL database with the PostGIS extension. Inside Docker, other services connect to it via the hostname `postgis`. In development mode, it is also exposed on `localhost:5432`. Credentials are defined in the `.env` file. For more information on the data model, see [datamodel.md](/docs/datamodel.md).

## pgadmin
A web interface to interact with the PostgreSQL database. It is accessible under [http://localhost:8051/](http://localhost:8051/). The credentials are defined in the `.env` file.

## server_reports
A background worker that continuously polls the RescueMate Knowledge Graph via SPARQL, and saves new social media posts and news headlines to the database. It runs on a fixed polling interval (`REQUEST_DELAY = 10` seconds). Source code is in `src/server_reports.py`, Dockerfile at `docker/Dockerfile_server_reports`.

The KG runs as multiple failover nodes (peers, not replicas — a post written while one node was down lives only on another), so the worker reads from every configured node and unions the results, each as an independent pipeline. Requires the following environment variables (set in `.env`):
- `SPARQL_ENDPOINTS` — comma-separated list of node SPARQL endpoints (e.g. `https://node-1.../sparql,https://node-2.../sparql`). The singular `SPARQL_ENDPOINT` still works as a one-node fallback.
- `USERNAME` / `PASSWORD` — Keycloak credentials, shared across all nodes.
- `SPARQL_KEYCLOAK_URLS` — (optional) comma-separated list of per-node Keycloak base URLs, parallel to `SPARQL_ENDPOINTS`, for nodes that authenticate via a different Keycloak. Unset entries default to the node's own origin; a token from any Keycloak is accepted by every node.

## server_nina
A background worker that periodically fetches alerts from the [NINA API](https://nina.api.bund.dev/) and saves them to the database. Source code is in `src/server_nina.py`, Dockerfile at `docker/Dockerfile_server_nina`. Note: this service has a Dockerfile but is not yet included in `docker-compose.yaml`.
