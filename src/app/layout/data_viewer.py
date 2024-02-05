from datetime import date, timedelta, datetime
from datetime import datetime

from dash import Dash, html, dcc, Output, Input, State, dash_table
from dash.exceptions import PreventUpdate
import dash_leaflet as dl

from sqlalchemy import inspect

# internal imports
from data.model import Base, Feature, FeatureSet, Collection, Dataset, Layer, Style, Colormap, Scenario
from data.connect import autoconnect_db
from app.convert import overlay_id_to_layer_group

# tables to display in the data viewer
tables = {
    # 'Feature': Feature,   # dont display this table, it's too big
    'FeatureSet': FeatureSet,
    'Collection': Collection,
    'Dataset': Dataset,
    'Layer': Layer,
    'Style': Style,
    'Colormap': Colormap,
    'Scenario': Scenario
}

def format_table(table_name):
    # get the table
    table = tables[table_name]

    # connect to the database
    engine, session = autoconnect_db()

    # get the column names
    columns = [column.name for column in table.__table__.columns]  # Use list comprehension to get column names

    # get all rows from the table, ordered by id
    data = session.query(table).order_by(table.id).all()

    # close the database connection
    session.close()
    engine.dispose()

    # format the data for DataTable
    formatted_columns = [{'name': col, 'id': col} for col in columns]
    formatted_data = [{col: str(getattr(row, col)) for col in columns} for row in data]

    return formatted_columns, formatted_data

def build_layout_data_viewer():

    engine, session = autoconnect_db()

    # get the data from the Layer table
    columns, data = format_table("Layer")

    layout_data_viewer = [
        html.Div(
            children=[
                html.H1('Data Viewer', style={'margin-bottom': '20px'}),
                dcc.Dropdown(
                    id='dropdown-table',
                    options=[{'label': table, 'value': table} for table in tables.keys()],
                    value='Layer',
                    style={'margin-bottom': '20px'}
                ),
                dash_table.DataTable(
                    id='datatable',
                    columns=columns,
                    data=data,
                    fixed_rows={'headers':True},
                    style_table={'overflow':'scroll','height':550},
                    style_header={'backgroundColor':'#305D91','padding':'10px','color':'#FFFFFF'},
                    style_cell={'textAlign':'center','minWidth': 95, 'maxWidth': 95, 'width': 95,'font_size': '12px','whiteSpace':'normal','height':'auto'},
                    filter_action="native",     # allow filtering of data by user ('native') or not ('none')
                    sort_action="native",       # enables data to be sorted per-column by user or not ('none')
                    sort_mode="single",         # sort across 'multi' or 'single' columns
                    selected_columns=[],        # ids of columns that user selects
                    selected_rows=[],           # indices of rows that user selects
                    page_action="native"
                ),
            ],
            style = {'padding': '20px'}
        )

    ]

    # close the database connection
    session.close()
    engine.dispose()
    
    return layout_data_viewer

def callbacks_data_viewer(app):

    @app.callback(
        Output('datatable', 'columns'),
        Output('datatable', 'data'),
        Input('dropdown-table', 'value')
    )
    def update_table(table_name):

        if table_name is None:
            raise PreventUpdate

        # get the data from the table
        columns, data = format_table(table_name)

        return columns, data