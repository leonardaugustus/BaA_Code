# navigation_and_step4.py
import dash
from dash import dcc, html, dash_table
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import cm
import io

# Updated Header component with clickable steps
def get_header_with_navigation(current_step=0, step_states=None):
    """Create header with clickable step navigation"""
    if step_states is None:
        step_states = {0: True, 1: False, 2: False, 3: False, 4: False}
    
    steps = [
        {"label": "PDF & DB", "number": 0},
        {"label": "LISS-Werte", "number": 1},
        {"label": "Analyse", "number": 2},
        {"label": "Ergebnis", "number": 3},
        {"label": "Bericht", "number": 4}
    ]
    
    step_items = []
    for step in steps:
        is_active = current_step >= step["number"]
        is_completed = current_step > step["number"]
        is_clickable = step_states.get(step["number"], False)
        
        step_items.append(
            html.Button(
                [
                    html.Div(
                        str(step["number"]), 
                        className=f"step-number {'active' if is_active else ''} {'completed' if is_completed else ''}"
                    ),
                    html.Div(step["label"], className="step-label")
                ],
                id={"type": "step-nav", "index": step["number"]},
                className=f"step-item {'active' if is_active else ''} {'disabled' if not is_clickable else ''}",
                disabled=not is_clickable,
                style={"background": "none", "border": "none", "padding": "0", "cursor": "pointer" if is_clickable else "not-allowed"}
            )
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
        progress_indicator
    ])

# Step 4 - Reporting
def get_step4_layout(df, status_map, exclusion_reasons, user_selections, lot_number=""):
    """Build Step 4 layout with medical and lab technical reports"""
    
    # Create medical report content
    medical_report = create_medical_report(df, status_map, user_selections, lot_number)
    
    # Create lab technical report content
    lab_report = create_lab_technical_report(df, status_map, exclusion_reasons, user_selections)
    
    # Quick jump link component
    quick_jump = html.Div([
        html.Button(
            "⇠ Zurück zu Schritt 2",
            id="quick-jump-step2",
            className="quick-jump-link",
            style={
                "background": "none",
                "border": "none",
                "color": "#2e8bc0",
                "cursor": "pointer",
                "fontSize": "14px",
                "padding": "5px 10px",
                "textDecoration": "underline"
            }
        )
    ], style={"textAlign": "right", "marginBottom": "10px"})
    
    return html.Div([
        html.H3("Schritt 4: Berichtserstellung", className="step-title"),
        
        # Add quick jump link
        quick_jump,
        
        # Report header info
        html.Div([
            html.P(f"Datum: {datetime.now().strftime('%d.%m.%Y')}"),
            html.P(f"Uhrzeit: {datetime.now().strftime('%H:%M')}"),
            html.P(f"Benutzer: Labor"),
            html.P(f"Lot-Nr.: {lot_number if lot_number else 'Nicht angegeben'}")
        ], className="report-header"),
        
        # Tab selector for different reports
        dcc.Tabs([
            dcc.Tab(label="Medizinischer Bericht", children=[
                html.Div([
                    html.H4("Medizinischer Bericht", className="section-title"),
                    medical_report
                ], className="report-section")
            ], className="custom-tab", selected_className="custom-tab-selected"),
            
            dcc.Tab(label="Labortechnischer Bericht", children=[
                html.Div([
                    html.H4("Labortechnischer Bericht", className="section-title"),
                    lab_report
                ], className="report-section")
            ], className="custom-tab", selected_className="custom-tab-selected"),
        ], id="report-tabs", className="custom-tabs"),
        
        # Action buttons
        html.Div([
            html.Button("Zurück zu Schritt 3", id="step4-back-button", 
                       className="action-button secondary", style={"marginRight": "10px"}),
            html.Button("PDF erstellen", id="generate-report-pdf-button",
                       className="action-button accent", style={"marginRight": "10px"}),
            html.Button("In Datenbank speichern", id="save-to-db-button",
                       className="action-button primary", style={"marginRight": "10px"}),
            html.Button("Neue Analyse starten", id="step4-restart-button", 
                       className="action-button primary")
        ], style={"marginTop": "20px", "display": "flex", "justifyContent": "center"}),
        
        # Hidden component for PDF download
        dcc.Download(id="download-report-pdf")
    ], id="step4-content")

def create_medical_report(df, status_map, user_selections, lot_number):
    """Create medical report content"""
    # Filter for confirmed antigens
    confirmed_antigens = []
    for ag, status in status_map.items():
        if ag in user_selections and ("Bestätigt" in status):
            confirmed_antigens.append(ag)
    
    # Create antibody list
    antibody_text = "Folgende Antikörper wurden nachgewiesen: "
    if confirmed_antigens:
        antibody_text += ", ".join([f"Anti-{ag}" for ag in confirmed_antigens])
    else:
        antibody_text += "Keine Antikörper nachgewiesen"
    
    # Create reaction table
    reaction_data = []
    for idx, row in df.iterrows():
        if row.get("LISS", "-") != "-":
            row_data = {
                "Spender": row.get("Spender", ""),
                "LISS": row.get("LISS", ""),
            }
            # Add selected antigens
            for ag in user_selections:
                if ag in row:
                    row_data[ag] = row[ag]
            reaction_data.append(row_data)
    
    # Build table columns
    table_columns = [
        {"name": "Spender", "id": "Spender"},
        {"name": "LISS", "id": "LISS"}
    ]
    for ag in user_selections:
        table_columns.append({"name": ag, "id": ag})
    
    return html.Div([
        html.P(antibody_text, style={"marginBottom": "20px"}),
        html.H5("Antigen-Reaktionstabelle:"),
        dash_table.DataTable(
            columns=table_columns,
            data=reaction_data,
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center"},
            style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"}
        )
    ])

def create_lab_technical_report(df, status_map, exclusion_reasons, user_selections):
    """Create lab technical report content"""
    # Count reactions per antigen
    reaction_counts = {}
    for ag in ANTIGEN_COLUMNS:
        if ag in df.columns:
            positive_reactions = df[df["LISS"].isin(["+/-", "1+", "2+", "3+", "4+"])][ag]
            count = sum(positive_reactions == "+")
            reaction_counts[ag] = {
                "count": count,
                "status": status_map.get(ag, ""),
                "user_selected": ag in user_selections,
                "exclusion_reason": exclusion_reasons.get(ag, "")
            }
    
    # Create summary table data
    summary_data = []
    for ag, info in reaction_counts.items():
        summary_data.append({
            "Antigen": ag,
            "Reaktionen": info["count"],
            "Status": info["status"],
            "Benutzerauswahl": "Ja" if info["user_selected"] else "Nein",
            "Ausschlussgrund": info["exclusion_reason"]
        })
    
    # Highlight differences between user and system selection
    system_selected = [ag for ag, status in status_map.items() 
                      if "Ausgestrichen" not in status]
    differences = set(user_selections).symmetric_difference(set(system_selected))
    
    return html.Div([
        html.P(f"Anzahl getesteter Spender: {len(df)}"),
        html.P(f"System-Auswahl: {len(system_selected)} Antigene"),
        html.P(f"Benutzer-Auswahl: {len(user_selections)} Antigene"),
        html.P(f"Unterschiede: {len(differences)} Antigene", 
               style={"color": "red"} if differences else {}),
        
        html.H5("Antigen-Übersicht:"),
        dash_table.DataTable(
            columns=[
                {"name": "Antigen", "id": "Antigen"},
                {"name": "Reaktionen", "id": "Reaktionen"},
                {"name": "Status", "id": "Status"},
                {"name": "Benutzerauswahl", "id": "Benutzerauswahl"},
                {"name": "Ausschlussgrund", "id": "Ausschlussgrund"}
            ],
            data=summary_data,
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center"},
            style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
            style_data_conditional=[
                {
                    "if": {"filter_query": f"{{Antigen}} = {ag}"},
                    "backgroundColor": "#ffeb3b"
                } for ag in differences
            ]
        )
    ])

def generate_pdf_report(df, status_map, exclusion_reasons, user_selections, lot_number=""):
    """Generate PDF report using reportlab"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#145da0'),
        spaceAfter=30
    )
    story.append(Paragraph("Antigen Analyse Bericht", title_style))
    
    # Header info
    header_data = [
        ["Datum:", datetime.now().strftime('%d.%m.%Y')],
        ["Uhrzeit:", datetime.now().strftime('%H:%M')],
        ["Benutzer:", "Labor"],
        ["Lot-Nr.:", lot_number if lot_number else "Nicht angegeben"]
    ]
    header_table = Table(header_data, colWidths=[3*cm, 6*cm])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#145da0')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 20))
    
    # Medical report section
    story.append(Paragraph("Medizinischer Bericht", styles['Heading2']))
    
    # Confirmed antigens
    confirmed_antigens = [ag for ag, status in status_map.items() 
                         if ag in user_selections and "Bestätigt" in status]
    if confirmed_antigens:
        antibody_text = f"Folgende Antikörper wurden nachgewiesen: {', '.join([f'Anti-{ag}' for ag in confirmed_antigens])}"
    else:
        antibody_text = "Keine Antikörper nachgewiesen"
    story.append(Paragraph(antibody_text, styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Add more content as needed...
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# Constants needed (should be imported from main app)
ANTIGEN_COLUMNS = []  # This will be populated from the main app

# Step 2 Enhanced - Add exclusion summary
def create_exclusion_summary(exclusion_reasons, system_excluded):
    """Create a summary of excluded antigens for Step 2"""
    if not system_excluded:
        return html.Div("Keine Antigene wurden ausgeschlossen.", 
                       style={"color": "green", "fontWeight": "bold"})
    
    exclusion_items = []
    for ag in sorted(system_excluded):
        reason = exclusion_reasons.get(ag, "Unbekannter Grund")
        exclusion_items.append(
            html.Div([
                html.Strong(f"{ag}: "),
                html.Span(f"Ausgeschlossen wegen {reason}")
            ], className="exclusion-item")
        )
    
    return html.Div([
        html.H4("Zusammenfassung der ausgeschlossenen Antigene:"),
        html.Div(exclusion_items)
    ], className="exclusion-summary")

def create_provisional_report(status_map, user_selections):
    """Create provisional preliminary findings for Step 2"""
    confirmed_2x = []
    confirmed_3x = []
    
    for ag in user_selections:
        status = status_map.get(ag, "")
        if "Bestätigt (3x +)" in status:
            confirmed_3x.append(ag)
        elif "Bestätigt (2x +)" in status:
            confirmed_2x.append(ag)
    
    all_confirmed = confirmed_2x + confirmed_3x
    
    if all_confirmed:
        report_text = f"Bestätigt (2× + und 3× +): {', '.join(all_confirmed)}"
    else:
        report_text = "Keine bestätigten Antigene gefunden"
    
    # Add deprecation warning if needed
    deprecation_warning = ""
    # Add logic for deprecation warnings based on specific antigens
    
    return html.Div([
        html.H4("Provisorischer Vorbefund:"),
        html.P(report_text, style={"fontSize": "1.1em", "fontWeight": "bold"}),
        html.P(deprecation_warning, style={"color": "orange"}) if deprecation_warning else None
    ], style={"backgroundColor": "#e3f2fd", "padding": "15px", "borderRadius": "5px", "marginTop": "20px"})