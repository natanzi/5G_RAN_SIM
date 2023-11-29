# app.py
from dash import html, dcc  # Import html here
from app_instance import app  # Import the Dash app instance from app_instance.py
from layouts import create_login_modal, main_layout
from callbacks import register_callbacks

# Define the layout of the app
app.layout = html.Div([
    create_login_modal(),
    html.Div(id='main-layout-container', style={'display': 'none'}),  # Initially hidden
    dcc.Store(id='auth-store')
], className='body-background')

# Register the callbacks
register_callbacks(app)

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)


