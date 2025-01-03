from dash import Dash, html, dcc, Output, Input, State, callback, callback_context
from dash.exceptions import PreventUpdate

from sqlalchemy import inspect

# internal imports
from data.model import Base, Feature, FeatureSet, Collection, Dataset, Layer, Style, Colormap, Scenario
from data.connect import autoconnect_db
from data.build import get_default_style, feature_to_obj

import base64
import json

def validate_geojson(geojson_dict: dict):
    """
    Returns True if the geojson_dict is a valid geojson dictionary.
    Currently, only checks if "features" is part of the keys.
    """

    keys = geojson_dict.keys()

    return "features" in keys


def build_layout_config():
    """
    Returns the layout for the config tab. Callbacks need to be configured separately.
    This gets set as the child of a dcc.Tab in the main app.
    """

    layout_config = [
        dcc.Tabs([
            dcc.Tab([   # Upload GeoJSON
                dcc.Upload(
                    id='upload-data',
                    children=html.Div([
                        'Drag and Drop or ',
                        html.A('Select Files')
                    ]),
                    style={
                        'width': '100%',
                        'height': '60px',
                        'lineHeight': '60px',
                        'borderWidth': '1px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                        'margin': '10px'
                    },
                    multiple=False,
                    accept='application/json'
                ),
                html.Div(id='output-data-upload'),
            ],
            label="Upload GeoJSON"
            ),
            dcc.Tab([   # Change Style
                
            ],
            label="Change Style"
            )
        ])
    ]

    return layout_config

def callbacks_config(app: Dash):
    """
    Links the dash app with the necessary callbacks.
    Pass the Dash app as an argument.
    """

    @app.callback(
        Output('output-data-upload', 'children'),
        Input('upload-data', 'contents'),           # data:DATATYPE;ENCODING,CONTENT (i.e. data:application/json;base64,eyJncmFwaF9kaWN0Ijoge319)
        State('upload-data', 'filename'),           # FILENAME.EXT
        State('upload-data', 'last_modified')       # TIMESTAMP
    )
    def update_output(content, full_filename, last_modified):
        if content is not None:
            try:
                # Split the content into metadata and base64-encoded data
                content_type, content_string = content.split(',')

                # decode the base64 string
                decoded_bytes = base64.b64decode(content_string)

                # load it into a json dictionary
                decoded_str = decoded_bytes.decode('utf-8')
                json_data = json.loads(decoded_str)

                # validate the file
                valid = validate_geojson(json_data)

                filename, file_extension = full_filename.rsplit('.', 1)  # split filename and extension



                if not valid:
                    return f"Error: {full_filename} is not a valid GeoJSON file"
                
                # now, we create database entries for the file
                engine, session = autoconnect_db()

                # first we create a scenario
                # try to find a name that isnt taken
                existing_layers = session.query(Layer).filter(Layer.name.startswith(filename))
                existing_names = [layer.name for layer in existing_layers]
                

                layer_name = filename
                found_name = False

                if layer_name in existing_names: # does the name already exist?

                    # 1000 tries to find a new name
                    # after that, give up
                    for i in range(1, 1000):
                        layer_name = f'{filename}_{i}'

                        if layer_name not in existing_names: # we found a new, valid scenario name!
                            found_name = True
                            break
                
                else:
                    found_name = True
                
                if not found_name:
                    return f"Error saving file {full_filename}: too many entries with this name exist. Consider deleting some."
                
                # if we got here, we have a valid GeoJSON file and a valid name for it
                # now, we create the layer and featureset

                layer = Layer(
                    name = layer_name
                )

                session.add(layer)

                # and the featureset
                style = get_default_style()

                feature_set = FeatureSet(
                    name=layer_name,
                    layer=layer,
                    style=style
                )
                session.add(feature_set)

                # now we convert the geojson dict to features
                for geojson_feature in json_data['features']:
                    db_feature = feature_to_obj(geojson_feature)

                    if db_feature is None:
                        continue

                    # set the feature set manually
                    db_feature.feature_set = feature_set

                    session.add(db_feature)
                
                session.commit()
                
                session.close()

                return f"Successfully uploaded {full_filename}. Parsed JSON: {json_data}"
            except Exception as e:
                return f"Error processing file {full_filename}: {str(e)}"
        raise PreventUpdate