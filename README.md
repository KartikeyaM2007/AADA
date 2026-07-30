# Automated Data Analyst (ADA) — AI-Powered Data Analyst

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.59-ff4b4b?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![DuckDB](https://img.shields.io/badge/DuckDB-SQL_Engine-fff000?logo=duckdb&logoColor=black)](https://duckdb.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-20a779.svg)](LICENSE)
[![Author](https://img.shields.io/badge/Author-Kartikeya_Mishra-635bff.svg)](https://port-folio-main-window.vercel.app/)

> Developed by **Kartikeya Mishra** | [Portfolio](https://port-folio-main-window.vercel.app/)

ADA is a production-ready, privacy-conscious **AI-powered Data Analyst** built with Python, Streamlit, DuckDB, Pandas, and Plotly. Upload single or multiple CSV / Excel files, interact with your data in natural language, generate business insights, execute live SQL queries, perform anomaly detection, and view guarded forecasts.

---

## 🌟 Key Features

* 📁 **Multi-CSV & Relational Data Ingestion**: Upload one or more CSV / Excel files simultaneously. Tables are registered in an in-memory **DuckDB** relational database for cross-table joins.
* 💬 **Natural Language Querying (Ask ADA)**: Plain-English questions mapped to deterministic Pandas query plans and SQL code executed locally.
* ⚡ **SQL Code Generation & Execution Console**: View and copy generated SQL code (`SELECT`, `GROUP BY`, `ORDER BY`) or run custom SQL queries in the interactive SQL console tab.
* 🔍 **Anomaly Detection Engine**: Outlier detection (z-score / IQR / Isolation Forest) with clear natural language evidence explanations.
* 📈 **Guarded Baseline Forecasting**: Time-series forecasting with month-of-year seasonality, uncertainty bands, and backtested error margins.
* 📊 **Interactive Plotly Visualizations**: Dynamic Bar, Line, Pie, Scatter, Heatmap, and Movement Waterfall charts.
* 🎛️ **1-Click Pre-Loaded Sample Datasets**: Instantly try the app with 3 pre-configured sample datasets (E-Commerce Multi-CSV, SaaS Subscriptions, HR Analytics).
* 🔒 **Privacy & Deterministic Core**: Calculations run locally on your machine. Optional AI features receive schema metadata and computed evidence—**never raw uploaded data rows**.
* 🐳 **Docker Containerization**: Production-ready `Dockerfile` and `docker-compose.yml` for 1-command startup.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    A["Upload CSV(s) or Excel Workbooks / Sample Data"] --> B["Data Cleaning & Type Inference"]
    B --> C["Register DataFrames into DuckDB Engine & Infer Schema"]
    C --> D["Calculate Evidence, Anomalies & Baseline Forecast"]
    D --> E["Interactive Dashboard, Visualizations & Insights"]
    C --> G["Ask ADA: Natural Language → QueryPlan / DuckDB SQL → Local Execution"]
    G -. "Schema metadata only" .-> H["Optional AI Query Planner"]
    D -. "Computed evidence cards only" .-> F["Optional Strategic Executive Read"]
```

---

## 💻 Tech Stack

- **Frontend / UI**: Streamlit 1.59, Custom CSS, Plotly Interactive Visualizations
- **Relational SQL Engine**: DuckDB
- **Data Analytics Core**: Pandas, NumPy, Scikit-Learn, SciPy
- **LLM Integration**: OpenAI / Gemini compatible structured output planning (Optional)
- **Containerization**: Docker & Docker Compose

---

## 🚀 Quick Start & Local Execution

### Option 1: Running with Python Virtual Environment

```bash
# 1. Clone repository
git clone https://github.com/Kartikeyam2007/AADA.git
cd AADA

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run application
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

### Option 2: Running with Docker Compose

```bash
docker-compose up --build
```

Open `http://localhost:8501` in your browser.

---

## 🖼️ Application Preview & Demo Link

- **Live Application Link**: [http://localhost:8501](http://localhost:8501)
- **Social Preview & Architecture Diagram**: See `assets/ada-social-preview.svg`

---

## 📋 Assumptions & Implementation Notes

1. **Privacy-First Design**: The application executes 100% of calculations, SQL queries, and code locally. No raw rows or cell values are ever transmitted over the network.
2. **DuckDB Engine**: DuckDB is leveraged for lightning-fast ANSI SQL query execution across multiple uploaded CSV files.
3. **Deterministic Core with Optional LLM**: Core analytics, anomaly detection, and natural language query execution run via rule-based deterministic parsers. An optional LLM API key can be provided for complex natural language questions and strategic synthesis.

---

## 🧪 Testing

Run the test suite with `pytest` or `unittest`:

```bash
python -m unittest discover -s tests -v
```

---

## 📄 License & Author

- **Author**: Kartikeya Mishra
- **Portfolio**: [https://port-folio-main-window.vercel.app/](https://port-folio-main-window.vercel.app/)
- **License**: [MIT License](LICENSE)
