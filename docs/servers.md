# Servers
This file explains the different servers and containers used in the project. For more information, see `docker-compose.yml` and the respective Dockerfiles in `docker/`.

## python-map
The main container of the project. It contains the Dash app and the logic to request and display data. It is accessible by default under [http://localhost:8050/](http://localhost:8050/). Starting this container for the first time will trigger the `build()` function in `build.py`, which will create and configure the database and request the data from the API. Additionally, you can force a rebuild of the database by starting the project locally via `python src/main.py --rebuild`.

## postgis
A PostgreSQL database with the PostGIS extension. The database is accessible under `localhost:5432` with the credentials defined in the `.env` file. For more information on the database amd datamodel, see [datamodel.md](/docs/datamodel.md).

## pgadmin
A web interface to interact with the PostgreSQL database. It is accessible under [http://localhost:5050/](http://localhost:5050/). The credentials are defined in the `.env` file.

## python-server-nina
A simple Python server to request data from the NINA API. Every hour, this server requests the newest alerts from the NINA API, and saves them to the database. For more information, see `Alerts` in [datamodel.md](/docs/datamodel.md) and `server_nina.py`.

## python-server-reports
A simple Python server that requests reports from the `python-social-media-requester-api`, classifies them according to event type (e.g., "fire", "flood"), and saves them to the database. For more information, see `server_reports.py`.

## python-social-media-requester-api
A Python API that can be used to request social media data from specific social media platforms. This container is **not** contained in this project, but is from the [sems-social-media-requester](https://github.com/semantic-systems/sems-social-media-retriever) project. For more information on setting this up, see [setup.md](/docs/setup.md) and the README file of the `sems-social-media-retriever` project.

## python-server-events
A simple Python server that recieves POST requests with event data and saves them to the database. This server was used to recieve data about event propagation, which generated predictions of how one event (i.e. a fire, flood, etc) could spread. This server is currently unused, and it is unlikely that it will be used in the future. For more information, see `server_events.py`.