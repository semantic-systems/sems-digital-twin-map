# Setup

## Setting up this project

Start by cloning the project with `git clone https://github.com/semantic-systems/sems-digital-twin-map/`. Next, add your credentials to the `example.env` file in the base directory and rename it to `.env`.

If you want to use the reports server (see `server_reports` in [servers.md](/docs/servers.md)), you need access to a RescueMate Knowledge Graph SPARQL endpoint and set the `SPARQL_ENDPOINT`, `USERNAME`, and `PASSWORD` variables in `.env`.

Finally, run `docker compose up -d --build` in the project directory.

This will launch:
- The **React frontend** accessible under [http://localhost:8050/](http://localhost:8050/)
- The **FastAPI backend** accessible under [http://localhost:8052/](http://localhost:8052/) (Swagger UI at [http://localhost:8052/docs](http://localhost:8052/docs))

## Configuration
All geodata is requested from [https://api.hamburg.de/datasets/v1/](https://api.hamburg.de/datasets/v1/). For more information, see [datasources.md](/docs/datasources.md).

## Development setup
For local development outside Docker, use `start_dev.sh`. This starts only the `postgis` and `pgadmin` containers (with port 5432 exposed to the host) using `docker-compose.dev.yaml`, so the backend and frontend can be run locally in your IDE.
