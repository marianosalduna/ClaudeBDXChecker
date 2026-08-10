# BDX Integrity Checker

A production-ready Streamlit application that validates bordereau (BDX) spreadsheets and identifies structural defects that can cause sorting and filtering corruption in Excel.

---

## Background

A real-world incident triggered the creation of this tool. A completely blank column existed within a data range:

```
Column AX = populated data
Column AY = completely blank  ← split point
Column AZ = populated data
```

Excel treated column AY as the boundary of the data region. When a user applied a sort or filter, only columns A–AX moved while AZ onward remained stationary. This **silently mismatched policy numbers with financial values** — a critical data integrity failure.

This tool identifies these risks **before approval**.

---

## Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | File Upload | XLSX upload with multi-sheet support, 100k+ rows |
| 2 | Column Detection | Automatic header matching with confidence scoring |
| 3 | Blank Column Detection | Identifies blank columns splitting the data region |
| 4 | Data Region Analysis | Maps populated vs blank regions, shows affected range |
| 5 | Excel Table Validation | Checks if data is stored as an official Excel Table |
| 6 | Configurable Mapping | User-selectable key and financial columns |
| 7 | Row Signatures | SHA-256 hash fingerprints for each row |
| 8 | Policy Validation | Missing keys, duplicates, blank financial values |
| 9 | Sort Simulation | Simulates partial sort and estimates corruption |
| 10 | Reconciliation | Record counts, unique policies, financial summaries |
| 11 | Tie-Out Engine | Policy-to-value relationship maps and anomaly detection |
| 12 | Risk Scoring | CRITICAL/HIGH/MEDIUM/LOW severity at finding/sheet/workbook level |
| 13 | Visual Dashboard | Plotly charts, KPI cards, heatmaps |
| 14 | Reports | Downloadable Excel audit report and PDF executive report |
| 15 | Recommendations | Prioritised, actionable remediation steps |
| 16 | Sample Data | Four-sheet workbook demonstrating each scenario |
| 17 | Unit Tests | Tests for all core modules |
| 18 | Replit Deployment | Full Replit configuration included |

---

## Quick Start

### Option A: Run locally

```bash
# Clone and install
pip install -r requirements.txt

# Launch
streamlit run app.py
```

### Option B: Deploy on Replit

1. Create a new Replit project (Python template)
2. Upload the ZIP package (or import from GitHub)
3. Click **Run** — Replit will install dependencies and launch the app

### Option C: Import ZIP into Replit

```bash
# Generate the ZIP package
python create_zip.py

# Upload bdx_integrity_checker.zip to Replit
# Extract and click Run
```

---

## Project Structure

```
ClaudeBDXChecker/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── .replit                         # Replit run configuration
├── replit.nix                      # Replit Nix environment
├── config_sample.yaml              # Sample configuration
├── create_zip.py                   # Packaging script
├── README.md                       # This file
│
├── .streamlit/
│   └── config.toml                 # Streamlit server settings
│
├── modules/
│   ├── __init__.py
│   ├── file_handler.py             # Feature 1: File upload & processing
│   ├── column_detector.py          # Feature 2: Automatic column detection
│   ├── blank_column_detector.py    # Features 3 & 4: Blank column + region analysis
│   ├── excel_table_validator.py    # Feature 5: Excel Table detection
│   ├── signature_engine.py         # Feature 7: SHA-256 row signatures
│   ├── policy_validator.py         # Feature 8: Policy-to-value validation
│   ├── sort_simulator.py           # Feature 9: Sort corruption simulation
│   ├── reconciliation.py           # Feature 10: Reconciliation controls
│   ├── tieout_engine.py            # Feature 11: Tie-out engine
│   ├── risk_scorer.py              # Feature 12: Risk scoring engine
│   ├── recommendations.py          # Feature 15: Recommendation engine
│   ├── reporter.py                 # Feature 14: Excel + PDF reports
│   └── sample_data.py              # Feature 16: Sample workbook generator
│
└── tests/
    ├── __init__.py
    ├── test_blank_column_detector.py
    ├── test_policy_validator.py
    ├── test_signature_engine.py
    ├── test_risk_scorer.py
    ├── test_excel_table_validator.py
    └── test_sort_simulator.py
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Or run a specific test file:

```bash
python -m pytest tests/test_blank_column_detector.py -v
```

---

## Sample Data

The tool includes a built-in sample BDX workbook with four sheets:

| Sheet | Content |
|-------|---------|
| `Healthy_BDX` | Clean data with an Excel Table — passes all checks |
| `Split_Blank_Col` | Blank column between populated columns — CRITICAL risk |
| `Duplicate_Policies` | Multiple rows per policy with conflicting amounts |
| `Missing_Values` | Blank key fields and missing financial data |

Download it from the sidebar: **⬇ Download Sample BDX**

---

## Configuration

Copy `config_sample.yaml` and customise:

- **key_fields** — your policy identifier columns
- **financial_fields** — your numeric value columns  
- **validation thresholds** — acceptable rates for duplicates and blanks
- **risk thresholds** — minimum pass score and rejection levels

---

## Risk Levels

| Level | Description |
|-------|-------------|
| CRITICAL | Blank column splitting populated data; simulated sort corruption |
| HIGH | Missing key identifiers; excessive duplicates |
| MEDIUM | Non-table structure; reconciliation discrepancies |
| LOW | Cosmetic or best-practice issues |

The integrity score runs from **0 (worst) to 100 (best)**. A score below 80 is recommended for rejection pending remediation.

---

## Replit Deployment Notes

- Port: **8080** (configured in `.replit` and `.streamlit/config.toml`)
- Max upload size: **500 MB**
- No database or external API dependencies — fully self-contained

---

## Licence

MIT — see `LICENSE` file.
