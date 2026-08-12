"""PM-E2 — correlation/idempotency/external work reference model."""

import pytest

from app.database import MasterSessionLocal
from app.ecosystem.intake_service import (
    record_external_work,
    attach_local_mapping,
    add_evidence,
    IdempotencyConflict,
)


PAYLOAD = {"workPackageId": "wp-100", "title": "Build a thing", "state": "PLANNED"}


def test_replay_same_payload_is_idempotent_no_duplicate():
    with MasterSessionLocal() as db:
        ref1, created1 = record_external_work(
            db,
            source_system="CONDUCTOR_MAIN",
            source_object_type="DELIVERY_WORK_PACKAGE",
            source_object_id="wp-100",
            correlation_id="corr-100",
            idempotency_key="idem-100",
            payload=PAYLOAD,
        )
        assert created1 is True

        ref2, created2 = record_external_work(
            db,
            source_system="CONDUCTOR_MAIN",
            source_object_type="DELIVERY_WORK_PACKAGE",
            source_object_id="wp-100",
            correlation_id="corr-100",
            idempotency_key="idem-100",
            payload=dict(PAYLOAD),  # same content, fresh dict instance
        )
        assert created2 is False
        assert ref2.id == ref1.id


def test_replay_with_mutated_payload_same_key_is_conflict():
    with MasterSessionLocal() as db:
        record_external_work(
            db,
            source_system="CONDUCTOR_MAIN",
            source_object_type="DELIVERY_WORK_PACKAGE",
            source_object_id="wp-101",
            correlation_id="corr-101",
            idempotency_key="idem-101",
            payload=PAYLOAD,
        )
        with pytest.raises(IdempotencyConflict):
            record_external_work(
                db,
                source_system="CONDUCTOR_MAIN",
                source_object_type="DELIVERY_WORK_PACKAGE",
                source_object_id="wp-101",
                correlation_id="corr-101",
                idempotency_key="idem-101",
                payload={**PAYLOAD, "state": "CANCELLED"},
            )


def test_attach_local_mapping_and_evidence():
    with MasterSessionLocal() as db:
        ref, _ = record_external_work(
            db,
            source_system="CONDUCTOR_MAIN",
            source_object_type="DELIVERY_WORK_PACKAGE",
            source_object_id="wp-102",
            correlation_id="corr-102",
            idempotency_key="idem-102",
            payload=PAYLOAD,
        )
        ref = attach_local_mapping(db, ref, local_object_type="project", local_object_id="1", status="MAPPED")
        assert ref.status == "MAPPED"
        assert ref.local_object_type == "project"

        evidence = add_evidence(db, ref, type="log", source="pm-again", reference_value="task-1", summary="created")
        assert evidence.external_work_reference_id == ref.id
