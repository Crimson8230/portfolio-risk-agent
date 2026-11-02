"""Observable execution events; no raw model payloads or private reasoning."""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExecutionTrace:
    def __init__(self, mode: str) -> None:
        self.run_id = str(uuid4())
        self.mode = mode
        self.started_at = utc_now()
        self.ended_at: str | None = None
        self.status: str | None = None
        self.events: list[dict] = []

    def record(self, event_type: str, **details: object) -> None:
        if self.status is not None:
            raise RuntimeError("Cannot add events to a finished trace")
        self.events.append({
            "sequence": len(self.events) + 1,
            "timestamp": utc_now(),
            "event_type": event_type,
            **details,
        })

    def finish(self, status: str) -> None:
        if status not in {"success", "rejected", "error"}:
            raise ValueError("Invalid trace status")
        if self.status is not None:
            raise RuntimeError("Trace already finished")
        self.status = status
        self.ended_at = utc_now()

    def as_dict(self) -> dict:
        return {
            "schema_version": 1,
            "run_id": self.run_id,
            "mode": self.mode,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "events": self.events,
        }

    def render(self) -> str:
        """JSON escaping prevents terminal control characters from executing."""
        return json.dumps(self.as_dict(), indent=2, ensure_ascii=True, allow_nan=False)

    def export(self, path: str | Path) -> None:
        """Explicit local export, never overwriting an existing file."""
        if self.status is None:
            raise RuntimeError("Finish the run before exporting its trace")
        payload = self.render()
        with Path(path).open("x", encoding="utf-8") as target:
            target.write(payload + "\n")
