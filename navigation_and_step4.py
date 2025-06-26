# navigation_and_step4.py - FIXED VERSION

from __future__ import annotations
import io
from datetime import datetime
from typing import Iterable, Mapping, Sequence
import dash
import pandas as pd
from dash import dcc, html, dash_table
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Spacer, Paragraph, Table,
                                TableStyle)

###############################################################################
# ───────────────────────── Helper / shared utilities ──────────────────────── #
###############################################################################

_SUPERSCRIPT_MAP: dict[str, str] = {
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ", "g": "ᵍ",
    "h": "ʰ", "i": "ⁱ", "j": "ʲ", "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ",
    "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ", "v": "ᵛ",
    "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ", "A": "ᴬ", "B": "ᴮ", "C": "ᶜ", 
    "D": "ᴰ", "E": "ᴱ", "F": "ᶠ", "G": "ᴳ", "H": "ᴴ", "I": "ᴵ", "J": "ᴶ", 
    "K": "ᴷ", "L": "ᴸ", "M": "ᴹ", "N": "ᴺ", "O": "ᴼ", "P": "ᴾ", "R": "ᴿ", 
    "S": "ˢ", "T": "ᵀ", "U": "ᵁ", "V": "ⱽ", "W": "ᵂ", "X": "ˣ", "Y": "ʸ", "Z": "ᶻ",
    "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅"  # subscript numbers
}

# Fixed antigen order for consistent sorting
ANTIGEN_ORDER = [
    "D", "C", "E", "c", "e", "Cw", "K", "k", "Kpa", "Kpb", "Jsa", "Jsb", 
    "Fya", "Fyb", "Jka", "Jkb", "Lea", "Leb", "P1", "M", "N", "S", "s", 
    "Lua", "Lub", "Xga"
]

_POSITIVE_LISS_VALUES: set[str] = {"+/-", "1+", "2+", "3+", "4+"}

###############################################################################
# ────────────────────────────── Navigation bar ────────────────────────────── #
###############################################################################

def format_antigen(antigen: str) -> str:  # noqa: D401 – simple function
    """Return an antigen name with proper superscript/subscript formatting."""
    if len(antigen) <= 1:
        return antigen
    
    # Special case for P1 - should be P₁ (subscript 1)
    if antigen == "P1":
        return "P₁"
    
    # For other antigens, last character becomes superscript
    prefix = antigen[:-1]
    last_char = antigen[-1]
    formatted_char = _SUPERSCRIPT_MAP.get(last_char, last_char)
    return f"{prefix}{formatted_char}"

def format_antigen_for_pdf(antigen: str) -> str:
    """Format antigen for PDF with proper Unicode superscripts and subscripts"""
    if len(antigen) <= 1:
        return antigen
    
    # Special case for P1 - should be P₁ (subscript 1)
    if antigen == "P1":
        return "P₁"
    
    # For other antigens, apply superscript formatting
    prefix = antigen[:-1]
    last_char = antigen[-1]
    
    # Use actual Unicode superscripts for better PDF rendering
    superscript_map = {
        "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ", "g": "ᵍ",
        "h": "ʰ", "i": "ⁱ", "j": "ʲ", "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ",
        "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ", "v": "ᵛ",
        "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ"
    }
    
    formatted_char = superscript_map.get(last_char.lower(), last_char)
    return f"{prefix}{formatted_char}"

# 2. FIXED: Updated PDF generation with proper antigen formatting
def generate_pdf_report_fixed(
    df: pd.DataFrame,
    status_map: dict,
    exclusion_reasons: dict,
    user_selections: list,
    *,
    lot_number: str = "",
) -> bytes:
    """Generate a PDF representation of the report with proper antigen formatting."""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []

    styles = getSampleStyleSheet()

    # Title
    story.append(
        Paragraph(
            "Antigen Analyse Bericht",
            ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor("#145da0"),
                spaceAfter=30,
            ),
        )
    )

    # Header table with lot number
    header_data = [
        ["Datum:", f"{datetime.now():%d.%m.%Y}"],
        ["Uhrzeit:", f"{datetime.now():%H:%M}"],
        ["Benutzer:", "Labor"],
        ["Lot-Nr.:", lot_number or "Nicht angegeben"],
    ]
    tbl = Table(header_data, colWidths=[3 * cm, 6 * cm])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#145da0")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]
        )
    )
    story.extend([tbl, Spacer(1, 20)])

    # FIXED: Medical section with distinct 3x and 2x findings, properly formatted
    story.append(Paragraph("Medizinischer Bericht", styles["Heading2"]))

    sorted_selections = sort_antigens(user_selections)
    confirmed_3x = [ag for ag in sorted_selections if "Bestätigt (3x +)" in status_map.get(ag, "")]
    confirmed_2x = [ag for ag in sorted_selections if "Bestätigt (2x +)" in status_map.get(ag, "")]

    # FIXED: Updated text to use "bestätigt" instead of "vorhanden"
    if confirmed_3x:
        formatted_3x = [f"Anti-{format_antigen_for_pdf(ag)}" for ag in confirmed_3x]
        antibody_3x_text = "3× Antikörper bestätigt: " + ", ".join(formatted_3x)
        story.append(Paragraph(antibody_3x_text, styles["Normal"]))
    
    if confirmed_2x:
        formatted_2x = [f"Anti-{format_antigen_for_pdf(ag)}" for ag in confirmed_2x]
        antibody_2x_text = "2× Antikörper bestätigt: " + ", ".join(formatted_2x)
        story.append(Paragraph(antibody_2x_text, styles["Normal"]))

    if not confirmed_3x and not confirmed_2x:
        story.append(Paragraph("Keine Antikörper nachgewiesen", styles["Normal"]))

    story.append(Spacer(1, 20))

    # FIXED: Add labortechnischer bericht section with antibody summary and no donor count
    story.append(Paragraph("Labortechnischer Bericht", styles["Heading2"]))
    
    # Add same antibody summary
    if confirmed_3x:
        formatted_3x = [f"Anti-{format_antigen_for_pdf(ag)}" for ag in confirmed_3x]
        antibody_3x_text = "3× Antikörper bestätigt: " + ", ".join(formatted_3x)
        story.append(Paragraph(antibody_3x_text, styles["Normal"]))
    
    if confirmed_2x:
        formatted_2x = [f"Anti-{format_antigen_for_pdf(ag)}" for ag in confirmed_2x]
        antibody_2x_text = "2× Antikörper bestätigt: " + ", ".join(formatted_2x)
        story.append(Paragraph(antibody_2x_text, styles["Normal"]))
    
    # REMOVED: "Anzahl getesteter Spender" line as requested
    
    story.append(Spacer(1, 20))

    # FIXED: Add reaction table to PDF with proper formatting
    story.append(Paragraph("Antigen-Reaktionstabelle", styles["Heading3"]))
    
    # Build table data for PDF with proper antigen formatting
    positive_liss_values = {"+/-", "1+", "2+", "3+", "4+"}
    table_data = []
    
    # Header row with properly formatted antigen names using format_antigen_for_pdf
    header_row = [" ", "Sp.Nr.", "LISS"]  # FIXED: Use single space for Tz.Nr. column
    header_row.extend([format_antigen_for_pdf(ag) for ag in sorted_selections])
    table_data.append(header_row)
    
    # Data rows
    for _, row in df.iterrows():
        liss_val = row.get("LISS", "-")
        if liss_val not in positive_liss_values:
            continue
            
        data_row = [
            str(row.get("Tz.Nr.", "")),
            str(row.get("Sp.Nr.", "")),
            str(liss_val)
        ]
        data_row.extend([str(row.get(ag, "")) for ag in sorted_selections])
        table_data.append(data_row)
    
    if len(table_data) > 1:  # If we have data beyond the header
        pdf_table = Table(table_data)
        pdf_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ])
        )
        story.append(pdf_table)

    story.append(Spacer(1, 20))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def sort_antigens(antigen_list):
    """Sort antigens according to the predefined order."""
    if not antigen_list:
        return []
    
    # Create a mapping from antigen name to its order index
    order_map = {ag: i for i, ag in enumerate(ANTIGEN_ORDER)}
    
    # Sort the list based on the predefined order
    # Antigens not in ANTIGEN_ORDER will appear at the end
    def sort_key(antigen):
        return order_map.get(antigen, len(ANTIGEN_ORDER))
    
    return sorted(antigen_list, key=sort_key)

def get_header_with_navigation(
    current_step: int = 0,
    step_states: Mapping[int, bool] | None = None,
) -> html.Div:
    """Return a header that shows the five-step progress bar.

    Parameters
    ----------
    current_step
        Zero-based index of the wizard step that is *currently shown*.
    step_states
        Optional mapping that decides whether a given step *button* should be
        clickable.  If *None*, every step up to (and incl.) `current_step` is
        enabled so users may navigate back to completed steps, while future
        steps stay disabled.
    """

    if step_states is None:
        # enable all steps the user has already *been through*
        step_states = {i: i <= current_step for i in range(5)}

    steps = [
        {"label": "PDF & DB", "number": 0},
        {"label": "LISS-Werte", "number": 1},
        {"label": "Analyse", "number": 2},
        {"label": "Ergebnis", "number": 3},
        {"label": "Bericht", "number": 4},
    ]

    step_items: list[html.Button] = []
    for step in steps:
        number = step["number"]
        is_active = current_step == number
        is_completed = current_step > number
        is_clickable = bool(step_states.get(number, False))

        button = html.Button(
            [
                html.Div(
                    str(number),
                    className="step-number " + (
                        "active" if is_active else "completed" if is_completed else ""
                    ),
                ),
                html.Div(step["label"], className="step-label"),
            ],
            id={"type": "step-nav", "index": number},
            className="step-item " + ("active " if is_active else "") + (
                "disabled" if not is_clickable else ""
            ),
            disabled=not is_clickable,
            style={
                "background": "none",
                "border": "none",
                "padding": "0",
                "cursor": "pointer" if is_clickable else "not-allowed",
            },
        )
        step_items.append(button)

    progress_indicator = html.Div(step_items, className="progress-steps")

    return html.Div(
        [
            html.Div(
                [
                    html.H1("Antigen Analyse Dashboard", className="dashboard-title"),
                    html.Div(
                        [
                            dcc.Upload(
                                id="upload-data",
                                children=html.Button("Datei hochladen", className="upload-button"),
                                multiple=False,
                                accept="application/pdf,image/jpeg,.pdf,.jpg,.jpeg"
                            )
                        ],
                        className="header-actions",
                    ),
                ],
                className="dashboard-header",
            ),
            progress_indicator,
        ]
    )

###############################################################################
# ───────────────────────────────── Step 4 layout ──────────────────────────── #
###############################################################################

def _guess_antigen_columns(df: pd.DataFrame) -> list[str]:
    """Best-effort guess which columns store antigen reactivity (+/−)."""
    # CORRECTED naming
    ignored = {"Sp.Nr.", "LISS", "Tz.Nr.", "Tz.Nr. (Kopie)", "Spez. Antigen"}
    return [col for col in df.columns if col not in ignored]


def get_step4_layout(
    df: pd.DataFrame,
    status_map: Mapping[str, str],
    exclusion_reasons: Mapping[str, str],
    user_selections: Sequence[str],
    *,
    lot_number: str = "",
    antigen_columns: Sequence[str] | None = None,
) -> html.Div:
    """Return the Dash layout for *Schritt 4 – Bericht*."""

    if antigen_columns is None:
        antigen_columns = _guess_antigen_columns(df)

    medical_report = create_medical_report(df, status_map, user_selections, lot_number)
    lab_report = create_lab_technical_report(
        df, status_map, exclusion_reasons, user_selections, antigen_columns
    )

    quick_jump = html.Div(
        [
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
                    "textDecoration": "underline",
                },
            )
        ],
        style={"textAlign": "right", "marginBottom": "10px"},
    )

    return html.Div(
        [
            html.H3("Schritt 4 – Berichtserstellung", className="step-title"),
            quick_jump,
            html.Div(
                [
                    html.P(f"Datum: {datetime.now():%d.%m.%Y}"),
                    html.P(f"Uhrzeit: {datetime.now():%H:%M}"),
                    html.P("Benutzer: Labor"),
                    html.P(f"Lot-Nr.: {lot_number or 'Nicht angegeben'}"),
                ],
                className="report-header",
            ),
            dcc.Tabs(
                [
                    dcc.Tab(
                        label="Medizinischer Bericht",
                        children=[
                            html.Div(
                                [
                                    html.H4("Medizinischer Bericht", className="section-title"),
                                    html.Div([
                                        html.Button(
                                            "⇠ Zurück zu Schritt 2",
                                            id="quick-jump-step2-med",
                                            className="quick-jump-link",
                                            style={
                                                "background": "none",
                                                "border": "none",
                                                "color": "#2e8bc0",
                                                "cursor": "pointer",
                                                "fontSize": "14px",
                                                "padding": "5px 10px",
                                                "textDecoration": "underline",
                                                "float": "right"
                                            },
                                        )
                                    ], style={"textAlign": "right", "marginBottom": "10px"}),
                                    medical_report,
                                ],
                                className="report-section",
                            )
                        ],
                        className="custom-tab",
                        selected_className="custom-tab-selected",
                    ),
                    dcc.Tab(
                        label="Labortechnischer Bericht",
                        children=[
                            html.Div(
                                [
                                    html.H4("Labortechnischer Bericht", className="section-title"),
                                    html.Div([
                                        html.Button(
                                            "⇠ Zurück zu Schritt 2",
                                            id="quick-jump-step2-lab",
                                            className="quick-jump-link",
                                            style={
                                                "background": "none",
                                                "border": "none",
                                                "color": "#2e8bc0",
                                                "cursor": "pointer",
                                                "fontSize": "14px",
                                                "padding": "5px 10px",
                                                "textDecoration": "underline",
                                                "float": "right"
                                            },
                                        )
                                    ], style={"textAlign": "right", "marginBottom": "10px"}),
                                    lab_report,
                                ],
                                className="report-section",
                            )
                        ],
                        className="custom-tab",
                        selected_className="custom-tab-selected",
                    ),
                ],
                id="report-tabs",
                className="custom-tabs",
            ),
            html.Div(
                [
                    html.Button(
                        "Zurück zu Schritt 3",
                        id="step4-back-button",
                        className="action-button secondary",
                        style={"marginRight": "10px"},
                    ),
                    html.Button(
                        "PDF erstellen",
                        id="generate-report-pdf-button",
                        className="action-button accent",
                        style={"marginRight": "10px"},
                    ),
                    html.Button(
                        "In Datenbank speichern",
                        id="save-to-db-button",
                        className="action-button primary",
                        style={"marginRight": "10px"},
                    ),
                    html.Button(
                        "Neue Analyse starten",
                        id="step4-restart-button",
                        className="action-button primary",
                    ),
                ],
                style={"marginTop": "20px", "display": "flex", "justifyContent": "center"},
            ),
            dcc.Download(id="download-report-pdf"),
        ],
        id="step4-content",
    )

###############################################################################
# ────────────────────────── Report helper functions ───────────────────────── #
###############################################################################

def create_medical_report(
    df: pd.DataFrame,
    status_map: Mapping[str, str],
    user_selections: Sequence[str],
    lot_number: str = "",
) -> html.Div:
    """Return a Dash subtree summarising the medical findings."""

    # Remove Index column if it exists
    if "Index" in df.columns:
        df = df.drop(columns=["Index"])

    # Sort user selections and separate 3x and 2x confirmed antigens
    sorted_selections = sort_antigens(user_selections)
    
    confirmed_3x = [
        ag for ag in sorted_selections if "Bestätigt (3x +)" in status_map.get(ag, "")
    ]
    confirmed_2x = [
        ag for ag in sorted_selections if "Bestätigt (2x +)" in status_map.get(ag, "")
    ]

    # FIXED: Create properly formatted antibody text with superscripts
    antibody_text_parts = []
    if confirmed_3x:
        formatted_3x = [f"Anti-{format_antigen(ag)}" for ag in confirmed_3x]
        antibody_text_parts.append(
            f"3+ Antikörper vorhanden: {', '.join(formatted_3x)}"
        )
    if confirmed_2x:
        formatted_2x = [f"Anti-{format_antigen(ag)}" for ag in confirmed_2x]
        antibody_text_parts.append(
            f"2+ Antikörper vorhanden: {', '.join(formatted_2x)}"
        )
    
    if not antibody_text_parts:
        antibody_text_parts = ["Keine Antikörper nachgewiesen"]

    # Build the reaction table – include only rows that have positive LISS values
    positive_liss_values = {"+/-", "1+", "2+", "3+", "4+"}
    reaction_rows: list[dict[str, str]] = []
    for _, row in df.iterrows():
        liss_val = row.get("LISS", "-")
        if liss_val not in positive_liss_values:
            continue
        # CORRECTED naming: use Tz.Nr. and Sp.Nr.
        record = {"Sp.Nr.": row.get("Sp.Nr.", ""), "LISS": liss_val}
        # Add Tz.Nr. if available
        if "Tz.Nr." in row:
            record["Tz.Nr."] = row["Tz.Nr."]
        # FIXED: Add antigens in sorted order with formatting
        for ag in sorted_selections:
            if ag in row:
                record[format_antigen(ag)] = row[ag]
        reaction_rows.append(record)

    # Dash DataTable definition - FIXED: compact layout for single page fit
    columns_list = ["Tz.Nr.", "Sp.Nr.", "LISS"] if "Tz.Nr." in df.columns else ["Sp.Nr.", "LISS"]
    columns_list.extend([format_antigen(ag) for ag in sorted_selections])
    
    columns = [
        {"name": col, "id": col if col in ["Tz.Nr.", "Sp.Nr.", "LISS"] else col} 
        for col in columns_list
    ]

    # Build style_cell_conditional properly
    style_cell_conditional = [
        {"if": {"column_id": "Tz.Nr."}, "width": "50px"},
        {"if": {"column_id": "Sp.Nr."}, "width": "100px"},
        {"if": {"column_id": "LISS"}, "width": "60px"},
    ]
    
    # Add antigen column styles with proper formatting
    for ag in sorted_selections:
        formatted_ag = format_antigen(ag)
        style_cell_conditional.append({
            "if": {"column_id": formatted_ag}, 
            "width": "35px", 
            "minWidth": "35px", 
            "maxWidth": "35px"
        })

    # FIXED: Compact table style for single page fit
    return html.Div(
        [
            html.Div([
                html.P(text, style={"marginBottom": "10px", "fontWeight": "bold"}) 
                for text in antibody_text_parts
            ]),
            html.H5("Antigen-Reaktionstabelle:"),
            dash_table.DataTable(
                columns=columns,
                data=reaction_rows,
                style_table={
                    "overflowX": "auto",
                    "maxHeight": "400px",  # Fixed height to fit on screen
                    "height": "400px"
                },
                style_cell={
                    "textAlign": "center",
                    "padding": "4px",  # Compact padding
                    "fontSize": "11px",  # Smaller font
                    "height": "25px"  # Compact row height
                },
                style_header={
                    "backgroundColor": "#e3f2fd",  # Light blue background
                    "fontWeight": "bold",
                    "fontSize": "11px",
                    "height": "30px"
                },
                style_cell_conditional=style_cell_conditional,
                page_size=12,  # Fit more rows on screen
            ),
        ]
    )


def create_lab_technical_report(
    df: pd.DataFrame,
    status_map: dict,
    exclusion_reasons: dict,
    user_selections: list,
    antigen_columns: list = None,
) -> html.Div:
    """Return a Dash subtree with the lab-technical overview - FIXED: Added antibody summary, removed donor count"""

    if antigen_columns is None:
        antigen_columns = _guess_antigen_columns(df)

    # Remove Index column if it exists
    if "Index" in df.columns:
        df = df.drop(columns=["Index"])

    # Sort antigens for consistent display
    sorted_antigen_columns = sort_antigens(antigen_columns)
    sorted_user_selections = sort_antigens(user_selections)

    # FIXED: Add the same antibody summary as in medical report
    confirmed_3x = [ag for ag in sorted_user_selections if "Bestätigt (3x +)" in status_map.get(ag, "")]
    confirmed_2x = [ag for ag in sorted_user_selections if "Bestätigt (2x +)" in status_map.get(ag, "")]

    # Create antibody summary text
    antibody_summary_parts = []
    if confirmed_3x:
        formatted_3x = [f"Anti-{format_antigen(ag)}" for ag in confirmed_3x]
        antibody_summary_parts.append(
            html.P(f"3× Antikörper bestätigt: {', '.join(formatted_3x)}", 
                  style={"fontSize": "1.1em", "fontWeight": "bold", "color": "#2d6a4f"})
        )
    if confirmed_2x:
        formatted_2x = [f"Anti-{format_antigen(ag)}" for ag in confirmed_2x]
        antibody_summary_parts.append(
            html.P(f"2× Antikörper bestätigt: {', '.join(formatted_2x)}", 
                  style={"fontSize": "1.1em", "fontWeight": "bold", "color": "#52b788"})
        )
    
    if not antibody_summary_parts:
        antibody_summary_parts = [
            html.P("Keine Antikörper nachgewiesen", 
                  style={"fontSize": "1.1em", "fontWeight": "bold", "color": "#666"})
        ]

    # Count + reactions per antigen (only for *reactive* LISS rows)
    reactive_mask = df["LISS"].isin(_POSITIVE_LISS_VALUES)
    reaction_counts = {}
    for ag in sorted_antigen_columns:
        if ag not in df.columns:
            continue
        count = int((reactive_mask & (df[ag] == "+")).sum())
        reaction_counts[ag] = {
            "count": count,
            "status": status_map.get(ag, ""),
            "user_selected": ag in user_selections,
            "exclusion_reason": exclusion_reasons.get(ag, ""),
        }

    # FIXED: Apply format_antigen to summary data
    summary_data = [
        {
            "Antigen": format_antigen(ag),
            "Reaktionen": info["count"],
            "Status": info["status"],
            "Benutzerauswahl": "Ja" if info["user_selected"] else "Nein",
            "Ausschlussgrund": info["exclusion_reason"],  # FIXED: terminology
        }
        for ag, info in reaction_counts.items()
    ]

    system_selected = [ag for ag, status in status_map.items() if "Ausgeschlossen" not in status]  # FIXED: terminology
    differences = set(user_selections).symmetric_difference(system_selected)

    # DataTable conditional formatting for differences with proper formatting
    highlight_styles = [
        {
            "if": {"filter_query": f'{{Antigen}} = "{format_antigen(ag)}"'},
            "backgroundColor": "#ffeb3b",
        }
        for ag in differences
    ]

    # Create original reaction table as requested with sorted columns - FIXED: compact layout
    original_table_data = []
    for _, row in df.iterrows():
        record = {}
        if "Tz.Nr." in df.columns:
            record[" "] = row["Tz.Nr."]  # FIXED: Column name is now single space
        record["Sp.Nr."] = row.get("Sp.Nr.", "")
        record["LISS"] = row.get("LISS", "")
        # FIXED: Add antigens in sorted order with formatting
        for ag in sorted_antigen_columns:
            if ag in row:
                record[format_antigen(ag)] = row[ag]
        original_table_data.append(record)

    original_columns_list = []
    if "Tz.Nr." in df.columns:
        original_columns_list.append(" ")  # FIXED: Single space for display
    original_columns_list.extend(["Sp.Nr.", "LISS"])
    original_columns_list.extend([format_antigen(ag) for ag in sorted_antigen_columns])
    
    original_columns = [{"name": col, "id": col} for col in original_columns_list]

    # Build style_cell_conditional properly for original table
    original_style_cell_conditional = [
        {"if": {"column_id": " "}, "width": "45px"},  # FIXED: Single space column
        {"if": {"column_id": "Sp.Nr."}, "width": "90px"},
        {"if": {"column_id": "LISS"}, "width": "50px"},
    ]
    
    # Add antigen column styles with proper formatting
    for ag in sorted_antigen_columns:
        formatted_ag = format_antigen(ag)
        original_style_cell_conditional.append({
            "if": {"column_id": formatted_ag}, 
            "width": "30px", 
            "minWidth": "30px", 
            "maxWidth": "30px"
        })

    return html.Div(
        [
            # FIXED: Added antibody summary at the top
            html.Div([
                html.H5("Antikörper-Zusammenfassung:"),
                html.Div(antibody_summary_parts)
            ], style={"marginBottom": "20px", "padding": "15px", "backgroundColor": "#e3f2fd", "borderRadius": "5px"}),
            
            # REMOVED: "Anzahl getesteter Spender" line as requested
            html.P(f"System-Auswahl: {len(system_selected)} Antigene"),
            html.P(f"Benutzer-Auswahl: {len(user_selections)} Antigene"),
            html.P(
                f"Unterschiede: {len(differences)} Antigene",
                style={"color": "red"} if differences else {},
            ),
            html.H5("Antigen-Übersicht:"),
            dash_table.DataTable(
                columns=[
                    {"name": col, "id": col}
                    for col in (
                        "Antigen",
                        "Reaktionen",
                        "Status",
                        "Benutzerauswahl",
                        "Ausschlussgrund",  # FIXED: terminology
                    )
                ],
                data=summary_data,
                style_table={"overflowX": "auto", "maxHeight": "250px"},
                style_cell={"textAlign": "center", "fontSize": "11px", "padding": "4px"},
                style_header={"backgroundColor": "#e3f2fd", "fontWeight": "bold"},
                style_data_conditional=highlight_styles,
                page_size=8,
            ),
            html.H5("Original Reaktionstabelle:", style={"marginTop": "20px"}),
            dash_table.DataTable(
                columns=original_columns,
                data=original_table_data,
                style_table={
                    "overflowX": "auto",
                    "maxHeight": "300px",  # Fixed height
                    "height": "300px"
                },
                style_cell={
                    "textAlign": "center",
                    "fontSize": "10px",  # Smaller font for compact view
                    "padding": "3px",
                    "height": "22px"  # Compact rows
                },
                style_header={
                    "backgroundColor": "#e3f2fd",  # Light blue background
                    "fontWeight": "bold",
                    "fontSize": "10px",
                    "height": "25px"
                },
                style_cell_conditional=original_style_cell_conditional,
                page_size=10
            ),
        ]
    )

###############################################################################
# ───────────────────────────── PDF export helper ──────────────────────────── #
###############################################################################

def generate_pdf_report(
    df: pd.DataFrame,
    status_map: Mapping[str, str],
    exclusion_reasons: Mapping[str, str],
    user_selections: Sequence[str],
    *,
    lot_number: str = "",
) -> bytes:
    """Generate a PDF representation of the report and return its raw bytes."""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story: list = []

    styles = getSampleStyleSheet()

    # Title
    story.append(
        Paragraph(
            "Antigen Analyse Bericht",
            ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=24,
                textColor=colors.HexColor("#145da0"),
                spaceAfter=30,
            ),
        )
    )

    # Header table with lot number
    header_data = [
        ["Datum:", f"{datetime.now():%d.%m.%Y}"],
        ["Uhrzeit:", f"{datetime.now():%H:%M}"],
        ["Benutzer:", "Labor"],
        ["Lot-Nr.:", lot_number or "Nicht angegeben"],
    ]
    tbl = Table(header_data, colWidths=[3 * cm, 6 * cm])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#145da0")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]
        )
    )
    story.extend([tbl, Spacer(1, 20)])

    # FIXED: Medical section with distinct 3x and 2x findings, sorted, and properly formatted
    story.append(Paragraph("Medizinischer Bericht", styles["Heading2"]))

    sorted_selections = sort_antigens(user_selections)
    confirmed_3x = [ag for ag in sorted_selections if "Bestätigt (3x +)" in status_map.get(ag, "")]
    confirmed_2x = [ag for ag in sorted_selections if "Bestätigt (2x +)" in status_map.get(ag, "")]

    if confirmed_3x:
        # FIXED: Format antigens for PDF with proper formatting
        formatted_3x = [f"Anti-{format_antigen_for_pdf(ag)}" for ag in confirmed_3x]
        antibody_3x_text = "3+ Antikörper vorhanden: " + ", ".join(formatted_3x)
        story.append(Paragraph(antibody_3x_text, styles["Normal"]))
    
    if confirmed_2x:
        # FIXED: Format antigens for PDF with proper formatting
        formatted_2x = [f"Anti-{format_antigen_for_pdf(ag)}" for ag in confirmed_2x]
        antibody_2x_text = "2+ Antikörper vorhanden: " + ", ".join(formatted_2x)
        story.append(Paragraph(antibody_2x_text, styles["Normal"]))

    if not confirmed_3x and not confirmed_2x:
        story.append(Paragraph("Keine Antikörper nachgewiesen", styles["Normal"]))

    story.append(Spacer(1, 20))

    # FIXED: Add reaction table to PDF with proper formatting
    story.append(Paragraph("Antigen-Reaktionstabelle", styles["Heading3"]))
    
    # Build table data for PDF
    positive_liss_values = {"+/-", "1+", "2+", "3+", "4+"}
    table_data = []
    
    # Header row with properly formatted antigen names
    header_row = ["Tz.Nr.", "Sp.Nr.", "LISS"]
    header_row.extend([format_antigen_for_pdf(ag) for ag in sorted_selections])
    table_data.append(header_row)
    
    # Data rows
    for _, row in df.iterrows():
        liss_val = row.get("LISS", "-")
        if liss_val not in positive_liss_values:
            continue
            
        data_row = [
            str(row.get("Tz.Nr.", "")),
            str(row.get("Sp.Nr.", "")),
            str(liss_val)
        ]
        data_row.extend([str(row.get(ag, "")) for ag in sorted_selections])
        table_data.append(data_row)
    
    if len(table_data) > 1:  # If we have data beyond the header
        pdf_table = Table(table_data)
        pdf_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ])
        )
        story.append(pdf_table)

    story.append(Spacer(1, 20))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

###############################################################################
# ────────────────────────────── Step 2 helpers ────────────────────────────── #
###############################################################################

def create_exclusion_summary(
    exclusion_reasons: Mapping[str, str],
    system_excluded: Iterable[str],
) -> html.Div:
    """Return a summary widget listing antigens that were excluded."""

    system_excluded = set(system_excluded)
    if not system_excluded:
        return html.Div(
            "Keine Antigene wurden ausgeschlossen.",
            style={"color": "green", "fontWeight": "bold"},
        )

    # Sort excluded antigens for consistent display
    sorted_excluded = sort_antigens(list(system_excluded))
    
    items: list[html.Div] = []
    for ag in sorted_excluded:
        reason = exclusion_reasons.get(ag, "Unbekannter Grund")
        items.append(
            html.Div(
                [html.Strong(f"{format_antigen(ag)}: "), html.Span(f"Ausgeschlossen wegen {reason}")],
                className="exclusion-item",
            )
        )

    return html.Div(
        [html.H4("Zusammenfassung der ausgeschlossenen Antigene:"), html.Div(items)],
        className="exclusion-summary",
    )


def create_provisional_report(
    status_map: Mapping[str, str],
    user_selections: Sequence[str],
) -> html.Div:
    """Return the provisional findings widget for Step 2."""

    # Sort selections for consistent display
    sorted_selections = sort_antigens(user_selections)
    
    confirmed_3x = [ag for ag in sorted_selections if "Bestätigt (3x +)" in status_map.get(ag, "")]
    confirmed_2x = [ag for ag in sorted_selections if "Bestätigt (2x +)" in status_map.get(ag, "")]

    # FIXED: Create distinct reports for 2x and 3x as requested with proper formatting
    report_sections = []
    
    if confirmed_3x:
        formatted_3x = [format_antigen(ag) for ag in confirmed_3x]
        report_sections.append(
            html.P(f"3+ Antikörper vorhanden: {', '.join(formatted_3x)}", 
                  style={"fontSize": "1.1em", "fontWeight": "bold", "color": "#2d6a4f"})
        )
    
    if confirmed_2x:
        formatted_2x = [format_antigen(ag) for ag in confirmed_2x]
        report_sections.append(
            html.P(f"2+ Antikörper vorhanden: {', '.join(formatted_2x)}", 
                  style={"fontSize": "1.1em", "fontWeight": "bold", "color": "#52b788"})
        )
    
    if not confirmed_3x and not confirmed_2x:
        report_sections.append(
            html.P("Keine bestätigten Antikörper gefunden", 
                  style={"fontSize": "1.1em", "fontWeight": "bold", "color": "#666"})
        )

    children: list = [html.H4("Provisorischer Vorbefund:")] + report_sections

    return html.Div(
        children,
        style={
            "backgroundColor": "#e3f2fd",
            "padding": "15px",
            "borderRadius": "5px",
            "marginTop": "20px",
        },
    )