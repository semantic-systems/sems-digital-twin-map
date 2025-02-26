# Configuring Data Sources

Currently, this project is specifically designed to work with [OGC API Features](https://ogcapi.ogc.org/features/) services, specifically the datasets of the [Urban Data Platform Hamburg](https://api.hamburg.de/datasets/v1).

## Configuring OGC API Features Data Sources
You can configure which OGC API Features to request in `api_config.json`. To add a new datasource, add a new entry to the `datasets` list as follows:


```
{
    "name":"Schulen",
    "id":"schulen",
    "url":"https://api.hamburg.de/datasets/v1/schulen",
    "collections":{
        "staatliche_schulen": {
            "name": "Staatliche Schule",
            "layer": "Schulen",
            "popup_properties": {
                "Name": "schulname", 
                "Typ": "kapitelbezeichnung", 
                "Adresse": "adresse_strasse_hausnr",
                "Schüler": "anzahl_schueler",
                "Tel.Nr.": "schul_telefonnr",
                "Homepage": "schul_homepage"
            },
            "style": {
                "marker_color": "blue",
                "marker_icon": "school-flag"
            }
        },
        "nicht_staatliche_schulen": {
            "name": "Nicht-Staatliche Schule",
            "layer": "Schulen",
            "popup_properties": {
                "Name": "schulname", 
                "Typ": "kapitelbezeichnung", 
                "Adresse": "adresse_strasse_hausnr",
                "Schüler": "anzahl_schueler",
                "Tel.Nr.": "schul_telefonnr",
                "Homepage": "schul_homepage"
            },
            "style": {
                "marker_color": "blue",
                "marker_icon": "school"
            }
        }
    }
}
```
This will request the collections `staatliche_schulen` and `nicht_staatliche_schulen` from the dataset `schulen` and save both under the layer `Schulen`.

- `name`: Display name of the Dataset
- `id`: Unique identifier of the Dataset
- `url`: Base URL of the Dataset
- `collections`: List of collections to be used from the Dataset. Only collections listed here will be requested.
- `collections.<collection_id>`: Unique identifier of the collection. Must be the same as the collection id in the API.
- `collections.<collection_id>.name`: Display name of the collection, gets used in popups
- `collections.<collection_id>.layer`: The layer the collection gets assigned to
- `collections.<collection_id>.popup_properties`: Display names and fields to be used in popups.
- `collections.<collection_id>.style`: Controls how the collections features get styled. See [dash-leaflet documentation](https://leafletjs.com/reference.html#path) or the `Style` class in `src/data/model.py` for more information on how to style features.

When rebuilding the database, the following happens (see `api_to_db()` in `build.py`):
1. Metadata about the dataset is requested, and saved as a Dataset object
2. Metadata about all specified collections is requested
3. For each collection, the specified layer is assigned
4. For each collection, a Style object is created and assigned, as well as a Colormap object if specified, and saved to the database
5. For each collection, a Collection object is created and saved to the database
6. For each collection, a FeatureSet is created and saved to the database
7. Afterwards, the database is refreshed (if the parameter `refresh` is set to `True`)

Refreshing does the following (see `refresh()` in `build.py`):
1. Deletes all existing Features from the database
2. Iterate through all FeatureSets, get their collections, and request the features from the API
3. For each feature, a Feature object is created, and saved to the database

## Adding other Data Sources
To add features from other data sources to the map, you need to do the following (see [datamodel.md](/docs/datamodel.md) for more information on the database schema).

- Create a `Layer` object, which represents a toggleable layer on the map.
- Create a `Style` object, which controls how features are styled. If you want to use a colormap, create a `Colormap` object as well. You can use `get_default_style()` from `build.py` to get a Style object with default values.
- Create a `FeatureSet` object, which represents a logical group of features. Assign the `Layer` and `Style` objects to the `FeatureSet`.
- Create Feature objects for all features in your data source, and assign the `FeatureSet` you just created. If you are handling GeoJSON data, you can use the `feature_to_obj` function in `build.py` to convert a GeoJSON feature to a Feature object.
- Add all objects to the database, and commit.