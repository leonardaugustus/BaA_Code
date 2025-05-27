# step0_components.py
import dash
from dash import dcc, html, dash_table
import pandas as pd
import base64
import io
from datetime import datetime
import tabula
import json

def parse_pdf_content(contents, filename):
    """Parse uploaded PDF using tabula-py"""
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    
    try:
        # Save temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(decoded)
            tmp_path = tmp_file.name
        
        # Extract tables from PDF
        tables = tabula.read_pdf(tmp_path, pages='all', multiple_tables=True)
        
        # Clean up
        import os
        os.unlink(tmp_path)
        
        if tables:
            # Assume the first table contains our data
            df = tables[0]
            return df
        else:
            return None
            
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return None

def build_diff_table(pdf_data, current_data):
    """Build a comparison table showing differences between PDF and current data"""
    if pdf_data is None or current_data is None:
        return html.Div("Keine Daten zum Vergleichen vorhanden")
    
    # Create a difference summary
    diff_rows = []
    
    # Compare row by row
    max_rows = max(len(pdf_data), len(current_data))
    
    for i in range(max_rows):
        row_diff = {}
        
        if i < len(pdf_data) and i < len(current_data):
            # Compare existing rows
            pdf_row = pdf_data.iloc[i]
            current_row = current_data.iloc[i]
            
            for col in pdf_row.index:
                if col in current_row.index:
                    if str(pdf_row[col]) != str(current_row[col]):
                        row_diff[col] = {
                            'pdf': str(pdf_row[col]),
                            'current': str(current_row[col]),
                            'different': True
                        }
                    else:
                        row_diff[col] = {
                            'pdf': str(pdf_row[col]),
                            'current': str(current_row[col]),
                            'different': False
                        }
        
        if row_diff:
            diff_rows.append(row_diff)
    
    return html.Div([
        html.H4("Datenvergleich: PDF vs. Aktuelle Tabelle"),
        html.Div([
            html.Div([
                html.H5("PDF-Daten"),
                dash_table.DataTable(
                    id="pdf-preview-table",
                    columns=[{"name": col, "id": col} for col in pdf_data.columns],
                    data=pdf_data.to_dict('records'),
                    style_table={"maxHeight": "400px", "overflowY": "auto"},
                    style_cell={"textAlign": "center"},
                    editable=True,
                    page_size=10
                )
            ], style={"width": "48%", "display": "inline-block", "verticalAlign": "top"}),
            
            html.Div([
                html.H5("Aktuelle Tabelle"),
                dash_table.DataTable(
                    id="current-preview-table",
                    columns=[{"name": col, "id": col} for col in current_data.columns],
                    data=current_data.to_dict('records'),
                    style_table={"maxHeight": "400px", "overflowY": "auto"},
                    style_cell={"textAlign": "center"},
                    page_size=10
                )
            ], style={"width": "48%", "display": "inline-block", "verticalAlign": "top", "marginLeft": "4%"})
        ])
    ])

def get_step0_layout(db_session=None):
    """Build Step 0 layout for PDF import and database selection"""
    
    # Get available analyses from database
    analysis_options = []
    if db_session:
        analyses = db_session.query(Analysis).order_by(Analysis.timestamp.desc()).all()
        analysis_options = [
            {
                "label": f"ID {a.id} - {a.timestamp.strftime('%Y-%m-%d %H:%M')} - Spender: {a.spendernummer}",
                "value": a.id
            }
            for a in analyses
        ]
    
    return html.Div([
        html.H3("Schritt 0: PDF einladen & vergleichen / Datenbank öffnen", className="step-title"),
        
        # Lot number input
        html.Div([
            html.Label("Lot-Nummer:"),
            dcc.Input(
                id="lot-number-input",
                type="text",
                placeholder="z.B. LOT-2024-001",
                style={"width": "300px", "marginBottom": "20px"}
            )
        ]),
        
        # Two-column layout
        html.Div([
            # Left column - PDF upload
            html.Div([
                html.H4("PDF-Import"),
                dcc.Upload(
                    id='pdf-upload',
                    children=html.Div([
                        'PDF-Datei hier ablegen oder ',
                        html.A('auswählen', style={"color": "#2e8bc0", "cursor": "pointer"})
                    ]),
                    style={
                        'width': '100%',
                        'height': '80px',
                        'lineHeight': '80px',
                        'borderWidth': '2px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                        'margin': '10px 0',
                        'backgroundColor': '#f8f9fa'
                    },
                    multiple=False
                ),
                html.Div(id="pdf-parse-status"),
            ], style={"width": "48%", "display": "inline-block", "verticalAlign": "top"}),
            
            # Right column - Database selection
            html.Div([
                html.H4("Datenbank-Auswahl"),
                dcc.Dropdown(
                    id="db-analysis-dropdown",
                    options=analysis_options,
                    placeholder="Vorherige Analyse auswählen...",
                    style={"marginBottom": "10px"}
                ),
                html.Button(
                    "Aus Datenbank öffnen",
                    id="open-from-db-button",
                    className="action-button secondary",
                    style={"width": "100%"}
                )
            ], style={"width": "48%", "display": "inline-block", "verticalAlign": "top", "marginLeft": "4%"})
        ]),
        
        # Comparison area
        html.Div(id="pdf-comparison-area", style={"marginTop": "30px"}),
        
        # Action buttons
        html.Div([
            html.Button(
                "Bestätigen und fortfahren",
                id="step0-confirm-button",
                className="action-button primary",
                disabled=True,
                style={"marginRight": "10px"}
            ),
            html.Button(
                "Manuelle Eingabe",
                id="step0-manual-button",
                className="action-button secondary"
            )
        ], style={"marginTop": "20px", "textAlign": "center"}),
        
        # Toggle for automatic/manual evaluation
        html.Div([
            html.Label([
                "Auswertungsmodus: ",
                dcc.RadioItems(
                    id="evaluation-mode",
                    options=[
                        {"label": "Automatische Auswertung", "value": "auto"},
                        {"label": "Manuelle Auswertung", "value": "manual"}
                    ],
                    value="auto",
                    inline=True,
                    style={"marginLeft": "10px"}
                )
            ])
        ], style={"marginTop": "20px", "padding": "10px", "backgroundColor": "#f8f9fa", "borderRadius": "5px"})
    ], id="step0-content")