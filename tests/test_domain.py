from __future__ import annotations

import json

from noctra.domain import ACTIVE_STATUSES, Job, JobStatus


def test_status_serializes_as_plain_string() -> None:
    assert str(JobStatus.PENDING) == "pending"
    assert json.dumps({"s": str(JobStatus.DONE)}) == '{"s": "done"}'


def test_job_to_dict_is_json_serializable() -> None:
    job = Job(id=1, path="/tmp/a.m4a", status=JobStatus.PROCESSING)
    data = job.to_dict()
    assert data["status"] == "processing"
    # Round-trips through json without custom encoders.
    assert json.loads(json.dumps(data))["status"] == "processing"


def test_active_statuses() -> None:
    assert JobStatus.PENDING in ACTIVE_STATUSES
    assert JobStatus.PROCESSING in ACTIVE_STATUSES
    assert JobStatus.DONE not in ACTIVE_STATUSES
    assert Job(id=1, path="x", status=JobStatus.PENDING).is_active
    assert not Job(id=1, path="x", status=JobStatus.DONE).is_active
