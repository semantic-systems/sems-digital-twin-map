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
        html.Div(
            children = [
                html.H1('Scenario Editor', className='editor-title'),
                html.Label('Select a Scenario', className='form-label'),
                html.Div(
                    className='dropdown-container',
                    children=[
                        dcc.Dropdown(
                            id='scenario_dropdown',
                            options=dropdown_scenarios,
                            value=None,
                            placeholder='Scenarios',
                            className='form-dropdown'
                        ),
                    ]
                ),
                dcc.Store(id='selected_scenario', data=None),
                html.Div(
                    className='button-group',
                    children=[
                        html.Button('Refresh Scenarios', id='button_refresh_scenarios', className='button-common'),
                        html.Button('Create Scenario', id='button_create_scenario', className='button-common'),
                        html.Button('Delete Scenario', id='button_delete_scenario', className='button-common'),
                    ]
                ),
                html.Div(
                    className='input-group',
                    children=[
                        html.Label('Scenario Name', className='form-label'),
                        dcc.Input(id='scenario_name_input', type='text', value='', className='form-input')
                    ]
                ),
                html.Div(
                    className='input-group',
                    children=[
                        html.Label('Scenario Description', className='form-label'),
                        dcc.Input(id='scenario_description_input', type='text', value='', className='form-input')
                    ]
                ),
                html.Div( # just some vertical spacing
                    style={'height': '20px'}
                ),
                html.Label('Assign FeatureSets to the Scenario', className='form-label'),
                html.Div(
                    className='dropdown-container',
                    children=[
                        dcc.Dropdown(
                            id='feature_set_dropdown',
                            options=dropdown_feature_sets,
                            value=None,
                            multi=True,
                            placeholder='FeatureSets',
                            className='form-dropdown'
                        ),
                    ]
                ),
                html.Div(
                    className='button-group',
                    children=[
                        html.Button('Refresh FeatureSets', id='button_refresh_feature_sets', className='button-common'),
                        html.Button('Save', id='button_save_scenario', className='button-common'),
                    ]
                )
            ],
            style = {'padding': '20px'}
        )
    ]

    return layout_scenario_editor

def callbacks_scenario_editor(app: Dash):
    """
    Links the dash app with the necessary callbacks.
    Pass the Dash app as an argument.
    """

    @app.callback(
        [Output('feature_set_dropdown', 'options')],
        [Input('button_refresh_feature_sets', 'n_clicks')],
        running=[
            (Output("button_refresh_feature_sets", "disabled"), True, False),
        ]
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
        running=[
            (Output("button_create_scenario", "disabled"), True, False),
            (Output("button_delete_scenario", "disabled"), True, False),
            (Output("button_refresh_scenarios", "disabled"), True, False),
        ],
        prevent_initial_call=True
    )
    def load_create_delete_scenario(scenario_id, n_clicks_create, n_clicks_delete, n_clicks_refresh, selected_scenario):
        """
        This callback is triggered when:
        - a scenario is selected from the dropdown
        - a scenario is created with the create scenario button
        - a scenario is deleted with the delete scenario button
        - the refresh scenarios button is clicked

        This function sets the scenario name, description, feature set ids in the menu.
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
                session.close()
                engine.dispose()
                raise PreventUpdate
            
            # if the selected scenario is the same as the currently selected scenario, do nothing
            # this is done to prevent circular callbacks
            if scenario_id is selected_scenario:
                session.close()
                engine.dispose()
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
                session.close()
                engine.dispose()
                raise PreventUpdate
    
            # delete the scenario
            session.delete(scenario)
            session.commit()

            # get the scenario right before the deleted one
            scenario = session.query(Scenario).filter(Scenario.id < scenario_id).order_by(Scenario.id.desc()).first()

            if scenario is None:
                # it seems like the scenario was the first one
                # instead, just select the first scenario
                scenario = session.query(Scenario).first()

            if scenario is None:
                # we tried to select the first scenario, but got None
                # this means that there are no scenarios left
                scenario_name = ''
                scenario_description = ''
                feature_set_ids = []
                next_scenario_id = None
            else:
                # get the scenario's name and description
                scenario_name = scenario.name
                scenario_description = scenario.description
                feature_set_ids = get_feature_sets_scenario(scenario.id)
                next_scenario_id = scenario.id

        elif trigger_id == 'button_refresh_scenarios':

            # get the scenario with the id from selected_scenario
            scenario = session.query(Scenario).get(selected_scenario)

            if scenario is None:
                # it seems like the selected scenario was just deleted
                # instead, now select the first scenario
                scenario = session.query(Scenario).first()	
            
            if scenario is None:
                # we tried to select the first scenario, but got None
                # this means that there are no scenarios left
                scenario_name = ''
                scenario_description = ''
                feature_set_ids = []
                next_scenario_id = None
            else:
                # get the scenario's name and description
                scenario_name = scenario.name
                scenario_description = scenario.description
                feature_set_ids = get_feature_sets_scenario(scenario.id)
                next_scenario_id = scenario.id
        
        # close database connection
        session.close()
        engine.dispose()

        # refresh the scenario dropdown
        scenario_dropdown = build_scenario_dropdown()

        return scenario_name, scenario_description, feature_set_ids, scenario_dropdown, next_scenario_id, next_scenario_id

    @app.callback(
        [Output('scenario_dropdown', 'options', allow_duplicate=True)],
        [Input('button_save_scenario', 'n_clicks')],
        [State('scenario_dropdown', 'value'), State('scenario_name_input', 'value'), State('scenario_description_input', 'value'), State('feature_set_dropdown', 'value')],
        running=[
            (Output("button_save_scenario", "disabled"), True, False),
        ],
        prevent_initial_call=True,
        background=True
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

            # discard empty scenarios
            if name == '' and description == '':
                session.close()
                engine.dispose()
                raise PreventUpdate

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

            if scenario is None:
                session.close()
                engine.dispose()
                raise PreventUpdate
    
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

        # refresh the scenario dropdown
        scenario_dropdown = build_scenario_dropdown()

        return [scenario_dropdown]