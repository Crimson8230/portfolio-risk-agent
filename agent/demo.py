"""Scripted demonstration of the loop. This is not a live LLM integration."""

import argparse
import json

from agent.model import ModelTurn, ToolCall, ToolResult
from agent.runner import run_agent
from portfolio.loaders import PortfolioInputError, load_catalog, load_portfolio


class ScriptedDemoClient:
    model_name = "scripted-demo-no-llm"

    def __init__(self, blocked: bool = False) -> None:
        self.blocked = blocked

    def respond(self, question: str, results: tuple[ToolResult, ...]) -> ModelTurn:
        if not results:
            name = "execute_trade" if self.blocked else "analyze_concentration"
            return ModelTurn(calls=(ToolCall(name, "{}", "demo-call-1"),))
        result = results[0].result
        return ModelTurn(answer=(
            f"Largest position: {result['largest_position_pct']:.2f}%. "
            f"Position HHI: {result['hhi']}. "
            "This measures position concentration, not overall investment risk."
        ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scripted agent loop demo; no LLM or network calls.")
    parser.add_argument("portfolio")
    parser.add_argument("--blocked", action="store_true", help="Simulate an unauthorized trade tool request")
    parser.add_argument("--trace-out", help="Export trace with holdings/results; use demo data. Never overwrites files.")
    args = parser.parse_args(argv)
    try:
        portfolio, catalog = load_portfolio(args.portfolio), load_catalog()
    except PortfolioInputError as error:
        print(json.dumps({"status": "rejected", "error": str(error)}))
        return 1
    result = run_agent("How concentrated is my portfolio?", portfolio, catalog,
                       ScriptedDemoClient(args.blocked), mode="simulated")
    print("Scripted simulation; no LLM was used.")
    print(result.trace.render())
    if args.trace_out:
        try:
            result.trace.export(args.trace_out)
        except OSError:
            print("Trace export failed: file exists or destination is not writable.")
            return 1
    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
