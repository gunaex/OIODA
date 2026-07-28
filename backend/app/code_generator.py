"""Running Code Generator — `<PJ><T/F><Alphabet><Number>`, e.g. CBTA01, TBFB12.

Task and Function each have their own sequence per project (`code_sequences`,
one row per entity_type). A code is never invented from nothing: it always
comes from PJ (the project's own `project_code`, set once in Project
Settings) plus the sequence pointer, which only ever moves forward.

Two ways a pointer moves:
  - `next_code()` burns the next free slot and returns it (committing).
  - `peek_next_code()` computes the same thing without persisting anything,
    for the on-screen preview a user can regenerate as many times as they
    like before actually saving.
A manually-typed or imported code that happens to match this project's own
pattern also moves the pointer forward to match it (never backward), so the
next auto-generated code continues from there rather than colliding with
something a person already claimed by hand.
"""

import re
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models

ENTITY_TYPES = ("task", "function")
ENTITY_PREFIX = {"task": "T", "function": "F"}
ENTITY_MODEL = {"task": models.Task, "function": models.Function}
ENTITY_CODE_COLUMN = {"task": models.Task.task_code, "function": models.Function.function_code}

LAST_LETTER = "Z"

# PJ is 2-4 uppercase letters (validated on the project side); the running
# code itself is that PJ, then T or F, then one letter A-Z, then two digits.
_CODE_RE = re.compile(r"^([A-Z]{2,4})([TF])([A-Z])(\d{2})$")


class CodeGeneratorError(Exception):
    """Raised for the two ways generation can't proceed: no Project Code set,
    or the alphabet is exhausted. Routers turn this into a 400."""


def as_http_error(exc: CodeGeneratorError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def get_project_code(master_db: Session, slug: str) -> Optional[str]:
    project = master_db.query(models.Project).filter(models.Project.slug == slug).first()
    return project.project_code if project and project.project_code else None


def _get_or_create_sequence(db: Session, entity_type: str) -> models.CodeSequence:
    """Only ever called from a path that goes on to commit — `next_code()`
    and `maybe_advance_pointer()`. The read-only preview reads the pointer
    directly instead, specifically so a GET can never leave a row behind for
    a caller who was only looking."""
    seq = db.query(models.CodeSequence).filter(models.CodeSequence.entity_type == entity_type).first()
    if seq is None:
        seq = models.CodeSequence(entity_type=entity_type, current_alphabet="A", current_number=0)
        db.add(seq)
        db.flush()
    return seq


def _read_sequence_position(db: Session, entity_type: str) -> tuple:
    """(alphabet, number) for a preview — never creates a row. A project
    that has never generated a code for this entity type simply starts from
    the same A/0 a real row would default to."""
    seq = db.query(models.CodeSequence).filter(models.CodeSequence.entity_type == entity_type).first()
    if seq is None:
        return "A", 0
    return seq.current_alphabet, seq.current_number


def _next_letter(letter: str) -> str:
    if letter >= LAST_LETTER:
        raise CodeGeneratorError(
            f"Ran out of running codes for this entity type — {LAST_LETTER}99 has been reached. "
            "This needs a developer to extend the code range before more can be created."
        )
    return chr(ord(letter) + 1)


def _format(pj: str, entity_type: str, alphabet: str, number: int) -> str:
    return f"{pj}{ENTITY_PREFIX[entity_type]}{alphabet}{number:02d}"


def code_exists(db: Session, entity_type: str, code: str) -> bool:
    model = ENTITY_MODEL[entity_type]
    column = ENTITY_CODE_COLUMN[entity_type]
    return db.query(model).filter(column == code).first() is not None


def _require_project_code(master_db: Session, slug: str) -> str:
    pj = get_project_code(master_db, slug)
    if not pj:
        raise CodeGeneratorError(
            "This project has no Project Code set — add one in Project Settings before generating running codes."
        )
    return pj


def peek_next_code(db: Session, master_db: Session, slug: str, entity_type: str) -> str:
    """Non-committing preview: shows what `next_code()` would return right
    now, without moving the pointer. Safe to call as many times as the user
    hits "Regenerate"."""
    pj = _require_project_code(master_db, slug)
    alphabet, number = _read_sequence_position(db, entity_type)
    while True:
        number += 1
        if number > 99:
            number = 1
            alphabet = _next_letter(alphabet)
        candidate = _format(pj, entity_type, alphabet, number)
        if not code_exists(db, entity_type, candidate):
            return candidate


def next_code(db: Session, master_db: Session, slug: str, entity_type: str) -> str:
    """Commits: advances the persisted pointer and returns the code it
    landed on. Flushes (not a full commit) so the pointer move lands in the
    same transaction as whatever entity is about to be created with it —
    both succeed together or neither does."""
    pj = _require_project_code(master_db, slug)
    seq = _get_or_create_sequence(db, entity_type)
    while True:
        seq.current_number += 1
        if seq.current_number > 99:
            seq.current_number = 1
            seq.current_alphabet = _next_letter(seq.current_alphabet)
        candidate = _format(pj, entity_type, seq.current_alphabet, seq.current_number)
        # A collision means something already claimed this slot by hand
        # (typed in, or imported) — keep advancing rather than erroring, the
        # collision is exactly what the loop is for.
        if not code_exists(db, entity_type, candidate):
            break
    db.flush()
    return candidate


def parse_code(code: Optional[str]) -> Optional[tuple]:
    """(pj, T|F, alphabet, number) if `code` matches the running-code
    pattern at all, regardless of which project it belongs to. None for
    anything freeform — a freeform code is a valid override, just not one
    that says anything about the sequence."""
    if not code:
        return None
    m = _CODE_RE.match(code.strip().upper())
    if not m:
        return None
    pj, tf, alphabet, number = m.groups()
    return pj, tf, alphabet, int(number)


def maybe_advance_pointer(db: Session, master_db: Session, slug: str, entity_type: str, code: Optional[str]) -> None:
    """If `code` matches THIS project's own pattern for THIS entity type, and
    names a slot at or past the current pointer, moves the pointer there —
    so the next auto-generated code continues past it instead of racing back
    over ground a human already claimed.

    Silently does nothing for a code that doesn't match the pattern, or
    matches a different project's PJ, or is behind the current pointer —
    all three are just "an ordinary override", not a sequence event.
    """
    parsed = parse_code(code)
    if parsed is None:
        return
    pj, tf, alphabet, number = parsed
    project_code = get_project_code(master_db, slug)
    if not project_code or pj != project_code.upper() or tf != ENTITY_PREFIX[entity_type]:
        return

    seq = _get_or_create_sequence(db, entity_type)
    if (alphabet, number) > (seq.current_alphabet, seq.current_number):
        seq.current_alphabet = alphabet
        seq.current_number = number
        db.flush()


def validate_import_codes(
    db: Session, entity_type: str, records: list, code_column: str
) -> list:
    """Pre-pass for a bulk import: finds every duplicate code — against the
    database and within the file itself — before a single row is saved, so
    the caller can report every problem with its Excel row number in one
    response, the same way import_engine reports enum errors. Never mutates
    anything; a clean result is what licenses actually saving the rows.
    """
    column = ENTITY_CODE_COLUMN[entity_type]
    existing = {code for (code,) in db.query(column).filter(column.isnot(None), column != "").all()}
    seen_in_file: dict = {}
    errors = []
    for index, record in enumerate(records):
        excel_row = index + 2
        code = (record.get(code_column) or "").strip() or None
        if code is None:
            continue
        if code in existing:
            errors.append(
                {
                    "row": excel_row,
                    "column": code_column,
                    "value": code,
                    "problem": f"already used by another {entity_type} in this project",
                }
            )
        elif code in seen_in_file:
            errors.append(
                {
                    "row": excel_row,
                    "column": code_column,
                    "value": code,
                    "problem": f"duplicated within this file (also at row {seen_in_file[code]})",
                }
            )
        else:
            seen_in_file[code] = excel_row
    return errors


def resolve_code_for_import_row(
    db: Session, master_db: Session, slug: str, entity_type: str, code: Optional[str]
) -> Optional[str]:
    """Per-row companion to `resolve_code_for_create`, used only once
    `validate_import_codes` has already cleared the whole file — so unlike
    the on-screen version, this never needs to raise for a duplicate, only
    fill in the blanks and advance the pointer for the codes given by hand.

    A blank cell with no Project Code set stays blank, same as before this
    feature existed. A blank cell that DOES have a Project Code but can't be
    generated (sequence exhausted) is a real problem the importer needs to
    know about, not a silent skip — it propagates as a 400, same as
    `resolve_code_for_create`. Nothing has been committed yet at that point
    (the caller's `db.commit()` runs once, after the whole loop), so the
    request fails cleanly with no partial import."""
    code = (code or "").strip() or None
    if code is None:
        if not get_project_code(master_db, slug):
            return None
        try:
            return next_code(db, master_db, slug, entity_type)
        except CodeGeneratorError as exc:
            raise as_http_error(exc)
    maybe_advance_pointer(db, master_db, slug, entity_type, code)
    return code


def resolve_code_for_create(
    db: Session, master_db: Session, slug: str, entity_type: str, code: Optional[str]
) -> Optional[str]:
    """The single decision point used by both the on-screen create endpoint
    and (per-row) the import endpoint:

      code blank + project has a Project Code  -> auto-generate (commits the
                                                    pointer advance)
      code blank + project has none             -> stays blank, unchanged
                                                    from before this feature
                                                    existed (no hard error —
                                                    the UI already explains
                                                    why prefill isn't offered)
      code given                                 -> used as typed; if it
                                                    matches this project's own
                                                    pattern, the pointer is
                                                    advanced to match it

    Raises HTTPException for a code given by hand that's already taken, and
    also for a blank code that a Project Code IS set for but couldn't
    actually be generated (sequence exhausted) — that's a real failure the
    caller needs to see, not the same silent "no Project Code" fallback.
    """
    code = (code or "").strip() or None
    if code is None:
        if not get_project_code(master_db, slug):
            return None
        try:
            return next_code(db, master_db, slug, entity_type)
        except CodeGeneratorError as exc:
            raise as_http_error(exc)

    if code_exists(db, entity_type, code):
        raise HTTPException(
            status_code=400,
            detail=f"{entity_type.capitalize()} code '{code}' is already used by another {entity_type} in this project.",
        )
    maybe_advance_pointer(db, master_db, slug, entity_type, code)
    return code
