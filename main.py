# main.py
import dash
from dash import dcc, html, Input, Output, State, dash_table, callback_context, ALL, MATCH
import pandas as pd
import numpy as np
import base64
import io
from datetime import datetime
import json

# Import from your modules
from database import get_db, Analysis, Donor
from step0_components import get_step0_layout, parse_pdf_content, build_diff_table
from navigation_and_step4 import (
    get_header_with_navigation, get_step4_layout, 
    create_exclusion_summary, create_provisional_report,
    generate_pdf_report, create_medical_report, create_lab_technical_report
)





# Mapping of uppercase and lowercase letters to their superscript equivalents
superscript_map = {
    'A': 'ᴬ', 'B': 'ᴮ', 'C': 'ᶜ', 'D': 'ᴰ', 'E': 'ᴱ', 'F': 'ᶠ', 'G': 'ᴳ', 'H': 'ᴴ',
    'I': 'ᴵ', 'J': 'ᴶ', 'K': 'ᴷ', 'L': 'ᴸ', 'M': 'ᴹ', 'N': 'ᴺ', 'O': 'ᴼ', 'P': 'ᴾ',
    'R': 'ᴿ', 'T': 'ᵀ', 'U': 'ᵁ', 'V': 'ⱽ', 'W': 'ᵂ', 'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ',
    'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ', 'g': 'ᵍ', 'h': 'ʰ', 'i': 'ⁱ', 'j': 'ʲ', 'k': 'ᵏ',
    'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ', 'o': 'ᵒ', 'p': 'ᵖ', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ',
    'u': 'ᵘ', 'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ'
}

def format_antigen(ag: str) -> str:
    """Format antigen label so that the last character is in superscript."""
    if len(ag) <= 1:
        return ag
    prefix = ag[:-1]
    last_char = ag[-1]
    superscript = superscript_map.get(last_char, last_char)
    return f"{prefix}{superscript}"

# Test with some examples for Formatting ***
example_antigens = ["Lea", "JsB", "Jka", "FyB", "M", "K"]















# Initialize app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Antigen Analyse Dashboard"

# Load default data
data = pd.read_csv("data.csv")

# Setup options
LISS_VALUES = ["-", "+/-", "1+", "2+", "3+", "4+"]
ANTIGEN_COLUMNS = [col for col in data.columns if col not in ["Sp.Nr.", "spendernummer", "Spender", "Spez. Antigen", "Gen.", "LISS"]]





# Update the navigation module with ANTIGEN_COLUMNS
import navigation_and_step4
navigation_and_step4.ANTIGEN_COLUMNS = ANTIGEN_COLUMNS

# Color codes for analysis status
STATUS_COLORS = {
    "Bestätigt (3x +)": "#2d6a4f",
    "Bestätigt (2x +)": "#b7e4c7",
    "Nicht ausgeschlossen": "#ffd166",
    "Keine Reaktion": "#e9ecef",
    "Ausgestrichen": "#e63946"
}

# --- Utility functions ---
# 2. Update prepare_data function to rename column
def prepare_data(df):
    """Prepare and clean the dataframe"""
    df = df.copy()
    
    # Rename spendernummer to Sp.Nr. if it exists
    if "spendernummer" in df.columns:
        df = df.rename(columns={"spendernummer": "Sp.Nr."})
    
    if "Spez. Antigen" in df.columns:
        spez_antigen = df["Spez. Antigen"]
        df = df.drop(columns=["Spez. Antigen"])
        df["Spez. Antigen"] = spez_antigen
    
    if "Gen." in df.columns:
        df = df.drop(columns=["Gen."])
    
    if "LISS" in df.columns:
        df["LISS"] = df["LISS"].apply(lambda x: x if str(x).strip() in LISS_VALUES else "-")
    
    if "Index" not in df.columns and "LISS" in df.columns:
        df.insert(df.columns.get_loc("LISS") + 1, "Index", range(1, len(df)+1))
    
    return df

def analyze_data(df, manual_mode=False):
    """Analyze the data to determine antigen status"""
    if manual_mode:
        status_map = {}
        exclusion_reasons = {}
        system_excluded = set()
        
        for ag in ANTIGEN_COLUMNS:
            if ag in ["Sp.Nr.", "spendernummer"]:  # Skip both variations
                continue
            status_map[ag] = "Nicht ausgeschlossen"
        
        return status_map, exclusion_reasons, system_excluded
    
    # Automatic mode
    exclusion_pairs = [("C", "c"), ("E", "e"), ("K", "k"), ("KpA", "KpB"),
                      ("JsA", "JsB"), ("FyA", "FyB"), ("Jka", "Jkb"),
                      ("Lea", "Leb"), ("M", "N"), ("S", "s"), ("LuA", "LuB")]
    allowed_hetero = ["CW", "K", "KpA", "LuA"]
    
    def zygosity(val1, val2):
        if val1 == "+" and val2 == "+": return "hetero"
        if val1 == "+" or val2 == "+": return "homo"
        return "negativ"
    
    exclusion_tracking = {col: [] for col in ANTIGEN_COLUMNS}
    negatives = df[df["LISS"] == "-"].drop(columns=["Spender", "Index", "Spez. Antigen", "LISS"], errors='ignore')
    
    spendernummer_map = {}
    if "Spendernummer" in df.columns:
        for idx, row in df.iterrows():
            spendernummer_map[idx] = row.get("Spendernummer", idx + 1)
    
    system_excluded = set()
    for idx, row in negatives.iterrows():
        temp_excl = []
        for a in [col for col in negatives.columns if col in ANTIGEN_COLUMNS]:
            if row.get(a) == "+":
                temp_excl.append(a)
                exclusion_tracking[a].append(idx + 1)
        
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
    
    status_map = {}
    exclusion_reasons = {}
    
    for ag in ANTIGEN_COLUMNS:
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

# --- Build table components ---
def build_liss_table(df):
    """Build the data table for LISS selection in Step 1"""
    df = prepare_data(df)
    
    # Don't drop Sp.Nr. column anymore
    
    columns = []
    for col in df.columns:
        col_def = {
            "name": col,
            "id": col,
            # Only LISS and Spez. Antigen are editable, Sp.Nr. is NOT
            "editable": col == "LISS" or col == "Spez. Antigen"
        }
        
        if col == "LISS":
            col_def["presentation"] = "dropdown"
            col_def["type"] = "text"
        
        columns.append(col_def)
    
    dropdown_dict = {
        "LISS": {
            "options": [{"label": val, "value": val} for val in LISS_VALUES],
            "clearable": False
        }
    }
    
    style_cell_conditional = [
        {"if": {"column_id": "Index"}, "width": "60px", "textAlign": "center"},
        {"if": {"column_id": "LISS"}, "width": "80px", "textAlign": "center"},
        {"if": {"column_id": "Spender"}, "width": "120px", "textAlign": "left"},
        {"if": {"column_id": "Spez. Antigen"}, "width": "150px", "textAlign": "left"},
    ]
    
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
        style_table={"maxWidth": "1100px", "margin": "0", "overflowX": "auto"},
        style_cell={"textAlign": "center", "height": "35px"},
        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
        style_cell_conditional=style_cell_conditional,
        page_size=15
    )

def build_analysis_table(df, status_map, exclusion_reasons, system_excluded):
    df = prepare_data(df)
    styles = []
    all_columns = list(df.columns)

    header_checkboxes = html.Div(
        id="checkbox-container",
        style={
            "display": "flex",
            "flexDirection": "row",
            "alignItems": "center",
            "marginBottom": "10px",
            "overflowX": "auto",
            "whiteSpace": "nowrap",
            "paddingLeft": "0"
        },
        children=[]
    )

    for ag in ANTIGEN_COLUMNS:
        if ag in all_columns:
            status = status_map.get(ag, "")
            is_excluded = ag in system_excluded
            background_color = STATUS_COLORS.get(status, "#ffffff")

            styles.append({
                "if": {"column_id": ag},
                "backgroundColor": background_color,
                "color": "#000000" if status != "Ausgestrichen" else "#ffffff"
            })

            display_label = format_antigen(ag)

            if ag in ["Sp.Nr.", "spendernummer"]:
                header_checkboxes.children.append(
                    html.Div([
                        html.Div(ag, style={"fontSize": "11px", "textAlign": "center", "marginBottom": "2px"}),
                        html.Div(style={"height": "18px"})
                    ], style={"width": "40px", "display": "inline-block", "textAlign": "center"})
                )
                continue

            header_checkboxes.children.append(
                html.Div([
                    html.Div(display_label, style={"fontSize": "11px", "textAlign": "center", "marginBottom": "2px"}),
                    dcc.Checklist(
                        id={"type": "column-select", "index": ag},
                        options=[{"label": "", "value": ag}],
                        value=[ag] if (ag not in system_excluded) else [],
                        className="column-checkbox",
                        style={"pointerEvents": "auto"}
                    )
                ], style={
                    "width": "40px",
                    "display": "inline-block",
                    "textAlign": "center",
                    "opacity": "0.5" if is_excluded else "1"
                })
            )

    antigen_selector = html.Div([
        dcc.Checklist(
            id="antigen-select-checkboxes",
            options=[{"label": format_antigen(ag), "value": ag} for ag in ANTIGEN_COLUMNS if ag != "spendernummer"],
            value=[ag for ag in ANTIGEN_COLUMNS if ag not in system_excluded and ag != "spendernummer"],
            style={"display": "none"}
        )
    ])

    columns = [
        {"name": format_antigen(col) if col in ANTIGEN_COLUMNS else col, "id": col, "editable": False}
        for col in df.columns
    ]

    style_cell_conditional = [
        {"if": {"column_id": "Spendernummer"}, "width": "60px", "textAlign": "center"},
        {"if": {"column_id": "Index"}, "width": "40px", "textAlign": "center"},
        {"if": {"column_id": "LISS"}, "width": "50px", "textAlign": "center"},
        {"if": {"column_id": "Spender"}, "width": "80px", "textAlign": "left"},
        {"if": {"column_id": "Spez. Antigen"}, "width": "100px", "textAlign": "left"},
    ] + [{
        "if": {"column_id": col},
        "minWidth": "40px", "width": "40px", "maxWidth": "40px", "textAlign": "center"
    } for col in ANTIGEN_COLUMNS]

    return html.Div([
        antigen_selector,
        header_checkboxes,
        dash_table.DataTable(
            id="analysis-table",
            columns=columns,
            data=df.to_dict("records"),
            editable=False,
            style_table={"maxWidth": "1100px", "margin": "0", "overflowX": "auto"},
            style_cell={"textAlign": "center", "height": "35px"},
            style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
            style_cell_conditional=style_cell_conditional,
            style_data_conditional=styles,
            page_size=15
        )
    ])

def build_final_table(df, included_columns, user_selections=None):
    display_columns = ['Index']
    if "Sp.Nr." in df.columns:
        display_columns.append('Sp.Nr.')
    elif "spendernummer" in df.columns:
        display_columns.append('spendernummer')
    display_columns.extend(['Spender', 'LISS'])
    display_columns.extend(included_columns)
    display_df = df[display_columns].copy()

    columns = [
        {"name": format_antigen(col) if col in ANTIGEN_COLUMNS else col, "id": col, "editable": False}
        for col in display_df.columns
    ]

    style_cell_conditional = [
        {"if": {"column_id": "Sp.Nr."}, "width": "60px", "textAlign": "center"},
        {"if": {"column_id": "spendernummer"}, "width": "60px", "textAlign": "center"},
        {"if": {"column_id": "Index"}, "width": "60px", "textAlign": "center"},
        {"if": {"column_id": "Spendernummer"}, "width": "80px", "textAlign": "center"},
        {"if": {"column_id": "LISS"}, "width": "80px", "textAlign": "center"},
        {"if": {"column_id": "Spender"}, "width": "120px", "textAlign": "left"},
    ] + [{
        "if": {"column_id": col},
        "minWidth": "40px", "width": "40px", "maxWidth": "40px", "textAlign": "center"
    } for col in included_columns]

    style_data_conditional = []
    if user_selections:
        user_included = set(user_selections)
        system_included = set(included_columns)
        differences = user_included.symmetric_difference(system_included)
        for col in differences:
            if col in display_df.columns:
                style_data_conditional.append({
                    "if": {"column_id": col},
                    "backgroundColor": "#FFEB3B",
                    "border": "2px solid #FFC107"
                })

    return dash_table.DataTable(
        id="final-table",
        columns=columns,
        data=display_df.to_dict("records"),
        editable=False,
        style_table={"maxWidth": "1100px", "margin": "0", "overflowX": "auto"},
        style_cell={"textAlign": "center", "height": "35px"},
        style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
        style_cell_conditional=style_cell_conditional,
        style_data_conditional=style_data_conditional,
        page_size=15
    )

# --- Layout functions ---
def get_landing_page():
    return html.Div([
        html.H2("Willkommen beim Antigen Analyse Dashboard", className="welcome-title"),
        html.P("Dieses Tool hilft Ihnen bei der Analyse von Antigen-Tests in fünf einfachen Schritten:"),
        
        html.Div([
            html.Div([
                html.Div("0", className="step-number active"),
                html.H3("PDF & Datenbank"),
                html.P("PDF-Daten importieren oder vorherige Analyse aus der Datenbank laden.")
            ], className="welcome-step"),
            
            html.Div([
                html.Div("1", className="step-number"),
                html.H3("LISS-Werte auswählen"),
                html.P("LISS-Werte für jede Probe auswählen.")
            ], className="welcome-step"),
            
            html.Div([
                html.Div("2", className="step-number"),
                html.H3("Analyse prüfen"),
                html.P("Automatische Analyse überprüfen und relevante Antigene auswählen.")
            ], className="welcome-step"),
        ], className="welcome-steps"),
        
        html.Div([
            html.Div([
                html.Div("3", className="step-number"),
                html.H3("Finales Ergebnis"),
                html.P("Gefilterte Tabelle mit ausgewählten Antigenen ansehen.")
            ], className="welcome-step"),
            
            html.Div([
                html.Div("4", className="step-number"),
                html.H3("Berichtserstellung"),
                html.P("Medizinische und labortechnische Berichte erstellen.")
            ], className="welcome-step"),
        ], className="welcome-steps", style={"marginTop": "20px"}),
        
        html.Div([
            html.Button("Neue Analyse starten", id="start-analysis-button", 
                       className="action-button primary"),
        ], style={"marginTop": "30px", "display": "flex", "justifyContent": "center"}),
    ], id="landing-page", className="welcome-container")

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
        
        html.Div(id="step1-table-container", children=[build_liss_table(df)]),
        
        html.Div([
            html.Button("LISS-Werte bestätigen", id="step1-next-button", 
                       className="action-button primary"),
        ], style={"marginTop": "20px", "display": "flex", "justifyContent": "center"}),
    ], id="step1-content")

def get_step2_layout(df, status_map, exclusion_reasons, system_excluded, manual_mode=False):
    """Enhanced Step 2 layout with exclusion summary and provisional report"""
    legend_items = []
    for status, color in STATUS_COLORS.items():
        legend_items.append(
            html.Div([
                html.Div(style={"backgroundColor": color, "width": "20px", "height": "20px", "border": "1px solid #ccc"}),
                html.Span(status)
            ], style={"display": "flex", "alignItems": "center", "gap": "8px", "marginRight": "20px"})
        )
    
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
    
    antigen_selection_component = html.Div([
        html.H4("Antigene auswählen:", className="section-title"),
        html.P("Wählen Sie die Antigene aus, die im finalen Ergebnis angezeigt werden sollen:"),
        html.Div([
            html.Button("Alle auswählen", id="select-all-button", className="selection-button"),
            html.Button("Alle abwählen", id="deselect-all-button", className="selection-button"),
            html.Button("Standard-Auswahl", id="default-selection-button", className="selection-button"),
        ], className="selection-buttons")
    ], className="antigen-selection-controls")
    
    default_selected = [ag for ag in ANTIGEN_COLUMNS if ag not in system_excluded and ag != "spendernummer"]
    
    return html.Div([
        html.H3("Schritt 2: Analyse prüfen und Antigene auswählen", className="step-title"),
        
        html.Div([
            html.P(f"Modus: {'Manuelle Auswertung' if manual_mode else 'Automatische Auswertung'}", 
                   style={"fontWeight": "bold", "color": "#7209b7" if manual_mode else "#2e8bc0"})
        ]),
        
        html.Div([
            html.H4("Farbliche Legende:", className="section-title"),
            html.Div(legend_items, className="legend-container")
        ], className="legend-section"),
        
        create_exclusion_summary(exclusion_reasons, system_excluded),
        
        html.Div([
            html.H4(["Antigen-Analyse Übersicht und Auswahl:", analysis_tooltip], 
                   className="section-title with-tooltip"),
            html.P("Die Tabelle zeigt die Analyseergebnisse für alle Antigene."),
            antigen_selection_component
        ]),
        
        html.Div(id="analysis-table-container", className="analysis-table-container", 
                children=[build_analysis_table(df, status_map, exclusion_reasons, system_excluded)]),
        
        html.Div([
            html.H4("Ausgewählte Antigene:", className="section-title"),
            html.Div(id="selected-antigens-display", className="selected-antigens-list")
        ], className="selected-antigens-section"),
        
        create_provisional_report(status_map, default_selected),
        
        html.Div([
            html.Button("Zurück zu Schritt 1", id="step2-back-button", 
                       className="action-button secondary", style={"marginRight": "10px"}),
            html.Button("Antigene bestätigen", id="step2-next-button", 
                       className="action-button primary")
        ], style={"marginTop": "20px", "display": "flex", "justifyContent": "center"}),
    ], id="step2-content")

def get_step3_layout(df, included_columns, excluded_columns, user_selections=None, lot_number=""):
    """Build step 3 layout with lot number display"""
    if included_columns is None:
        included_columns = []
    if excluded_columns is None:
        excluded_columns = []
    if user_selections is None:
        user_selections = []
    
    included_columns = list(included_columns) if isinstance(included_columns, (list, set, tuple)) else []
    excluded_columns = list(excluded_columns) if isinstance(excluded_columns, (list, set, tuple)) else []
    user_selections = list(user_selections) if isinstance(user_selections, (list, set, tuple)) else []
    
    differences = []
    if user_selections:
        user_included = set(user_selections)
        system_included = set(included_columns)
        differences = list(user_included.symmetric_difference(system_included))
    
    try:
        included_str = ", ".join(sorted(included_columns)) if included_columns else "Keine"
        user_str = ", ".join(sorted(user_selections)) if user_selections else "Keine"
        diff_str = ", ".join(sorted(differences)) if differences else "Keine"
    except Exception:
        included_str = "Keine"
        user_str = "Keine"
        diff_str = "Keine"
    
    return html.Div([
        html.H3("Schritt 3: Finalisierte Tabelle", className="step-title"),
        
        html.Div([
            html.P(f"Lot-Nummer: {lot_number if lot_number else 'Nicht angegeben'}", 
                   style={"fontWeight": "bold", "marginBottom": "15px"})
        ]),
        
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
                        build_final_table(df, user_selections)
                    ])
                ])
            ], className="custom-tab", selected_className="custom-tab-selected"),
            
            dcc.Tab(label="Vergleich", children=[
                html.Div([
                    html.H4("Vergleich System- und Benutzerauswahl:", className="section-title"),
                    html.Div([
                        html.P("System-Auswahl: " + included_str),
                        html.P("Benutzer-Auswahl: " + user_str),
                        html.P("Unterschiede: " + diff_str)
                    ], className="comparison-info"),
                    html.Div(id="comparison-table-container", children=[
                        build_final_table(df, list(set(included_columns + user_selections)), user_selections)
                    ])
                ])
            ], className="custom-tab", selected_className="custom-tab-selected"),
        ], id="result-tabs", className="custom-tabs"),
        
        html.Div([
            html.H4("Ausgeschlossene Antigene:", className="section-title"),
            html.Div(", ".join(sorted(excluded_columns)) if excluded_columns else "Keine", 
                    className="excluded-antigens-list")
        ], className="excluded-antigens-section"),
        
        html.Div([
            html.Button("Zurück zu Schritt 2", id="step3-back-button", 
                       className="action-button secondary", style={"marginRight": "10px"}),
            html.Button("Weiter zu Berichtserstellung", id="step3-next-button",
                       className="action-button primary")
        ], style={"marginTop": "20px", "display": "flex", "justifyContent": "center"}),
    ], id="step3-content")

# --- Main App Layout ---
app.layout = html.Div([
    html.Div(id="header-container", children=[
        get_header_with_navigation(current_step=-1)
    ]),
    
    html.Div(id="main-content", children=[
        get_landing_page()
    ], className="main-content"),
    
    # Store components
    dcc.Store(id='current-step', data=-1),
    dcc.Store(id='step-states', data={0: True, 1: False, 2: False, 3: False, 4: False}),
    dcc.Store(id='analyzed-data'),
    dcc.Store(id='status-map'),
    dcc.Store(id='exclusion-reasons'),
    dcc.Store(id='system-excluded'),
    dcc.Store(id='selected-antigens'),
    dcc.Store(id='user-selections'),
    dcc.Store(id='lot-number'),
    dcc.Store(id='evaluation-mode-store', data='auto'),
    dcc.Store(id='pdf-data'),
    dcc.Store(id='pdf-confidence', data=0), 
    dcc.Store(id='db-analysis-id'),
    
    html.Div(id="dummy-div", style={"display": "none"}),
    html.Div(id="dummy-output", style={"display": "none"})
], className="dashboard-container")

# --- Callbacks ---

# Navigation callback - Handle step navigation clicks
@app.callback(
    [Output('main-content', 'children'),
     Output('header-container', 'children'),
     Output('current-step', 'data')],
    [Input({'type': 'step-nav', 'index': ALL}, 'n_clicks')],
    [State('current-step', 'data'),
     State('step-states', 'data'),
     State('analyzed-data', 'data'),
     State('status-map', 'data'),
     State('exclusion-reasons', 'data'),
     State('system-excluded', 'data'),
     State('user-selections', 'data'),
     State('lot-number', 'data'),
     State('evaluation-mode-store', 'data')],
    prevent_initial_call=True
)

def handle_step_navigation(n_clicks_list, current_step, step_states, analyzed_data, 
                          status_map, exclusion_reasons, system_excluded, 
                          user_selections, lot_number, eval_mode):
    ctx = callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    
    # Find which button was clicked
    button_id = None
    for i, clicks in enumerate(n_clicks_list):
        if clicks:
            prop_id = ctx.triggered[0]['prop_id']
            if f'"index":{i}' in prop_id:
                button_id = i
                break
    
    if button_id is None:
        raise dash.exceptions.PreventUpdate
    
    step_num = button_id
    
    # Check if step is accessible
    if not step_states.get(step_num, False):
        raise dash.exceptions.PreventUpdate
    
    # Navigate to requested step
    if step_num == 0:
        db_session = next(get_db())
        return [get_step0_layout(db_session), get_header_with_navigation(0, step_states), 0]
    elif step_num == 1:
        df = pd.DataFrame(analyzed_data) if analyzed_data else data
        return [get_step1_layout(df), get_header_with_navigation(1, step_states), 1]
    elif step_num == 2:
        df = pd.DataFrame(analyzed_data)
        return [get_step2_layout(df, status_map, exclusion_reasons, set(system_excluded), eval_mode == 'manual'),
                get_header_with_navigation(2, step_states), 2]
    elif step_num == 3:
        df = pd.DataFrame(analyzed_data)
        included = [ag for ag in ANTIGEN_COLUMNS if ag not in system_excluded]
        excluded = system_excluded
        return [get_step3_layout(df, included, excluded, user_selections, lot_number),
                get_header_with_navigation(3, step_states), 3]
    elif step_num == 4:
        df = pd.DataFrame(analyzed_data)
        return [get_step4_layout(df, status_map, exclusion_reasons, user_selections, lot_number),
                get_header_with_navigation(4, step_states), 4]
    
    raise dash.exceptions.PreventUpdate

# Replace the incorrect callback section starting at line ~735 with:

# Quick jump callback
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True)],
    [Input('quick-jump-step2', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('status-map', 'data'),
     State('exclusion-reasons', 'data'),
     State('system-excluded', 'data'),
     State('evaluation-mode-store', 'data'),
     State('step-states', 'data')],
    prevent_initial_call=True
)
def quick_jump_to_step2(n_clicks, analyzed_data, status_map, exclusion_reasons, 
                        system_excluded, eval_mode, step_states):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    df = pd.DataFrame(analyzed_data)
    system_excluded = set(system_excluded)
    
    step2_layout = get_step2_layout(df, status_map, exclusion_reasons, 
                                   system_excluded, eval_mode == 'manual')
    
    return [step2_layout, get_header_with_navigation(2, step_states), 2]

# Start analysis from landing page
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True),
     Output('step-states', 'data', allow_duplicate=True)],
    [Input('start-analysis-button', 'n_clicks')],
    prevent_initial_call=True
)
def start_analysis(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    step_states = {0: True, 1: True, 2: False, 3: False, 4: False}
    return [get_step0_layout(), get_header_with_navigation(0, step_states), 0, step_states]

@app.callback(
    [Output('pdf-comparison-area', 'children'),
     Output('pdf-parse-status', 'children'),
     Output('pdf-data', 'data'),
     Output('step0-confirm-button', 'disabled'),
     Output('pdf-confidence', 'data')],
    [Input('pdf-upload', 'contents')],
    [State('pdf-upload', 'filename'),
     State('analyzed-data', 'data')],
    prevent_initial_call=True
)
def handle_file_upload(contents, filename, current_data):
    if not contents:
        raise dash.exceptions.PreventUpdate
    
    # Parse file with confidence scoring
    parsed_df, confidence, error_msg = parse_file_content(contents, filename)
    
    if error_msg:
        return [
            None,
            html.Div(error_msg, style={"color": "red"}),
            None,
            True,
            0
        ]
    
    current_df = pd.DataFrame(current_data) if current_data else data
    
    # Use editable view if confidence < 0.95
    if confidence < 0.95:
        comparison = build_editable_diff_table(parsed_df, current_df, confidence)
    else:
        comparison = build_diff_table(parsed_df, current_df)
    
    status_msg = html.Div([
        html.Span(f"✓ {filename} erfolgreich geladen", style={"color": "green"}),
        html.Span(f" (Genauigkeit: {confidence:.1%})", 
                 style={"marginLeft": "10px", "color": "#666"})
    ])
    
    return [
        comparison,
        status_msg,
        parsed_df.to_dict('records'),
        False,
        confidence
    ]

# Step 0 - Database loading
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('analyzed-data', 'data', allow_duplicate=True),
     Output('status-map', 'data', allow_duplicate=True),
     Output('exclusion-reasons', 'data', allow_duplicate=True),
     Output('system-excluded', 'data', allow_duplicate=True),
     Output('user-selections', 'data', allow_duplicate=True),
     Output('lot-number', 'data', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True),
     Output('step-states', 'data', allow_duplicate=True)],
    [Input('open-from-db-button', 'n_clicks')],
    [State('db-analysis-dropdown', 'value')],
    prevent_initial_call=True
)
def load_from_database(n_clicks, analysis_id):
    if not n_clicks or not analysis_id:
        raise dash.exceptions.PreventUpdate
    
    db = next(get_db())
    analysis = db.query(Analysis).filter_by(id=analysis_id).first()
    
    if not analysis:
        raise dash.exceptions.PreventUpdate
    
    liss_data = analysis.get_liss_data()
    status_data = analysis.get_status_data()
    user_sel = analysis.get_user_selections()
    
    df = pd.DataFrame(liss_data)
    
    step_states = {0: True, 1: True, 2: True, 3: False, 4: False}
    
    included = [ag for ag in ANTIGEN_COLUMNS if ag not in status_data.get('system_excluded', [])]
    excluded = status_data.get('system_excluded', [])
    
    return [
        get_step3_layout(df, included, excluded, user_sel, analysis.lot_number),
        liss_data,
        status_data.get('status_map', {}),
        status_data.get('exclusion_reasons', {}),
        status_data.get('system_excluded', []),
        user_sel,
        analysis.lot_number,
        3,
        step_states
    ]

# Step 0 - Confirm and proceed
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True),
     Output('analyzed-data', 'data', allow_duplicate=True),
     Output('lot-number', 'data', allow_duplicate=True),
     Output('step-states', 'data', allow_duplicate=True)],
    [Input('step0-confirm-button', 'n_clicks'),
     Input('step0-manual-button', 'n_clicks')],
    [State('pdf-data', 'data'),
     State('lot-number-input', 'value')],
    prevent_initial_call=True
)
def proceed_from_step0(confirm_clicks, manual_clicks, pdf_data, lot_num):
    ctx = callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'step0-confirm-button' and pdf_data:
        df = pd.DataFrame(pdf_data)
    else:
        df = data
    
    step_states = {0: True, 1: True, 2: True, 3: True, 4: False}
    
    return [
        get_step1_layout(df),
        get_header_with_navigation(1, step_states),
        1,
        df.to_dict('records'),
        lot_num,
        step_states
    ]

# Step 0 - Evaluation mode toggle
@app.callback(
    Output('evaluation-mode-store', 'data'),
    [Input('evaluation-mode', 'value')],
    prevent_initial_call=True
)
def update_evaluation_mode(mode):
    return mode

# Step 1 -> Step 2
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True),
     Output('analyzed-data', 'data', allow_duplicate=True),
     Output('status-map', 'data', allow_duplicate=True),
     Output('exclusion-reasons', 'data', allow_duplicate=True),
     Output('system-excluded', 'data', allow_duplicate=True),
     Output('selected-antigens', 'data', allow_duplicate=True),
     Output('user-selections', 'data', allow_duplicate=True),
     Output('step-states', 'data', allow_duplicate=True)],
    [Input('step1-next-button', 'n_clicks')],
    [State('data-table', 'data'),
     State('current-step', 'data'),
     State('evaluation-mode-store', 'data'),
     State('step-states', 'data')],
    prevent_initial_call=True
)
def go_to_step2(n_clicks, table_data, current_step, eval_mode, step_states):
    # Only continue after the user presses “LISS-Werte bestätigen”
    if not n_clicks or current_step != 1:
        raise dash.exceptions.PreventUpdate
    # -----------------------------------------------------------------
    df = pd.DataFrame(table_data)
    
    # Handle both old and new column names
    if "spendernummer" not in df.columns and "Sp.Nr." not in df.columns:
        if "spendernummer" in data.columns:
            df.insert(0, "Sp.Nr.", data["spendernummer"].values)
        elif "Sp.Nr." in data.columns:
            df.insert(0, "Sp.Nr.", data["Sp.Nr."].values)
    
    status_map, exclusion_reasons, system_excluded = analyze_data(df, eval_mode == 'manual')
    
    selected_antigens = [ag for ag in ANTIGEN_COLUMNS if ag not in system_excluded]
    user_selections = selected_antigens.copy()
    
    step_states[2] = True
    step_states[3] = True
    
    step2_layout = get_step2_layout(df, status_map, exclusion_reasons, system_excluded, eval_mode == 'manual')
    
    return [
        step2_layout,
        get_header_with_navigation(2, step_states),
        2,
        df.to_dict('records'),
        status_map,
        exclusion_reasons,
        list(system_excluded),
        selected_antigens,
        user_selections,
        step_states
    ]

# Step 2 -> Step 1 (Back)
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True)],
    [Input('step2-back-button', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('current-step', 'data'),
     State('step-states', 'data')],
    prevent_initial_call=True
)
def go_back_to_step1(n_clicks, analyzed_data, current_step, step_states):
    if not n_clicks or current_step != 2:
        raise dash.exceptions.PreventUpdate
    
    df = pd.DataFrame(analyzed_data)
    return [get_step1_layout(df), get_header_with_navigation(1, step_states), 1]

# Update selected antigens display
@app.callback(
    Output('selected-antigens-display', 'children'),
    [Input('user-selections', 'data')]
)
def update_selected_antigens_display(selected_antigens):
    if not selected_antigens:
        return "Keine Antigene ausgewählt"
    
    try:
        if isinstance(selected_antigens, list):
            return ", ".join(sorted(selected_antigens))
        else:
            return "Keine Antigene ausgewählt"
    except Exception:
        return "Keine Antigene ausgewählt"

# Checkbox synchronization
@app.callback(
    Output('antigen-select-checkboxes', 'value'),
    [Input({'type': 'column-select', 'index': ALL}, 'value')],
    [State('system-excluded', 'data')],
    prevent_initial_call=True
)
def update_main_checklist_from_column_checkboxes(checkbox_values, system_excluded):
    system_excluded = system_excluded or []
    selected_antigens = []
    for values in checkbox_values:
        if values and isinstance(values, list) and len(values) > 0:
            selected_antigens.extend(values)
    
    # Filter out Sp.Nr. and spendernummer
    return [ag for ag in selected_antigens if ag not in ['Sp.Nr.', 'spendernummer']]

@app.callback(
    Output('user-selections', 'data', allow_duplicate=True),
    [Input('antigen-select-checkboxes', 'value')],
    [State('current-step', 'data')],
    prevent_initial_call=True
)
def update_user_selections_from_main_checklist(selected_values, current_step):
    if current_step != 2:
        raise dash.exceptions.PreventUpdate
    if selected_values is None:
        selected_values = []
    return selected_values

# Selection buttons
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
    
    # Select all antigens from status_map, excluding Sp.Nr.
    all_antigens = []
    for ag in status_map.keys():
        if ag not in ["Sp.Nr.", "spendernummer"]:
            all_antigens.append(ag)
    
    return all_antigens

# Deselect all antigens button
@app.callback(
    Output('user-selections', 'data', allow_duplicate=True),
    [Input('deselect-all-button', 'n_clicks')],
    prevent_initial_call=True
)
def deselect_all_antigens(n_clicks):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    # Return empty list to deselect all
    return []

@app.callback(
    Output('user-selections', 'data', allow_duplicate=True),
    [Input('default-selection-button', 'n_clicks')],
    [State('selected-antigens', 'data')],
    prevent_initial_call=True
)
def default_selection(n_clicks, system_selection):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    # Filter out Sp.Nr. from system selection
    filtered_selection = []
    if system_selection:
        for ag in system_selection:
            if ag not in ["Sp.Nr.", "spendernummer"]:
                filtered_selection.append(ag)
    
    return filtered_selection



# Step 2 -> Step 3
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True),
     Output('step-states', 'data', allow_duplicate=True)],
    [Input('step2-next-button', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('selected-antigens', 'data'),
     State('user-selections', 'data'),
     State('current-step', 'data'),
     State('lot-number', 'data'),
     State('step-states', 'data')],
    prevent_initial_call=True
)

def go_to_step3(n_clicks, analyzed_data, selected_antigens, user_selections, current_step, lot_number, step_states):
    # Only proceed if the button was clicked and we are on the correct step
    if not n_clicks or current_step != 2:
        raise dash.exceptions.PreventUpdate

    # Validate input data
    if not analyzed_data or not isinstance(analyzed_data, list):
        raise ValueError("Analyzed data must be a non-empty list of dictionaries.")
    
    df = pd.DataFrame(analyzed_data)

    # Use only selected antigens, if any
    included_columns = selected_antigens if selected_antigens else []
    
    # ANTIGEN_COLUMNS must be defined somewhere globally in your app
    if 'ANTIGEN_COLUMNS' not in globals():
        raise NameError("ANTIGEN_COLUMNS is not defined.")
    
    excluded_columns = [ag for ag in ANTIGEN_COLUMNS if ag not in included_columns]

    # Update step states for navigation
    step_states[3] = True
    step_states[4] = True

    # Generate the layout for step 3
    step3_layout = get_step3_layout(df, included_columns, excluded_columns, user_selections, lot_number)

    # Return the layout, navigation header, new current step, and updated step states
    return [step3_layout, get_header_with_navigation(3, step_states), 3, step_states]


# Step 3 -> Step 2 (Back)
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True)],
    [Input('step3-back-button', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('status-map', 'data'),
     State('exclusion-reasons', 'data'),
     State('system-excluded', 'data'),
     State('current-step', 'data'),
     State('evaluation-mode-store', 'data'),
     State('step-states', 'data')],
    prevent_initial_call=True
)
def go_back_to_step2(n_clicks, analyzed_data, status_map, exclusion_reasons, 
                     system_excluded, current_step, eval_mode, step_states):
    if not n_clicks or current_step != 3:
        raise dash.exceptions.PreventUpdate
    
    df = pd.DataFrame(analyzed_data)
    system_excluded = set(system_excluded)
    
    step2_layout = get_step2_layout(df, status_map, exclusion_reasons, 
                                   system_excluded, eval_mode == 'manual')
    
    return [step2_layout, get_header_with_navigation(2, step_states), 2]

# Step 3 -> Step 4
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True)],
    [Input('step3-next-button', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('status-map', 'data'),
     State('exclusion-reasons', 'data'),
     State('user-selections', 'data'),
     State('lot-number', 'data'),
     State('current-step', 'data'),
     State('step-states', 'data')],
    prevent_initial_call=True
)
def go_to_step4(n_clicks, analyzed_data, status_map, exclusion_reasons, 
                user_selections, lot_number, current_step, step_states):
    if not n_clicks or current_step != 3:
        raise dash.exceptions.PreventUpdate
    
    df = pd.DataFrame(analyzed_data)
    step4_layout = get_step4_layout(df, status_map, exclusion_reasons, 
                                   user_selections, lot_number)
    
    return [step4_layout, get_header_with_navigation(4, step_states), 4]

# Step 4 - Generate PDF
@app.callback(
    Output('download-report-pdf', 'data'),
    [Input('generate-report-pdf-button', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('status-map', 'data'),
     State('exclusion-reasons', 'data'),
     State('user-selections', 'data'),
     State('lot-number', 'data')],
    prevent_initial_call=True
)
def download_pdf_report(n_clicks, analyzed_data, status_map, exclusion_reasons, 
                       user_selections, lot_number):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    df = pd.DataFrame(analyzed_data)
    pdf_bytes = generate_pdf_report(df, status_map, exclusion_reasons, 
                                   user_selections, lot_number)
    
    filename = f"antigen_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    return dcc.send_bytes(pdf_bytes, filename)

# Step 4 - Save to database
@app.callback(
    Output('dummy-output', 'children', allow_duplicate=True),
    [Input('save-to-db-button', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('status-map', 'data'),
     State('exclusion-reasons', 'data'),
     State('system-excluded', 'data'),
     State('user-selections', 'data'),
     State('lot-number', 'data')],
    prevent_initial_call=True
)
def save_to_database(n_clicks, analyzed_data, status_map, exclusion_reasons,
                    system_excluded, user_selections, lot_number):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    
    db = next(get_db())
    
    df = pd.DataFrame(analyzed_data)
    
    # Handle both column names
    spendernummer = None
    if 'Sp.Nr.' in df.columns:
        spendernummer = df['Sp.Nr.'].iloc[0]
    elif 'spendernummer' in df.columns:
        spendernummer = df['spendernummer'].iloc[0]
    
    if not spendernummer:
        spendernummer = 'Unknown'
    
    donor = db.query(Donor).filter_by(spendernummer=spendernummer).first()
    if not donor:
        donor = Donor(spendernummer=spendernummer)
        db.add(donor)
    
    analysis = Analysis(
        spendernummer=spendernummer,
        lot_number=lot_number  # Now properly saved with lot number
    )
    
    analysis.set_liss_data(analyzed_data)
    analysis.set_status_data({
        'status_map': status_map,
        'exclusion_reasons': exclusion_reasons,
        'system_excluded': system_excluded
    })
    analysis.set_user_selections(user_selections)
    
    db.add(analysis)
    db.commit()
    
    return "Saved to database"

# Step 4 -> Step 3 (Back)
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True)],
    [Input('step4-back-button', 'n_clicks')],
    [State('analyzed-data', 'data'),
     State('selected-antigens', 'data'),
     State('system-excluded', 'data'),
     State('user-selections', 'data'),
     State('lot-number', 'data'),
     State('current-step', 'data'),
     State('step-states', 'data')],
    prevent_initial_call=True
)
def go_back_to_step3(n_clicks, analyzed_data, selected_antigens, system_excluded,
                     user_selections, lot_number, current_step, step_states):
    if not n_clicks or current_step != 4:
        raise dash.exceptions.PreventUpdate
    
    df = pd.DataFrame(analyzed_data)
    included = [ag for ag in ANTIGEN_COLUMNS if ag not in system_excluded]
    excluded = system_excluded
    
    step3_layout = get_step3_layout(df, included, excluded, user_selections, lot_number)
    
    return [step3_layout, get_header_with_navigation(3, step_states), 3]

# Restart from Step 4
@app.callback(
    [Output('main-content', 'children', allow_duplicate=True),
     Output('header-container', 'children', allow_duplicate=True),
     Output('current-step', 'data', allow_duplicate=True),
     Output('analyzed-data', 'data', allow_duplicate=True),
     Output('status-map', 'data', allow_duplicate=True),
     Output('exclusion-reasons', 'data', allow_duplicate=True),
     Output('system-excluded', 'data', allow_duplicate=True),
     Output('selected-antigens', 'data', allow_duplicate=True),
     Output('user-selections', 'data', allow_duplicate=True),
     Output('lot-number', 'data', allow_duplicate=True),
     Output('step-states', 'data', allow_duplicate=True)],
    [Input('step4-restart-button', 'n_clicks')],
    [State('current-step', 'data')],
    prevent_initial_call=True
)
def restart_analysis_from_step4(n_clicks, current_step):
    if not n_clicks or current_step != 4:
        raise dash.exceptions.PreventUpdate
    
    step_states = {0: True, 1: True, 2: True, 3: True, 4: True}
    
    return [
        get_landing_page(),
        get_header_with_navigation(-1, step_states),
        -1,
        None, None, None, None, None, None, None,
        step_states
    ]

# Custom index string
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
        <link rel="stylesheet" href="/assets/styles.css">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
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