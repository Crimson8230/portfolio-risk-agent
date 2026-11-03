# Portfolio Risk Agent

CLI agent for EUR portfolio composition and position concentration. It validates
a local JSON portfolio, lets an LLM select analysis tools, and explains results
calculated by Python. Offline analysis works without an API key.

## Setup

Requires Python 3.11 or newer. Run commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m pytest -q
```

Tests run offline using fake model responses and mock HTTP.

## Usage

Analyze the bundled portfolio without network access:

```bash
python cli.py data/sample_portfolio.json
```

The sample holds Apple, Microsoft, and an MSCI World ETF with weights of
40%, 30%, and 30%. Total value: EUR 10,000; position HHI: 0.34;
concentration flag: `MODERATE`.

For natural-language questions, copy the configuration template and set your
API key locally:

```bash
cp -n .env.example .env
```

```dotenv
OPENAI_API_KEY=your_local_api_key
OPENAI_MODEL=gpt-4.1-mini
```

```bash
python cli.py data/sample_portfolio.json --question "How concentrated is my portfolio?"
```

Question mode sends the question and executed tool results to OpenAI and incurs
API charges. Results may include holdings and values. Each question starts a
fresh run. Requests use `store=False`; this does not guarantee zero provider
retention. Environment variables take precedence over `.env`. Never commit keys.

## Portfolio input

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

`value` is the current position market value in EUR. Inputs must be UTF-8 JSON,
at most 1 MB, with 1–100 holdings. ISINs must be uppercase, checksum-valid,
unique, and present in `data/assets.json`. Values must be finite positive
numbers up to EUR 10 million per position. Other currencies, extra fields,
duplicate JSON fields, booleans, and numeric strings are rejected.

## Tools and execution

| Tool | Result |
|---|---|
| `get_asset_data` | Holding metadata from the local catalog |
| `calculate_allocation` | Total value, position weights, and grouped allocations |
| `analyze_concentration` | Largest positions, HHI, and concentration flag |

The model selects tools; Python calculates metrics. The dispatcher supplies the
validated portfolio and accepts only these three tools with empty arguments.
No shell, trading, filesystem, or arbitrary network tool is exposed to the model.

Runs allow four tool rounds, eight attempted calls, and five model requests.
API requests have a 30-second timeout, no automatic retries, and a 2,000-token
output limit. Invalid calls and execution failures stop the run. The CLI shows
the AI explanation separately from verified tool facts; model prose is not
fully automatically fact-checked.

## Execution traces

The CLI displays tool requests, results, blocked actions, and final run status.
Export a trace explicitly to a new filename:

```bash
python cli.py data/sample_portfolio.json \
  --question "How concentrated is my portfolio?" --trace-out traces/concentration.json
```

The destination directory must exist. Existing files are never overwritten.
Traces can contain questions and portfolio results; they are excluded from Git.
API keys, raw rejected arguments, and private model reasoning are not logged.

Run the scripted loop or a blocked trade request without credentials:

```bash
python -m agent.demo data/sample_portfolio.json
python -m agent.demo data/sample_portfolio.json --blocked
```

The blocked scenario exits with code 1 and `UNAUTHORIZED_TOOL`.

## Docker

```bash
docker build -t portfolio-risk-agent .
docker run --rm --network none portfolio-risk-agent
```

The image runs as a non-root user and defaults to offline sample analysis.
Builds require network access. Local secrets, traces, and additional portfolios
are excluded from the build context. The Docker build/run has not yet been
verified locally.

For question mode, inject credentials at runtime:

```bash
docker run --rm --env-file .env portfolio-risk-agent \
  data/sample_portfolio.json --question "How concentrated is my portfolio?"
```

## Limitations

The local catalog contains three instruments. ETF underlying exposures and
overlap, live prices, performance, volatility, correlations, and expected
returns are unavailable. Unknown ETF exposures remain explicitly unresolved.

HHI measures instrument-level concentration. The concentration flag uses a
simple heuristic based on the largest position: `HIGH` above 40%, `MODERATE`
above 20% through 40%, otherwise `LOW`. It is not a validated investment risk
score. The agent does not place trades or provide a comprehensive risk assessment.

## Project structure

- `portfolio/`: input models, ISIN validation, and JSON loading.
- `tools/`: deterministic analysis functions.
- `agent/`: model adapter, prompts, dispatcher, execution loop, traces, and demos.
- `cli.py`: offline and question-mode entry point.
- `data/`: catalog and sample portfolios.
- `tests/`: offline unit, integration, adversarial, and CLI tests.
