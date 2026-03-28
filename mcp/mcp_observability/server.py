"""Observability MCP server exposing VictoriaLogs and VictoriaTraces APIs."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

server = Server("observability")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_victorialogs_url: str = ""
_victoriatraces_url: str = ""


def _get_victorialogs_url() -> str:
    return _victorialogs_url or os.environ.get("VICTORIALOGS_URL", "http://victorialogs:9428")


def _get_victoriatraces_url() -> str:
    return _victoriatraces_url or os.environ.get("VICTORIATRACES_URL", "http://victoriatraces:10428")


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class _LogsSearchQuery(BaseModel):
    query: str = Field(
        default="*",
        description="LogsQL query string. Use 'severity:ERROR' for errors, '_stream:{service.name=\"backend\"}' for service filter.",
    )
    limit: int = Field(default=10, ge=1, le=1000, description="Max entries to return.")
    time_range: str = Field(
        default="1h",
        description="Time range like '1h', '30m', '1d'. Default is 1 hour.",
    )


class _LogsErrorCountQuery(BaseModel):
    time_range: str = Field(
        default="1h",
        description="Time range like '1h', '30m', '1d'. Default is 1 hour.",
    )
    service: str = Field(
        default="",
        description="Optional service name filter, e.g., 'Learning Management Service'.",
    )


class _TracesListQuery(BaseModel):
    service: str = Field(
        default="Learning Management Service",
        description="Service name to list traces for.",
    )
    limit: int = Field(default=10, ge=1, le=100, description="Max traces to return.")


class _TracesGetQuery(BaseModel):
    trace_id: str = Field(description="The trace ID to fetch.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text(data: Any) -> list[TextContent]:
    """Serialize data to JSON text."""
    if isinstance(data, (dict, list)):
        return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False))]
    return [TextContent(type="text", text=str(data))]


async def _http_get(url: str, params: dict[str, str] | None = None) -> Any:
    """Make an HTTP GET request."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


async def _logs_search(args: _LogsSearchQuery) -> list[TextContent]:
    """Search VictoriaLogs using LogsQL."""
    url = f"{_get_victorialogs_url()}/select/logsql/query"
    params = {
        "query": args.query,
        "limit": str(args.limit),
    }
    try:
        result = await _http_get(url, params)
        return _text(result)
    except httpx.HTTPError as e:
        return _text({"error": f"VictoriaLogs query failed: {e}"})


async def _logs_error_count(args: _LogsErrorCountQuery) -> list[TextContent]:
    """Count errors per service over a time window."""
    url = f"{_get_victorialogs_url()}/select/logsql/stats_query"
    query = "severity:ERROR"
    if args.service:
        query = f'severity:ERROR AND service.name="{args.service}"'
    params = {
        "query": f"{query} | stats by(service.name) count()",
        "time": args.time_range,
    }
    try:
        result = await _http_get(url, params)
        return _text(result)
    except httpx.HTTPError as e:
        return _text({"error": f"VictoriaLogs stats query failed: {e}"})


async def _traces_list(args: _TracesListQuery) -> list[TextContent]:
    """List recent traces for a service."""
    url = f"{_get_victoriatraces_url()}/jaeger/api/traces"
    params = {
        "service": args.service,
        "limit": str(args.limit),
    }
    try:
        result = await _http_get(url, params)
        return _text(result)
    except httpx.HTTPError as e:
        return _text({"error": f"VictoriaTraces list failed: {e}"})


async def _traces_get(args: _TracesGetQuery) -> list[TextContent]:
    """Fetch a specific trace by ID."""
    url = f"{_get_victoriatraces_url()}/jaeger/api/traces/{urllib.parse.quote(args.trace_id)}"
    try:
        result = await _http_get(url)
        return _text(result)
    except httpx.HTTPError as e:
        return _text({"error": f"VictoriaTraces fetch failed: {e}"})


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_Registry = tuple[type[BaseModel], Callable[..., Awaitable[list[TextContent]]], Tool]

_TOOLS: dict[str, _Registry] = {}


def _register(
    name: str,
    description: str,
    model: type[BaseModel],
    handler: Callable[..., Awaitable[list[TextContent]]],
) -> None:
    schema = model.model_json_schema()
    schema.pop("$defs", None)
    schema.pop("title", None)
    _TOOLS[name] = (model, handler, Tool(name=name, description=description, inputSchema=schema))


_register(
    "logs_search",
    "Search logs in VictoriaLogs using LogsQL. Use 'severity:ERROR' for errors, '_stream:{service.name=\"...\"}' for service filter.",
    _LogsSearchQuery,
    _logs_search,
)
_register(
    "logs_error_count",
    "Count errors per service over a time window. Returns stats grouped by service name.",
    _LogsErrorCountQuery,
    _logs_error_count,
)
_register(
    "traces_list",
    "List recent traces for a service from VictoriaTraces.",
    _TracesListQuery,
    _traces_list,
)
_register(
    "traces_get",
    "Fetch a specific trace by ID from VictoriaTraces.",
    _TracesGetQuery,
    _traces_get,
)


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [entry[2] for entry in _TOOLS.values()]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    entry = _TOOLS.get(name)
    if entry is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    model_cls, handler, _ = entry
    try:
        args = model_cls.model_validate(arguments or {})
        return await handler(args)
    except Exception as exc:
        return [TextContent(type="text", text=f"Error: {type(exc).__name__}: {exc}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
