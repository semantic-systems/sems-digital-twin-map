# Servers
This file explains the different services and containers used in the project. For more information, see `docker-compose.yaml` and the respective Dockerfiles.

## backend
The FastAPI backend. Serves all data to the frontend via a REST API and handles per-user state. It is accessible by default under [http://localhost:8052/](http://localhost:8052/), with Swagger UI at [http://localhost:8052/docs](http://localhost:8052/docs). On first start, the backend automatically creates all required database tables. Source code is in `backend/`.

## frontend
The React (Vite) frontend. Serves the interactive map UI. It is accessible by default under [http://localhost:8050/](http://localhost:8050/). Source code is in `frontend/`.

## postgis
A PostgreSQL database with the PostGIS extension. Inside Docker, other services connect to it via the hostname `postgis`. In development mode, it is also exposed on `localhost:5432`. Credentials are defined in the `.env` file. For more information on the data model, see [datamodel.md](/docs/datamodel.md).

## pgadmin
A web interface to interact with the PostgreSQL database. It is accessible under [http://localhost:8080/](http://localhost:8080/). The credentials are defined in the `.env` file.

## server_reports
A background worker that continuously polls the RescueMate Knowledge Graph via SPARQL, and saves new social media posts and news headlines to the database. It runs on a fixed polling interval (`REQUEST_DELAY = 10` seconds). Source code is in `src/server_reports.py`, Dockerfile at `docker/Dockerfile_server_reports`.

Requires the following environment variables (set in `.env`):
- `SPARQL_ENDPOINT` — URL of the RescueMate SPARQL endpoint
- `USERNAME` / `PASSWORD` — Keycloak credentials for the SPARQL endpoint

## server_nina
A background worker that periodically fetches alerts from the [NINA API](https://nina.api.bund.dev/) and saves them to the database. Source code is in `src/server_nina.py`, Dockerfile at `docker/Dockerfile_server_nina`. Note: this service has a Dockerfile but is not yet included in `docker-compose.yaml`.

## server_events (unused)
A simple Python server that received POST requests with event propagation/prediction data and saved them to the database. This server is currently unused and is not included in `docker-compose.yaml`. Source code is in `src/server_events.py`.
