"""
Feature 14: Reporting Module
Generates downloadable Excel Audit Report and PDF Executive Report.
"""
from __future__ import annotations

import io
import datetime
from typing import Dict, List, Optional

import pandas as pd
import xlsxwriter


# PDF via reportlab — imported lazily to avoid crash if not installed
def _get_reportlab():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak,
    )
    return dict(
        A4=A4, getSampleStyleSheet=getSampleStyleSheet,
        ParagraphStyle=ParagraphStyle, cm=cm, colors=colors,
        SimpleDocTemplate=SimpleDocTemplate, Paragraph=Paragraph,
        Spacer=Spacer, Table=Table, TableStyle=TableStyle,
        HRFlowable=HRFlowable, PageBreak=PageBreak,
    )


# ---------------------------------------------------------------------------
# Excel Report
# ---------------------------------------------------------------------------

def generate_excel_report(
    filename: str,
    workbook_risk,          # WorkbookRiskReport
    sheet_analyses: Dict,   # sheet_name -> dict of analysis results
    recommendations,        # List[Recommendation]
) -> bytes:
    """Return Excel workbook bytes for the audit report."""
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {"in_memory": True})

    # Formats
    title_fmt = wb.add_format({"bold": True, "font_size": 16, "bg_color": "#1565C0", "font_color": "white"})
    header_fmt = wb.add_format({"bold": True, "bg_color": "#1976D2", "font_color": "white", "border": 1})
    critical_fmt = wb.add_format({"bg_color": "#FFCDD2", "bold": True, "border": 1})
    high_fmt = wb.add_format({"bg_color": "#FFE0B2", "border": 1})
    medium_fmt = wb.add_format({"bg_color": "#FFF9C4", "border": 1})
    low_fmt = wb.add_format({"bg_color": "#C8E6C9", "border": 1})
    cell_fmt = wb.add_format({"border": 1})
    pct_fmt = wb.add_format({"num_format": "0.0%", "border": 1})
    num_fmt = wb.add_format({"num_format": "#,##0.00", "border": 1})

    sev_fmt = {"CRITICAL": critical_fmt, "HIGH": high_fmt, "MEDIUM": medium_fmt, "LOW": low_fmt}

    # ---- Sheet 1: Executive Summary ----
    ws = wb.add_worksheet("Executive Summary")
    ws.set_column("A:A", 30)
    ws.set_column("B:B", 20)
    ws.set_column("C:C", 50)

    ws.merge_range("A1:C1", "BDX Integrity Checker — Audit Report", title_fmt)
    ws.write("A2", f"File: {filename}", wb.add_format({"italic": True}))
    ws.write("A3", f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", wb.add_format({"italic": True}))
    ws.write("A5", "Overall Risk Level", header_fmt)
    ws.write("B5", workbook_risk.workbook_risk, sev_fmt.get(workbook_risk.workbook_risk, cell_fmt))
    ws.write("A6", "Workbook Integrity Score", header_fmt)
    ws.write("B6", f"{workbook_risk.workbook_score}/100", cell_fmt)

    row = 8
    ws.write(row, 0, "Sheet", header_fmt)
    ws.write(row, 1, "Score", header_fmt)
    ws.write(row, 2, "Risk Level", header_fmt)
    ws.write(row, 3, "Critical", header_fmt)
    ws.write(row, 4, "High", header_fmt)
    ws.write(row, 5, "Medium", header_fmt)
    row += 1
    for sname, rs in workbook_risk.sheet_scores.items():
        fmt = sev_fmt.get(rs.risk_level, cell_fmt)
        ws.write(row, 0, sname, cell_fmt)
        ws.write(row, 1, rs.overall_score, cell_fmt)
        ws.write(row, 2, rs.risk_level, fmt)
        ws.write(row, 3, rs.critical_count, critical_fmt if rs.critical_count else cell_fmt)
        ws.write(row, 4, rs.high_count, high_fmt if rs.high_count else cell_fmt)
        ws.write(row, 5, rs.medium_count, medium_fmt if rs.medium_count else cell_fmt)
        row += 1

    # ---- Sheet 2: Blank Column Findings ----
    ws2 = wb.add_worksheet("Blank Column Findings")
    ws2.set_column("A:A", 20)
    ws2.set_column("B:B", 12)
    ws2.set_column("C:C", 20)
    ws2.set_column("D:D", 12)
    ws2.set_column("E:E", 60)

    ws2.merge_range("A1:E1", "Blank Column Findings", title_fmt)
    headers = ["Sheet", "Column", "Header", "Risk Level", "Description"]
    for ci, h in enumerate(headers):
        ws2.write(1, ci, h, header_fmt)

    r = 2
    for sname, analysis in sheet_analyses.items():
        for finding in analysis.get("blank_findings", []):
            fmt = sev_fmt.get(finding.risk_level, cell_fmt)
            ws2.write(r, 0, finding.sheet_name, cell_fmt)
            ws2.write(r, 1, finding.col_letter, cell_fmt)
            ws2.write(r, 2, finding.col_header or "", cell_fmt)
            ws2.write(r, 3, finding.risk_level, fmt)
            ws2.write(r, 4, finding.description, cell_fmt)
            r += 1
    if r == 2:
        ws2.write(r, 0, "No blank column issues detected.", wb.add_format({"italic": True, "font_color": "#388e3c"}))

    # ---- Sheet 3: Policy Findings ----
    ws3 = wb.add_worksheet("Policy Findings")
    ws3.set_column("A:A", 20)
    ws3.set_column("B:B", 22)
    ws3.set_column("C:C", 12)
    ws3.set_column("D:D", 10)
    ws3.set_column("E:E", 60)

    ws3.merge_range("A1:E1", "Policy Integrity Findings", title_fmt)
    headers3 = ["Sheet", "Finding Type", "Severity", "Count", "Description"]
    for ci, h in enumerate(headers3):
        ws3.write(1, ci, h, header_fmt)

    r = 2
    for sname, analysis in sheet_analyses.items():
        for pf in analysis.get("policy_findings", []):
            fmt = sev_fmt.get(pf.severity, cell_fmt)
            ws3.write(r, 0, sname, cell_fmt)
            ws3.write(r, 1, pf.finding_type, cell_fmt)
            ws3.write(r, 2, pf.severity, fmt)
            ws3.write(r, 3, pf.count, cell_fmt)
            ws3.write(r, 4, pf.description[:200], cell_fmt)
            r += 1
    if r == 2:
        ws3.write(r, 0, "No policy integrity issues detected.", wb.add_format({"italic": True, "font_color": "#388e3c"}))

    # ---- Sheet 4: Recommendations ----
    ws4 = wb.add_worksheet("Recommendations")
    ws4.set_column("A:A", 8)
    ws4.set_column("B:B", 12)
    ws4.set_column("C:C", 18)
    ws4.set_column("D:D", 35)
    ws4.set_column("E:E", 50)

    ws4.merge_range("A1:E1", "Recommendations", title_fmt)
    headers4 = ["Priority", "Severity", "Category", "Title", "Action"]
    for ci, h in enumerate(headers4):
        ws4.write(1, ci, h, header_fmt)

    for ri, rec in enumerate(recommendations):
        fmt = sev_fmt.get(rec.severity, cell_fmt)
        ws4.write(ri + 2, 0, rec.priority, cell_fmt)
        ws4.write(ri + 2, 1, rec.severity, fmt)
        ws4.write(ri + 2, 2, rec.category, cell_fmt)
        ws4.write(ri + 2, 3, rec.title, cell_fmt)
        ws4.write(ri + 2, 4, rec.action, cell_fmt)

    wb.close()
    return output.getvalue()


# ---------------------------------------------------------------------------
# PDF Report
# ---------------------------------------------------------------------------

def generate_pdf_report(
    filename: str,
    workbook_risk,
    sheet_analyses: Dict,
    recommendations,
) -> bytes:
    """Return PDF bytes for the executive report."""
    rl = _get_reportlab()
    output = io.BytesIO()

    doc = rl["SimpleDocTemplate"](
        output,
        pagesize=rl["A4"],
        rightMargin=2 * rl["cm"],
        leftMargin=2 * rl["cm"],
        topMargin=2.5 * rl["cm"],
        bottomMargin=2 * rl["cm"],
    )

    styles = rl["getSampleStyleSheet"]()
    elements = []

    # Title
    title_style = rl["ParagraphStyle"](
        "title", parent=styles["Title"],
        textColor=rl["colors"].HexColor("#1565C0"),
        fontSize=20, spaceAfter=12,
    )
    elements.append(rl["Paragraph"]("BDX Integrity Checker", title_style))
    elements.append(rl["Paragraph"]("Executive Audit Report", title_style))
    elements.append(rl["Spacer"](1, 0.3 * rl["cm"]))

    h2 = rl["ParagraphStyle"]("h2", parent=styles["Heading2"], textColor=rl["colors"].HexColor("#1565C0"))
    body = styles["Normal"]

    elements.append(rl["Paragraph"](f"<b>File:</b> {filename}", body))
    elements.append(rl["Paragraph"](
        f"<b>Generated:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", body
    ))
    elements.append(rl["Spacer"](1, 0.5 * rl["cm"]))

    # Executive Summary
    elements.append(rl["Paragraph"]("Executive Summary", h2))
    elements.append(rl["HRFlowable"](width="100%", color=rl["colors"].HexColor("#1565C0")))
    elements.append(rl["Spacer"](1, 0.2 * rl["cm"]))

    risk_color_map = {
        "CRITICAL": rl["colors"].HexColor("#d32f2f"),
        "HIGH": rl["colors"].HexColor("#f57c00"),
        "MEDIUM": rl["colors"].HexColor("#fbc02d"),
        "LOW": rl["colors"].HexColor("#388e3c"),
    }

    summary_data = [
        ["Metric", "Value"],
        ["Overall Risk Level", workbook_risk.workbook_risk],
        ["Integrity Score", f"{workbook_risk.workbook_score}/100"],
        ["Sheets Analysed", str(len(workbook_risk.sheet_scores))],
        ["Critical Findings", str(sum(rs.critical_count for rs in workbook_risk.sheet_scores.values()))],
        ["High Findings", str(sum(rs.high_count for rs in workbook_risk.sheet_scores.values()))],
    ]
    tbl = rl["Table"](summary_data, colWidths=[8 * rl["cm"], 8 * rl["cm"]])
    tbl.setStyle(rl["TableStyle"]([
        ("BACKGROUND", (0, 0), (-1, 0), rl["colors"].HexColor("#1976D2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl["colors"].white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, rl["colors"].grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl["colors"].white, rl["colors"].HexColor("#EEF2FF")]),
    ]))
    elements.append(tbl)
    elements.append(rl["Spacer"](1, 0.5 * rl["cm"]))

    # Blank Column Findings
    elements.append(rl["Paragraph"]("Blank Column Findings", h2))
    elements.append(rl["HRFlowable"](width="100%", color=rl["colors"].HexColor("#1565C0")))
    elements.append(rl["Spacer"](1, 0.2 * rl["cm"]))

    found_blanks = False
    for sname, analysis in sheet_analyses.items():
        for bf in analysis.get("blank_findings", []):
            found_blanks = True
            elements.append(rl["Paragraph"](
                f"<b>Sheet:</b> {bf.sheet_name} | <b>Column:</b> {bf.col_letter} | "
                f"<b>Header:</b> {bf.col_header or 'N/A'} | <b>Risk:</b> {bf.risk_level}",
                body,
            ))
            elements.append(rl["Paragraph"](bf.description, body))
            elements.append(rl["Spacer"](1, 0.2 * rl["cm"]))

    if not found_blanks:
        elements.append(rl["Paragraph"]("No blank column issues detected.", body))

    elements.append(rl["PageBreak"]())

    # Recommendations
    elements.append(rl["Paragraph"]("Recommendations", h2))
    elements.append(rl["HRFlowable"](width="100%", color=rl["colors"].HexColor("#1565C0")))
    elements.append(rl["Spacer"](1, 0.2 * rl["cm"]))

    for rec in recommendations[:15]:
        elements.append(rl["Paragraph"](
            f"<b>[{rec.severity}] {rec.title}</b>", body
        ))
        elements.append(rl["Paragraph"](f"Action: {rec.action}", body))
        elements.append(rl["Spacer"](1, 0.15 * rl["cm"]))

    doc.build(elements)
    return output.getvalue()
