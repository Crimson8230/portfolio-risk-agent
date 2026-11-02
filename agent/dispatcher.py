"""Application-owned tool permissions and trusted portfolio context."""

import json
from time import perf_counter
from types import MappingProxyType
from typing import Callable, Mapping

from agent.trace import ExecutionTrace
from portfolio.models import Asset, Portfolio
from tools.allocation import calculate_allocation
from tools.asset_lookup import get_asset_data
from tools.concentration import analyze_concentration


class ToolExecutionError(ValueError):
    """Safe error code that a future runner must treat as terminal."""


class Dispatcher:
    def __init__(self, portfolio: Portfolio, catalog: dict[str, Asset], trace: ExecutionTrace) -> None:
        trusted_catalog = dict(catalog)
        self._tools: Mapping[str, Callable[[], dict]] = MappingProxyType({
            "get_asset_data": lambda: get_asset_data(portfolio, trusted_catalog),
            "calculate_allocation": lambda: calculate_allocation(portfolio, trusted_catalog),
            "analyze_concentration": lambda: analyze_concentration(portfolio),
        })
        self.trace = trace
        self.attempts = 0
        self._stopped = False
        self._call_ids: set[str] = set()

    def _reject(self, code: str, call_id: str, name: str) -> None:
        self._stopped = True
        self.trace.record("tool_blocked", call_id=call_id, tool_name=name,
                          status="rejected", error_code=code)
        raise ToolExecutionError(code)

    def dispatch(self, name: str, arguments: str, call_id: str) -> dict:
        """Every attempted call counts; rejected arguments are never logged."""
        self.attempts += 1
        self.trace.record("tool_requested", call_id=call_id, tool_name=name,
                          attempt=self.attempts)
        if self._stopped:
            self._reject("RUN_ALREADY_STOPPED", call_id, name)
        if self.attempts > 8:
            self._reject("TOOL_LIMIT_EXCEEDED", call_id, name)
        if not call_id or call_id in self._call_ids:
            self._reject("INVALID_CALL_ID", call_id, name)
        self._call_ids.add(call_id)
        if name not in self._tools:
            self._reject("UNAUTHORIZED_TOOL", call_id, name)
        # A zero-argument call needs exactly an empty JSON object. Bounding the
        # raw text also prevents unnecessarily large parsing workloads.
        if len(arguments) > 1024:
            self._reject("INVALID_ARGUMENTS", call_id, name)
        try:
            parsed = json.loads(arguments)
        except (ValueError, RecursionError):
            self._reject("INVALID_ARGUMENTS", call_id, name)
        if parsed != {}:
            self._reject("INVALID_ARGUMENTS", call_id, name)
        started = perf_counter()
        try:
            result = self._tools[name]()
            json.dumps(result, allow_nan=False)
        except Exception:
            self._stopped = True
            self.trace.record("tool_failed", call_id=call_id, tool_name=name,
                              status="error", error_code="TOOL_FAILED",
                              duration_ms=(perf_counter() - started) * 1000)
            raise ToolExecutionError("TOOL_FAILED") from None
        self.trace.record("tool_completed", call_id=call_id, tool_name=name,
                          arguments={}, status="success", result=result,
                          duration_ms=(perf_counter() - started) * 1000)
        return result
