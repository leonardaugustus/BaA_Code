# navigation_and_step4_fixed.py

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
    "A": "ᴬ", "B": "ᴮ", "C": "ᶜ", "D": "ᴰ", "E": "ᴱ", "F": "ᶠ", "G": "ᴳ",
    "H": "ᴴ", "I": "ᴵ", "J": "ᴶ", "K": "ᴷ", "L": "ᴸ", "M": "ᴹ", "N": "ᴺ",
    "O": "ᴼ", "P": "ᴾ", "R": "ᴿ", "T": "ᵀ", "U": "ᵁ", "V": "ⱽ", "W": "ᵂ",
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ", "g": "ᵍ",
    "h": "ʰ", "i": "ⁱ", "j": "ʲ", "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ",
    "o": "ᵒ", "p": "ᵖ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ", "v": "ᵛ",
    "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ",
}

_POSITIVE_LISS_VALUES: set[str] = {"+/-", "1+", "2+", "3+", "4+"}

###############################################################################
# ────────────────────────────── Navigation bar ────────────────────────────── #
###############################################################################

def format_antigen(antigen: str) -> str:  # noqa: D401 – simple function
    """Return an antigen name with the last letter rendered as superscript."""
    return antigen if len(antigen) <= 1 else antigen[:-1] + _SUPERSCRIPT_MAP.get(antigen[-1], antigen[-1])


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
    ignored = {"Spender", "LISS"}
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

    confirmed_antigens = [
        ag for ag in user_selections if "Bestätigt" in status_map.get(ag, "")
    ]

    antibody_text = (
        "Folgende Antikörper wurden nachgewiesen: "
        + ", ".join(f"Anti-{ag}" for ag in confirmed_antigens)
        if confirmed_antigens
        else "Keine Antikörper nachgewiesen"
    )

    # Build the reaction table – include only rows that have a LISS value
    reaction_rows: list[dict[str, str]] = []
    for _, row in df.iterrows():
        if (liss_val := row.get("LISS", "-")) == "-":
            continue
        record = {"Spender": row.get("Spender", ""), "LISS": liss_val}
        for ag in user_selections:
            if ag in row:
                record[ag] = row[ag]
        reaction_rows.append(record)

    # Dash DataTable definition
    columns = [
        {"name": col, "id": col} for col in (["Spender", "LISS"] + list(user_selections))
    ]

    return html.Div(
        [
            html.P(antibody_text, style={"marginBottom": "20px"}),
            html.H5("Antigen-Reaktionstabelle:"),
            dash_table.DataTable(
                columns=columns,
                data=reaction_rows,
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "center"},
                style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
            ),
        ]
    )


def create_lab_technical_report(
    df: pd.DataFrame,
    status_map: Mapping[str, str],
    exclusion_reasons: Mapping[str, str],
    user_selections: Sequence[str],
    antigen_columns: Sequence[str] | None = None,
) -> html.Div:
    """Return a Dash subtree with the lab-technical overview."""

    if antigen_columns is None:
        antigen_columns = _guess_antigen_columns(df)

    # Count + reactions per antigen (only for *reactive* LISS rows)
    reactive_mask = df["LISS"].isin(_POSITIVE_LISS_VALUES)
    reaction_counts: dict[str, dict[str, object]] = {}
    for ag in antigen_columns:
        if ag not in df.columns:
            continue
        count = int((reactive_mask & (df[ag] == "+")).sum())
        reaction_counts[ag] = {
            "count": count,
            "status": status_map.get(ag, ""),
            "user_selected": ag in user_selections,
            "exclusion_reason": exclusion_reasons.get(ag, ""),
        }

    summary_data = [
        {
            "Antigen": ag,
            "Reaktionen": info["count"],
            "Status": info["status"],
            "Benutzerauswahl": "Ja" if info["user_selected"] else "Nein",
            "Ausschlussgrund": info["exclusion_reason"],
        }
        for ag, info in reaction_counts.items()
    ]

    system_selected = [ag for ag, status in status_map.items() if "Ausgestrichen" not in status]
    differences = set(user_selections).symmetric_difference(system_selected)

    # DataTable conditional formatting for differences
    highlight_styles = [
        {
            "if": {"filter_query": f'{{Antigen}} = "{ag}"'},
            "backgroundColor": "#ffeb3b",
        }
        for ag in differences
    ]

    return html.Div(
        [
            html.P(f"Anzahl getesteter Spender: {len(df)}"),
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
                        "Ausschlussgrund",
                    )
                ],
                data=summary_data,
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "center"},
                style_header={"backgroundColor": "#f8f9fa", "fontWeight": "bold"},
                style_data_conditional=highlight_styles,
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

    # Header table
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

    # Medical section
    story.append(Paragraph("Medizinischer Bericht", styles["Heading2"]))

    confirmed = [ag for ag in user_selections if "Bestätigt" in status_map.get(ag, "")]
    antibody_text = (
        "Folgende Antikörper wurden nachgewiesen: "
        + ", ".join(f"Anti-{ag}" for ag in confirmed)
        if confirmed
        else "Keine Antikörper nachgewiesen"
    )
    story.extend([Paragraph(antibody_text, styles["Normal"]), Spacer(1, 20)])

    # TODO: add detailed reaction tables, graphs etc. if required by lab SOP

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

    items: list[html.Div] = []
    for ag in sorted(system_excluded):
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

    confirmed_3x = [ag for ag in user_selections if "Bestätigt (3x +)" in status_map.get(ag, "")]
    confirmed_2x = [ag for ag in user_selections if "Bestätigt (2x +)" in status_map.get(ag, "")]

    confirmed = confirmed_3x + confirmed_2x
    report_text = (
        "Bestätigt (2× + und 3× +): " + ", ".join(confirmed)
        if confirmed
        else "Keine bestätigten Antigene gefunden"
    )

    # Placeholder for future deprecation warnings if certain antigens require it
    deprecation_warning = ""

    children: list = [
        html.H4("Provisorischer Vorbefund:"),
        html.P(report_text, style={"fontSize": "1.1em", "fontWeight": "bold"}),
    ]
    if deprecation_warning:
        children.append(html.P(deprecation_warning, style={"color": "orange"}))

    return html.Div(
        children,
        style={
            "backgroundColor": "#e3f2fd",
            "padding": "15px",
            "borderRadius": "5px",
            "marginTop": "20px",
        },
    )
