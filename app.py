"""
BDX Integrity Checker — Main Streamlit Application
"""
from __future__ import annotations

import io
import traceback
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.file_handler import (
    WorkbookInfo, load_workbook_info, load_sheet_dataframe, get_column_letter,
)
from modules.column_detector import detect_columns, confidence_label
from modules.blank_column_detector import detect_blank_columns, DataRegionReport
from modules.excel_table_validator import validate_excel_tables
from modules.signature_engine import add_signatures, find_duplicate_signatures
from modules.policy_validator import validate_policies, build_policy_summary
from modules.sort_simulator import simulate_sort_corruption
from modules.reconciliation import build_reconciliation_report, format_currency
from modules.tieout_engine import run_tieout
from modules.risk_scorer import score_sheet, score_workbook, risk_color, score_badge
from modules.recommendations import generate_recommendations
from modules.reporter import generate_excel_report, generate_pdf_report
from modules.sample_data import create_sample_workbook

# ── Page config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BDX Integrity Checker",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.risk-badge-CRITICAL{background:#d32f2f;color:#fff;padding:3px 10px;border-radius:4px;font-weight:bold}
.risk-badge-HIGH{background:#f57c00;color:#fff;padding:3px 10px;border-radius:4px;font-weight:bold}
.risk-badge-MEDIUM{background:#fbc02d;color:#000;padding:3px 10px;border-radius:4px;font-weight:bold}
.risk-badge-LOW{background:#388e3c;color:#fff;padding:3px 10px;border-radius:4px;font-weight:bold}
.kpi-box{background:#1565C0;color:#fff;border-radius:8px;padding:12px 16px;text-align:center;margin:4px}
.kpi-value{font-size:28px;font-weight:bold}
.kpi-label{font-size:12px;opacity:0.85}
.finding-row{border-left:4px solid #d32f2f;padding:8px 12px;margin:6px 0;background:#fff5f5;border-radius:4px}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# Helper / utility functions  (defined BEFORE the routing if/elif chain)
# ══════════════════════════════════════════════════════════════════════════

def _reset_analysis():
    for k in [
        "df_raw", "df_with_sig", "blank_findings", "region_report",
        "table_result", "policy_findings", "sort_sim", "recon_report",
        "tieout_report", "sheet_risk", "workbook_risk", "recommendations",
        "detected_cols", "sheet_analyses",
    ]:
        st.session_state.pop(k, None)


def _run_full_analysis(wb_info: WorkbookInfo, sheet_name: str, df_raw: pd.DataFrame):
    key_fields = st.session_state.get("key_fields", [])
    financial_fields = st.session_state.get("financial_fields", [])

    with st.spinner("Running integrity check…"):
        prog = st.progress(0)

        prog.progress(10)
        blank_findings, region_report = detect_blank_columns(wb_info.workbook, sheet_name, df_raw)
        st.session_state["blank_findings"] = blank_findings
        st.session_state["region_report"] = region_report

        prog.progress(20)
        table_result = validate_excel_tables(wb_info.workbook, sheet_name)
        st.session_state["table_result"] = table_result

        prog.progress(30)
        detected = detect_columns(df_raw)
        st.session_state["detected_cols"] = detected

        if not key_fields and detected["policy_id"]:
            st.session_state["key_fields"] = [detected["policy_id"][0].column_name]
        if not financial_fields and detected["financial"]:
            st.session_state["financial_fields"] = [m.column_name for m in detected["financial"][:3]]

        key_fields = st.session_state.get("key_fields", [])
        financial_fields = st.session_state.get("financial_fields", [])

        prog.progress(40)
        df_with_sig = add_signatures(df_raw, key_fields, financial_fields) if (key_fields or financial_fields) else df_raw.copy()
        st.session_state["df_with_sig"] = df_with_sig

        prog.progress(55)
        policy_findings, _ = validate_policies(df_with_sig, key_fields, financial_fields)
        st.session_state["policy_findings"] = policy_findings

        prog.progress(65)
        sort_sim = simulate_sort_corruption(df_with_sig, region_report, key_fields, financial_fields)
        st.session_state["sort_sim"] = sort_sim

        prog.progress(75)
        recon = build_reconciliation_report(df_with_sig, key_fields, financial_fields, sheet_name)
        st.session_state["recon_report"] = recon

        prog.progress(85)
        tieout = run_tieout(df_with_sig, key_fields, financial_fields, sheet_name)
        st.session_state["tieout_report"] = tieout

        prog.progress(92)
        sheet_risk = score_sheet(sheet_name, blank_findings, region_report, table_result, policy_findings, sort_sim, tieout)
        st.session_state["sheet_risk"] = sheet_risk
        workbook_risk = score_workbook(wb_info.filename, {sheet_name: sheet_risk})
        st.session_state["workbook_risk"] = workbook_risk

        recs = generate_recommendations(blank_findings, region_report, table_result, policy_findings, sort_sim, tieout)
        st.session_state["recommendations"] = recs
        st.session_state["sheet_analyses"] = {
            sheet_name: {"blank_findings": blank_findings, "policy_findings": policy_findings,
                         "sort_sim": sort_sim, "tieout": tieout}
        }
        prog.progress(100)
        prog.empty()


def _show_feature_overview():
    st.markdown("---")
    st.subheader("What this tool checks")
    cols = st.columns(3)
    features = [
        ("⬜", "Blank Column Detection", "Identifies blank columns that split data regions and cause partial sort corruption."),
        ("📊", "Data Region Analysis", "Maps populated vs blank columns and shows the affected range."),
        ("🔀", "Sort Corruption Simulation", "Simulates partial sorts and estimates how many rows are corrupted."),
        ("✅", "Policy Validation", "Checks for missing keys, duplicates, and blank financial values."),
        ("🔗", "Tie-Out Engine", "Builds policy-to-value maps and detects conflicting amounts."),
        ("📄", "Audit Reports", "Generates downloadable Excel and PDF audit reports."),
    ]
    for i, (icon, title, desc) in enumerate(features):
        with cols[i % 3]:
            st.markdown(f"**{icon} {title}**\n\n{desc}")


def _render_column_map(region_report: DataRegionReport, df_raw: pd.DataFrame):
    all_cols = list(df_raw.columns)
    n = len(all_cols)
    if n == 0:
        return
    blank_set = set(region_report.blank_columns)
    colors_list, hover_list, text_list = [], [], []
    for i, col in enumerate(all_cols):
        letter = get_column_letter(i)
        if letter in blank_set:
            colors_list.append("#d32f2f")
            hover_list.append(f"<b>BLANK</b>: {letter}<br>Header: {col or 'empty'}")
            text_list.append("⬜")
        else:
            colors_list.append("#1976D2")
            hover_list.append(f"{letter}: {col}")
            text_list.append("")
    fig = go.Figure(go.Bar(
        x=list(range(n)), y=[1] * n,
        marker_color=colors_list, hovertext=hover_list, hoverinfo="text", text=text_list,
    ))
    fig.update_layout(
        title="Column Liveness Map (Blue = Populated, Red = Blank)",
        height=150, showlegend=False,
        yaxis=dict(visible=False),
        xaxis=dict(title="Column Index", tickvals=list(range(0, n, max(1, n // 20)))),
        margin=dict(l=0, r=0, t=40, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_region_chart(region_report: DataRegionReport):
    labels = ["Worksheet"]
    parents = [""]
    values = [region_report.total_columns]
    colors = ["#1565C0"]
    for i, reg in enumerate(region_report.regions, 1):
        labels.append(f"Region {i}: {reg['start']}:{reg['end']}")
        parents.append("Worksheet")
        values.append(reg["count"])
        colors.append("#388e3c" if i == 1 else "#d32f2f")
    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values,
        marker_colors=colors, textinfo="label+value",
    ))
    fig.update_layout(title="Data Region Map (green = safe, red = at risk)", height=300)
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("BDX Integrity Checker")
    st.caption("Version 1.0 | Production Ready")
    st.divider()

    page = st.radio(
        "Navigation",
        [
            "📂 Upload & Configure",
            "🔍 Column Detection",
            "⬜ Blank Column Analysis",
            "📊 Data Region Analysis",
            "📋 Excel Table Check",
            "🔐 Row Signatures",
            "✅ Policy Validation",
            "🔀 Sort Simulation",
            "💰 Reconciliation",
            "🔗 Tie-Out Engine",
            "🎯 Risk Dashboard",
            "📄 Reports",
        ],
        key="nav_page",
    )
    st.divider()

    if st.button("⬇ Download Sample BDX", use_container_width=True):
        sample_bytes = create_sample_workbook()
        st.download_button(
            "💾 Save sample_bdx.xlsx",
            data=sample_bytes,
            file_name="sample_bdx.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ══════════════════════════════════════════════════════════════════════════
# Page routing — single if/elif chain with no interleaved defs
# ══════════════════════════════════════════════════════════════════════════

# ── UPLOAD & CONFIGURE ────────────────────────────────────────────────────
if page == "📂 Upload & Configure":
    st.header("📂 Upload & Configure")
    st.markdown(
        "Upload a BDX (bordereau) XLSX file. The tool will analyse its structure "
        "and identify risks that could cause sorting or filtering corruption."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded = st.file_uploader(
            "Upload XLSX file", type=["xlsx"],
            help="Supports files with 100,000+ rows. Multiple worksheets supported.",
        )
    with col2:
        st.info("**Supported formats**\n- .xlsx (Excel 2007+)\n- Multiple worksheets\n- Up to 100,000+ rows")

    if uploaded:
        if "wb_info" not in st.session_state or st.session_state.get("uploaded_filename") != uploaded.name:
            _reset_analysis()
            with st.spinner("Loading workbook structure…"):
                try:
                    wb_info = load_workbook_info(uploaded)
                    st.session_state["wb_info"] = wb_info
                    st.session_state["uploaded_file"] = uploaded
                    st.session_state["uploaded_filename"] = uploaded.name
                    st.success(f"✅ Loaded **{uploaded.name}** — {len(wb_info.sheet_names)} sheet(s)")
                except Exception as e:
                    st.error(f"Failed to load file: {e}")
                    st.stop()

        wb_info: WorkbookInfo = st.session_state["wb_info"]

        st.subheader("Select Worksheet")
        sheet_options = [f"{n} ({wb_info.sheets[n].row_count:,} rows)" for n in wb_info.sheet_names]
        sel_idx = st.selectbox("Worksheet", range(len(wb_info.sheet_names)),
                               format_func=lambda i: sheet_options[i], key="selected_sheet_idx")
        selected_sheet = wb_info.sheet_names[sel_idx]

        if st.session_state.get("active_sheet") != selected_sheet:
            _reset_analysis()
            st.session_state["active_sheet"] = selected_sheet

        if "df_raw" not in st.session_state:
            prog_bar = st.progress(0)
            status_txt = st.empty()

            def _progress(pct, msg):
                prog_bar.progress(pct)
                status_txt.text(msg)

            try:
                df_raw, _ = load_sheet_dataframe(
                    st.session_state["uploaded_file"], selected_sheet, progress_callback=_progress
                )
                st.session_state["df_raw"] = df_raw
                prog_bar.empty(); status_txt.empty()
            except Exception as e:
                st.error(f"Error reading sheet: {e}")
                st.stop()

        df_raw: pd.DataFrame = st.session_state["df_raw"]
        st.success(f"Sheet **{selected_sheet}**: {len(df_raw):,} rows × {len(df_raw.columns)} columns")

        with st.expander("📋 Data Preview (first 50 rows)", expanded=True):
            st.dataframe(df_raw.head(50), use_container_width=True, height=300)

        st.subheader("Run Analysis")
        if st.button("🚀 Run Full Integrity Check", type="primary", use_container_width=True):
            _run_full_analysis(wb_info, selected_sheet, df_raw)
            st.success("✅ Analysis complete. Navigate the pages to explore results.")
    else:
        st.info("👆 Upload a BDX file above, or download the sample workbook from the sidebar.")
        _show_feature_overview()

# ── COLUMN DETECTION ─────────────────────────────────────────────────────
elif page == "🔍 Column Detection":
    st.header("🔍 Automatic Column Detection & Mapping")

    df_raw = st.session_state.get("df_raw")
    if df_raw is None:
        st.warning("Upload a file first.")
        st.stop()

    detected = st.session_state.get("detected_cols") or detect_columns(df_raw)
    st.session_state["detected_cols"] = detected

    st.markdown("Column headers were scored against known bordereau patterns. Review and adjust below.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Policy / Key Fields")
        if detected["policy_id"]:
            df_pol = pd.DataFrame([
                {"Column": m.column_name, "Confidence": f"{m.confidence}%",
                 "Level": confidence_label(m.confidence), "Sample": str(m.sample_values[:2])}
                for m in detected["policy_id"][:8]
            ])
            st.dataframe(df_pol, use_container_width=True, hide_index=True)

        default_keys = [detected["policy_id"][0].column_name] if detected["policy_id"] else []
        saved_keys = st.session_state.get("key_fields", default_keys)
        key_fields = st.multiselect(
            "Select Key Field(s)", options=list(df_raw.columns),
            default=[k for k in saved_keys if k in df_raw.columns],
            help="Columns that uniquely identify each policy.",
        )
        st.session_state["key_fields"] = key_fields

    with col2:
        st.subheader("Financial Fields")
        if detected["financial"]:
            df_fin = pd.DataFrame([
                {"Column": m.column_name, "Confidence": f"{m.confidence}%",
                 "Level": confidence_label(m.confidence)}
                for m in detected["financial"][:8]
            ])
            st.dataframe(df_fin, use_container_width=True, hide_index=True)

        default_fin = [m.column_name for m in detected["financial"][:4]]
        saved_fin = st.session_state.get("financial_fields", default_fin)
        financial_fields = st.multiselect(
            "Select Financial Field(s)", options=list(df_raw.columns),
            default=[f for f in saved_fin if f in df_raw.columns],
            help="Numeric columns containing premiums, commissions, or other values.",
        )
        st.session_state["financial_fields"] = financial_fields

    st.divider()
    st.subheader("All Columns — Confidence Overview")
    all_col_data = []
    for cat, matches in detected.items():
        for m in matches:
            all_col_data.append({"Column": m.column_name, "Category": cat.replace("_", " ").title(),
                                  "Confidence": m.confidence})
    if all_col_data:
        df_all = pd.DataFrame(all_col_data)
        top = df_all[df_all["Confidence"] > 0].sort_values("Confidence", ascending=False).head(20)
        if not top.empty:
            fig = px.bar(top, x="Column", y="Confidence", color="Category",
                         title="Column Detection Confidence Scores",
                         labels={"Confidence": "Confidence (%)"})
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

# ── BLANK COLUMN ANALYSIS ─────────────────────────────────────────────────
elif page == "⬜ Blank Column Analysis":
    st.header("⬜ Blank Column Detection")

    df_raw = st.session_state.get("df_raw")
    wb_info = st.session_state.get("wb_info")
    if df_raw is None or wb_info is None:
        st.warning("Upload and process a file first.")
        st.stop()

    sheet_name = st.session_state.get("active_sheet", wb_info.sheet_names[0])
    blank_findings = st.session_state.get("blank_findings")
    region_report = st.session_state.get("region_report")

    if blank_findings is None:
        with st.spinner("Scanning for blank columns…"):
            blank_findings, region_report = detect_blank_columns(wb_info.workbook, sheet_name, df_raw)
            st.session_state["blank_findings"] = blank_findings
            st.session_state["region_report"] = region_report

    if not blank_findings:
        st.success("✅ No internal blank columns detected. The data range appears contiguous.")
    else:
        st.error(f"🚨 {len(blank_findings)} blank column(s) found that split the data region.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Columns", region_report.total_columns)
    c2.metric("Populated Columns", len(region_report.populated_columns))
    c3.metric("Blank Columns", len(region_report.blank_columns))
    c4.metric("Internal Splits", region_report.internal_blank_count)

    for f in blank_findings:
        st.markdown(
            f'<div class="finding-row"><b>🚨 {f.risk_level}: Column {f.col_letter}</b>'
            f'{f" — Header: <i>{f.col_header}</i>" if f.col_header else ""}'
            f"<br/>{f.description}</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"Before: {', '.join(f.populated_before)} | After: {', '.join(f.populated_after)}")

    st.subheader("Column Map Visualisation")
    _render_column_map(region_report, df_raw)

# ── DATA REGION ANALYSIS ──────────────────────────────────────────────────
elif page == "📊 Data Region Analysis":
    st.header("📊 Data Region Integrity Analysis")

    region_report = st.session_state.get("region_report")
    if region_report is None:
        st.warning("Run blank column analysis first.")
        st.stop()

    st.subheader(f"Region Analysis — {region_report.sheet_name}")

    if region_report.regions:
        st.markdown(f"**{len(region_report.regions)} contiguous data region(s) detected:**")
        for i, reg in enumerate(region_report.regions, 1):
            label = "⚠️ Potentially excluded from partial sorts" if i > 1 else "✅ Primary data region"
            with st.expander(f"Region {i}: {reg['start']}:{reg['end']} — {reg['count']} columns {label}"):
                st.write(f"**Columns:** {', '.join(reg['cols'][:20])}{'…' if len(reg['cols']) > 20 else ''}")
                if i > 1:
                    st.error(
                        f"**WARNING:** Columns {reg['start']}:{reg['end']} may not move during "
                        "sorting if a user sorts only the detected primary region."
                    )
    else:
        st.success("Data appears as a single contiguous region — no split risk detected.")

    if region_report.affected_region:
        ar = region_report.affected_region
        st.error(
            f"**Affected Region:** {ar['start']}:{ar['end']} "
            f"({ar['count']} columns) may not move during Excel sort operations."
        )

    if region_report.split_points:
        st.subheader("Split Points")
        for sp in region_report.split_points:
            st.markdown(f"- Column **{sp}** — blank, acts as data boundary")

    if len(region_report.regions) >= 2:
        _render_region_chart(region_report)

# ── EXCEL TABLE CHECK ─────────────────────────────────────────────────────
elif page == "📋 Excel Table Check":
    st.header("📋 Excel Table Validation")

    table_result = st.session_state.get("table_result")
    wb_info = st.session_state.get("wb_info")
    if table_result is None:
        if wb_info is None:
            st.warning("Upload a file first.")
            st.stop()
        sheet_name = st.session_state.get("active_sheet", wb_info.sheet_names[0])
        table_result = validate_excel_tables(wb_info.workbook, sheet_name)
        st.session_state["table_result"] = table_result

    if table_result.has_table:
        st.success(f"✅ {table_result.message}")
        for tbl in table_result.tables:
            with st.expander(f"Table: {tbl.table_name}"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Table Name", tbl.table_name)
                c2.metric("Range", tbl.table_range)
                c3.metric("Columns", tbl.col_count)
    else:
        st.warning(f"⚠️ {table_result.message}")

    st.divider()
    st.markdown(f'**Risk Level:** <span class="risk-badge-{table_result.risk_level}">{table_result.risk_level}</span>',
                unsafe_allow_html=True)
    st.subheader("Recommendation")
    st.info(f"💡 {table_result.recommendation}")

# ── ROW SIGNATURES ────────────────────────────────────────────────────────
elif page == "🔐 Row Signatures":
    st.header("🔐 Row Integrity Signature Engine")

    df_raw = st.session_state.get("df_raw")
    if df_raw is None:
        st.warning("Upload a file first.")
        st.stop()

    key_fields = st.session_state.get("key_fields", [])
    financial_fields = st.session_state.get("financial_fields", [])

    if not key_fields and not financial_fields:
        st.info("Configure key and financial fields on the Column Detection page first.")
        st.stop()

    st.markdown(
        "Each row receives a **SHA-256 hash** computed from the selected key and financial fields. "
        "Rows with identical hashes are exact duplicates. After sorting, hash comparison reveals corruption."
    )
    st.markdown(f"**Key fields:** {', '.join(key_fields) or 'None'} | "
                f"**Financial fields:** {', '.join(financial_fields) or 'None'}")

    df_with_sig = st.session_state.get("df_with_sig")
    if df_with_sig is None:
        with st.spinner("Computing row signatures…"):
            df_with_sig = add_signatures(df_raw, key_fields, financial_fields)
            st.session_state["df_with_sig"] = df_with_sig

    st.metric("Total Rows", f"{len(df_with_sig):,}")
    dups = find_duplicate_signatures(df_with_sig)

    if not dups.empty:
        st.warning(f"⚠️ {len(dups):,} rows share duplicate signatures.")
        with st.expander("View duplicate rows"):
            disp = [c for c in key_fields + financial_fields + ["__row_signature__"] if c in dups.columns]
            st.dataframe(dups[disp].head(50), use_container_width=True)
    else:
        st.success("✅ All row signatures are unique.")

    with st.expander("Sample: First 20 rows with signatures"):
        disp = [c for c in key_fields + financial_fields + ["__row_signature__"] if c in df_with_sig.columns]
        st.dataframe(df_with_sig[disp].head(20), use_container_width=True)

# ── POLICY VALIDATION ─────────────────────────────────────────────────────
elif page == "✅ Policy Validation":
    st.header("✅ Policy-to-Value Validation")

    df_with_sig = st.session_state.get("df_with_sig") or st.session_state.get("df_raw")
    key_fields = st.session_state.get("key_fields", [])
    financial_fields = st.session_state.get("financial_fields", [])

    if df_with_sig is None:
        st.warning("Upload a file first.")
        st.stop()

    policy_findings = st.session_state.get("policy_findings")
    if policy_findings is None:
        with st.spinner("Validating policies…"):
            policy_findings, _ = validate_policies(df_with_sig, key_fields, financial_fields)
            st.session_state["policy_findings"] = policy_findings

    if not policy_findings:
        st.success("✅ No policy validation issues found.")
    else:
        st.error(f"🚨 {len(policy_findings)} policy validation finding(s)")

    sev_emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "⚡", "LOW": "ℹ️"}
    for pf in policy_findings:
        with st.expander(f"{sev_emoji.get(pf.severity, '•')} [{pf.severity}] "
                         f"{pf.finding_type.replace('_', ' ').title()} — {pf.count:,} rows"):
            st.write(pf.description)
            if pf.example_values:
                st.caption(f"Examples: {', '.join(pf.example_values[:5])}")
            if pf.affected_rows:
                st.caption(f"Affected rows (first 20): {pf.affected_rows[:20]}")

    if key_fields and financial_fields:
        st.subheader("Policy Summary Table")
        summary = build_policy_summary(df_with_sig, key_fields, financial_fields)
        if not summary.empty:
            st.dataframe(summary.head(100), use_container_width=True)
            st.caption(f"Showing first 100 of {len(summary):,} unique policy combinations.")

# ── SORT SIMULATION ───────────────────────────────────────────────────────
elif page == "🔀 Sort Simulation":
    st.header("🔀 Sort Corruption Simulation")

    df_raw = st.session_state.get("df_raw")
    region_report = st.session_state.get("region_report")

    if df_raw is None:
        st.warning("Upload a file first.")
        st.stop()
    if region_report is None:
        st.warning("Run blank column analysis first.")
        st.stop()

    if not region_report.split_points:
        st.success(
            "✅ No blank column splits detected. Sort simulation is not applicable. "
            "Your data should sort safely."
        )
        st.stop()

    sort_sim = st.session_state.get("sort_sim")
    if sort_sim is None:
        key_fields = st.session_state.get("key_fields", [])
        financial_fields = st.session_state.get("financial_fields", [])
        df_with_sig = st.session_state.get("df_with_sig") or df_raw
        with st.spinner("Running sort simulation…"):
            sort_sim = simulate_sort_corruption(df_with_sig, region_report, key_fields, financial_fields)
            st.session_state["sort_sim"] = sort_sim

    if sort_sim is None:
        st.info("Unable to run simulation — insufficient data.")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Rows", f"{sort_sim.total_rows:,}")
    c2.metric("Corrupted Rows", f"{sort_sim.corrupted_rows:,}")
    c3.metric("Corruption %", f"{sort_sim.corruption_pct}%")
    c4.metric("Risk Level", sort_sim.risk_level)
    st.error(sort_sim.description)

    st.subheader("Before vs After Comparison")
    co1, co2, co3 = st.columns(3)
    with co1:
        st.markdown("**🔵 Before Sort (Original)**")
        st.dataframe(sort_sim.before_sample, use_container_width=True, height=280)
    with co2:
        st.markdown("**🔴 After Partial Sort (Corrupted)**")
        st.dataframe(sort_sim.after_sample, use_container_width=True, height=280)
    with co3:
        st.markdown("**✅ After Full Sort (Correct)**")
        st.dataframe(sort_sim.full_sort_sample, use_container_width=True, height=280)

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=sort_sim.corruption_pct,
        title={"text": "Row Corruption Risk (%)"},
        delta={"reference": 0},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#d32f2f"},
            "steps": [{"range": [0, 20], "color": "#c8e6c9"},
                      {"range": [20, 50], "color": "#fff9c4"},
                      {"range": [50, 100], "color": "#ffcdd2"}],
        },
    ))
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)

# ── RECONCILIATION ────────────────────────────────────────────────────────
elif page == "💰 Reconciliation":
    st.header("💰 Reconciliation Controls")

    df_raw = st.session_state.get("df_raw")
    key_fields = st.session_state.get("key_fields", [])
    financial_fields = st.session_state.get("financial_fields", [])

    if df_raw is None:
        st.warning("Upload a file first.")
        st.stop()

    recon = st.session_state.get("recon_report")
    if recon is None:
        recon = build_reconciliation_report(df_raw, key_fields, financial_fields,
                                            st.session_state.get("active_sheet", "Sheet1"))
        st.session_state["recon_report"] = recon

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Records", f"{recon.total_rows:,}")
    c2.metric("Unique Policies", f"{recon.unique_policy_count:,}")
    c3.metric("Duplicates", f"{recon.duplicate_count:,}")
    c4.metric("Missing Keys", f"{recon.missing_key_count:,}")

    st.divider()
    st.subheader("Financial Field Summaries")
    if recon.financial_summaries:
        for fs in recon.financial_summaries:
            with st.expander(f"📊 {fs.field_name}"):
                mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                mc1.metric("Sum", format_currency(fs.total))
                mc2.metric("Average", format_currency(fs.average))
                mc3.metric("Min", format_currency(fs.minimum))
                mc4.metric("Max", format_currency(fs.maximum))
                mc5.metric("Null %", f"{fs.pct_null}%")

        totals_df = pd.DataFrame([{"Field": fs.field_name, "Total": fs.total}
                                   for fs in recon.financial_summaries])
        fig = px.bar(totals_df, x="Field", y="Total", title="Financial Field Totals",
                     labels={"Total": "Sum ($)"}, color_discrete_sequence=["#1976D2"])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No financial fields selected. Configure them on the Column Detection page.")

# ── TIE-OUT ENGINE ────────────────────────────────────────────────────────
elif page == "🔗 Tie-Out Engine":
    st.header("🔗 Advanced Policy/Value Tie-Out Engine")

    df_raw = st.session_state.get("df_raw")
    key_fields = st.session_state.get("key_fields", [])
    financial_fields = st.session_state.get("financial_fields", [])

    if df_raw is None:
        st.warning("Upload a file first.")
        st.stop()

    tieout = st.session_state.get("tieout_report")
    if tieout is None:
        df_with_sig = st.session_state.get("df_with_sig") or df_raw
        tieout = run_tieout(df_with_sig, key_fields, financial_fields,
                            st.session_state.get("active_sheet", "Sheet1"))
        st.session_state["tieout_report"] = tieout

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Relationships", f"{tieout.total_relationships:,}")
    c2.metric("Unique Keys", f"{tieout.unique_keys:,}")
    c3.metric("Anomalies Found", len(tieout.anomalies))
    c4.metric("Integrity Score", f"{tieout.integrity_score}/100")

    st.markdown(f'**Overall Risk:** <span class="risk-badge-{tieout.overall_risk}">{tieout.overall_risk}</span>',
                unsafe_allow_html=True)
    st.divider()
    st.subheader("Anomalies")

    sev_emoji = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "⚡", "LOW": "ℹ️"}
    if not tieout.anomalies:
        st.success("✅ No tie-out anomalies detected.")
    else:
        for anomaly in tieout.anomalies:
            with st.expander(
                f"{sev_emoji.get(anomaly.risk_level, '•')} [{anomaly.risk_level}] "
                f"{anomaly.anomaly_type.replace('_', ' ').title()} — {anomaly.count:,} records"
            ):
                st.write(anomaly.description)
                if anomaly.affected_keys:
                    st.caption(f"Affected keys: {', '.join(str(k) for k in anomaly.affected_keys[:10])}")
                if anomaly.sample_data is not None and not anomaly.sample_data.empty:
                    st.dataframe(anomaly.sample_data, use_container_width=True)

    if tieout.policy_value_map is not None and not tieout.policy_value_map.empty:
        st.subheader("Policy-Value Relationship Map")
        st.dataframe(tieout.policy_value_map.head(50), use_container_width=True)
        st.caption(f"Showing first 50 of {len(tieout.policy_value_map):,} unique policy groups.")

# ── RISK DASHBOARD ────────────────────────────────────────────────────────
elif page == "🎯 Risk Dashboard":
    st.header("🎯 Risk Dashboard")

    workbook_risk = st.session_state.get("workbook_risk")
    sheet_risk = st.session_state.get("sheet_risk")
    recommendations = st.session_state.get("recommendations", [])

    if workbook_risk is None:
        st.warning("Run the full integrity check first (Upload & Configure page).")
        st.stop()

    score = workbook_risk.workbook_score
    risk_lvl = workbook_risk.workbook_risk

    st.markdown(
        f'<div style="display:flex;gap:16px;margin-bottom:16px">'
        f'<div class="kpi-box" style="flex:1"><div class="kpi-value">{score}</div>'
        f'<div class="kpi-label">Integrity Score / 100</div></div>'
        f'<div class="kpi-box" style="flex:1;background:{risk_color(risk_lvl)}">'
        f'<div class="kpi-value">{risk_lvl}</div><div class="kpi-label">Overall Risk Level</div></div>'
        f'<div class="kpi-box" style="flex:1"><div class="kpi-value">{score_badge(score)}</div>'
        f'<div class="kpi-label">Rating</div></div></div>',
        unsafe_allow_html=True,
    )

    if workbook_risk.sheet_scores:
        st.subheader("Sheet Risk Summary")
        scores_data = [
            {"Sheet": n, "Score": rs.overall_score, "Risk": rs.risk_level,
             "Critical": rs.critical_count, "High": rs.high_count, "Medium": rs.medium_count}
            for n, rs in workbook_risk.sheet_scores.items()
        ]
        df_scores = pd.DataFrame(scores_data)
        st.dataframe(df_scores, use_container_width=True, hide_index=True)

        fig_score = px.bar(df_scores, x="Sheet", y="Score", color="Risk",
                           color_discrete_map={"CRITICAL": "#d32f2f", "HIGH": "#f57c00",
                                               "MEDIUM": "#fbc02d", "LOW": "#388e3c"},
                           title="Sheet Integrity Scores")
        fig_score.update_layout(height=300)
        st.plotly_chart(fig_score, use_container_width=True)

    if workbook_risk.top_findings:
        st.subheader("Top Findings")
        df_top = pd.DataFrame(workbook_risk.top_findings)
        display_cols = [c for c in ["severity", "description", "category", "sheet"] if c in df_top.columns]
        st.dataframe(df_top[display_cols].head(10), use_container_width=True, hide_index=True)

    if recommendations:
        st.subheader("Priority Recommendations")
        for i, rec in enumerate(recommendations[:5], 1):
            badge = f'<span class="risk-badge-{rec.severity}">{rec.severity}</span>'
            st.markdown(f"{badge} **{i}. {rec.title}**<br><small>{rec.action}</small>",
                        unsafe_allow_html=True)
            st.divider()

    if sheet_risk:
        labels = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        values = [sheet_risk.critical_count, sheet_risk.high_count,
                  sheet_risk.medium_count, sheet_risk.low_count]
        if any(v > 0 for v in values):
            fig_pie = px.pie(names=labels, values=values, color=labels,
                             color_discrete_map={"CRITICAL": "#d32f2f", "HIGH": "#f57c00",
                                                 "MEDIUM": "#fbc02d", "LOW": "#388e3c"},
                             title="Finding Severity Distribution")
            fig_pie.update_layout(height=300)
            st.plotly_chart(fig_pie, use_container_width=True)

# ── REPORTS ───────────────────────────────────────────────────────────────
elif page == "📄 Reports":
    st.header("📄 Downloadable Reports")

    workbook_risk = st.session_state.get("workbook_risk")
    sheet_analyses = st.session_state.get("sheet_analyses", {})
    recommendations = st.session_state.get("recommendations", [])
    filename = st.session_state.get("uploaded_filename", "bdx_file.xlsx")

    if workbook_risk is None:
        st.warning("Run the full integrity check first (Upload & Configure page).")
        st.stop()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Excel Audit Report")
        st.markdown("Comprehensive workbook with Executive Summary, Findings, and Recommendations.")
        if st.button("Generate Excel Report", use_container_width=True):
            with st.spinner("Generating…"):
                try:
                    excel_bytes = generate_excel_report(filename, workbook_risk, sheet_analyses, recommendations)
                    st.download_button(
                        "⬇ Download Excel Report", data=excel_bytes,
                        file_name=f"bdx_audit_{filename.replace('.xlsx', '')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Error: {e}")

    with col2:
        st.subheader("📝 PDF Executive Report")
        st.markdown("Professional PDF with Risk Score, Key Findings, and Recommendations.")
        if st.button("Generate PDF Report", use_container_width=True):
            with st.spinner("Generating…"):
                try:
                    pdf_bytes = generate_pdf_report(filename, workbook_risk, sheet_analyses, recommendations)
                    st.download_button(
                        "⬇ Download PDF Report", data=pdf_bytes,
                        file_name=f"bdx_executive_{filename.replace('.xlsx', '')}.pdf",
                        mime="application/pdf", use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Error generating PDF: {e}\n\n{traceback.format_exc()}")

    st.divider()
    if recommendations:
        st.subheader("📋 Recommendations")
        df_recs = pd.DataFrame([
            {"Priority": r.priority, "Severity": r.severity, "Category": r.category,
             "Title": r.title, "Detail": r.detail, "Action": r.action}
            for r in recommendations
        ])
        st.dataframe(df_recs, use_container_width=True, hide_index=True)
        csv = df_recs.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download Recommendations CSV", data=csv,
                           file_name="bdx_recommendations.csv", mime="text/csv")
