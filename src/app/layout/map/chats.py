from dash import html

from data.model import Chat
from data.connect import autoconnect_db



def fetch_chats():
    engine, session = autoconnect_db()

    # Add dummy chats for demonstration purposes
    try:
        chats = session.query(Chat).order_by(Chat.last_message_at.desc()).all()
        chat_dicts = [{'id': c.id, 'title': c.title, 'is_open': c.is_open} for c in chats]

    finally:
        session.close()
        engine.dispose()
    return chat_dicts

def get_chat_sidebar(chats):
    if not chats:
        return html.Div([
            html.P("Chats", style={'font-weight': 'bold', 'font-size': '14pt', 'margin-bottom': '10px'}),
            html.Div(
                "No chats available.",
                style={
                    "font-size": "13pt",
                    "color": "#777",
                    "padding": "34px 0",
                    "text-align": "center",
                    "height": "120px",
                    "background": "#f8f8f8"
                }
            )
        ])
    else:
        return html.Div([
            html.P("Chats", style={'font-weight': 'bold', 'font-size': '14pt', 'margin-bottom': '10px'}),
            html.Ul(
                [
                    html.Li(
                        html.Button(
                            chat['title'],
                            id={'type': 'chat-selector', 'index': chat['id']},
                            n_clicks=0,
                            style={'width': '100%', 'margin-bottom': '4px'}
                        ),
                        style={'background': '#eee' if chat['is_open'] else '#fcc'}
                    )
                    for chat in chats
                ],
                style={
                    'padding': 0,
                    'list-style-type': 'none',
                    'margin': 0,
                    'max-height': '100px',
                    'overflow-y': 'auto'
                }
            )
        ])

