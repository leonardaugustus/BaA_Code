import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import pandas as pd
import numpy as np
import base64
import io

# --- Initialize app ---
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Antigen Analyse Dashboard"

# --- Load data ---
data = pd.read_csv("data.csv")

# --- Setup options ---
LISS_VALUES = ["-", "+/-", "1+", "2+", "3+", "4+"]
ANTIGEN_COLUMNS = [col for col in data.columns if col not in ["Spendernummer", "Spender", "Spez. Antigen", "Gen.", "LISS"]]

# Color codes for the analysis status
STATUS_COLORS = {
    "Bestätigt (3x +)": "#2d6a4f",  # Dark green
    "Bestätigt (2x +)": "#b7e4c7",  # Light green
    "Nicht ausgeschlossen": "#ffd166",  # Yellow
    "Keine Reaktion": "#e9ecef",    # Light grey
    "Ausgestrichen": "#e63946"      # Red
}

# --- Utility functions ---
def prepare_data(df):
    """Prepare and clean the dataframe"""
    # Create a clean copy of the dataframe
    df = df.copy()
    
    # Ensure Spendernummer column exists
    if "Spendernummer" not in df.columns:
        df.insert(0, "Spendernummer", range(1, len(df)+1))
    
    # Remove Gen. column if it exists
    if "Gen." in df.columns:
        df = df.drop(columns=["Gen."])
    
    # Clean up LISS values
    if "LISS" in df.columns:
        df["LISS"] = df["LISS"].apply(lambda x: x if str(x).strip() in LISS_VALUES else "-")
    
    # Add index column after LISS if it doesn't already exist
    if "Index" not in df.columns and "LISS" in df.columns:
        df.insert(df.columns.get_loc("LISS") + 1, "Index", range(1, len(df)+1))
    
    return df

# --- Analysis function ---
def analyze_data(df):
    """Analyze the data to determine antigen status"""
    # --- Identify system-excluded antigens ---
    exclusion_pairs = [("C", "c"), ("E", "e"), ("K", "k"), ("KpA", "KpB"),
                      ("JsA", "JsB"), ("FyA", "FyB"), ("Jka", "Jkb"),
                      ("Lea", "Leb"), ("M", "N"), ("S", "s"), ("LuA", "LuB")]
    allowed_hetero = ["CW", "K", "KpA", "LuA"]
    
    def zygosity(val1, val2):
        if val1 == "+" and val2 == "+": return "hetero"
        if val1 == "+" or val2 == "+": return "homo"
        return "negativ"
    
    # Create a dictionary to track which row excluded which columns
    exclusion_tracking = {col: [] for col in ANTIGEN_COLUMNS}
    
    # Get rows with negative LISS reaction
    negatives = df[df["LISS"] == "-"].drop(columns=["Spendernummer", "Spender", "Index", "Spez. Antigen", "LISS"], errors='ignore')
    
    # Analyze each negative row for exclusions
    system_excluded = set()
    for idx, row in negatives.iterrows():
        temp_excl = []
        # Check homozygote antigens
        for a in [col for col in negatives.columns if col in ANTIGEN_COLUMNS]:
            if row.get(a) == "+":
                temp_excl.append(a)
                exclusion_tracking[a].append(idx + 1)  # +1 for human-readable indexing
        
        # Check exclusion pairs
        for a1, a2 in exclusion_pairs:
            if a1 in negatives.columns and a2 in negatives.columns:
                status = zygosity(row.get(a1, ""), row.get(a2, ""))
                if status == "homo":
                    if row.get(a1) == "+": 
                        temp_excl.append(a1)
                        exclusion_tracking[a1].append(idx + 1)
                    if row.get(a2) == "+": 
                        temp_excl.append(a2)
                        exclusion_tracking[a2].append(idx + 1)
                elif status == "hetero":
                    for ag in (a1, a2):
                        if ag in allowed_hetero and row.get(ag) == "+": 
                            temp_excl.append(ag)
                            exclusion_tracking[ag].append(idx + 1)
        
        system_excluded |= set(temp_excl)
    
    # --- Calculate statuses ---
    status_map = {}
    exclusion_reasons = {}
    
    positives = df[df["LISS"].isin(["+/-", "1+", "2+", "3+", "4+"])]
    for ag in ANTIGEN_COLUMNS:
        if ag in system_excluded:
            status_map[ag] = "Ausgestrichen"
            exclusion_reasons[ag] = f"Zeilen: {', '.join(map(str, sorted(set(exclusion_tracking[ag]))))}"
        else:
            pos_count = sum(positives[ag].fillna('').astype(str) == "+")
            if pos_count >= 3:
                status_map[ag] = "Bestätigt (3x +)"
            elif pos_count == 2:
                status_map[ag] = "Bestätigt (2x +)"
            elif pos_count == 1:
                status_map[ag] = "Nicht ausgeschlossen"
            else:
                status_map[ag] = "Keine Reaktion"
    
    return status_map, exclusion_reasons, system_excluded

# --- LISS Selection Table (Step 1) ---
def build_liss_table(df):
    """Build the data table for LISS selection in Step 1"""
    df = prepare_data(df)
    
    # Create column definitions
    columns = []
    for col in df.columns:
        col_def = {
            "name": col,
            "id": col,
            "editable": col == "LISS"  # Only LISS column is editable
        }
        
        # Add dropdown for LISS column
        if col == "LISS":
            col_def["presentation"] = "dropdown"
        
        columns.append(col_def)
    
    # Create dropdown options for LISS
    dropdown_dict = {
        "LISS": {"options": [{"label": val, "value": val} for val in LISS_VALUES]}
    }
    
    # Cell styling
    style_cell_conditional = [
        {"if": {"column_id": "Spendernummer"}, "width": "80px", "textAlign": "center"},
        {"if": {"column_id": "Index"}, "width": "60px", "textAlign": "center"},
        {"if": {"column_id": "LISS"}, "width": "80px", "textAlign": "center"},
    ]
    
    # Add compact styling for antigen columns
    style_cell_conditional.extend([{
        "if": {"column_id": col},
        "minWidth": "40px",
        "width": "40px",
        "maxWidth": "40px",
        "textAlign": "center",
    } for col in ANTIGEN_COLUMNS])
    
    return dash_table.DataTable(
        id="data-table",
        columns=columns,
        data=df.to_dict("records"),
        editable=True,
        dropdown=dropdown_dict,
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "center", "height": "35px"},
        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
        style_cell_conditional=style_cell_conditional,
        page_size=15
    )

# --- Colored analysis table (Step 2) ---
def build_analysis_table(df, status_map):
    """Build the colored analysis table for Step 2"""
    df = prepare_data(df)
    
    # Create styles based on status map
    styles = []
    for ag, status in status_map.items():
        if ag in df.columns:
            styles.append({
                "if": {"column_id": ag},
                "backgroundColor": STATUS_COLORS.get(status, "#ffffff"),
                "color": "#000000" if status != "Ausgestrichen" else "#ffffff"
            })
    
    # Create column definitions - all non-editable in the colored view
    columns = []
    for col in df.columns:
        col_def = {
            "name": col,
            "id": col,
            "editable": False
        }
        columns.append(col_def)
    
    # Cell styling
    style_cell_conditional = [
        {"if": {"column_id": "Spendernummer"}, "width": "80px", "textAlign": "center"},
        {"if": {"column_id": "Index"}, "width": "60px", "textAlign": "center"},
        {"if": {"column_id": "LISS"}, "width": "80px", "textAlign": "center"},
    ]
    
    # Add compact styling for antigen columns
    style_cell_conditional.extend([{
        "if": {"column_id": col},
        "minWidth": "40px",
        "width": "40px",
        "maxWidth": "40px",
        "textAlign": "center",
    } for col in ANTIGEN_COLUMNS])
    
    return dash_table.DataTable(
        id="analysis-table",
        columns=columns,
        data=df.to_dict("records"),
        editable=False,
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "center", "height": "35px"},
        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
        style_cell_conditional=style_cell_conditional,
        style_data_conditional=styles,
        page_size=15
    )

# --- Final filtered table (Step 3) ---
def build_final_table(df, included_columns):
    """Build the final filtered table for Step 3"""
    # Keep only columns that should be included
    display_columns = ['Spendernummer', 'Spender', 'LISS', 'Index'] + included_columns
    display_df = df[display_columns].copy()
    
    # Create column definitions
    columns = []
    for col in display_df.columns:
        col_def = {
            "name": col,
            "id": col,
            "editable": False
        }
        columns.append(col_def)
    
    # Cell styling
    style_cell_conditional = [
        {"if": {"column_id": "Spendernummer"}, "width": "80px", "textAlign": "center"},
        {"if": {"column_id": "Index"}, "width": "60px", "textAlign": "center"},
        {"if": {"column_id": "LISS"}, "width": "80px", "textAlign": "center"},
    ]
    
    # Add compact styling for antigen columns
    style_cell_conditional.extend([{
        "if": {"column_id": col},
        "minWidth": "40px",
        "width": "40px",
        "maxWidth": "40px",
        "textAlign": "center",
    } for col in included_columns])
    
    return dash_table.DataTable(
        id="final-table",
        columns=columns,
        data=display_df.to_dict("records"),
        editable=False,
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "center", "height": "35px"},
        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
        style_cell_conditional=style_cell_conditional,
        page_size=15
    )

# --- File upload component ---
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    
    try:
        if 'csv' in filename:
            # Assume that the user uploaded a CSV file
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
            return df
        else:
            # For future implementation: PDF or image parsing
            return None
    except Exception as e:
        print(e)
        return None

# --- Layout components ---
# Header component
def get_header():
    return html.Div([
        html.H1("Antigen Analyse Dashboard", className="dashboard-title"),
        html.Div([
            dcc.Upload(
                id='upload-data',
                children=html.Button('Datei hochladen', className="upload-button"),
                multiple=False
            ),
        ], className="header-actions")
    ], className="dashboard-header")

# Step 1 layout
def get_step1_layout(df=None):
    if df is None:
        df = data
    
    return html.Div([
        html.Div([
            html.Div([
                html.Label("ID-DiaPanel:"),
                dcc.Input(id="id-panel-number", type="text", placeholder="z.B. 45161.80.x"),
            ], className="panel-input"),
            html.Div([
                html.Label("ID-DiaPanel P:"),
                dcc.Input(id="id-panel-p-number", type="text", placeholder="z.B. 45171.80.x"),
            ], className="panel-input"),
        ], style={"display": "flex", "gap": "20px", "marginBottom": "20px"}),
        
        html.H3("Schritt 1: LISS-Werte auswählen", className="step-title"),
        html.P("Wählen Sie für jede Zeile den entsprechenden LISS-Wert aus."),
        
        html.Div(id="step1-table-container", children=[
            build_liss_table(df)
        ]),
        
        html.Div([
            html.Button("LISS-Werte bestätigen", id="step1-next-button", 
                       className="action-button primary"),
        ], style={"marginTop": "20px", "display": "flex", "justifyContent": "center"}),
    ], id="step1-content")

# Step 2 layout
def get_step2_layout(df, status_map, exclusion_reasons, system_excluded):
    # Create color legend
    legend_items = []
    for status, color in STATUS_COLORS.items():
        legend_items.append(
            html.Div([
                html.Div(style={"backgroundColor": color, "width": "20px", "height": "20px", "border": "1px solid #ccc"}),
                html.Span(status)
            ], style={"display": "flex", "alignItems": "center", "gap": "8px", "marginRight": "20px"})
        )
    
    # Create antigen selection checklist with color coding
    antigen_items = []
    for ag in sorted(ANTIGEN_COLUMNS):
        status = status_map.get(ag, "")
        reason = exclusion_reasons.get(ag, "")
        
        # Determine if this antigen is excluded by the system
        is_excluded = ag in system_excluded
        
        # Create the antigen selection item with appropriate styling
        antigen_items.append(
            html.Div([
                dcc.Checklist(
                    id={"type": "antigen-select", "index": ag},
                    options=[{"label": "", "value": ag}],
                    value=[ag] if not is_excluded else [],
                    className="antigen-checkbox"
                ),
                html.Div([
                    html.Span(ag, style={
                        "fontWeight": "bold",
                        "color": "#000" if not is_excluded else "#fff",
                        "backgroundColor": STATUS_COLORS.get(status, "#ffffff"),
                        "padding": "3px 8px",
                        "borderRadius": "4px"
                    }),
                    html.Span(f" - {status}", style={"marginLeft": "5px"})
                ]),
                html.Div(reason, className="exclusion-reason") if reason else None
            ], className="antigen-selection-item")
        )
    
    # Group antigens in columns for better layout
    antigen_columns = []
    items_per_column = len(antigen_items) // 3 + (1 if len(antigen_items) % 3 > 0 else 0)
    
    for i in range(0, len(antigen_items), items_per_column):
        column_items = antigen_items[i:i+items_per_column]
        antigen_columns.append(
            html.Div(column_items, className="antigen-column")
        )
    
    # Create the layout
    return html.Div([
        html.H3("Schritt 2: Analyse prüfen und Antigene auswählen", className="step-title"),
        
        # Color legend
        html.Div([
            html.H4("Farbliche Legende:", className="section-title"),
            html.Div(legend_items, className="legend-container")
        ], className="legend-section"),
        
        # Antigen table
        html.Div([
            html.Div([
                html.H4("Antigene auswählen:", className="section-title"),
                html.P("Wählen Sie die Antigene aus, die im finalen Ergebnis angezeigt werden sollen. System-ausgeschlossene Antigene sind standardmäßig abgewählt."),
                html.Div(antigen_columns, className="antigen-selection-container")
            ], className="antigen-selection-section"),
            
            html.Div([
                html.H4("Antigen-Analyse Übersicht:", className="section-title"),
                html.Div(id="analysis-table-container", children=[
                    build_analysis_table(df, status_map)
                ])
            ], className="analysis-table-section")
        ], className="step2-main-content"),
        
        # Navigation buttons
        html.Div([
            html.Button("Zurück zu Schritt 1", id="step2-back-button", 
                       className="action-button secondary", style={"marginRight": "10px"}),
            html.Button("Antigene bestätigen", id="step2-next-button", 
                       className="action-button primary")
        ], style={"marginTop": "20px", "display": "flex", "justifyContent": "center"}),
    ], id="step2-content")

# Step 3 layout
def get_step3_layout(df, included_columns, excluded_columns):
    return html.Div([
        html.H3("Schritt 3: Finalisierte Tabelle", className="step-title"),
        
        html.Div([
            html.H4("Finales Ergebnis:", className="section-title"),
            html.Div(id="final-table-container", children=[
                build_final_table(df, included_columns)
            ])
        ]),
        
        html.Div([
            html.H4("Ausgeschlossene Antigene:", className="section-title"),
            html.Div(", ".join(sorted(excluded_columns)) if excluded_columns else "Keine", 
                    className="excluded-antigens-list")
        ], className="excluded-antigens-section"),
        
        html.Div([
            html.Button("Zurück zu Schritt 2", id="step3-back-button", 
                       className="action-button secondary", style={"marginRight": "10px"}),
            html.Button("Neue Analyse starten", id="step3-restart-button", 
                       className="action-button primary")
        ], style={"marginTop": "20px", "display": "flex", "justifyContent": "center"}),
    ], id="step3-content")

# --- Main App Layout ---
app.layout = html.Div([
    # Header
    get_header(),
    
    # Main content area - will be updated by callbacks
    html.Div(id="main-content", children=[
        get_step1_layout()
    ], className="main-content"),
    
    # Store components to keep state between callbacks
    dcc.Store(id='current-step', data=1),
    dcc.Store(id='analyzed-data'),
    dcc.Store(id='status-map'),
    dcc.Store(id='exclusion-reasons'),
    dcc.Store(id='system-excluded'),
    dcc.Store(id='selected-antigens'),
    
    # Hidden dummy components for callback stability
    html.Div(id="dummy-div", style={"display": "none"}),
    html.Div(id="dummy-output", style={"display": "none"})
], className="dashboard-container")

# --- Callbacks ---
# Step 1 -> Step 2: Analyze data and go to step 2
@app.callback(
    [Output('main-content', 'children'),
     Output('current-step', 'data'),
     Output('analyzed-data', 'data'),
     Output('status-map', 'data'),
     Output('exclusion-reasons', 'data'),
     Output('system-excluded', 'data'),
     Output('selected-antigens', 'data')],
    [Input('step1-next-button', 'n_clicks')],
    [State('data-table', 'data'),
     State('current-step', 'data')]
)
def go_to_step2(n_clicks, table_data, current_step):
    if not n_clicks or current_step != 1:
        raise dash.exceptions.PreventUpdate
    
    # Convert table data to dataframe
    df = pd.DataFrame(table_data)
    
    # Analyze the data
    status_map, exclusion_reasons, system_excluded = analyze_data(df)
    
    # Initialize selected antigens - include all except system-excluded
    selected_antigens = [ag for ag in ANTIGEN_COLUMNS if ag not in system_excluded]
    
    # Create and return step 2 layout
    step2_layout = get_step2_layout(df, status_map, exclusion_reasons, system_excluded)
    
    return [
        step2_layout,
        2,  # Set step to 2
        df.to_dict('records'),
        status_map,
        exclusion_reasons,
        list(system_excluded),
        selected_antigens
    ]

# Step 2 -> Step 1: Go back to step 1
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True)],
    [Input('step2-back-button', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('current-step', 'data')],
    prevent_initial_call=True
)
def go_back_to_step1(n_clicks, analyzed_data, current_step):
    if not n_clicks or current_step != 2:
        raise dash.exceptions.PreventUpdate
    
    # Convert stored data back to dataframe
    df = pd.DataFrame(analyzed_data)
    
    # Go back to step 1, keeping the current data
    step1_layout = get_step1_layout(df)
    
    return [
        step1_layout,
        1  # Set step to 1
    ]

# Update selected antigens based on checklist changes
@app.callback(
    Output('selected-antigens', 'data', allow_duplicate=True),
    [Input({'type': 'antigen-select', 'index': dash.dependencies.ALL}, 'value')],
    [State('selected-antigens', 'data')],
    prevent_initial_call=True
)
def update_selected_antigens(checkbox_values, current_selected):
    # Get the context that triggered the callback
    ctx = callback_context
    
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    
    # Initialize list if None
    if current_selected is None:
        current_selected = []
    
    # Update selected antigens based on all checkboxes
    selected_antigens = []
    for i, values in enumerate(checkbox_values):
        if values and len(values) > 0:
            # Get the antigen id from the checkbox that was changed
            prop_id = ctx.triggered[0]['prop_id']
            if '.value' in prop_id:
                antigen_id = values[0]  # Use the value directly from the checkbox
                selected_antigens.append(antigen_id)
    
    return selected_antigens

# Step 2 -> Step 3: Finalize and go to step 3
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True)],
    [Input('step2-next-button', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('selected-antigens', 'data'),
     State('current-step', 'data')],
    prevent_initial_call=True
)
def go_to_step3(n_clicks, analyzed_data, selected_antigens, current_step):
    if not n_clicks or current_step != 2:
        raise dash.exceptions.PreventUpdate
    
    # Convert stored data back to dataframe
    df = pd.DataFrame(analyzed_data)
    
    # Determine included and excluded columns
    included_columns = selected_antigens if selected_antigens else []
    excluded_columns = [ag for ag in ANTIGEN_COLUMNS if ag not in included_columns]
    
    # Create and return step 3 layout
    step3_layout = get_step3_layout(df, included_columns, excluded_columns)
    
    return [
        step3_layout,
        3  # Set step to 3
    ]

# Step 3 -> Step 2: Go back to step 2
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True)],
    [Input('step3-back-button', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('status-map', 'data'),
     State('exclusion-reasons', 'data'),
     State('system-excluded', 'data'),
     State('current-step', 'data')],
    prevent_initial_call=True
)
def go_back_to_step2(n_clicks, analyzed_data, status_map, exclusion_reasons, system_excluded, current_step):
    if not n_clicks or current_step != 3:
        raise dash.exceptions.PreventUpdate
    
    # Convert stored data back to dataframe
    df = pd.DataFrame(analyzed_data)
    
    # Convert system_excluded back to set
    system_excluded = set(system_excluded)
    
    # Go back to step 2
    step2_layout = get_step2_layout(df, status_map, exclusion_reasons, system_excluded)
    
    return [
        step2_layout,
        2  # Set step to 2
    ]

# Step 3 -> Step 1: Start new analysis
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True),
     Output('analyzed-data', 'data', allow_duplicate=True),
     Output('status-map', 'data', allow_duplicate=True),
     Output('exclusion-reasons', 'data', allow_duplicate=True),
     Output('system-excluded', 'data', allow_duplicate=True),
     Output('selected-antigens', 'data', allow_duplicate=True)],
    [Input('step3-restart-button', 'n_clicks')],
    [State('current-step', 'data')],
    prevent_initial_call=True
)
def restart_analysis(n_clicks, current_step):
    if not n_clicks or current_step != 3:
        raise dash.exceptions.PreventUpdate
    
    # Start a new analysis (reset to step 1 with fresh data)
    step1_layout = get_step1_layout()
    
    return [
        step1_layout,
        1,  # Set step to 1
        None,  # Clear analyzed data
        None,  # Clear status map
        None,  # Clear exclusion reasons
        None,  # Clear system excluded
        None   # Clear selected antigens
    ]

# File upload callback
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True),
     Output('analyzed-data', 'data', allow_duplicate=True),
     Output('status-map', 'data', allow_duplicate=True),
     Output('exclusion-reasons', 'data', allow_duplicate=True),
     Output('system-excluded', 'data', allow_duplicate=True),
     Output('selected-antigens', 'data', allow_duplicate=True)],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')],
    prevent_initial_call=True
)
def update_from_upload(contents, filename):
    if not contents:
        raise dash.exceptions.PreventUpdate
    
    # Parse the uploaded file
    uploaded_df = parse_contents(contents, filename)
    
    if uploaded_df is not None:
        # Use the uploaded data for step 1
        step1_layout = get_step1_layout(uploaded_df)
        
        return [
            step1_layout,
            1,  # Set step to 1
            None,  # Clear analyzed data
            None,  # Clear status map
            None,  # Clear exclusion reasons
            None,  # Clear system excluded
            None   # Clear selected antigens
        ]
    
    # If upload fails, maintain current state
    raise dash.exceptions.PreventUpdate

# --- Custom CSS ---
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            :root {
                --primary-color: #2e8bc0;
                --secondary-color: #145da0;
                --success-color: #2d6a4f;
                --warning-color: #ffd166;
                --danger-color: #e63946;
                --light-color: #f8f9fa;
                --dark-color: #212529;
                --border-color: #dee2e6;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f5f7f9;
                color: var(--dark-color);
            }
            
            .dashboard-container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }
            
            .dashboard-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
                padding-bottom: 10px;
                border-bottom: 1px solid var(--border-color);
            }
            
            .dashboard-title {
                margin: 0;
                color: var(--secondary-color);
            }
            
            .main-content {
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
                padding: 25px;
            }
            
            .step-title {
                color: var(--secondary-color);
                border-bottom: 2px solid var(--primary-color);
                padding-bottom: 8px;
                margin-bottom: 20px;
            }
            
            .section-title {
                color: var(--secondary-color);
                margin-top: 25px;
                margin-bottom: 15px;
                font-size: 1.2em;
            }
            
            .action-button {
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: 500;
                transition: background-color 0.2s;
            }
            
            .primary {
                background-color: var(--primary-color);
                color: white;
            }
            
            .primary:hover {
                background-color: var(--secondary-color);
            }
            
            .secondary {
                background-color: white;
                color: var(--primary-color);
                border: 1px solid var(--primary-color);
            }
            
            .secondary:hover {
                background-color: #f0f7ff;
            }
            
            .panel-input {
                margin-bottom: 10px;
            }
            
            .panel-input label {
                display: block;
                margin-bottom: 5px;
                font-weight: 500;
            }
            
            .panel-input input {
                padding: 8px;
                border: 1px solid var(--border-color);
                border-radius: 4px;
                width: 200px;
            }
            
            .upload-button {
                background-color: var(--light-color);
                color: var(--dark-color);
                padding: 8px 16px;
                border: 1px solid var(--border-color);
                border-radius: 4px;
                cursor: pointer;
            }
            
            .upload-button:hover {
                background-color: #e9ecef;
            }
            
            /* Step 2 specific styles */
            .legend-container {
                display: flex;
                flex-wrap: wrap;
                margin-bottom: 15px;
                background-color: #f8f9fa;
                padding: 10px;
                border-radius: 4px;
            }
            
            .step2-main-content {
                display: grid;
                grid-template-columns: 300px 1fr;
                grid-gap: 20px;
                margin-top: 20px;
            }
            
            .antigen-selection-container {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 20px;
                max-height: 500px;
                overflow-y: auto;
                padding: 10px;
                background-color: #f8f9fa;
                border-radius: 4px;
            }
            
            .antigen-column {
                flex: 1;
                min-width: 200px;
            }
            
            .antigen-selection-item {
                display: flex;
                align-items: center;
                margin-bottom: 12px;
                padding: 5px;
                border-radius: 4px;
                transition: background-color 0.2s;
            }
            
            .antigen-selection-item:hover {
                background-color: #f0f7ff;
            }
            
            .antigen-checkbox {
                margin-right: 10px;
                display: inline-block;
            }
            
            .exclusion-reason {
                color: var(--danger-color);
                font-size: 0.85em;
                margin-top: 3px;
                margin-left: 30px;
            }
            
            /* Step 3 specific styles */
            .excluded-antigens-section {
                margin-top: 20px;
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
            }
            
            .excluded-antigens-list {
                font-weight: 500;
                color: var(--danger-color);
            }
            
            /* DataTable customizations */
            .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner td, 
            .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner th {
                border: 1px solid var(--border-color);
            }
            
            .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner .column-header-name {
                font-weight: bold;
            }
            
            /* Make dropdown inputs in table more visible */
            .Select-control {
                border: 1px solid #b8daff !important;
            }
            
            .Select-value {
                background-color: #f0f7ff !important;
            }
            
            /* Make sure checkboxes are visible and properly aligned */
            input[type="checkbox"] {
                width: 18px;
                height: 18px;
                margin-right: 5px;
                vertical-align: middle;
            }
            
            @media (max-width: 768px) {
                .step2-main-content {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

if __name__ == "__main__":
    app.run(debug=True)