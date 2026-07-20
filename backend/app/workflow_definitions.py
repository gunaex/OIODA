"""Single source of truth for status/type transition rules. Both the
validation enforced in routers/documents.py and routers/board_items.py,
and the state-diagram generator (routers/diagrams.py), read from these
tables — so the two can never quietly drift apart the way independently
hardcoded copies could."""

DOCUMENT_TRANSITIONS = {
    "Draft": ["InReview"],
    "InReview": ["Confirmed", "Rejected"],
    "Confirmed": ["Draft"],  # editing a confirmed doc invalidates it -> back to Draft
    "Rejected": ["Draft"],  # editing a rejected doc -> back to Draft
}

BOARD_ITEM_TRANSITIONS = {
    "backlog": ["issue"],
    "issue": ["incident", "task"],
    "incident": ["task"],
}


def is_transition_allowed(transitions: dict[str, list[str]], current: str, target: str) -> bool:
    return target in transitions.get(current, [])
