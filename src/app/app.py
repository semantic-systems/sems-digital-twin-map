from dash import Dash, html, dcc
from dash.long_callback import DiskcacheLongCallbackManager
import diskcache

# map layout imports
from app.layout.map import get_layout_map, callbacks_map
from app.layout.scenario_editor import get_layout_scenario_editor, callbacks_scenario_editor
from app.layout.data_viewer import build_layout_data_viewer, callbacks_data_viewer
from app.layout.nina_warnings import build_layout_nina_warnings, callbacks_nina_warnings

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
        long_callback_manager=long_callback_manager,
        suppress_callback_exceptions=True
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
                        children = html.Div(get_layout_map(), className='fullscreen-container') # these outer divs are here to force the tabs to fill the screen
                    ),
                    # Tab 2: The Scenario Editor
                    dcc.Tab(
                        label='Scenario Editor',
                        children = html.Div(get_layout_scenario_editor(), className='fullscreen-container')
                    ),
                    # Tab 3: The NINA Warnings
                    dcc.Tab(
                        label='NINA Warnings',
                        children = html.Div(build_layout_nina_warnings(), className='fullscreen-container')
                    ),
                    # Tab 4: The Data Viewer
                    dcc.Tab(
                        label='Data Viewer',
                        children = html.Div(build_layout_data_viewer(), className='fullscreen-container')
                    ),
                ]
            )
        ],
        style={'display': 'flex', 'flex-wrap': 'wrap'}
    )

    # link the callbacks
    callbacks_map(app)
    callbacks_scenario_editor(app)
    callbacks_data_viewer(app)
    callbacks_nina_warnings(app)

    return app