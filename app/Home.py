"""Home page — landing page for the Asset Performance Analytics Dashboard."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Asset Performance Analytics Dashboard",
    page_icon="💧",
    layout="wide",
)

st.title("💧 Asset Performance Analytics Dashboard")
st.subheader("Municipal Water Pump Fleet — Overview")

st.markdown(
    """
Welcome to the **Asset Performance Analytics Dashboard** for your municipal water pump fleet.

Use the sidebar to navigate between pages:

| Page | Description |
|------|-------------|
| 📊 Overview | Fleet-level KPIs, failure trends, and top risky assets |
| 🔍 Asset Explorer | Drill into a single pump's history and sensor readings |
| ⚠️ Risk Insights | Risk by zone, age, and failure mode analysis |
| 🔧 Maintenance Planner | Budget-based maintenance/replacement recommendations |

---

### Getting Started

If the database has not been initialised yet, open a terminal and run:

```bash
python -m src.data_generation   # generate synthetic CSV data
python -m src.etl               # load CSVs into SQLite
```

Then refresh this page.
"""
)

# Check database availability
from pathlib import Path

DB_PATH = Path("database/pumps.db")
if DB_PATH.exists():
    st.success(f"✅ Database found at `{DB_PATH}`")
else:
    st.warning(
        "⚠️ Database not found. Please run the setup commands above before exploring the dashboard."
    )
