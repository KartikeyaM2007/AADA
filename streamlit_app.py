"""Streamlit entry point for Streamlit Community Cloud. v4 - force fresh deploy"""

import sys
import importlib
import runpy

# Force reload all local modules on every run to prevent stale cache issues
_LOCAL_MODULES = ["ui", "nlq", "ai_insights", "business_insights", "pipeline",
                  "sql_engine", "file_io", "demo_data", "forecasting", "anomalies"]
for _mod in _LOCAL_MODULES:
    if _mod in sys.modules:
        del sys.modules[_mod]

runpy.run_path("app.py")
