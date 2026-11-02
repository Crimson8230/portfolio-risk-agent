# Portfolio Risk Agent — MVP Specification

## 1. Purpose and assignment

Build a small educational agent that analyzes a portfolio and answers questions about its composition and position concentration.

The university assignment requires a suitable process, prototype tools, LLM integration if available, implemented guardrails, and submission through GitHub or Gitea.

The agent selects tools. Python calculates all portfolio metrics. The application controls execution. This is a teaching prototype, not a trading system or a comprehensive financial risk assessment.

All code, prompts, documentation, CLI messages, and commit messages must be in English. Work in small phases with tests and review between phases.

## 2. MVP scope

Required:
- JSON portfolio input and a small local asset catalog.
- Three independently callable, deterministic analysis tools.
- CLI for offline analysis and individual natural-language questions in agent mode.
- Optional OpenAI Responses API integration when credentials are available; offline operation must remain usable without credentials.
- Input validation, controlled tool execution, execution limits, and safe failure handling.
- Visible execution trace and optional JSON export for evaluation.
- Offline tests, sample data, demo scenarios, and one clear README.

Excluded:
- Streamlit or another web UI, charts, CSV, chat history, and session management.
- A separate diversification tool.
- Live market data, external asset lookup, ETF look-through, databases, and user accounts.
- Orders, buy/sell instructions, return forecasts, volatility, correlations, and Value at Risk.
- Comprehensive automatic verification of arbitrary LLM prose.

## 3. Input and catalog

Input contract:

```json
{
  "currency": "EUR",
  "holdings": [
    {"isin": "US0378331005", "value": 4000},
    {"isin": "US5949181045", "value": 3000},
    {"isin": "IE00B4L5Y983", "value": 3000}
  ]
}
```

`value` is the current position market value in EUR, not a share quantity. No currency conversion occurs.

Validation:
- UTF-8 JSON, maximum file size 1 MB (1,048,576 bytes).
- Only EUR; 1–100 holdings; reject additional fields.
- Uppercase ISIN with valid format and Luhn check digit.
- Reject duplicate ISINs and ISINs missing from the local catalog.
- Values must be JSON numbers, finite, greater than zero, and at most EUR 10 million per position. Reject booleans and numeric strings.
- Parse monetary values as `Decimal`; round only for display. Serialize monetary values as decimal strings in tool output and trace exports.
- Questions must contain non-whitespace text and be at most 2,000 characters.
- Uploaded/input portfolio content is never persisted automatically.

Initial offline catalog:

| ISIN | Name | Asset type | Direct-stock sector | Direct-stock country |
|---|---|---|---|---|
| US0378331005 | Apple Inc. | stock | Technology | US |
| US5949181045 | Microsoft Corp. | stock | Technology | US |
| IE00B4L5Y983 | iShares Core MSCI World UCITS ETF | etf | unavailable | unavailable |

The catalog is demonstration data. ETF underlying sector and country exposures are unknown; do not use domicile as an exposure proxy.

## 4. Deterministic tools

Tools are typed Python functions with JSON-serializable output and no LLM calls. All three operate on trusted, previously validated portfolio context supplied by the application. The LLM-facing tools take no arguments.

### `get_asset_data`

Return the local catalog metadata for all holdings and identify missing ETF look-through information.

### `calculate_allocation`

Return total EUR value, position weights, and allocation by asset type. Show direct-stock sector/country allocations separately from an unresolved ETF look-through bucket.

`position_weight_pct = 100 * position_value / total_value`

Display percentages to two decimal places; do not round intermediate calculations. Direct technology stocks representing 70% does not establish total technology exposure, because the ETF may also hold technology stocks.

### `analyze_concentration`

Return the largest position, all positions tied for largest, and position-level HHI:

`HHI = sum((position_value / total_value) ** 2)`

Illustrative `concentration_flag` based on the largest position:
- `HIGH`: greater than 40%.
- `MODERATE`: greater than 20% and at most 40%.
- `LOW`: at most 20%.

Preserve input order for tied positions. The flag is an arbitrary teaching heuristic, not a validated overall risk rating. ETF holdings are treated as individual instruments; HHI does not measure their underlying diversification or overlap.

Expected sample result: EUR 10,000 total, weights 40/30/30%, largest position Apple at 40%, HHI 0.34, flag `MODERATE`.

## 5. Agent and guardrails

Flow:

```text
JSON → validation → trusted portfolio context
Question → LLM tool selection → validated dispatcher → Python tools
         ← tool results ← execution trace
         → final explanation + separately displayed verified facts
```

- Use Python 3.11+, Pydantic v2, pytest, and the OpenAI Python SDK for optional Responses API integration. Keep dependencies minimal and document compatible versions.
- Read credentials and model configuration from the environment; provide `.env.example` and never commit secrets.
- The model adapter must support fake responses for offline tests.
- Each question starts a new run; no conversation memory is required.
- Only the three named tools are allowed. Validate tool names and strict empty argument objects; reject malformed JSON and unexpected arguments.
- Never accept portfolio replacements, paths, URLs, or executable code from model tool arguments.
- No shell, filesystem, trading, payment, or arbitrary network tool is exposed to the model. The application reads the explicit local input/catalog files and may call the configured LLM API.
- Allow at most four tool-call rounds, eight attempted tool calls, and five model requests per run. Count rejected attempts toward the tool budget. Never execute calls beyond the limit.
- Use a 30-second API request timeout, no automatic SDK retries, and a maximum output budget of 2,000 tokens per model response. These bound calls and outputs; they are not a fixed monetary cost guarantee.
- Match tool results to the exact provider call ID.
- On invalid calls, exceeded limits, API errors, or tool failures, stop the run and display a safe error and available verified facts. Do not continue with an unchecked answer.
- Treat questions and portfolio content as untrusted data. Instructions cannot override application permissions.
- Instruct the model to use tool results for numbers, acknowledge unavailable data, avoid guarantees and personalized trading decisions, and distinguish concentration from overall investment risk.
- Present tool facts separately from the LLM explanation. Label model prose as an AI explanation; it is not fully automatically fact-checked. Prompts and disclaimers do not replace execution controls.
- Explain that tool results sent to the LLM may reveal holdings, values, and derived metrics. Offline mode makes no LLM requests.

## 6. Execution trace and evaluation

The execution trace is a required deliverable. It records observable application actions, not private model reasoning or chain of thought.

Show a concise trace in the CLI. Support optional export through an explicit `--trace-out PATH` argument. The path comes from the CLI user, never from the LLM. Refuse to overwrite an existing file. No trace file is written by default.

Export one structured JSON document per run with:
- Trace schema version, run ID, UTC start/end timestamps, mode, and final status (`success`, `rejected`, or `error`).
- In agent mode: configured model, question, and model request count.
- Ordered events with sequence number, UTC timestamp, event type, and duration where applicable.
- Input validation success or safe rejection details.
- Each model request and response status; provider usage counts if available.
- Every requested tool name, provider call ID, validated arguments or safe rejection reason, and execution status.
- Actual tool results for successful calls and safe error codes/messages for failed or blocked calls.
- Guardrail events, including denied tools and exhausted execution budgets.
- Final displayed answer and the verified facts available to the user.

Never record API keys, authorization headers, environment dumps, raw HTTP payloads, stack traces, or private model reasoning. For malformed or unexpected tool arguments, record the rejection reason rather than the raw payload. Do not copy the original portfolio file into the trace. Tool results and questions may still contain sensitive portfolio information; explain this before users explicitly export or share traces. Escape control characters in terminal output.

The trace must make these questions answerable:
1. Which tools did the agent request and in what order?
2. Which calls actually ran, with what results?
3. Which actions were blocked and why?
4. Did the run terminate within its limits?
5. Which verified facts support the displayed answer?

No evaluation dashboard or separate logging service is required.

## 7. Tests and demonstration

All automated tests run without API credentials or network calls.

Required tests:
- Valid sample input and expected totals, allocation, HHI, and concentration flag.
- ISIN checksum, malformed JSON, unsupported currency, duplicates, unknown assets, empty/oversized holdings, extra fields, and invalid monetary values.
- File-size and question-length limits.
- Concentration threshold boundaries and tied largest positions.
- ETF look-through remains explicitly unknown.
- Fake-model sequence: request tools, receive matching results, produce a final answer.
- Unauthorized tools, malformed/unexpected arguments, call/round limits, model timeout, and tool exceptions.
- Offline analysis without an API key.
- Ordered trace events, successful and blocked calls, JSON export, overwrite prevention, and omission of secrets/raw rejected payloads.

README demo scenarios:
1. Offline sample analysis: 40/30/30%, HHI 0.34.
2. Agent question: "How concentrated is my portfolio?" with visible tool selection and result.
3. Invalid input rejected before any model invocation.
4. Simulated `execute_trade` request blocked by the dispatcher and recorded in the trace.
5. ETF exposure question answered with the known limitation.

A real LLM smoke test is manual and optional when credentials are available. Document whether it was performed; do not present fake-model tests as a live integration test.

## 8. Implementation phases

### Phase 1 — Offline core

Create models, ISIN validation, JSON loader, local catalog, sample portfolio, three tools, CLI analysis, and tests. No LLM integration yet. Verify the sample results and rejection cases.

### Phase 2 — Controlled agent

Add strict tool schemas, dispatcher, model adapter, bounded agent loop, CLI question mode, visible trace, optional JSON trace export, and offline fake-model tests. Implement execution guardrails alongside the agent, not as a later retrofit.

### Phase 3 — Evaluation and submission

Complete adversarial tests and trace checks, document the five demos, and verify clean installation. Perform a live smoke test only if credentials are available. Prepare the repository for GitHub/Gitea submission; do not publish or push without user instruction.

At each phase: explain the next changes, implement only that phase, run relevant tests, and present results for review.

## 9. Definition of done

A fresh clone can install documented dependencies, run all tests offline, and analyze the sample portfolio. With configured credentials it can answer an individual question through controlled LLM tool calling. The trace shows successful and denied actions and can be explicitly exported. The README explains setup, tools, architecture, guardrails, demo commands, data limitations, and any untested live integration.

Ignore `.venv/`, `.env`, Python/test caches, and generated trace exports in Git. Keep `.env.example` tracked. No credentials or user portfolio exports belong in the submission.
