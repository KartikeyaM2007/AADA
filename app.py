"""ADA: zero-configuration business intelligence for CSV and Excel data."""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from ai_insights import (
    DEFAULT_PRESET,
    MODEL_PRESETS,
    AINarrative,
    build_ai_payload,
    generate_ai_narrative,
    narrative_to_markdown,
    plan_query_with_ai,
)
from analysis import column_profile
from business_insights import BusinessBrief, analyze_business, build_business_report
from demo_data import (
    make_demo_data,
    make_hr_analytics_data,
    make_multi_table_ecommerce,
    make_saas_metrics_data,
)
from file_io import list_excel_sheets, read_multiple_files, read_tabular_file
from sql_engine import SQLEngine
from nlq import QueryAnswer, answer_question, execute_plan, suggested_questions
from pipeline import (
    apply_focus,
    apply_role_selection,
    cleaning_audit_frame,
    focus_options,
    prepare_analysis,
    schema_frame,
)
from ui import (
    inject_styles,
    render_ai_narrative,
    render_brief,
    render_chat_answer,
    render_chat_fallback,
    render_dashboard,
    render_dataset_bar,
    render_evidence,
    render_footer,
    render_how_it_works,
    render_kpis,
    render_landing,
    render_nav,
    render_recommendations,
    render_section_heading,
)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_ANALYSIS_ROWS = 250_000

st.set_page_config(
    page_title="ADA | AI Business Dashboard from CSV & Excel",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get Help": "https://port-folio-main-window.vercel.app/",
        "Report a bug": "https://port-folio-main-window.vercel.app/",
        "About": "ADA by Kartikeya Mishra turns business spreadsheets into evidence-backed dashboards and actions.",
    },
)


@st.cache_data(show_spinner=False)
def read_uploaded_file(contents: bytes, filename: str, sheet_name: str | None = None) -> pd.DataFrame:
    return read_tabular_file(contents, filename, sheet_name)


def get_openai_api_key() -> str:
    environment_key = os.getenv("GROQ_API_KEY", os.getenv("OPENAI_API_KEY", "")).strip()
    if environment_key:
        return environment_key
    try:
        return str(st.secrets.get("GROQ_API_KEY", st.secrets.get("OPENAI_API_KEY", ""))).strip()
    except (FileNotFoundError, StreamlitSecretNotFoundError):
        return ""


def get_safety_identifier() -> str:
    if "ada_session_id" not in st.session_state:
        st.session_state.ada_session_id = secrets.token_urlsafe(24)
    session_id = str(st.session_state.ada_session_id)
    return hashlib.sha256(f"ada:{session_id}".encode()).hexdigest()


def render_sidebar(*, server_api_key: str) -> str:
    with st.sidebar:
        st.title("ADA")
        st.caption("A dashboard that explains itself.")
        st.markdown("---")
        
        # Authentication & Access Control
        st.markdown("**🔐 Session Authentication**")
        auth_pass = os.getenv("ADA_APP_PASSWORD", "").strip()
        if auth_pass:
            entered_pass = st.text_input("Enter Passcode", type="password", key="auth_pass_input")
            if entered_pass != auth_pass:
                st.warning("Locked. Enter correct passcode to unlock ADA dashboard.")
                st.stop()
            else:
                st.success("Authenticated")
        else:
            st.caption("Status: Authenticated (Public Session)")

        st.markdown("---")
        st.markdown("**Analysis contract**")
        st.markdown(
            "- Calculations happen locally\n"
            "- Evidence is shown before interpretation\n"
            "- Raw rows are never sent to the strategy model\n"
            "- Recommendations are not causal proof"
        )
        st.markdown("---")
        if server_api_key:
            st.success("Optional strategy agent is available on this deployment.")
            api_key = server_api_key
        else:
            st.info("Deterministic mode is free and complete. No model call is required.")
            api_key = st.text_input(
                "Optional Groq (gsk_...) or OpenAI API key",
                type="password",
                placeholder="gsk_... or sk-...",
                help=(
                    "Use your Groq or OpenAI key to enable the optional strategic read. "
                    "Groq keys (gsk_...) unlock ultra-fast LLaMA 3.3 70B inference!"
                ),
            ).strip()
        st.link_button(
            "Kartikeya Mishra Portfolio",
            "https://port-folio-main-window.vercel.app/",
            width="stretch",
        )
    return api_key


def maybe_generate_narrative(
    *,
    api_key: str,
    brief: BusinessBrief,
    business_context: str,
) -> tuple[AINarrative | None, str | None]:
    if not api_key:
        return None, None

    payload = build_ai_payload(brief, context=business_context)
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    cached = st.session_state.get("ai_narrative")
    cached_fingerprint = st.session_state.get("ai_narrative_fingerprint")
    default_preset = "Groq · LLaMA 3.3 70B" if (api_key.startswith("gsk_") or os.getenv("GROQ_API_KEY")) else DEFAULT_PRESET
    default_idx = list(MODEL_PRESETS).index(default_preset) if default_preset in MODEL_PRESETS else 0
    selected_preset = st.selectbox(
        "Strategy model",
        list(MODEL_PRESETS),
        index=default_idx,
        help="Select the AI reasoning model (Groq LLaMA 3.3 70B provides ultra-fast inference).",
    )
    config = MODEL_PRESETS[selected_preset]

    if st.button("Generate AI strategic read", type="primary", width="stretch"):
        try:
            with st.spinner("Connecting the evidence into a strategic read…"):
                cached = generate_ai_narrative(
                    brief,
                    api_key=api_key,
                    config=config,
                    context=business_context,
                    safety_identifier=get_safety_identifier(),
                )
            st.session_state.ai_narrative = cached
            st.session_state.ai_narrative_fingerprint = fingerprint
            st.session_state.ai_narrative_model = config.model
            cached_fingerprint = fingerprint
        except Exception:  # API failures should never take down the deterministic product.
            st.error("The optional strategy agent is temporarily unavailable. Try again or switch models.")
            return None, None

    if cached_fingerprint != fingerprint or not isinstance(cached, AINarrative):
        return None, None
    model = str(st.session_state.get("ai_narrative_model", config.model))
    return cached, model


def answer_with_ai_planner(
    question: str,
    dataframe: pd.DataFrame,
    roles,
    api_key: str,
) -> QueryAnswer | None:
    """Plan with the model over schema only, then execute locally."""
    try:
        plan = plan_query_with_ai(
            question,
            dataframe,
            roles,
            api_key=api_key,
            safety_identifier=get_safety_identifier(),
        )
        if plan is None:
            return None
        executed = execute_plan(plan, dataframe, roles)
    except Exception:  # A planner outage must never break the chat.
        return None
    return QueryAnswer(
        question=question,
        plan=executed.plan,
        answer=executed.answer,
        calculation=executed.calculation,
        table=executed.table,
        chart=executed.chart,
    )


def render_ask_ada(dataframe: pd.DataFrame, roles, source_name: str, api_key: str) -> None:
    """Chat over the analyzed dataset; every answer is a local calculation."""
    fingerprint = f"{source_name}:{len(dataframe)}:{','.join(dataframe.columns)}"
    if st.session_state.get("chat_fingerprint") != fingerprint:
        st.session_state.chat_fingerprint = fingerprint
        st.session_state.chat_history = []

    suggestions = suggested_questions(dataframe, roles)
    chips = st.columns(len(suggestions))
    question = None
    for chip, suggestion in zip(chips, suggestions, strict=True):
        if chip.button(suggestion, key=f"chip_{suggestion}", width="stretch"):
            question = suggestion

    typed = st.chat_input("Ask about this data — try “top 5 by revenue” or “which segment grew fastest?”")
    question = typed or question
    if question:
        result = answer_question(question, dataframe, roles)
        if result is None and api_key:
            with st.spinner("Planning the calculation…"):
                result = answer_with_ai_planner(question, dataframe, roles, api_key)
        st.session_state.chat_history.append({"question": question, "result": result})

    if not st.session_state.chat_history:
        st.markdown(
            '<div class="empty-state">Ask anything about the analyzed table. '
            "Answers are computed locally and every one shows its calculation.</div>",
            unsafe_allow_html=True,
        )
    for entry in st.session_state.chat_history:
        with st.chat_message("user"):
            st.markdown(entry["question"])
        with st.chat_message("assistant"):
            if entry["result"] is not None:
                render_chat_answer(entry["result"])
            else:
                render_chat_fallback(suggestions)


inject_styles()
render_nav()
render_landing()

api_key = render_sidebar(server_api_key=get_openai_api_key())

source_mode = st.segmented_control(
    "Choose a source",
    ["Explore the live demo", "Upload your file(s)"],
    default="Explore the live demo",
    label_visibility="collapsed",
)

uploaded_files = None
business_context = ""
sample_choice = "E-Commerce (Multi-CSV Relational)"

if source_mode == "Explore the live demo":
    sample_choice = st.selectbox(
        "Select a Sample Dataset",
        [
            "E-Commerce (Multi-CSV Relational)",
            "SaaS Subscriptions & Churn Metrics",
            "HR & Employee Analytics",
        ],
        help="Select a pre-loaded sample dataset to analyze instantly.",
    )

if source_mode == "Upload your file(s)":
    uploaded_files = st.file_uploader(
        "Upload CSV or Excel files",
        type=["csv", "xlsx", "xlsm"],
        accept_multiple_files=True,
        help="Maximum file size per file: 25 MB. Upload one or multiple files.",
    )
    business_context = st.text_input(
        "Optional business context",
        placeholder="Example: Subscription revenue by customer, product, and month",
        max_chars=500,
    )
    if not uploaded_files:
        render_how_it_works()
        render_footer()
        st.stop()

extra_tables: dict[str, pd.DataFrame] = {}

try:
    if source_mode == "Explore the live demo":
        if sample_choice == "E-Commerce (Multi-CSV Relational)":
            dataset_dict = make_multi_table_ecommerce()
            raw_dataframe = dataset_dict["sales"]
            extra_tables["customers"] = dataset_dict["customers"]
            source_name = "E-Commerce Orders & Customers · Demo"
            business_context = "Orders and customer demographics across products, regions, and tiers."
        elif sample_choice == "SaaS Subscriptions & Churn Metrics":
            raw_dataframe = make_saas_metrics_data()
            source_name = "SaaS Metrics · Demo"
            business_context = "SaaS subscriptions, MRR, LTV, and churn status."
        else:
            raw_dataframe = make_hr_analytics_data()
            source_name = "HR & Employee Analytics · Demo"
            business_context = "Employee salaries, performance ratings, and department metrics."
    elif uploaded_files:
        if len(uploaded_files) == 1:
            uploaded_file = uploaded_files[0]
            if uploaded_file.size > MAX_UPLOAD_BYTES:
                st.error("That file is larger than ADA's 25 MB limit.")
                st.stop()
            contents = uploaded_file.getvalue()
            selected_sheet = None
            worksheets = list_excel_sheets(contents, uploaded_file.name)
            if len(worksheets) > 1:
                selected_sheet = st.selectbox(
                    "Worksheet to analyze",
                    worksheets,
                    help="The workbook has several sheets; ADA analyzes one at a time.",
                )
            raw_dataframe = read_uploaded_file(contents, uploaded_file.name, selected_sheet)
            source_name = (
                f"{uploaded_file.name} · {selected_sheet}" if selected_sheet else uploaded_file.name
            )
        else:
            # Multi-file upload handling
            file_tuples = [(f.name, f.getvalue()) for f in uploaded_files if f.size <= MAX_UPLOAD_BYTES]
            parsed_dict = read_multiple_files(file_tuples)
            if not parsed_dict:
                st.error("None of the uploaded files could be parsed.")
                st.stop()
            first_key = next(iter(parsed_dict))
            raw_dataframe = parsed_dict[first_key]
            for key, df in parsed_dict.items():
                if key != first_key:
                    extra_tables[key] = df
            source_name = f"Multi-CSV Dataset ({len(parsed_dict)} files uploaded)"
    else:
        render_how_it_works()
        render_footer()
        st.stop()

    prepared = prepare_analysis(raw_dataframe, row_limit=MAX_ANALYSIS_ROWS)
except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError, ValueError, ImportError) as error:
    st.error(f"ADA could not read this file: {error}")
    st.stop()

if prepared.truncated_rows:
    st.warning(
        f"ADA analyzed the first {MAX_ANALYSIS_ROWS:,} rows for predictable performance "
        f"and skipped {prepared.truncated_rows:,}."
    )

dataframe = prepared.dataframe
detected = prepared.detected_roles
date_options = [
    "None",
    *[
        column
        for column in dataframe.columns
        if pd.api.types.is_datetime64_any_dtype(dataframe[column])
    ],
]
measure_options = ["None", *detected.numeric]
dimension_options = ["None", *detected.dimensions]

with st.expander("Tune ADA's schema detection", expanded=False):
    st.caption("ADA selected these roles automatically. Override them only when the source schema needs context.")
    selectors = st.columns(3)
    selected_date = selectors[0].selectbox(
        "Date",
        date_options,
        index=date_options.index(detected.date) if detected.date in date_options else 0,
    )
    selected_measure = selectors[1].selectbox(
        "Primary metric",
        measure_options,
        index=measure_options.index(detected.measure) if detected.measure in measure_options else 0,
    )
    selected_dimension = selectors[2].selectbox(
        "Business segment",
        dimension_options,
        index=dimension_options.index(detected.dimension) if detected.dimension in dimension_options else 0,
    )

roles = apply_role_selection(
    detected,
    date=selected_date,
    measure=selected_measure,
    dimension=selected_dimension,
)

focus_value = None
focus_values = focus_options(dataframe, roles)
if focus_values:
    everything = f"All {roles.dimension} values"
    focus_columns = st.columns([0.34, 0.66])
    choice = focus_columns[0].selectbox(
        f"Drill into one {roles.dimension}",
        [everything, *focus_values],
        help="Focus the brief, dashboard, chat, and exports on a single slice. "
        "ADA regroups the slice by the next useful segment.",
    )
    if choice != everything:
        focus_value = choice

dataframe, roles = apply_focus(dataframe, roles, focus_value)
brief = analyze_business(dataframe, roles)

render_dataset_bar(source_name, dataframe, roles, focus=focus_value)
render_brief(brief)
render_kpis(brief)

executive_tab, ask_tab, sql_tab, dashboard_tab, evidence_tab, data_tab = st.tabs(
    ["Executive brief", "Ask ADA", "SQL Console & Code", "Live dashboard", "Evidence ledger", "Data room"]
)

with executive_tab:
    render_section_heading(
        "Decision layer",
        "The next move, with receipts",
        "ADA keeps recommendations beside the evidence that triggered them so judgment never masquerades as a metric.",
    )
    executive_columns = st.columns([1.08, 0.92], gap="large")
    with executive_columns[0]:
        st.markdown('<div class="section-label">What ADA would do next</div>', unsafe_allow_html=True)
        render_recommendations(brief)
    with executive_columns[1]:
        st.markdown('<div class="section-label">What the data says</div>', unsafe_allow_html=True)
        render_evidence(brief, limit=4)
        st.markdown(
            '<div class="trust-note"><strong>Trust contract:</strong> evidence cards are calculations. Recommendations are interpretations—not causal proof.</div>',
            unsafe_allow_html=True,
        )

    narrative = None
    narrative_model = None
    if api_key:
        render_section_heading(
            "Optional strategy agent",
            "Connect the signals into a strategic read",
            "Only the computed evidence and supplied business context are sent. Raw uploaded rows stay out of the model prompt.",
        )
        control_column, note_column = st.columns([.42, .58], gap="large")
        with control_column:
            narrative, narrative_model = maybe_generate_narrative(
                api_key=api_key,
                brief=brief,
                business_context=business_context,
            )
        with note_column:
            if api_key.startswith("gsk_") or os.getenv("GROQ_API_KEY"):
                st.info(
                    "Groq LLaMA 3.3 70B is the active default for ultra-fast strategic reasoning. "
                    "Qwen 2.5 Coder & Mixtral 8x7B are also available. "
                    "The calculated dashboard remains authoritative either way."
                )
            else:
                st.info(
                    "Luna is the efficient default. Terra is available when ambiguity justifies more reasoning. "
                    "The calculated dashboard remains authoritative either way."
                )
        if narrative and narrative_model:
            render_ai_narrative(narrative, model=narrative_model)
    else:
        narrative = None
        narrative_model = None

with ask_tab:
    render_section_heading(
        "Conversational analyst",
        "Ask this data anything",
        "Questions become transparent pandas calculations that run locally. "
        "No question or answer leaves the session, and every reply shows its math.",
    )
    render_ask_ada(dataframe, roles, source_name, api_key)

with sql_tab:
    render_section_heading(
        "Relational SQL Console",
        "Query CSVs with DuckDB SQL",
        "Execute high-performance ANSI SQL queries across single or multi-table datasets locally.",
    )

    sql_engine = SQLEngine()
    tables_to_register = {"data_table": dataframe}
    if "sales" not in extra_tables and source_mode == "Explore the live demo" and sample_choice.startswith("E-Commerce"):
        tables_to_register["sales"] = dataframe
    for tbl_name, tbl_df in extra_tables.items():
        tables_to_register[tbl_name] = tbl_df

    sql_engine.register_tables(tables_to_register)
    table_meta = sql_engine.list_tables()

    st.markdown("**Registered SQL Tables:**")
    meta_cols = st.columns(max(len(table_meta), 1))
    for idx, (tname, (r_cnt, c_cnt)) in enumerate(table_meta.items()):
        meta_cols[idx % len(meta_cols)].metric(f"Table `{tname}`", f"{r_cnt:,} rows", f"{c_cnt} columns")

    default_sql = "SELECT * FROM sales LIMIT 10;" if "sales" in table_meta and "customers" in table_meta else "SELECT * FROM data_table LIMIT 10;"
    if "sales" in table_meta and "customers" in table_meta:
        default_sql = """SELECT 
    s."Order ID", 
    s.Product, 
    s.Region, 
    s.Revenue, 
    c.Tier, 
    c."Segment Type"
FROM sales s
JOIN customers c ON s."Customer ID" = c."Customer ID"
ORDER BY s.Revenue DESC
LIMIT 10;"""

    sql_input = st.text_area(
        "SQL Query Editor",
        value=default_sql,
        height=140,
        help="Write any ANSI SQL query. Supported functions: COUNT, SUM, AVG, GROUP BY, JOIN, DATE_TRUNC, etc.",
    )

    if st.button("Run SQL Query", type="primary"):
        import time
        t0 = time.time()
        res_df, err = sql_engine.execute_query(sql_input)
        t1 = time.time()
        
        if err:
            st.error(f"SQL Execution Error: {err}")
        elif res_df is not None:
            st.success(f"Executed in {(t1 - t0) * 1000:.2f} ms ({len(res_df):,} rows returned)")
            st.dataframe(res_df, width="stretch", height=350)
            st.download_button(
                "Download SQL Results CSV",
                data=res_df.to_csv(index=False).encode("utf-8"),
                file_name="ada_sql_results.csv",
                mime="text/csv",
            )

with dashboard_tab:
    render_section_heading(
        "Operating view",
        "The shape of the business",
        "Trend, contribution, distribution, and the strongest measurable relationship—generated without chart configuration.",
    )
    render_dashboard(dataframe, roles)

with evidence_tab:
    render_section_heading(
        "Evidence ledger",
        "Trace every conclusion",
        "Every displayed signal exposes the calculation behind it. Adjust the detected schema when a business-specific field was misunderstood.",
    )
    render_evidence(brief)
    st.markdown('<div class="section-label" style="margin-top:1.5rem">Detected business schema</div>', unsafe_allow_html=True)
    st.dataframe(schema_frame(roles), hide_index=True, width="stretch")

with data_tab:
    render_section_heading(
        "Data room",
        "Clean, inspect, and take it with you",
        "Review ADA's cleaning audit, inspect the normalized table, and export both the executive brief and analysis-ready data.",
    )
    report = build_business_report(
        dataframe,
        brief,
        source_name=source_name,
        context=business_context,
    )
    if narrative and narrative_model:
        report += "\n\n" + narrative_to_markdown(narrative, model=narrative_model)

    downloads = st.columns(2)
    downloads[0].download_button(
        "Download executive brief",
        data=report,
        file_name="ada_executive_brief.md",
        mime="text/markdown",
        width="stretch",
    )
    downloads[1].download_button(
        "Download cleaned data",
        data=dataframe.to_csv(index=False).encode("utf-8"),
        file_name="ada_cleaned_data.csv",
        mime="text/csv",
        width="stretch",
    )

    quality_columns = st.columns(4)
    quality_columns[0].metric("Rows analyzed", f"{len(dataframe):,}")
    quality_columns[1].metric("Columns", f"{len(dataframe.columns):,}")
    quality_columns[2].metric(
        "Duplicates removed",
        f"{prepared.cleaning_report.duplicate_rows_removed:,}",
    )
    quality_columns[3].metric("Missing cells", f"{int(dataframe.isna().sum().sum()):,}")

    with st.expander("Cleaning audit"):
        st.dataframe(
            cleaning_audit_frame(prepared.cleaning_report),
            hide_index=True,
            width="stretch",
        )

    st.subheader("Cleaned data")
    st.dataframe(dataframe.head(1_000), width="stretch", height=420)
    st.caption("Preview limited to 1,000 rows. The download includes every analyzed row.")
    st.subheader("Semantic Column & Schema Search")
    search_term = st.text_input(
        "Search column names or keywords",
        placeholder="Type a metric, segment, or column name (e.g. 'revenue', 'region', 'order')",
        help="Semantically filter schema profiles across all uploaded data attributes.",
    )
    prof_df = column_profile(dataframe)
    if search_term:
        filtered_prof = prof_df[
            prof_df["column"].str.contains(search_term, case=False, na=False)
            | prof_df["data_type"].str.contains(search_term, case=False, na=False)
        ]
        st.dataframe(filtered_prof, hide_index=True, width="stretch")
    else:
        st.dataframe(prof_df, hide_index=True, width="stretch")

render_footer()
