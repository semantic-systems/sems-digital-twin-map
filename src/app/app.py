from dash import Dash, html, dcc
from dash.long_callback import DiskcacheLongCallbackManager
import diskcache

# map layout imports
from app.layout.map import get_layout_map, callbacks_map
from app.layout.scenario_editor import get_layout_scenario_editor, callbacks_scenario_editor

def get_app():

    # long callback setup
    cache = diskcache.Cache("./cache")
    long_callback_manager = DiskcacheLongCallbackManager(cache)

    app = Dash(
        __name__,
        external_stylesheets=[
            'https://maxcdn.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css',
            'https://getbootstrap.com/1.0.0/assets/css/bootstrap-1.0.0.min.css',
        ],
        external_scripts=[
            'http://cdn.leafletjs.com/leaflet-0.6.4/leaflet.js',
            'https://kit.fontawesome.com/5ae05e6c33.js'
        ],
        long_callback_manager=long_callback_manager
    )

    # create the map layout
    # for specific layouts see src/app/layout/*
    app.layout = html.Div(
        children = [
            dcc.Tabs(
                children = [
                    # Tab 1: The Map
                    dcc.Tab(
                        label='Map',
                        children = get_layout_map()
                ),
                    # Tab 2: The Scenario Editor
                    dcc.Tab(
                        label='Scenario Editor',
                        children = get_layout_scenario_editor()
                    )
                ]
            )
        ],
        style={'display': 'flex', 'flex-wrap': 'wrap'}
    )

    # link the callbacks
    callbacks_map(app)
    callbacks_scenario_editor(app)

    return app