# Portfolio Risk Agent

Educational CLI agent for EUR portfolio composition and position concentration.
It validates a local JSON portfolio, lets an LLM select among three tools, and
explains deterministic Python results. It never places trades.

The prototype fulfills the assignment's process selection, prototype tools,
optional LLM execution, and implemented guardrails. Three live scenarios were
verified with `gpt-4.1-mini` on 2026-11-01. See [Evaluation evidence](#evaluation-evidence).

## Why use an agent?

Different questions require different analyses. The model chooses whether to
retrieve metadata, calculate allocations, analyze concentration, or explain a
known limitation. Python performs the calculations, and application code
controls permissions and execution limits. Offline mode calls all tools directly.

## Architecture

```text
Local JSON → bounded parser → Pydantic + ISIN + catalog validation
                                      ↓
                            Trusted portfolio context
                                      ↓
Question → model → tool request → allowlisted dispatcher → Python tool
             ↑                                               ↓
             └──────── results with matching call IDs ────────┘
             ↓
AI explanation + separately displayed verified facts + execution trace
```

Only the question and requested tool results cross the model boundary. A model
cannot replace the portfolio or supply local paths. No shell, trading, payment,
filesystem, or arbitrary network tool is exposed.

## Setup and tests

Use Python 3.11 or newer. The verified environment is Python 3.12 on Linux.
Ubuntu may require `sudo apt-get install python3.12-venv` for its Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m pytest -q
```

`requirements-lock.txt` records the tested dependency snapshot. The shorter
`requirements.txt` defines allowed direct dependency ranges for development.
All automated tests run offline with fake model responses or mock HTTP; they
never need credentials. Run commands from the repository root.

## Offline analysis

```bash
python cli.py data/sample_portfolio.json
```

Expected result:

| Metric | Value |
|---|---|
| Total market value | EUR 10,000 |
| Apple / Microsoft / ETF weights | 40% / 30% / 30% |
| Largest position | Apple, 40% |
| Position HHI | 0.34 |
| Illustrative concentration flag | MODERATE |
| Direct technology stocks | 70%; ETF look-through unresolved |

No API key or external network request is needed in offline mode.

## Docker

Docker packages the CLI and its dependencies. It does not provide a web server
or a local language model. Python need not be installed on the host. Use a
Docker Engine/Desktop installation with a running daemon and permission to
access it. Build from the repository root:

```bash
docker build -t portfolio-risk-agent .
docker run --rm --network none portfolio-risk-agent
```

Container validation status: the Docker build could not be run in the coding
environment because the current user cannot access the Docker daemon and sudo
requires an interactive password. The commands in this section still need a
local build/run check. If your Ubuntu Docker installation requires sudo, use
`sudo docker ...` for these commands; do not change socket permissions.

The default command analyzes the bundled sample offline. Building needs network
access to download the Python base image and dependencies; offline analysis in
the built image does not. The container runs as non-root UID/GID `10001:10001`.
The build context includes only application code, tests, dependencies, and the
three declared demo data files. `.env`, local environments, traces, Git metadata,
and additional portfolio files are excluded. Credentials are not baked into the
image.

To analyze a custom portfolio, mount only that file as read-only. Replace
`my_portfolio.json` with your existing local file:

```bash
docker run --rm --network none \
  --mount "type=bind,source=$(pwd)/my_portfolio.json,target=/input/portfolio.json,readonly" \
  portfolio-risk-agent /input/portfolio.json
```

For OpenAI mode, inject the existing local `.env` at runtime. This makes external
API requests and incurs API charges, just like the Python CLI:

```bash
docker run --rm --env-file .env portfolio-risk-agent \
  data/sample_portfolio.json --question "How concentrated is my portfolio?"
```

To retain traces on the host, bind a writable output directory. On Linux, use
your host UID/GID so exported files belong to your user:

```bash
mkdir -p traces
docker run --rm --env-file .env --user "$(id -u):$(id -g)" \
  --mount "type=bind,source=$(pwd)/traces,target=/output" \
  portfolio-risk-agent data/sample_portfolio.json \
  --question "How concentrated is my portfolio?" --trace-out /output/docker-live.json
```

Trace names must be new. Without a bind mount, files written inside a container
are discarded when `--rm` removes it. Files mounted as input must be readable by
the container user. Host UID/GID commands above are for a Linux shell.

Run the tests or the scripted guardrail demo inside the same image:

```bash
docker run --rm --network none --entrypoint python portfolio-risk-agent -m pytest -q -p no:cacheprovider
docker run --rm --network none --entrypoint python portfolio-risk-agent -m agent.demo data/sample_portfolio.json --blocked
```

The blocked demo is expected to exit with code 1 and `UNAUTHORIZED_TOOL`.
Local Ollama support would require a separate model adapter and service; it is
not included in this Docker setup.

Docker references: [Dockerfile and entrypoint](https://docs.docker.com/reference/dockerfile/),
[bind mounts](https://docs.docker.com/engine/storage/bind-mounts/).

## Input contract and tools

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

`value` means current EUR position market value, not share quantity. Inputs must
be UTF-8 `.json` files, at most 1,048,576 bytes, containing 1–100 holdings.
ISINs must be uppercase, checksum-valid, unique, and in `data/assets.json`.
Values must be finite numbers greater than zero and at most EUR 10 million per
position. Booleans, numeric strings, additional fields, duplicate JSON fields,
and other currencies are rejected. Decimal monetary input precision is retained.

The catalog includes Apple, Microsoft, and an MSCI World ETF. ETF sector and
country look-through are unavailable (`null`), never inferred from domicile.
Portfolio files are read locally and never automatically persisted or uploaded.
Tool results in LLM mode can nevertheless disclose holdings and values.

| Tool | Purpose |
|---|---|
| `get_asset_data` | Resolve current holdings against the offline catalog |
| `calculate_allocation` | Calculate total, position weights, and grouped allocations |
| `analyze_concentration` | Calculate largest positions, HHI, and illustrative flag |

Tools return JSON-serializable facts. Monetary outputs are decimal strings;
percentages and HHI are numeric. Structured output retains unrounded percentage
results rather than forcing displayed weights to add up through rounding.

## LLM mode

Create a local configuration file without overwriting existing secrets:

```bash
cp -n .env.example .env
```

Edit `.env` locally:

```dotenv
OPENAI_API_KEY=your_local_api_key
OPENAI_MODEL=gpt-4.1-mini
```

Never share your key or commit `.env`; it is excluded by `.gitignore`.
Use a function-calling model available to your API account. Existing environment
variables take precedence. Without a key, question mode is disabled and offline
analysis remains available.

```bash
python cli.py data/sample_portfolio.json --question "How concentrated is my portfolio?"
```

`--question` enables OpenAI requests and API charges. The question and executed
tool results, including holdings, values, or metrics, are sent to the provider.
The original portfolio file is not uploaded. Each command starts a fresh run;
provider history is kept in memory and requests use `store=False`. This is not
a guarantee of zero provider retention.

The CLI displays the AI explanation, verified facts, and full execution trace
separately. Model prose is not fully automatically fact-checked.

## Execution trace

Trace events record ordered UTC timestamps, model requests, token usage when
available, requested tools, call IDs, successful results, tool durations, and
blocked actions with safe reasons. Final status is `success`, `rejected`, or
`error`. This describes observable execution, not private model reasoning.

To explicitly export a live trace:

```bash
mkdir -p traces
python cli.py data/sample_portfolio.json --question "How concentrated is my portfolio?" --trace-out traces/concentration.json
```

Choose a new filename each time: existing files are never overwritten. Exports
may reveal portfolio information; share only intended demonstration data.
Exports are excluded from Git and no trace is written by default. API keys,
authorization headers, raw HTTP bodies, stack traces, and rejected raw tool
arguments are not logged. Terminal JSON output escapes control characters.

## Guardrails

| Layer | Enforced control | Evidence |
|---|---|---|
| Input | Size, encoding, schema, value bounds, ISIN checksum, duplicates, catalog membership | `tests/test_loaders.py`, `tests/test_models.py` |
| Input | Nonempty question, maximum 2,000 characters | `tests/test_agent.py`, CLI |
| Tools | Three-name allowlist, strict empty arguments, trusted context, unique call IDs | `tests/test_dispatcher.py` |
| Execution | Four tool rounds, eight attempted calls, five model requests; stop on rejection/failure | `tests/test_agent.py` |
| Transport | 30-second SDK timeout, no automatic retries, 2,000 output tokens per response | `tests/test_openai_client.py` |
| Output | Separate verified facts, safe failures, reject empty/oversized answers | `tests/test_agent.py`, `tests/test_cli.py` |
| Audit | Ordered traces, rejected actions, no raw rejected arguments, safe exports | `tests/test_dispatcher.py`, `tests/test_demo.py` |

Questions cannot change dispatcher permissions. Adversarial tests simulate a
model requesting a trade or replacing the portfolio after an instruction to
ignore rules. Both are blocked. These tests establish execution controls; they
do not prove that all possible malicious prose is recognized.

Prompts instruct the model to avoid fabricated metadata, guarantees, and
personalized trading decisions. These behavioral instructions complement the
code controls; they do not guarantee the correctness of arbitrary model prose.
Timeouts and token limits bound requests, not a fixed monetary cost.

## Five reproducible demos

1. **Offline calculations:** `python cli.py data/sample_portfolio.json`.
   Verify EUR 10,000, 40/30/30%, HHI 0.34, and `MODERATE`.
2. **Live tool selection:** Run the concentration question above, then
   `python cli.py data/sample_portfolio.json --question "Which assets do I hold?"`.
   Inspect `tool_requested` and `tool_completed` and compare the final answer
   with the tool results. This requires credentials and incurs API charges.
3. **Input rejection:** `python cli.py data/invalid_portfolio.json`.
   The negative value is rejected with exit code 1 before model initialization.
4. **Unauthorized action:** `python -m agent.demo data/sample_portfolio.json --blocked`.
   This deliberately scripted model request yields `execute_trade` →
   `tool_blocked` → `UNAUTHORIZED_TOOL`, no completed tool, and exit code 1.
   It does not rely on a real model voluntarily issuing an unsafe call.
5. **Missing ETF data:**
   `python cli.py data/sample_portfolio.json --question "What is the exact underlying technology sector exposure of my MSCI World ETF?"`.
   The model should explain that look-through is unavailable, without inventing
   an exposure. A tool call is not necessary to state this known limitation.

A successful scripted loop is also available without credentials:

```bash
python -m agent.demo data/sample_portfolio.json
python -m agent.demo data/sample_portfolio.json --blocked --trace-out traces/blocked.json
```

The scripted demo is clearly labeled and is separate from the live integration.
For evaluation, screenshots of the command output and relevant trace events
can accompany these commands.

## Evaluation evidence

Final validation on 2026-11-01: **106 offline tests passed**. Installation from
`requirements-lock.txt` succeeded in a fresh temporary Python 3.12 environment;
`pip check` found no broken requirements. Tests and the offline CLI also passed
in a separate source copy without `.env`, API credentials, or the development
virtual environment. The CLI returned HHI 0.34; question mode without a key was
cleanly disabled. This was a clean source-copy check, not a Git clone.

On 2026-11-01, live checks with `gpt-4.1-mini` produced:

| Scenario | Observed tool selection | Result | Model requests | Total tokens across requests |
|---|---|---|---|---|
| Concentration | `analyze_concentration` | 40% largest position, HHI 0.34; caveat about overall risk | 2 | 779 |
| Holdings | `get_asset_data` | Apple, Microsoft, MSCI World ETF; missing ETF exposures stated | 2 | 781 |
| ETF technology exposure | No tool needed | Explained look-through unavailable, no invented percentage | 1 | 362 |

These are observed examples, not guarantees of future model behavior. The
concentration answer matched the verified facts. The model did not explicitly
cite tool names in every explanation despite the prompt; trace call IDs and
results provide the execution evidence independently of prose attribution.

Full live traces are local ignored files under `traces/live-*.json`; the
shareable summary above contains only demonstration data. Invalid-input and
unauthorized-trade demos were also executed successfully. The blocked demo's
local trace is `traces/submission-blocked.json`.

## Limitations

This is a three-instrument demonstration catalog, not comprehensive market
coverage. HHI describes instrument-level position concentration. The flag is
an arbitrary teaching heuristic: `HIGH` above 40%, `MODERATE` above 20% through
40%, otherwise `LOW`. It is not a validated investment risk score.

ETF overlap, underlying exposures, live prices, performance, volatility,
correlations, expected returns, and total investment risk are unavailable.
There are no orders, accounts, CSV import, web UI, or conversation memory.

## Repository map

- `portfolio/`: input models, ISIN validation, and JSON loading.
- `tools/`: deterministic metadata, allocation, and concentration functions.
- `agent/`: model interface, API adapter, prompts, schemas, dispatcher, runner,
  execution trace, and scripted demo.
- `cli.py`: offline and LLM entry point.
- `data/`: local catalog, valid sample, and deliberately invalid sample.
- `tests/`: offline unit, integration, adversarial, and CLI tests.
- `requirements-lock.txt`: tested dependency snapshot.
- `Dockerfile`, `.dockerignore`: container packaging and restricted build context.
- `Portfolio Risk Agent.md`: MVP specification and implementation phases.

Implementation references: [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
and [Responses state handling](https://developers.openai.com/api/docs/guides/migrate-to-responses).
