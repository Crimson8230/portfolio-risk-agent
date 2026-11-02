"""Strict, zero-argument tool descriptions for the model."""

from copy import deepcopy

_DESCRIPTIONS = {
    "get_asset_data": "List current holdings with names, asset types, and available offline metadata. ETF look-through is unavailable.",
    "calculate_allocation": "Calculate current EUR portfolio total, position weights, asset types, and direct-stock sector/country allocation with unresolved ETF exposure.",
    "analyze_concentration": "Calculate position-level HHI, largest holding and ties, and illustrative concentration flag. This is not overall financial risk.",
}


def tool_schemas() -> list[dict]:
    return deepcopy([
        {
            "type": "function",
            "name": name,
            "description": description,
            "strict": True,
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        }
        for name, description in _DESCRIPTIONS.items()
    ])
