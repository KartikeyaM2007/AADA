"""Streamlit entry point wrapper for Streamlit Community Cloud deployment."""

import sys
import runpy

# Invalidate stale cached modules in Streamlit Cloud worker memory
for mod_name in ("ui", "nlq", "ai_insights", "business_insights", "pipeline", "sql_engine", "file_io"):
    if mod_name in sys.modules:
        del sys.modules[mod_name]

runpy.run_path("app.py")
