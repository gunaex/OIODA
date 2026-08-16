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

# Which status transition counts as "work actually started" / "work actually
# finished" for each entity type. The Progress Matrix (Yotei-Jisseki) derives
# its actual_start / actual_end purely from activity_log entries matching
# these values — nobody types an actual date by hand.
#
# Lives here rather than in the Progress Matrix module so it stays the single
# source of truth alongside the transition tables above: if a status is ever
# renamed, both the transition rules and the progress derivation are looked at
# together instead of one quietly drifting from the other.
PROGRESS_TRIGGER_STATUS = {
    "task": {"start": "InProgress", "end": ["Done"]},
    "function": {"start": "InProgress", "end": ["Done", "Confirmed"]},
    "board_item": {"start": "InProgress", "end": ["Resolved", "Closed", "Done"]},
}

PROGRESS_ENTITY_TYPES = tuple(PROGRESS_TRIGGER_STATUS.keys())

# Change Request lifecycle. Deferred and Rejected can be reopened to Draft so
# a parked request doesn't need re-keying.
CHANGE_REQUEST_TRANSITIONS = {
    "Draft": ["UnderAnalysis", "Rejected", "Deferred"],
    "UnderAnalysis": ["PendingApproval", "Rejected", "Deferred", "Draft"],
    "PendingApproval": ["Approved", "Rejected", "Deferred", "UnderAnalysis"],
    "Approved": [],  # terminal — the scope is committed at this point
    "Rejected": ["Draft"],
    "Deferred": ["Draft", "UnderAnalysis"],
}

# The anti-scope-creep rule, enforced in the backend rather than the UI: a CR
# cannot reach Approved until the Impact Analysis document attached to it has
# been signed off (Document status "Confirmed"). That is what stops a change
# being committed before the client has seen and accepted its impact.
CHANGE_REQUEST_APPROVAL_REQUIRES_DOCUMENT_STATUS = "Confirmed"
CHANGE_REQUEST_APPROVED_STATUS = "Approved"

# CR statuses whose effort counts as committed-but-not-yet-delivered in the
# Effort Budget Gauge.
CHANGE_REQUEST_COMMITTED_STATUSES = ("Approved",)

# Entity statuses that mean the effort has actually been delivered — reuses
# the same end-state vocabulary as PROGRESS_TRIGGER_STATUS above so "done"
# means one thing across the whole app.
EFFORT_USED_STATUSES = {
    "function": set(PROGRESS_TRIGGER_STATUS["function"]["end"]),
    "task": set(PROGRESS_TRIGGER_STATUS["task"]["end"]),
}


def is_transition_allowed(transitions: dict[str, list[str]], current: str, target: str) -> bool:
    return target in transitions.get(current, [])
