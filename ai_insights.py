"""Optional evidence-grounded narrative synthesis through the Responses API."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Literal, Protocol

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype
from pydantic import BaseModel, Field

from business_insights import BusinessBrief, ColumnRoles
from nlq import QueryPlan, ValueFilter


class AIAction(BaseModel):
    title: str = Field(max_length=90)
    recommendation: str = Field(max_length=320)
    evidence: str = Field(max_length=320)
    confidence: Literal["high", "medium", "low"]


class AINarrative(BaseModel):
    executive_summary: str = Field(max_length=650)
    strategic_read: str = Field(max_length=900)
    actions: list[AIAction] = Field(min_length=1, max_length=3)
    watchouts: list[str] = Field(max_length=3)


@dataclass(frozen=True)
class AIConfig:
    model: str
    reasoning_effort: Literal["none", "low", "medium", "high"]
    label: str


MODEL_PRESETS = {
    "Fast · Luna": AIConfig("gpt-5.6-luna", "low", "Fast · Luna"),
    "Deep · Terra": AIConfig("gpt-5.6-terra", "medium", "Deep · Terra"),
    "Groq · LLaMA 3.3 70B": AIConfig("llama-3.3-70b-versatile", "low", "Groq · LLaMA 3.3 70B"),
    "Groq · Qwen 2.5 Coder": AIConfig("qwen-2.5-coder-32b", "low", "Groq · Qwen 2.5 Coder"),
    "Groq · Mixtral 8x7B": AIConfig("mixtral-8x7b-32768", "low", "Groq · Mixtral 8x7B"),
}

DEFAULT_PRESET = "Fast · Luna"


class _Responses(Protocol):
    def parse(self, **kwargs: object) -> object: ...


class _Client(Protocol):
    responses: _Responses


SYSTEM_INSTRUCTIONS = """You are ADA's strategic interpretation layer.
Use only the supplied deterministic calculations and business context.
Never invent numbers, entities, benchmarks, causes, or certainty.
Distinguish observed evidence from hypotheses. Make actions specific, testable, and prioritized.
If evidence is insufficient, state the limitation instead of filling the gap.
Write for an operator who needs the decision, not an analytics lecture.
Return your response as a valid JSON object matching the schema."""


def build_ai_payload(brief: BusinessBrief, *, context: str = "") -> str:
    """Serialize only computed evidence; raw uploaded rows never enter the prompt."""
    payload = {
        "business_context": context.strip() or "Not provided",
        "detected_schema": asdict(brief.roles),
        "executive_headline": brief.headline,
        "computed_summary": brief.summary,
        "computed_evidence": [asdict(item) for item in brief.evidence],
        "deterministic_recommendations": [asdict(item) for item in brief.recommendations],
        "required_json_schema": AINarrative.model_json_schema(),
        "task": (
            "Synthesize the business meaning into a single JSON object matching required_json_schema strictly. "
            "Root keys MUST be 'executive_summary', 'strategic_read', 'actions' (list of objects with title, recommendation, evidence, confidence), and 'watchouts' (list of strings)."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def generate_ai_narrative(
    brief: BusinessBrief,
    *,
    api_key: str,
    config: AIConfig,
    context: str = "",
    safety_identifier: str = "",
    base_url: str | None = None,
    client: _Client | None = None,
) -> AINarrative:
    """Generate a typed narrative while keeping the deterministic brief authoritative."""
    if not api_key.strip():
        raise ValueError("An API key is required for the optional AI narrative.")

    is_groq = api_key.startswith("gsk_") or any(k in config.model for k in ("llama", "mixtral", "qwen"))
    resolved_base_url = base_url or ("https://api.groq.com/openai/v1" if is_groq else None)

    if client is None:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=resolved_base_url, timeout=25.0, max_retries=1)

    if is_groq:
        chat_res = client.chat.completions.create(
            model=config.model,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": build_ai_payload(brief, context=context)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = chat_res.choices[0].message.content or "{}"
        return AINarrative.model_validate_json(content)

    response = client.responses.parse(
        model=config.model,
        instructions=SYSTEM_INSTRUCTIONS,
        input=build_ai_payload(brief, context=context),
        text_format=AINarrative,
        reasoning={"effort": config.reasoning_effort},
        max_output_tokens=1_400,
        safety_identifier=safety_identifier,
        store=False,
    )
    narrative = getattr(response, "output_parsed", None)
    if narrative is None:
        raise RuntimeError("The strategy agent returned no structured narrative.")
    if isinstance(narrative, AINarrative):
        return narrative
    return AINarrative.model_validate(narrative)


class AIQueryFilter(BaseModel):
    column: str
    value: str = Field(max_length=120)


class AIQueryPlan(BaseModel):
    """Typed plan the model must emit; execution always happens locally."""

    answerable: bool
    intent: Literal["aggregate", "count", "rank", "breakdown", "trend", "growth", "overview", "greeting", "scatter"] = "aggregate"
    aggregation: Literal["sum", "mean", "median", "min", "max", "count"] = "sum"
    measure: str | None = None
    dimension: str | None = None
    top_n: int | None = Field(default=None, ge=1, le=50)
    ascending: bool = False
    filters: list[AIQueryFilter] = Field(default_factory=list, max_length=4)
    year: int | None = Field(default=None, ge=1900, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    grain: Literal["D", "W", "M", "Q", "Y"] | None = None
    explanation: str | None = Field(default=None, max_length=350)
    use_pie: bool = False
    scatter_x: str | None = None  # secondary numeric column for scatter chart


PLANNER_CONFIG = AIConfig("gpt-5.6-luna", "low", "Query planner")

PLANNER_INSTRUCTIONS = """You are ADA's Natural Language Query Compiler & Conversation Agent.
Your job is to translate any user question into an explicit JSON query plan for the loaded table schema.

Rules:
1. GREETINGS & CASUAL INTROS ("hi", "hello", "who are you", "what can you do", "hey"):
   - Set answerable = true, intent = "greeting".
2. VAGUE & OVERVIEW INQUIRIES ("what about this", "what is this about", "brief it", "summary", "explain this"):
   - Set answerable = true, intent = "overview".
3. SPECIFIC DATA QUESTIONS (totals, top 5, trends, breakdowns):
   - Set answerable = true, match listed column names exactly.
4. OUT-OF-DOMAIN / UNRELATED QUESTIONS ("who won the world cup", "tell me a joke", "recipe for pizza"):
   - Set answerable = false, and set explanation to a polite note stating you are an AI Data Analyst focused on the uploaded dataset, suggesting relevant dataset questions instead.
5. PROPORTION / SHARE / COMPOSITION QUESTIONS ("what share", "percentage", "pie chart", "distribution", "proportion"):
   - Set intent = "breakdown" or "rank" AND set use_pie = true. Do NOT set intent to "pie".
6. CORRELATION / COMPARISON BETWEEN TWO COLUMNS ("vs", "versus", "compare X and Y", "relationship between", "scatter"):
   - Set intent = "scatter", measure = primary numeric column (y-axis), scatter_x = secondary numeric column (x-axis).
7. FOLLOW-UP / CONTEXT-DEPENDENT QUESTIONS: When the conversation history contains prior questions, resolve ambiguous references like "that", "same", "it", "by region" by using the prior turn's measure/dimension as context.
Return your output as a valid JSON object matching the query plan schema."""


def build_query_schema(dataframe: pd.DataFrame, roles: ColumnRoles) -> list[dict[str, str]]:
    """Describe columns for the planner without exposing a single cell value."""
    schema: list[dict[str, str]] = []
    for column in dataframe.columns:
        series = dataframe[column]
        if is_datetime64_any_dtype(series):
            kind = "datetime"
        elif is_numeric_dtype(series):
            kind = "numeric"
        else:
            kind = "category"
        if column == roles.measure:
            role = "primary measure"
        elif column == roles.date:
            role = "date"
        elif column == roles.dimension:
            role = "primary dimension"
        elif column == roles.identifier:
            role = "identifier"
        elif column in roles.dimensions:
            role = "dimension"
        else:
            role = "other"
        schema.append({"column": column, "type": kind, "role": role})
    return schema


def build_planner_payload(question: str, dataframe: pd.DataFrame, roles: ColumnRoles) -> str:
    payload = {
        "question": question.strip(),
        "columns": build_query_schema(dataframe, roles),
        "required_json_schema": AIQueryPlan.model_json_schema(),
        "task": "Emit the single best query plan for this question matching required_json_schema, or set answerable to false.",
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _resolve_filter(item: AIQueryFilter, dataframe: pd.DataFrame) -> ValueFilter | None:
    """Map a quoted filter phrase onto real values; refuse rather than guess."""
    if item.column not in dataframe.columns:
        return None
    wanted = item.value.casefold().strip()
    matched = tuple(
        str(value)
        for value in dataframe[item.column].dropna().unique()
        if str(value).casefold().strip() == wanted
    )
    return ValueFilter(column=item.column, values=matched) if matched else None


def _to_query_plan(
    parsed: AIQueryPlan, dataframe: pd.DataFrame, roles: ColumnRoles
) -> QueryPlan | None:
    measure = parsed.measure or roles.measure
    dimension = parsed.dimension
    for column in (parsed.measure, parsed.dimension):
        if column is not None and column not in dataframe.columns:
            return None
    if parsed.intent in ("trend", "growth") and not roles.date:
        return None
    if parsed.intent == "aggregate" and not measure:
        return None
    if parsed.intent in ("rank", "breakdown"):
        dimension = dimension or roles.dimension
        if not dimension:
            return None
    filters: list[ValueFilter] = []
    for item in parsed.filters:
        resolved = _resolve_filter(item, dataframe)
        if resolved is None:
            return None
        filters.append(resolved)
    return QueryPlan(
        intent=parsed.intent,
        aggregation=parsed.aggregation,
        measure=measure,
        dimension=dimension,
        top_n=parsed.top_n,
        ascending=parsed.ascending,
        filters=tuple(filters),
        year=parsed.year,
        month=parsed.month,
        grain=parsed.grain,
        source="ai",
        explanation=parsed.explanation,
        use_pie=getattr(parsed, "use_pie", False),
        scatter_x=getattr(parsed, "scatter_x", None),
    )


def plan_query_with_ai(
    question: str,
    dataframe: pd.DataFrame,
    roles: ColumnRoles,
    *,
    api_key: str,
    safety_identifier: str = "",
    config: AIConfig = PLANNER_CONFIG,
    base_url: str | None = None,
    client: _Client | None = None,
    chat_history: list[dict] | None = None,
) -> QueryPlan | None:
    """Ask the model for a typed plan over the schema; execution stays local.

    Args:
        chat_history: Optional list of prior chat entries (dicts with 'question' and 'result' keys).
            The last up to 5 turns are forwarded as conversation context so the model can resolve
            follow-up references like 'now show that by region' or 'same for last year'.
    """
    if not api_key.strip():
        raise ValueError("An API key is required for the optional AI query planner.")
    if not question.strip():
        return None

    is_groq = api_key.startswith("gsk_") or any(k in config.model for k in ("llama", "mixtral", "qwen"))
    resolved_base_url = base_url or ("https://api.groq.com/openai/v1" if is_groq else None)

    if client is None:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=resolved_base_url, timeout=25.0, max_retries=1)

    if is_groq:
        # Build messages list: system + last-N prior turns + current question
        messages: list[dict] = [{"role": "system", "content": PLANNER_INSTRUCTIONS}]
        # Inject up to 5 prior turns for multi-turn context (question + answer text only)
        if chat_history:
            for prior in chat_history[-5:]:
                prior_q = prior.get("question", "")
                prior_result = prior.get("result")
                if prior_q:
                    messages.append({"role": "user", "content": prior_q})
                if prior_result is not None and hasattr(prior_result, "answer"):
                    messages.append({"role": "assistant", "content": prior_result.answer})
        # Current question payload
        messages.append({"role": "user", "content": build_planner_payload(question, dataframe, roles)})
        chat_res = client.chat.completions.create(
            model=config.model if "llama" in config.model or "qwen" in config.model or "mixtral" in config.model else "llama-3.3-70b-versatile",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = chat_res.choices[0].message.content or "{}"
        parsed = AIQueryPlan.model_validate_json(content)
    else:
        response = client.responses.parse(
            model=config.model,
            instructions=PLANNER_INSTRUCTIONS,
            input=build_planner_payload(question, dataframe, roles),
            text_format=AIQueryPlan,
            reasoning={"effort": config.reasoning_effort},
            max_output_tokens=500,
            safety_identifier=safety_identifier,
            store=False,
        )
        parsed = getattr(response, "output_parsed", None)

    if parsed is None:
        return None
    if not isinstance(parsed, AIQueryPlan):
        parsed = AIQueryPlan.model_validate(parsed)
    if not parsed.answerable:
        if parsed.explanation:
            return QueryPlan(
                intent="greeting",
                measure=roles.measure,
                dimension=roles.dimension,
                source="ai_explanation",
                explanation=parsed.explanation,
            )
        return None
    return _to_query_plan(parsed, dataframe, roles)


def narrative_to_markdown(narrative: AINarrative, *, model: str) -> str:
    lines = [
        "## Optional AI strategic read",
        "",
        narrative.executive_summary,
        "",
        narrative.strategic_read,
        "",
        "### Recommended actions",
        "",
    ]
    for action in narrative.actions:
        lines.extend(
            [
                f"#### {action.title} · {action.confidence.title()} confidence",
                "",
                action.recommendation,
                "",
                f"_Evidence: {action.evidence}_",
                "",
            ]
        )
    if narrative.watchouts:
        lines.extend(["### Watchouts", ""])
        lines.extend(f"- {item}" for item in narrative.watchouts)
        lines.append("")
    lines.extend(
        [
            f"_Generated with {model} from the calculated evidence above; raw rows were not sent._",
            "",
        ]
    )
    return "\n".join(lines)


def test_ai_connection(api_key: str) -> tuple[bool, int, str]:
    """Test API connection to Groq / OpenAI model and measure latency in ms."""
    if not api_key or not api_key.strip():
        return False, 0, "No API key provided"

    start_time = time.time()
    try:
        is_groq = api_key.startswith("gsk_")
        resolved_base_url = "https://api.groq.com/openai/v1" if is_groq else None
        from openai import OpenAI

        client = OpenAI(api_key=api_key.strip(), base_url=resolved_base_url, timeout=10.0, max_retries=0)

        model = "llama-3.3-70b-versatile" if is_groq else "gpt-4o-mini"
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        latency_ms = int((time.time() - start_time) * 1000)
        model_label = "Groq LLaMA 3.3 70B" if is_groq else "OpenAI Model"
        return True, latency_ms, f"{model_label} Online ({latency_ms}ms)"
    except Exception as exc:
        latency_ms = int((time.time() - start_time) * 1000)
        return False, latency_ms, f"Offline ({str(exc)[:60]})"

