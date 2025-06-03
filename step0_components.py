# step0_components.py
import dash
from dash import dcc, html, dash_table
import pandas as pd
import base64
import io
from datetime import datetime
import json
from database import Analysis

def parse_pdf_content(contents, filename):
    """Parse uploaded PDF using tabula-py with improved error handling"""
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    
    try:
        # Only process PDF files
        if not filename.lower().endswith('.pdf'):
            return None
            
        # Try to import tabula-py
        try:
            import tabula
        except ImportError:
            print("Warning: tabula-py not installed. Install with: pip install tabula-py")
            return None
        
        # Save temporary file
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(decoded)
            tmp_path = tmp_file.name
        
        # Extract tables from PDF
        tables = tabula.read_pdf(tmp_path, pages='all', multiple_tables=True)
        
        # Clean up
        os.unlink(tmp_path)
        
        if tables and len(tables) > 0:
            # Assume the first table contains our data
            df = tables[0]
            
            # Clean and standardize column names
            if "spendernummer" in df.columns:
                df = df.rename(columns={"spendernummer": "Sp.Nr."})
            
            return df
        else:
            return None
            
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return None

def parse_image_content(contents, filename):
    """Parse uploaded JPEG image using OCR (placeholder implementation)"""
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    
    try:
        # This would require OCR libraries like pytesseract
        # For now, return None as OCR is complex to implement
        print(f"Image processing not yet implemented for {filename}")
        return None
        
    except Exception as e:
        print(f"Error parsing image: {e}")
        return None

def calculate_confidence(df):
    """Calculate confidence score for parsed data"""
    if df is None or len(df) == 0:
        return 0.0
    
    confidence = 0.8  # Base confidence
    
    # Check for expected columns
    expected_columns = ["Sp.Nr.", "Spender", "LISS"]
    found_columns = sum(1 for col in expected_columns if col in df.columns)
    confidence += (found_columns / len(expected_columns)) * 0.15
    
    # Check for reasonable data values
    if "LISS" in df.columns:
        valid_liss_values = {"-", "+/-", "1+", "2+", "3+", "4+"}
        liss_validity = df["LISS"].isin(valid_liss_values).mean()
        confidence += liss_validity * 0.05
    
    return min(confidence, 1.0)

def build_diff_table(pdf_data, current_data):
    """Build a comparison table showing differences between PDF and current data"""
    if pdf_data is None or current_data is None:
        return html.Div("Keine Daten zum Vergleichen vorhanden")
    
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

def build_editable_diff_table(pdf_data, current_data, confidence):
    """Build editable comparison table for low confidence imports"""
    if pdf_data is None or current_data is None:
        return html.Div("Keine Daten zum Vergleichen vorhanden")
    
    confidence_color = "#28a745" if confidence >= 0.95 else "#ffc107" if confidence >= 0.8 else "#dc3545"
    
    return html.Div([
        html.Div([
            html.H4("Datenvergleich: Importierte Daten vs. Aktuelle Tabelle"),
            html.Div([
                html.Span(f"Erkennungsgenauigkeit: {confidence:.1%}", 
                         style={"backgroundColor": confidence_color, "color": "white", 
                               "padding": "5px 10px", "borderRadius": "4px"})
            ], style={"marginBottom": "10px"}),
            html.P("Niedrige Genauigkeit erkannt - bitte überprüfen und korrigieren Sie die Daten falls nötig:",
                  style={"color": "#856404", "fontStyle": "italic"})
        ]),
        
        html.Div([
            html.Div([
                html.H5("Importierte Daten (bearbeitbar)"),
                dash_table.DataTable(
                    id="pdf-preview-table",
                    columns=[{"name": col, "id": col, "editable": True} 
                            for col in pdf_data.columns],
                    data=pdf_data.to_dict('records'),
                    style_table={"maxHeight": "400px", "overflowY": "auto"},
                    style_cell={"textAlign": "center"},
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
                    editable=False,
                    page_size=10
                )
            ], style={"width": "48%", "display": "inline-block", "verticalAlign": "top", "marginLeft": "4%"})
        ])
    ])

def parse_file_content(contents, filename):
    """Wrapper function to handle file parsing with validation"""
    
    # Validate file type
    if filename.lower().endswith('.pdf'):
        df = parse_pdf_content(contents, filename)
        if df is not None:
            confidence = calculate_confidence(df)
            return df, confidence, None
        else:
            return None, 0, "Fehler beim Parsen der PDF-Datei. Stellen Sie sicher, dass die PDF Tabellendaten enthält."
    
    elif filename.lower().endswith(('.jpg', '.jpeg')):
        df = parse_image_content(contents, filename)
        if df is not None:
            confidence = calculate_confidence(df)
            return df, confidence, None
        else:
            return None, 0, "Bildverarbeitung noch nicht implementiert. Bitte verwenden Sie PDF-Dateien."
    
    else:
        return None, 0, "Nur PDF- und JPEG-Dateien werden unterstützt."

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
                html.H4("PDF & Bilddaten-Import"),
                dcc.Upload(
                    id='pdf-upload',
                    children=html.Div([
                        'PDF- oder JPEG-Datei hier ablegen oder ',
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
                    multiple=False,
                    accept="application/pdf,image/jpeg,.pdf,.jpg,.jpeg"
                ),
                html.Div(id="pdf-parse-status"),
                html.P("Unterstützte Formate: PDF, JPEG", 
                      style={"fontSize": "12px", "color": "#666", "marginTop": "5px"})
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
                "PDF vergleichen & bestätigen",
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