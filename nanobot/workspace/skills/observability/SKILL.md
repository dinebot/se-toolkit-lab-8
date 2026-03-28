---
name: observability
description: "Observability skill — query VictoriaLogs and VictoriaTraces to investigate errors and trace request flows."
metadata: {"nanobot":{"emoji":"🔍","always":true}}
---

# Observability Skill

You have access to observability tools that query VictoriaLogs and VictoriaTraces. Use these to investigate system health, errors, and request flows.

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `logs_search` | Search logs using LogsQL | `query` (default "*"), `limit` (default 10), `time_range` (default "1h") |
| `logs_error_count` | Count errors per service | `time_range` (default "1h"), `service` (optional) |
| `traces_list` | List recent traces for a service | `service` (default "Learning Management Service"), `limit` (default 10) |
| `traces_get` | Fetch a specific trace by ID | `trace_id` (required) |

## LogsQL Query Examples

- **All errors**: `severity:ERROR`
- **Errors for a service**: `severity:ERROR AND service.name="Learning Management Service"`
- **Service logs**: `_stream:{service.name="Learning Management Service"}`
- **Specific event**: `event:"db_query"`
- **Time range**: Use the `time_range` parameter (e.g., "1h", "30m", "1d")

## How to Use

### When user asks "What went wrong?" or "Check system health"
**This is a multi-step investigation. Do all steps in one pass:**

1. **Check for errors first**: Call `logs_error_count` with `time_range="30m"` to see if there are recent errors
2. **Get error details**: If errors exist, call `logs_search` with `query="severity:ERROR"` and `time_range="30m"` to see the actual error messages
3. **Extract trace ID**: From the error logs, find the `trace_id` field
4. **Fetch the trace**: Call `traces_get` with that `trace_id` to see the full failure context
5. **Summarize findings**: Combine log evidence + trace evidence into one coherent report:
   - What failed (error message from logs)
   - When it happened (timestamp)
   - Which service/component (from logs)
   - The full request flow (from trace)
   - Root cause hypothesis

### When user asks about errors
1. Call `logs_error_count` with the time range to get an overview
2. If errors found, call `logs_search` with `query="severity:ERROR"` to see details
3. Summarize findings concisely — don't dump raw JSON

### When user asks about a specific service
1. Call `logs_search` with `query='_stream:{service.name="..."}'` to see recent logs
2. If there's a trace ID in the logs, offer to fetch the full trace with `traces_get`

### When user asks about request flows
1. Call `traces_list` to see recent traces
2. Pick a relevant trace ID and call `traces_get` for details
3. Explain the span hierarchy and timing

### When investigating a failure
1. Start with `logs_search` with `query="severity:ERROR"` to find errors
2. Extract the `trace_id` from error logs
3. Call `traces_get` with that trace ID to see the full failure context
4. Report: what failed, where, and when

## Response Style

- **Be concise**: Summarize findings in 2-3 sentences
- **Highlight errors**: Use ⚠️ for concerning findings
- **Include timestamps**: Mention when errors occurred
- **Offer follow-up**: "Would you like me to fetch the full trace?" or "Should I check a different time range?"

## What You Cannot Do

- You cannot modify logs or traces (read-only)
- You cannot access real-time metrics (only logs and traces)
- You cannot query logs older than the retention period (7 days by default)

## Example Interactions

**User**: "Any errors in the last hour?"
**You**: Call `logs_error_count` with `time_range="1h"`. If errors found, call `logs_search` with `query="severity:ERROR"`. Summarize.

**User**: "Show me logs from the backend"
**You**: Call `logs_search` with `query='_stream:{service.name="Learning Management Service"}'`.

**User**: "What happened in trace abc123?"
**You**: Call `traces_get` with `trace_id="abc123"`. Explain the span hierarchy and any errors.

**User**: "Is the system healthy?"
**You**: Call `logs_error_count` for recent time. If no errors, report healthy. If errors, summarize.
