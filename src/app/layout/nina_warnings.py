from datetime import date, timedelta, datetime
from datetime import datetime

from dash import html, dcc, Output, Input, State, dash_table, callback_context
from dash.exceptions import PreventUpdate

# internal imports
from data.model import Base, Alert
from data.connect import autoconnect_db
from data.req_nina import save_alerts


def format_table_nina(filter: str = None):
    engine, session = autoconnect_db()
    data = session.query(Alert).order_by(Alert.id).limit(20000).all()

    formatted_data = []

    for row in data:
        # Format date and other information
        date_str = row.timestamp.strftime('%d.%m.%Y %H:%M:%S')
        urgency_str = "High" if row.urgency == "high" else "Medium" if row.urgency == "medium" else "Low"

        # if we have a filter, check if one of the columns contains the filter string
        if filter is not None:
            filter_l = filter.lower()
            if filter_l not in date_str.lower() \
                and filter_l not in row.event.lower() \
                and filter_l not in urgency_str.lower() \
                and filter_l not in row.sender_name.lower() \
                and filter_l not in row.headline.lower() \
                and filter_l not in row.description.lower():
                continue

        # Append a dictionary for each row with more detailed columns
        formatted_data.append({
            "Date": date_str,
            "Event": row.event,
            "Urgency": urgency_str,
            "Sender": row.sender_name,
            "Headline": row.headline,
            "Description": row.description[:255] + ("..." if len(row.description) > 255 else "")
        })

    formatted_columns = [
        {'name': 'Date', 'id': 'Date'},
        {'name': 'Event', 'id': 'Event'},
        {'name': 'Urgency', 'id': 'Urgency'},
        {'name': 'Sender', 'id': 'Sender'},
        {'name': 'Headline', 'id': 'Headline'},
        {'name': 'Description', 'id': 'Description'}
    ]

    session.close()
    engine.dispose()

    return formatted_columns, formatted_data

def build_layout_nina_warnings():

    engine, session = autoconnect_db()

    # get the data from the Alert table
    columns, data = format_table_nina()

    layout_data_viewer = [
        html.Div(
            children=[
                html.H1('NINA Warnings', style={'margin-bottom': '20px'}),
                html.Button('Refresh', id='button-refresh-nina', className='button-common', style={'margin-bottom': '20px', 'width': '100px'}, n_clicks=0),
                dcc.Input(
                    id='input_nina',
                    type='text',
                    placeholder='Search...',
                    style={'margin-left': '20px', 'padding': '14px', 'transform': 'translateY(-2px)', 'width': 'calc(100% - 100px - 20px - 32px)'}
                ),
                dash_table.DataTable(
                    id='datatable_nina',
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

def callbacks_nina_warnings(app):

    @app.callback(
        Output('datatable_nina', 'columns'),
        Output('datatable_nina', 'data'),
        Input('button-refresh-nina', 'n_clicks'),
        Input('input_nina', 'value')
    )
    def update_table(button_n_clicks, input_value):

        trigger_id = callback_context.triggered[0]['prop_id'].split('.')[0]

        if button_n_clicks is None:
            raise PreventUpdate

        if trigger_id == 'button-refresh-nina':
            # get the newest alerts from the nina api
            save_alerts()

        # get the data from the table with thre refreshed values
        columns, data = format_table_nina(filter=input_value)

        return columns, data