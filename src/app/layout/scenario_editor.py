from dash import Dash, html, dcc, Output, Input, State, callback, callback_context
from dash.exceptions import PreventUpdate

from sqlalchemy import inspect

# internal imports
from data.model import Base, Feature, FeatureSet, Collection, Dataset, Layer, Style, Colormap, Scenario
from data.connect import autoconnect_db

def build_scenario_dropdown():
    """
    Build the scenario dropdown for the scenario editor.
    Format: `[Name1, Name2, Name3, ...]`
    """
    
    # get all available scenarios
    engine, session = autoconnect_db()

    # Check if the Scenario table exists
    inspector = inspect(engine)

    if 'scenarios' not in inspector.get_table_names():
        # Close database connection and return empty list if Scenario does not exist
        session.close()
        engine.dispose()
        print("Warning: Table 'scenarios' does not exist. No Scenario dropdown will be created. You can rebuild the database by running 'python main.py -rebuild'. See more information with 'python main.py -help'.")
        return []

    scenarios = session.query(Scenario).all()

    # sort by ID
    scenarios.sort(key=lambda x: x.id)

    scenario_dropdown = [{'label': f'{scenario.name} ({scenario.id})', 'value': scenario.id} for scenario in scenarios]

    # close database connection
    session.close()
    engine.dispose()

    return scenario_dropdown

def build_feature_set_dropdown():
    """
    Build the feature set dropdown for the scenario editor.
    Format: `[Name1, Name2, Name3, ...]`
    """
    
    # get all available feature sets
    engine, session = autoconnect_db()

    # Check if the FeatureSet table exists
    inspector = inspect(engine)

    if 'feature_sets' not in inspector.get_table_names():
        # Close database connection and return empty list if FeatureSet does not exist
        session.close()
        engine.dispose()
        print("Warning: Table 'feature_sets' does not exist. No FeatureSet dropdown will be created. You can rebuild the database by running 'python main.py -rebuild'. See more information with 'python main.py -help'.")
        return []

    feature_sets = session.query(FeatureSet).all()

    # sort by ID
    feature_sets.sort(key=lambda x: x.id)

    feature_set_dropdown = [{'label': f'{feature_set.name} ({feature_set.id})', 'value': feature_set.id} for feature_set in feature_sets]

    # close database connection
    session.close()
    engine.dispose()

    return feature_set_dropdown

def get_feature_sets_scenario(scenario_id: int):
    """
    Get the FeatureSets of a Scenario in a format that can be used for the FeatureSet dropdown.
    Format: `[Name1, Name2, Name3, ...]`
    """

    engine, session = autoconnect_db()

    # get the scenario
    scenario = session.query(Scenario).get(scenario_id)

    # get the scenario's feature sets
    feature_sets = scenario.feature_sets

    # get the feature set names
    feature_set_names = [feature_set.id for feature_set in feature_sets]

    # close database connection
    session.close()
    engine.dispose()

    return feature_set_names

def get_layout_scenario_editor():
    """
    Returns the layout for the scenario editor app. Callbacks need to be configured separately.
    This gets set as the child of a dcc.Tab in the main app.
    """

    # preload the dropdowns
    dropdown_scenarios = build_scenario_dropdown()
    dropdown_feature_sets = build_feature_set_dropdown()

    layout_scenario_editor = [
        html.Div( # this div is just here to force 100% width and height
            children=[
                html.H1('Scenario Editor'),
                dcc.Dropdown(
                    id='scenario_dropdown',
                    options=dropdown_scenarios,
                    value=None,
                    placeholder='Select Scenario'
                ),
                dcc.Store(id='selected_scenario', data=None),   # we store the scenario data in here
                html.Button(
                    children='Refresh Scenarios',
                    id='button_refresh_scenarios',
                    style={
                        'margin': '5px',
                        'padding': '5px'
                    }
                ),
                html.Button(
                    children='Create Scenario',
                    id='button_create_scenario',
                    style={
                        'margin': '5px',
                        'padding': '5px'
                    }
                ),
                html.Button(
                    children='Delete Scenario',
                    id='button_delete_scenario',
                    style={
                        'margin': '5px',
                        'padding': '5px'
                    }
                ),
                dcc.Input(
                    id='scenario_name_input',
                    placeholder='Scenario Name',
                    type='text',
                    value=''
                ),
                dcc.Input(
                    id='scenario_description_input',
                    placeholder='Scenario Description',
                    type='text',
                    value=''
                ),
                html.Br(),
                dcc.Dropdown(
                    id='feature_set_dropdown',
                    options=dropdown_feature_sets,
                    value=None,
                    multi=True,
                    placeholder='Assign FeatureSets'
                ),
                html.Button(
                    children='Refresh FeatureSets',
                    id='button_refresh_feature_sets',
                    style={
                        'margin': '5px',
                        'padding': '5px'
                    }
                ),
                html.Button(
                    children='Save',
                    id='button_save_scenario',
                    style={
                        'margin': '5px',
                        'padding': '5px'
                    }
                )
            ],
            style={
                'width': '100vw',
                'height': '100vh'
            }
        )
    ]

    return layout_scenario_editor

def callbacks_scenario_editor(app: Dash):
    """
    Links the dash app with the necessary callbacks.
    Pass the Dash app as an argument.
    """

    @app.long_callback(
        [Output('feature_set_dropdown', 'options')],
        [Input('button_refresh_feature_sets', 'n_clicks')],
        running=[
            (Output("button_refresh_feature_sets", "disabled"), True, False),
        ],
    )
    def refresh_feature_sets(n_clicks):
        """
        This callback is triggered when the refresh button is clicked.
        It refreshes the feature set dropdown.
        """

        # if the refresh button was not clicked, do nothing
        if n_clicks is None:
            raise PreventUpdate

        # call the scenario refresh function
        dropdown = build_feature_set_dropdown()

        # return nothing
        return [dropdown]
    
    @app.callback(
        [
            Output('scenario_name_input', 'value'),
            Output('scenario_description_input', 'value'),
            Output('feature_set_dropdown', 'value'),
            Output('scenario_dropdown', 'options'),
            Output('scenario_dropdown', 'value'),
            Output('selected_scenario', 'data')
        ],
        [
            Input('scenario_dropdown', 'value'),
            Input('button_create_scenario', 'n_clicks'),
            Input('button_delete_scenario', 'n_clicks'),
            Input('button_refresh_scenarios', 'n_clicks')
        ],
        [
            State('selected_scenario', 'data'),
        ],
        prevent_initial_call=True
    )
    def load_create_delete_scenario(scenario_id, n_clicks_create, n_clicks_delete, n_clicks_refresh, selected_scenario):
        """
        This callback is triggered when a scenario is selected from the dropdown or created with the create scenario button.
        It loads the scenario's name, description and feature sets into the corresponding inputs.
        """

        trigger_id = callback_context.triggered[0]['prop_id'].split('.')[0]

        engine, session = autoconnect_db()

        scenario_name = ''
        scenario_description = ''
        feature_set_ids = []
        scenario_dropdown = []
        next_scenario_id = None

        if trigger_id == 'scenario_dropdown':
            # if no scenario was selected, do nothing
            if scenario_id is None:
                raise PreventUpdate
            
            # if the selected scenario is the same as the currently selected scenario, do nothing
            # this is done to prevent circular callbacks
            if scenario_id is selected_scenario:
                raise PreventUpdate

            # get the scenario
            scenario = session.query(Scenario).get(scenario_id)

            # get the scenario's name and description
            scenario_name = scenario.name
            scenario_description = scenario.description
            next_scenario_id = scenario.id

            # get the feature set ids
            feature_set_ids = get_feature_sets_scenario(scenario_id)

        elif trigger_id == 'button_create_scenario':

            # create a new scenario
            scenario = Scenario(
                name='New Scenario',
                description=''
            )

            session.add(scenario)
            session.commit()

            # Reset for creating a new scenario
            scenario_name = scenario.name
            scenario_description = scenario.description
            feature_set_ids = []
            next_scenario_id = scenario.id
        
        elif trigger_id == 'button_delete_scenario':
    
            # get the scenario
            scenario = session.query(Scenario).get(scenario_id)

            if scenario is None:
                raise PreventUpdate
    
            # delete the scenario
            session.delete(scenario)
            session.commit()
    
            scenario_name = ''
            scenario_description = ''
            feature_set_ids = []
            next_scenario_id = None

        elif trigger_id == 'button_refresh_scenarios':

            # get the scenario with the id from selected_scenario
            scenario = session.query(Scenario).get(selected_scenario)

            if scenario is None:
                # it seems like the scenario was deleted
                # instead, just select the first scenario
                scenario = session.query(Scenario).first()	
            
            # get the scenario's name and description
            scenario_name = scenario.name
            scenario_description = scenario.description
            feature_set_ids = get_feature_sets_scenario(scenario.id)
            next_scenario_id = scenario.id
        
        # close database connection
        session.close()
        engine.dispose()

        scenario_dropdown = build_scenario_dropdown()

        return scenario_name, scenario_description, feature_set_ids, scenario_dropdown, next_scenario_id, next_scenario_id

    @app.long_callback(
        [Output('button_save_scenario', 'children')],
        [Input('button_save_scenario', 'n_clicks')],
        [State('scenario_dropdown', 'value'), State('scenario_name_input', 'value'), State('scenario_description_input', 'value'), State('feature_set_dropdown', 'value')],
        running=[
            (Output("button_save_scenario", "disabled"), True, False),
        ],
    )
    def save_scenario(n_clicks, scenario_id, name, description, feature_set_ids):
        """
        Saves or overrides a scenario.
        """

        # check if a scenario with that id already exists
        # if yes, override it
        # if no, create a new scenario
        engine, session = autoconnect_db()

        if feature_set_ids is None:
            feature_set_ids = [0]

        # get all FeatureSets that are selected in feature_set_ids
        feature_sets = session.query(FeatureSet).filter(FeatureSet.id.in_(feature_set_ids)).all()
        feature_sets = [] if feature_sets is None else feature_sets

        if scenario_id is None:

            # create a new scenario
            scenario = Scenario(
                name=name,
                description=description
            )

            # add the feature sets to the scenario
            scenario.feature_sets = feature_sets

            session.add(scenario)
            session.commit()

            # get the scenario id
            scenario_id = scenario.id
        else:
                
            # get the scenario
            scenario = session.query(Scenario).get(scenario_id)
    
            # update the scenario
            scenario.name = name
            scenario.description = description

            # get all FeatureSets that are selected in feature_set_ids
            feature_sets = session.query(FeatureSet).filter(FeatureSet.id.in_(feature_set_ids)).all()

            # add the feature sets to the scenario
            scenario.feature_sets = feature_sets
    
            session.commit()

        # close database connection
        session.close()
        engine.dispose()

        raise PreventUpdate

        # return nothing
        return []