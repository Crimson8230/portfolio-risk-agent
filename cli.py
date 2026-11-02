"""Offline analysis or an explicitly requested LLM question."""

import argparse
import json
import os
from pathlib import Path

from portfolio.loaders import PortfolioInputError, load_catalog, load_portfolio
from tools.allocation import calculate_allocation
from tools.asset_lookup import get_asset_data
from tools.concentration import analyze_concentration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze EUR portfolio composition offline.")
    parser.add_argument("portfolio", help="Path to a UTF-8 portfolio JSON file")
    parser.add_argument("--question", help="Enable LLM mode: send the question and tool results (holdings/values) to OpenAI; API charges apply")
    parser.add_argument("--trace-out", help="Export agent trace containing question and portfolio results; never overwrites files")
    args = parser.parse_args(argv)
    if args.trace_out and args.question is None:
        parser.error("--trace-out requires --question; use agent.demo for offline simulated traces")
    try:
        portfolio = load_portfolio(args.portfolio)
        catalog = load_catalog()
    except PortfolioInputError as error:
        # JSON escapes control characters in untrusted error locations.
        print(json.dumps({"status": "rejected", "error": str(error)}, ensure_ascii=True))
        return 1
    if args.question is not None:
        return _answer_question(args.question, portfolio, catalog, args.trace_out)
    print(json.dumps({
        "mode": "offline",
        "asset_data": get_asset_data(portfolio, catalog),
        "allocation": calculate_allocation(portfolio, catalog),
        "concentration": analyze_concentration(portfolio),
    }, indent=2, ensure_ascii=True, allow_nan=False))
    return 0


def _answer_question(question, portfolio, catalog, trace_out) -> int:
    if not question.strip() or len(question) > 2000:
        print('Question must contain text and be at most 2,000 characters.')
        return 1
    from dotenv import load_dotenv

    from agent.openai_client import create_openai_client
    from agent.runner import run_agent

    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini").strip()
    if not api_key or not model_name:
        print("Agent mode requires OPENAI_API_KEY and a non-empty OPENAI_MODEL. Offline analysis remains available.")
        return 1
    if trace_out and Path(trace_out).exists():
        print("Trace destination already exists. Choose a new path.")
        return 1
    print("LLM mode: question and tool results are sent to OpenAI; API charges apply.")
    try:
        client = create_openai_client(api_key, model_name)
    except Exception:
        print("Could not initialize the model client. Check local configuration.")
        return 1
    result = run_agent(question, portfolio, catalog, client)
    print("AI explanation (not fully automatically fact-checked):")
    print(json.dumps(result.answer, ensure_ascii=True))
    print("Verified tool facts:")
    print(json.dumps(result.verified_facts, indent=2, ensure_ascii=True, allow_nan=False))
    print("Execution trace:")
    print(result.trace.render())
    if trace_out:
        try:
            result.trace.export(trace_out)
        except OSError:
            print("Trace export failed: destination exists or is not writable.")
            return 1
    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
