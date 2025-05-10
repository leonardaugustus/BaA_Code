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
    
    # Move Spez. Antigen to the rightmost position if it exists
    if "Spez. Antigen" in df.columns:
        spez_antigen = df["Spez. Antigen"]
        df = df.drop(columns=["Spez. Antigen"])
        df["Spez. Antigen"] = spez_antigen
    
    # Remove Spendernummer column for Step 1 (but keep it in the data for later steps)
    # We'll handle this in the specific step functions
    
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




########################### start of part 2 ######################################################

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
    negatives = df[df["LISS"] == "-"].drop(columns=["Spender", "Index", "Spez. Antigen", "LISS"], errors='ignore')
    
    # Keep Spendernummer for reference in exclusion tracking if it exists in the original dataframe
    spendernummer_map = {}
    if "Spendernummer" in df.columns:
        for idx, row in df.iterrows():
            spendernummer_map[idx] = row.get("Spendernummer", idx + 1)
    
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
    
    # Ensure 'Spendernummer' is not treated as an antigen for status calculation
    for ag in ANTIGEN_COLUMNS:
        # Skip non-antigens like 'Spendernummer'
        if ag == "Spendernummer":
            continue
            
        positives = df[df["LISS"].isin(["+/-", "1+", "2+", "3+", "4+"])]
        
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



########################### end of part 2 ######################################################


########################### start of part 3 ######################################################

# --- LISS Selection Table (Step 1) ---
def build_liss_table(df):
    """Build the data table for LISS selection in Step 1"""
    df = prepare_data(df)
    
    # Drop Spendernummer column for Step 1 as requested
    if "Spendernummer" in df.columns:
        df = df.drop(columns=["Spendernummer"])
    
    # Create column definitions
    columns = []
    for col in df.columns:
        col_def = {
            "name": col,
            "id": col,
            "editable": col == "LISS" or col == "Spez. Antigen"  # Make LISS and Spez. Antigen editable
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
        {"if": {"column_id": "Index"}, "width": "60px", "textAlign": "center"},
        {"if": {"column_id": "LISS"}, "width": "80px", "textAlign": "center"},
        {"if": {"column_id": "Spender"}, "width": "120px", "textAlign": "left"},
        {"if": {"column_id": "Spez. Antigen"}, "width": "150px", "textAlign": "left"},
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
        style_table={"maxWidth": "900px", "margin": "0 auto"},
        style_cell={"textAlign": "center", "height": "35px"},
        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
        style_cell_conditional=style_cell_conditional,
        page_size=15
    )

# --- Colored analysis table with integrated antigen selection (Step 2) ---
def build_analysis_table(df, status_map, exclusion_reasons, system_excluded):
    """Build the colored analysis table with integrated antigen selection for Step 2"""
    df = prepare_data(df)
    
    # Create the header checkboxes for antigen columns
    header_checkboxes = []
    
    # Create the styles for the cells based on status
    styles = []
    
    # Get column list to determine positioning
    column_ids = list(df.columns)
    
    # Create individual checkbox for each antigen column that aligns with the table
    for ag in ANTIGEN_COLUMNS:
        if ag in column_ids:
            status = status_map.get(ag, "")
            is_excluded = ag in system_excluded
            background_color = STATUS_COLORS.get(status, "#ffffff")
            
            # Add style for the column
            styles.append({
                "if": {"column_id": ag},
                "backgroundColor": background_color,
                "color": "#000000" if status != "Ausgestrichen" else "#ffffff"
            })
            
            # Create checkbox that matches column width and is disabled if excluded
            checkbox_style = {
                "width": "25px",  # Same as column width
                "height": "25px",
                "padding": "0",
                "margin": "0 auto",
                "display": "block",
                "opacity": "0.5" if is_excluded else "1"
            }
            
            header_checkboxes.append(
                html.Div([
                    dcc.Checklist(
                        id={"type": "column-select", "index": ag},
                        options=[{"label": "", "value": ag}],
                        value=[ag] if not is_excluded else [],
                        className="column-checkbox",
                        style={"pointer-events": "none" if is_excluded else "auto"}
                    )
                ], style={"width": "25px", "display": "inline-block", "textAlign": "center"})
            )
    
    # Create a hidden checklist that will store the actual selected values
    antigen_selector = html.Div([
        dcc.Checklist(
            id="antigen-select-checkboxes",
            options=[{"label": ag, "value": ag} for ag in ANTIGEN_COLUMNS],
            value=[ag for ag in ANTIGEN_COLUMNS if ag not in system_excluded],
            style={"display": "none"}  # Hidden, just used for state
        )
    ])
    
    # Create regular columns for the table
    columns = []
    for col in df.columns:
        col_def = {
            "name": col,
            "id": col,
            "editable": False
        }
        columns.append(col_def)
    
    # Cell styling with reduced widths
    style_cell_conditional = [
        {"if": {"column_id": "Spendernummer"}, "width": "60px", "textAlign": "center"},
        {"if": {"column_id": "Index"}, "width": "40px", "textAlign": "center"},
        {"if": {"column_id": "LISS"}, "width": "50px", "textAlign": "center"},
        {"if": {"column_id": "Spender"}, "width": "80px", "textAlign": "left"},
        {"if": {"column_id": "Spez. Antigen"}, "width": "100px", "textAlign": "left"},
    ]
    
    # Add compact styling for antigen columns
    style_cell_conditional.extend([{
        "if": {"column_id": col},
        "minWidth": "25px",
        "width": "25px",
        "maxWidth": "25px",
        "textAlign": "center",
    } for col in ANTIGEN_COLUMNS])
    
    # Calculate offsets for checkbox positioning
    # We need to position the checkbox row so it aligns with the antigen columns
    non_antigen_width = sum([
        60,  # Spendernummer
        80,  # Spender
        40,  # Index
        50,  # LISS
    ])
    
    # Create the header with checkbox row + alignment padding
    header_row = html.Div([
        # Padding div to align with non-antigen columns
        html.Div(style={"display": "inline-block", "width": f"{non_antigen_width}px"}),
        # Container for antigen checkboxes
        html.Div(header_checkboxes, style={
            "display": "inline-block",
            "whiteSpace": "nowrap"
        })
    ], className="header-checkbox-row")
    
    # Combine the header row, antigen selector, and the table into a single layout
    return html.Div([
        antigen_selector,
        header_row,
        dash_table.DataTable(
            id="analysis-table",
            columns=columns,
            data=df.to_dict("records"),
            editable=False,
            style_table={"maxWidth": "900px", "margin": "0 auto"},
            style_cell={"textAlign": "center", "height": "35px"},
            style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
            style_cell_conditional=style_cell_conditional,
            style_data_conditional=styles,
            page_size=15
        )
    ])

# --- Final filtered table (Step 3) ---
def build_final_table(df, included_columns, user_selections=None):
    """Build the final filtered table for Step 3"""
    # Keep only columns that should be included
    display_columns = ['Spender', 'LISS', 'Index'] + included_columns
    
    # Add Spendernummer if it exists
    if "Spendernummer" in df.columns:
        display_columns = ['Spendernummer'] + display_columns
    
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
    
    # Cell styling with reduced width for Spender column
    style_cell_conditional = [
        {"if": {"column_id": "Spendernummer"}, "width": "80px", "textAlign": "center"},
        {"if": {"column_id": "Index"}, "width": "60px", "textAlign": "center"},
        {"if": {"column_id": "LISS"}, "width": "80px", "textAlign": "center"},
        {"if": {"column_id": "Spender"}, "width": "120px", "textAlign": "left"},  # Reduced width
    ]
    
    # Add compact styling for antigen columns
    style_cell_conditional.extend([{
        "if": {"column_id": col},
        "minWidth": "40px",
        "width": "40px",
        "maxWidth": "40px",
        "textAlign": "center",
    } for col in included_columns])
    
    # Highlight differences between system and user selections if available
    style_data_conditional = []
    if user_selections:
        user_included = set(user_selections)
        system_included = set(included_columns)
        differences = user_included.symmetric_difference(system_included)
        
        for col in differences:
            if col in display_df.columns:
                style_data_conditional.append({
                    "if": {"column_id": col},
                    "backgroundColor": "#FFEB3B",  # Yellow highlight for differences
                    "border": "2px solid #FFC107"
                })
    
    return dash_table.DataTable(
        id="final-table",
        columns=columns,
        data=display_df.to_dict("records"),
        editable=False,
        style_table={"maxWidth": "900px", "margin": "0 auto"},
        style_cell={"textAlign": "center", "height": "35px"},
        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
        style_cell_conditional=style_cell_conditional,
        style_data_conditional=style_data_conditional,
        page_size=15
    )

########################### end of part 3 ######################################################





########################### start of part 4 ######################################################

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
# Header component with progress indicator
def get_header(current_step=1):
    # Create progress indicator
    steps = [
        {"label": "LISS-Werte auswählen", "active": current_step >= 1, "completed": current_step > 1},
        {"label": "Analyse prüfen", "active": current_step >= 2, "completed": current_step > 2},
        {"label": "Finales Ergebnis", "active": current_step >= 3, "completed": False}
    ]
    
    step_items = []
    for i, step in enumerate(steps):
        step_items.append(
            html.Div([
                html.Div(f"{i+1}", className=f"step-number {'active' if step['active'] else ''} {'completed' if step['completed'] else ''}"),
                html.Div(step["label"], className="step-label")
            ], className=f"step-item {'active' if step['active'] else ''}")
        )
    
    progress_indicator = html.Div(step_items, className="progress-steps")
    
    return html.Div([
        html.Div([
            html.H1("Antigen Analyse Dashboard", className="dashboard-title"),
            html.Div([
                dcc.Upload(
                    id='upload-data',
                    children=html.Button('Datei hochladen', className="upload-button"),
                    multiple=False
                ),
            ], className="header-actions")
        ], className="dashboard-header"),
        
        # Add progress indicator
        progress_indicator
    ])

# Welcome/landing page layout
def get_landing_page():
    return html.Div([
        html.H2("Willkommen beim Antigen Analyse Dashboard", className="welcome-title"),
        html.P("Dieses Tool hilft Ihnen bei der Analyse von Antigen-Tests in drei einfachen Schritten:"),
        
        html.Div([
            html.Div([
                html.Div("1", className="step-number active"),
                html.H3("LISS-Werte auswählen"),
                html.P("Importieren Sie Ihre Daten und wählen Sie die LISS-Werte für jede Probe aus.")
            ], className="welcome-step"),
            
            html.Div([
                html.Div("2", className="step-number"),
                html.H3("Analyse prüfen"),
                html.P("Überprüfen Sie die automatische Analyse und wählen Sie relevante Antigene aus.")
            ], className="welcome-step"),
            
            html.Div([
                html.Div("3", className="step-number"),
                html.H3("Finales Ergebnis"),
                html.P("Sehen Sie die gefilterte Tabelle mit Ihren ausgewählten Antigenen.")
            ], className="welcome-step"),
        ], className="welcome-steps"),
        
        html.Div([
            html.Button("Neue Analyse starten", id="start-analysis-button", 
                       className="action-button primary"),
        ], style={"marginTop": "30px", "display": "flex", "justifyContent": "center"}),
    ], id="landing-page", className="welcome-container")

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
        html.P("Wählen Sie für jede Zeile den entsprechenden LISS-Wert aus. Die Spezifischen Antigene können Sie ebenfalls bearbeiten."),
        
        html.Div(id="step1-table-container", children=[
            build_liss_table(df)
        ]),
        
        html.Div([
            html.Button("LISS-Werte bestätigen", id="step1-next-button", 
                       className="action-button primary"),
        ], style={"marginTop": "20px", "display": "flex", "justifyContent": "center"}),
    ], id="step1-content")

# Step 2 layout with integrated antigen selection in table
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
    
    # Tooltip for the analysis explanation
    analysis_tooltip = html.Div([
        html.I(className="fas fa-info-circle"),
        html.Div([
            html.P("Die Farben zeigen den Status jedes Antigens:"),
            html.Ul([
                html.Li("Dunkelgrün: Bestätigt (3x +)"),
                html.Li("Hellgrün: Bestätigt (2x +)"),
                html.Li("Gelb: Nicht ausgeschlossen"),
                html.Li("Grau: Keine Reaktion"),
                html.Li("Rot: Ausgestrichen (Antigen wird ausgeschlossen)")
            ])
        ], className="tooltip-content")
    ], className="tooltip")
    
    # Create a dedicated antigen selection component for better usability
    antigen_selection_component = html.Div([
        html.H4("Antigene auswählen:", className="section-title"),
        html.P("Wählen Sie die Antigene aus, die im finalen Ergebnis angezeigt werden sollen:"),
        html.Div([
            html.Button("Alle auswählen", id="select-all-button", className="selection-button"),
            html.Button("Alle abwählen", id="deselect-all-button", className="selection-button"),
            html.Button("Standard-Auswahl", id="default-selection-button", className="selection-button"),
        ], className="selection-buttons")
    ], className="antigen-selection-controls")
    
    # Create the layout
    return html.Div([
        html.H3("Schritt 2: Analyse prüfen und Antigene auswählen", className="step-title"),
        
        # Color legend
        html.Div([
            html.H4("Farbliche Legende:", className="section-title"),
            html.Div(legend_items, className="legend-container")
        ], className="legend-section"),
        
        # Instructions for antigen selection
        html.Div([
            html.H4([
                "Antigen-Analyse Übersicht und Auswahl:",
                analysis_tooltip
            ], className="section-title with-tooltip"),
            html.P("Die Tabelle zeigt die Analyseergebnisse für alle Antigene. Wählen Sie die relevanten Antigene durch Anklicken der Checkboxen über der Tabelle aus."),
            antigen_selection_component
        ]),
        
        # Antigen analysis table with integrated selection
        html.Div(id="analysis-table-container", className="analysis-table-container", children=[
            build_analysis_table(df, status_map, exclusion_reasons, system_excluded)
        ]),
        
        # Selected antigens summary - will be updated by callbacks
        html.Div([
            html.H4("Ausgewählte Antigene:", className="section-title"),
            html.Div(id="selected-antigens-display", className="selected-antigens-list")
        ], className="selected-antigens-section"),
        
        # Navigation buttons
        html.Div([
            html.Button("Zurück zu Schritt 1", id="step2-back-button", 
                       className="action-button secondary", style={"marginRight": "10px"}),
            html.Button("Antigene bestätigen", id="step2-next-button", 
                       className="action-button primary")
        ], style={"marginTop": "20px", "display": "flex", "justifyContent": "center"}),
    ], id="step2-content")

# Step 3 layout with user vs system comparison
def get_step3_layout(df, included_columns, excluded_columns, user_selections=None):
    # Determine differences between system and user selections if provided
    differences = []
    if user_selections:
        user_included = set(user_selections)
        system_included = set(included_columns)
        differences = list(user_included.symmetric_difference(system_included))
    
    return html.Div([
        html.H3("Schritt 3: Finalisierte Tabelle", className="step-title"),
        
        # Tab selector for different views
        dcc.Tabs([
            dcc.Tab(label="Systemauswahl", children=[
                html.Div([
                    html.H4("Tabelle mit Systemauswahl:", className="section-title"),
                    html.Div(id="final-table-container", children=[
                        build_final_table(df, included_columns)
                    ])
                ])
            ], className="custom-tab", selected_className="custom-tab-selected"),
            
            dcc.Tab(label="Benutzerauswahl", children=[
                html.Div([
                    html.H4("Tabelle mit Benutzerauswahl:", className="section-title"),
                    html.Div(id="user-table-container", children=[
                        build_final_table(df, user_selections if user_selections else included_columns)
                    ])
                ])
            ], className="custom-tab", selected_className="custom-tab-selected"),
            
            dcc.Tab(label="Vergleich", children=[
                html.Div([
                    html.H4("Vergleich System- und Benutzerauswahl:", className="section-title"),
                    html.Div([
                        html.P("System-Auswahl: " + ", ".join(sorted(included_columns))),
                        html.P("Benutzer-Auswahl: " + ", ".join(sorted(user_selections if user_selections else included_columns))),
                        html.P("Unterschiede: " + (", ".join(sorted(differences)) if differences else "Keine"))
                    ], className="comparison-info"),
                    html.Div(id="comparison-table-container", children=[
                        build_final_table(df, list(set(included_columns + (user_selections if user_selections else []))), user_selections)
                    ])
                ])
            ], className="custom-tab", selected_className="custom-tab-selected"),
        ], id="result-tabs", className="custom-tabs"),
        
        # Excluded antigens summary
        html.Div([
            html.H4("Ausgeschlossene Antigene:", className="section-title"),
            html.Div(", ".join(sorted(excluded_columns)) if excluded_columns else "Keine", 
                    className="excluded-antigens-list")
        ], className="excluded-antigens-section"),
        
        # Navigation buttons
        html.Div([
            html.Button("Zurück zu Schritt 2", id="step3-back-button", 
                       className="action-button secondary", style={"marginRight": "10px"}),
            html.Button("PDF erstellen", id="generate-pdf-button",
                       className="action-button accent", style={"marginRight": "10px"}),
            html.Button("Neue Analyse starten", id="step3-restart-button", 
                       className="action-button primary")
        ], style={"marginTop": "20px", "display": "flex", "justifyContent": "center"}),
    ], id="step3-content")

########################### end of part 4 ######################################################




########################### start of part 5 ######################################################

# Sync the main checklist with user selections for buttons
@app.callback(
    Output('antigen-select-checkboxes', 'value', allow_duplicate=True),
    [Input('user-selections', 'data')],
    prevent_initial_call=True
)
def sync_main_checklist(user_selections):
    if user_selections is None:
        raise dash.exceptions.PreventUpdate
    
    return user_selections# Sync the column checkboxes with user selections
@app.callback(
    [Output({'type': 'column-select', 'index': dash.dependencies.MATCH}, 'value')],
    [Input('user-selections', 'data')],
    [State({'type': 'column-select', 'index': dash.dependencies.MATCH}, 'id')],
    prevent_initial_call=True
)
def sync_column_checkboxes(user_selections, checkbox_id):
    if not user_selections:
        return [[]]
    
    antigen = checkbox_id['index']
    if antigen in user_selections:
        return [[antigen]]
    else:
        return [[]]# --- Main App Layout ---
app.layout = html.Div([
    # Header - will be updated with current step
    html.Div(id="header-container", children=[
        get_header(current_step=1)
    ]),
    
    # Main content area - will be updated by callbacks
    html.Div(id="main-content", children=[
        get_landing_page()  # Start with welcome page
    ], className="main-content"),
    
    # Store components to keep state between callbacks
    dcc.Store(id='current-step', data=0),  # 0 = landing page, 1-3 = steps
    dcc.Store(id='analyzed-data'),
    dcc.Store(id='status-map'),
    dcc.Store(id='exclusion-reasons'),
    dcc.Store(id='system-excluded'),
    dcc.Store(id='selected-antigens'),
    dcc.Store(id='user-selections'),
    
    # Hidden dummy components for callback stability
    html.Div(id="dummy-div", style={"display": "none"}),
    html.Div(id="dummy-output", style={"display": "none"})
], className="dashboard-container")

# --- Callbacks ---
# Start analysis from landing page
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True)],
    [Input('start-analysis-button', 'n_clicks')],
    [State('current-step', 'data')],
    prevent_initial_call=True
)
def start_analysis(n_clicks, current_step):
    if not n_clicks or current_step != 0:
        raise dash.exceptions.PreventUpdate
    
    # Start with step 1
    return [
        get_step1_layout(),
        get_header(current_step=1),
        1  # Set step to 1
    ]

# Step 1 -> Step 2: Analyze data and go to step 2
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True),
     Output('analyzed-data', 'data', allow_duplicate=True),
     Output('status-map', 'data', allow_duplicate=True),
     Output('exclusion-reasons', 'data', allow_duplicate=True),
     Output('system-excluded', 'data', allow_duplicate=True),
     Output('selected-antigens', 'data', allow_duplicate=True),
     Output('user-selections', 'data', allow_duplicate=True)],
    [Input('step1-next-button', 'n_clicks')],
    [State('data-table', 'data'),
     State('current-step', 'data')],
    prevent_initial_call=True
)
def go_to_step2(n_clicks, table_data, current_step):
    if not n_clicks or current_step != 1:
        raise dash.exceptions.PreventUpdate
    
    # Convert table data to dataframe
    df = pd.DataFrame(table_data)
    
    # Add back Spendernummer if it was removed for step 1
    if "Spendernummer" not in df.columns and "Spendernummer" in data.columns:
        df.insert(0, "Spendernummer", data["Spendernummer"].values)
    
    # Analyze the data
    status_map, exclusion_reasons, system_excluded = analyze_data(df)
    
    # Initialize selected antigens - include all except system-excluded
    selected_antigens = [ag for ag in ANTIGEN_COLUMNS if ag not in system_excluded]
    
    # Initially set user selections same as system selections
    user_selections = selected_antigens.copy()
    
    # Create and return step 2 layout
    step2_layout = get_step2_layout(df, status_map, exclusion_reasons, system_excluded)
    
    return [
        step2_layout,
        get_header(current_step=2),
        2,  # Set step to 2
        df.to_dict('records'),
        status_map,
        exclusion_reasons,
        list(system_excluded),
        selected_antigens,
        user_selections
    ]

# Step 2 -> Step 1: Go back to step 1
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
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
        get_header(current_step=1),
        1  # Set step to 1
    ]

# Update selected antigens display in Step 2
@app.callback(
    Output('selected-antigens-display', 'children'),
    [Input('user-selections', 'data')]
)
def update_selected_antigens_display(selected_antigens):
    if not selected_antigens:
        return "Keine Antigene ausgewählt"
    
    return ", ".join(sorted(selected_antigens))

# Update user selections based on column checkboxes
@app.callback(
    Output('user-selections', 'data', allow_duplicate=True),
    [Input({'type': 'column-select', 'index': dash.dependencies.ALL}, 'value')],
    [State('current-step', 'data')],
    prevent_initial_call=True
)
def update_user_selections_from_column_checkboxes(checkbox_values, current_step):
    if not checkbox_values or current_step != 2:
        raise dash.exceptions.PreventUpdate
    
    # Get the context that triggered the callback
    ctx = callback_context
    
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    
    # Extract selected antigens from all checkboxes
    selected_antigens = []
    for values in checkbox_values:
        if values and len(values) > 0:
            selected_antigens.extend(values)
    
    return selected_antigens

# Select all antigens button
@app.callback(
    Output('user-selections', 'data', allow_duplicate=True),
    [Input('select-all-button', 'n_clicks')],
    [State('status-map', 'data')],
    prevent_initial_call=True
)
def select_all_antigens(n_clicks, status_map):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    # Select all antigens that have a status
    return list(status_map.keys())

# Deselect all antigens button
@app.callback(
    Output('user-selections', 'data', allow_duplicate=True),
    [Input('deselect-all-button', 'n_clicks')],
    prevent_initial_call=True
)
def deselect_all_antigens(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    return []

# Default selection button (same as system selection)
@app.callback(
    Output('user-selections', 'data', allow_duplicate=True),
    [Input('default-selection-button', 'n_clicks')],
    [State('selected-antigens', 'data')],
    prevent_initial_call=True
)
def default_selection(n_clicks, system_selection):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    return system_selection

# Step 2 -> Step 3: Finalize and go to step 3
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True)],
    [Input('step2-next-button', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('selected-antigens', 'data'),
     State('user-selections', 'data'),
     State('current-step', 'data')],
    prevent_initial_call=True
)
def go_to_step3(n_clicks, analyzed_data, selected_antigens, user_selections, current_step):
    if not n_clicks or current_step != 2:
        raise dash.exceptions.PreventUpdate
    
    # Convert stored data back to dataframe
    df = pd.DataFrame(analyzed_data)
    
    # Determine included and excluded columns
    included_columns = selected_antigens if selected_antigens else []
    excluded_columns = [ag for ag in ANTIGEN_COLUMNS if ag not in included_columns]
    
    # Create and return step 3 layout
    step3_layout = get_step3_layout(df, included_columns, excluded_columns, user_selections)
    
    return [
        step3_layout,
        get_header(current_step=3),
        3  # Set step to 3
    ]

# Step 3 -> Step 2: Go back to step 2
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
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
        get_header(current_step=2),
        2  # Set step to 2
    ]

# Step 3 -> Landing: Start new analysis
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True),
     Output('analyzed-data', 'data', allow_duplicate=True),
     Output('status-map', 'data', allow_duplicate=True),
     Output('exclusion-reasons', 'data', allow_duplicate=True),
     Output('system-excluded', 'data', allow_duplicate=True),
     Output('selected-antigens', 'data', allow_duplicate=True),
     Output('user-selections', 'data', allow_duplicate=True)],
    [Input('step3-restart-button', 'n_clicks')],
    [State('current-step', 'data')],
    prevent_initial_call=True
)
def restart_analysis(n_clicks, current_step):
    if not n_clicks or current_step != 3:
        raise dash.exceptions.PreventUpdate
    
    # Start a new analysis (reset to landing page)
    return [
        get_landing_page(),
        get_header(current_step=1),
        0,  # Set step to landing page
        None,  # Clear analyzed data
        None,  # Clear status map
        None,  # Clear exclusion reasons
        None,  # Clear system excluded
        None,  # Clear selected antigens
        None   # Clear user selections
    ]

# Generate PDF (placeholder functionality)
@app.callback(
    Output('dummy-output', 'children'),
    [Input('generate-pdf-button', 'n_clicks')],
    prevent_initial_call=True
)
def generate_pdf(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    # This is a placeholder - actual PDF generation would require additional implementation
    return "PDF generation requested"

# File upload callback
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True),
     Output('analyzed-data', 'data', allow_duplicate=True),
     Output('status-map', 'data', allow_duplicate=True),
     Output('exclusion-reasons', 'data', allow_duplicate=True),
     Output('system-excluded', 'data', allow_duplicate=True),
     Output('selected-antigens', 'data', allow_duplicate=True),
     Output('user-selections', 'data', allow_duplicate=True)],
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
            get_header(current_step=1),
            1,  # Set step to 1
            None,  # Clear analyzed data
            None,  # Clear status map
            None,  # Clear exclusion reasons
            None,  # Clear system excluded
            None,  # Clear selected antigens
            None   # Clear user selections
        ]
    
    # If upload fails, maintain current state
    raise dash.exceptions.PreventUpdate


########################### end of part 5 ######################################################






########################### start of part 6 ######################################################

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
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
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
                --accent-color: #7209b7;
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
                margin-bottom: 20px;
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
                margin-top: 20px;
            }
            
            /* Progress Steps */
            .progress-steps {
                display: flex;
                justify-content: space-between;
                margin: 20px 0;
                position: relative;
            }
            
            .progress-steps::before {
                content: '';
                position: absolute;
                top: 20px;
                left: 10%;
                right: 10%;
                height: 2px;
                background-color: var(--border-color);
                z-index: 1;
            }
            
            .step-item {
                display: flex;
                flex-direction: column;
                align-items: center;
                width: 33.33%;
                position: relative;
                z-index: 2;
            }
            
            .step-number {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background-color: white;
                border: 2px solid var(--border-color);
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                margin-bottom: 8px;
                color: var(--dark-color);
            }
            
            .step-number.active {
                background-color: var(--primary-color);
                border-color: var(--primary-color);
                color: white;
            }
            
            .step-number.completed {
                background-color: var(--success-color);
                border-color: var(--success-color);
                color: white;
            }
            
            .step-label {
                font-size: 0.9rem;
                text-align: center;
                color: var(--dark-color);
            }
            
            .step-item.active .step-label {
                font-weight: bold;
                color: var(--primary-color);
            }
            
            /* Welcome page */
            .welcome-container {
                text-align: center;
                padding: 30px;
            }
            
            .welcome-title {
                color: var(--secondary-color);
                margin-bottom: 20px;
            }
            
            .welcome-steps {
                display: flex;
                justify-content: space-between;
                margin-top: 40px;
                text-align: left;
            }
            
            .welcome-step {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 25px;
                width: 30%;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
            }
            
            .welcome-step h3 {
                color: var(--secondary-color);
                margin-top: 15px;
            }
            
            /* Common styles */
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
                display: flex;
                align-items: center;
            }
            
            .with-tooltip {
                position: relative;
            }
            
            .tooltip {
                position: relative;
                display: inline-block;
                margin-left: 8px;
                cursor: help;
            }
            
            .tooltip i {
                color: var(--primary-color);
            }
            
            .tooltip .tooltip-content {
                visibility: hidden;
                width: 300px;
                background-color: #333;
                color: #fff;
                text-align: left;
                border-radius: 6px;
                padding: 10px;
                position: absolute;
                z-index: 10;
                bottom: 125%;
                left: 50%;
                margin-left: -150px;
                opacity: 0;
                transition: opacity 0.3s;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            }
            
            .tooltip:hover .tooltip-content {
                visibility: visible;
                opacity: 1;
            }
            
            .action-button {
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: 500;
                transition: background-color 0.2s, transform 0.1s;
            }
            
            .action-button:hover {
                transform: translateY(-2px);
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            }
            
            .action-button:active {
                transform: translateY(0);
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
            
            .accent {
                background-color: var(--accent-color);
                color: white;
            }
            
            .accent:hover {
                background-color: #5a189a;
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
                transition: background-color 0.2s, transform 0.1s;
            }
            
            .upload-button:hover {
                background-color: #e9ecef;
                transform: translateY(-2px);
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
            
            .selection-buttons {
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
            }
            
            .selection-button {
                background-color: #f0f7ff;
                color: var(--secondary-color);
                border: 1px solid var(--border-color);
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                transition: background-color 0.2s;
            }
            
            .selection-button:hover {
                background-color: var(--primary-color);
                color: white;
            }
            
            .analysis-table-container {
                margin-top: 20px;
                margin-bottom: 30px;
                max-height: 500px;
                overflow-y: auto;
            }
            
            .selected-antigens-section {
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin-top: 20px;
            }
            
            .selected-antigens-list {
                font-weight: 500;
                color: var(--primary-color);
            }
            
            /* Step 3 specific styles */
            .custom-tabs {
                margin-top: 20px;
            }
            
            .custom-tab {
                padding: 12px 20px;
                font-weight: 500;
                color: var(--dark-color);
                border-radius: 4px 4px 0 0;
                border: 1px solid var(--border-color);
                border-bottom: none;
                background-color: #f0f0f0;
                margin-right: 5px;
            }
            
            .custom-tab-selected {
                background-color: white;
                border-top: 3px solid var(--primary-color);
                color: var(--primary-color);
            }
            
            .comparison-info {
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin-bottom: 20px;
            }
            
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
            
            /* Header checkbox row styling */
            .header-checkbox-row {
                margin-bottom: 8px;
                padding: 5px 0;
                background-color: #f8f9fa;
                border-radius: 4px;
                white-space: nowrap;
                overflow-x: auto;
            }
            
            .column-checkbox {
                display: flex;
                justify-content: center;
                align-items: center;
                margin: 0;
            }
            
            .column-checkbox input[type="checkbox"] {
                width: 16px;
                height: 16px;
                cursor: pointer;
            }
            
            /* Make sure checkboxes are visible and properly aligned */
            input[type="checkbox"] {
                width: 18px;
                height: 18px;
                margin-right: 5px;
                vertical-align: middle;
            }
            
            @media (max-width: 768px) {
                .welcome-steps {
                    flex-direction: column;
                    gap: 20px;
                }
                
                .welcome-step {
                    width: 100%;
                }
                
                .selection-buttons {
                    flex-direction: column;
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



########################### end of part 6 ######################################################