"""Agent tools: schemas + handlers.

The LLM sees only the schemas. Handlers run server-side: they read from the
InfluxClient (with the safety filter), the schema cache (SQLite), and the
result cache (in-memory).

`render_response` is the *terminal* tool — when the LLM calls it, the agent
loop ends and the result is what the user sees.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

from app.influx.client import InfluxClient
from app.influx.safety import UnsafeQueryError
from app.llm.provider import ToolDef
from app.state.models import SchemaCache
from app.state.results import ResultCache

logger = logging.getLogger(__name__)


GET_SCHEMA_FOR = ToolDef(
    name="get_schema_for",
    description=(
        "Look up tag keys, field keys, and sample tag values for one or more "
        "measurements. Use this BEFORE writing an InfluxQL query so you know which "
        "fields and tags exist on those measurements."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "measurements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Measurement names to look up.",
                "minItems": 1,
                "maxItems": 10,
            }
        },
        "required": ["measurements"],
    },
)

RUN_INFLUXQL = ToolDef(
    name="run_influxql",
    description=(
        "Execute a read-only InfluxQL query against the user's InfluxDB and return "
        "a small preview (first 5 rows + row count + time range + a `data_ref` "
        "you pass to render_response). The full data stays server-side. Only "
        "SELECT, SHOW, and EXPLAIN are accepted."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The InfluxQL statement to run.",
            }
        },
        "required": ["query"],
    },
)

RENDER_RESPONSE = ToolDef(
    name="render_response",
    description=(
        "Send the final answer back to the user and end this turn. Call this once "
        "you've gathered enough data. The summary is shown as text; the chart spec "
        "is rendered with Plotly client-side; the full data table is fetched from "
        "data_ref. Always include the InfluxQL query you used so the user can "
        "see and trust it."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "1–6 sentences of natural-language explanation.",
            },
            "query": {
                "type": "string",
                "description": "The final InfluxQL you ran (for the debug panel).",
            },
            "chart": {
                "type": ["object", "null"],
                "description": (
                    "Optional chart spec. Shape: "
                    "{type: line|bar|scatter|heatmap|table, x, y, series_by?, title}."
                ),
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["line", "bar", "scatter", "heatmap", "table"],
                    },
                    "x": {"type": "string"},
                    "y": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}},
                        ]
                    },
                    "series_by": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["type", "title"],
            },
            "data_ref": {
                "type": ["string", "null"],
                "description": "The data_ref returned by run_influxql, if any.",
            },
        },
        "required": ["summary", "query"],
    },
)

ALL_TOOLS: list[ToolDef] = [GET_SCHEMA_FOR, RUN_INFLUXQL, RENDER_RESPONSE]
TERMINAL_TOOL_NAME = "render_response"


@dataclass
class FinalResponse:
    summary: str
    query: str
    chart: dict[str, Any] | None
    data_ref: str | None
    raw_input: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolContext:
    influx: InfluxClient
    db_session: Session
    results: ResultCache


async def handle_tool_call(
    name: str,
    tool_input: dict[str, Any],
    ctx: ToolContext,
) -> tuple[str, FinalResponse | None, bool]:
    """Run the tool. Returns (string_to_send_back_to_llm, final_response, is_error)."""
    try:
        if name == GET_SCHEMA_FOR.name:
            payload = _handle_get_schema_for(tool_input, ctx)
            return json.dumps(payload), None, False
        if name == RUN_INFLUXQL.name:
            payload = await _handle_run_influxql(tool_input, ctx)
            return json.dumps(payload), None, False
        if name == RENDER_RESPONSE.name:
            final = FinalResponse(
                summary=tool_input.get("summary", ""),
                query=tool_input.get("query", ""),
                chart=tool_input.get("chart"),
                data_ref=tool_input.get("data_ref"),
                raw_input=tool_input,
            )
            return "ok", final, False
        return f"unknown tool: {name}", None, True
    except UnsafeQueryError as exc:
        return f"query rejected by safety filter: {exc}", None, True
    except Exception as exc:
        logger.exception("tool %s failed", name)
        return f"error executing {name}: {exc}", None, True


def _handle_get_schema_for(tool_input: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    names: list[str] = tool_input.get("measurements", []) or []
    out: dict[str, Any] = {}
    for n in names:
        row = ctx.db_session.get(SchemaCache, n)
        if row is None:
            out[n] = {"error": "unknown measurement"}
            continue
        out[n] = {
            "tag_keys": row.tag_keys,
            "field_keys": row.field_keys,
            "tag_values": row.tag_values,
        }
    return out


async def _handle_run_influxql(
    tool_input: dict[str, Any], ctx: ToolContext
) -> dict[str, Any]:
    query = tool_input.get("query", "").strip()
    if not query:
        return {"error": "query is empty"}

    result = await ctx.influx.query(query)

    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    for s in result.series:
        tags = s.get("tags") or {}
        for p in s["points"]:
            row = {**p}
            for k, v in tags.items():
                row.setdefault(k, v)
            for k in row:
                if k not in columns:
                    columns.append(k)
            rows.append(row)

    time_range: dict[str, Any] = {}
    if rows and "time" in columns:
        times = [r.get("time") for r in rows if r.get("time") is not None]
        if times:
            time_range = {"start": str(min(times)), "end": str(max(times))}

    ref = ctx.results.put(
        sql=result.sql,
        columns=columns,
        rows=rows,
        metadata={"row_count": len(rows), "time_range": time_range},
    )

    preview_rows = rows[:5]

    return {
        "data_ref": ref,
        "executed_sql": result.sql,
        "row_count": len(rows),
        "columns": columns,
        "time_range": time_range,
        "preview": preview_rows,
        "truncated": len(rows) > 5,
    }
