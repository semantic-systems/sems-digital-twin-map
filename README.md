# sems-digital-twin-map
An interactive map to visualize datasets from the [Urban Data Hub](https://api.hamburg.de/datasets/v1/).

## Usage

First, configure the `.env.example` file in the base directory and rename it to `.env`.

Then, run `docker compose up -d --build` in the project directory.

This will launch a simple dash Flask server accessible under [http://127.0.0.1:8050/](http://127.0.0.1:8050/)

## Configuration
All data is requested from [https://api.hamburg.de/datasets/v1/](https://api.hamburg.de/datasets/v1/).
You can configure which API endpoints are used in `api_config.json`.

Example:
```
{
    "name":"Perspektive Wohnen",
    "id":"perspektive_wohnen",
    "url":"https://api.hamburg.de/datasets/v1/perspektive_wohnen",
    "collections":{
        "perspektive_wohnen_bestehend":{
            "name":"Perspektive Wohnen",
            "layer": "Perspektive Wohnen",
            "popup_properties": {
                "Bezeichnung": "bezeichnung", 
                "Bezirk": "bezirk", 
                "Plätze": "platzzahl"
            },
            "style": {
                "marker_color": "beige",
                "marker_icon": "person-shelter"
            }
        }
    }
},
```
- `name`: Display name of the Dataset
- `id`: Unique identifier of the Dataset
- `url`: Base URL of the Dataset
- `collections`: List of collections to be used from the Dataset. Only collections listed here will be requested.
- `collections.<collection_id>`: Unique identifier of the collection. Must be the same as the collection id in the API.
- `collections.<collection_id>.name`: Display name of the collection, gets used in popups
- `collections.<collection_id>.layer`: The layer the collection gets assigned to
- `collections.<collection_id>.popup_properties`: Display names and fields to be used in popups.
- `collections.<collection_id>.style`: Controls how the collections features get styled. See [dash-leaflet documentation](https://leafletjs.com/reference.html#path) or the `Style` class in `src/data/model.py` for more information.