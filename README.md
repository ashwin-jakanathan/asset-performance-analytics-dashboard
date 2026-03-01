# Asset Performance Analytics Dashboard

A **Python + Streamlit** multipage dashboard for analysing the performance of a fleet of municipal water pumps using synthetic data.

---

## Architecture

```
asset-performance-analytics-dashboard/
├── app/
│   ├── Home.py                  # Landing page
│   └── pages/
│       ├── 1_Overview.py        # Fleet KPIs, failure trends, top risky assets
│       ├── 2_Asset_Explorer.py  # Per-asset sensor readings & risk score
│       ├── 3_Risk_Insights.py   # Risk by zone/age, failure-mode pareto
│       └── 4_Maintenance_Planner.py  # Budget-based maintenance plan
├── src/
│   ├── data_generation.py  # Synthetic pump data (assets, readings, events)
│   ├── etl.py              # CSV → SQLite loader with validation
│   ├── db.py               # DB connection helpers & query functions
│   ├── kpis.py             # KPI calculations (fleet and per-asset)
│   ├── risk.py             # Rule-based risk model
│   ├── planner.py          # Budget-based maintenance planner
│   └── plots.py            # Plotly chart helpers
├── data/                   # Generated CSV files (gitignored)
├── database/               # SQLite database (gitignored)
├── requirements.txt
└── README.md
```

**Data flow:**  
`data_generation.py` → CSV files in `data/` → `etl.py` → `database/pumps.db` → `src/db.py` → Streamlit pages

**Business logic** lives exclusively in `src/`; Streamlit pages only call service functions.

---

## Setup & Run

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate synthetic data (100 pumps, 5 years of monthly readings)
python -m src.data_generation

# 4. Load data into SQLite
python -m src.etl

# 5. Launch the dashboard
streamlit run app/Home.py
```

Open <http://localhost:8501> in your browser.

---

## Data Model

| Table | Key columns |
|-------|-------------|
| `assets` | `asset_id` (PK), `pump_type`, `install_date`, `zone`, `criticality`, `replacement_cost` |
| `events` | `event_id` (PK), `asset_id` (FK), `event_date`, `event_type`, `failure_mode`, `downtime_hours`, `maintenance_cost` |
| `readings` | `asset_id`+`reading_date` (PK), monthly sensor values: `flow_gpm`, `pressure_psi`, `power_kw`, `vibration_mm_s`, `temperature_c` |

---

## Risk Model

The probability-of-failure score is a weighted sum of four normalised components:

```
pf_score = 0.35 × age_norm
         + 0.30 × recent_fail_norm
         + 0.20 × overdue_norm
         + 0.15 × condition_norm

risk = clamp(pf_score, 0, 1) × (criticality/5) × replacement_cost
```

Top risk drivers are reported per asset for explainability.
