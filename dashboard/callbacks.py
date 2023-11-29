# callbacks.py
from dash import Output, Input, State, dcc
from app_instance import app  # Import the Dash app instance

def check_credentials(username, password):
    return username == "admin" and password == "admin"

def register_callbacks(app):
    @app.callback(
        Output('login-modal', 'is_open'),
        Output('main-layout-container', 'children'),  # This will hold the main layout
        [Input("login-button", "n_clicks")],
        [State("username-input", "value"), State("password-input", "value")],
        prevent_initial_call=True
    )
    def toggle_modal(n_clicks, username, password):
        if n_clicks > 0:
            if check_credentials(username, password):
                return False, main_layout()  # Close modal and display main layout
            else:
                return True, None  # Keep modal open and main layout empty
        return True, None  # Default: keep modal open and main layout empty

    @app.callback(
        Output("tab-content", "children"),
        [Input("tabs", "active_tab")],
        prevent_initial_call=True
    )
    def switch_tab(active_tab):
        if active_tab == "tab-ue":
            return ue_level_report_layout()
        elif active_tab == "tab-cell":
            return cell_level_report_layout()
# Note: You need to implement the switch_tab callback to handle the content of each tab.







