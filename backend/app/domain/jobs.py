from __future__ import annotations

import enum
import random
from datetime import UTC, datetime, timedelta


class InvalidJobTransition(Exception):
    pass


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {self.succeeded, self.failed, self.cancelled}


# Allowed transitions from each state.
TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.queued: {JobStatus.running, JobStatus.cancelled},
    JobStatus.running: {JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled},
    JobStatus.succeeded: set(),
    JobStatus.failed: set(),
    JobStatus.cancelled: set(),
}


def transition(state_before: JobStatus, state_after: JobStatus) -> JobStatus:
    allowed = TRANSITIONS[state_before]
    if state_after not in allowed:
        raise InvalidJobTransition(f"cannot transition job {state_before.value} -> {state_after.value}")
    return state_after


class ErrorCode(str, enum.Enum):
    """Attempt error codes. Retryable membership decides the retry policy."""

    # infra / transient => retryable
    transient_error = "transient_error"
    timeout = "timeout"
    dependency_unavailable = "dependency_unavailable"
    # permanent => not retryable
    invalid_params = "invalid_params"
    artifact_write_failed = "artifact_write_failed"
    worker_error = "worker_error"
    unknown = "unknown"

    @property
    def retryable(self) -> bool:
        return self in {self.transient_error, self.timeout, self.dependency_unavailable}


RETRYABLE_EXCEPTION_CODES = {ErrorCode.transient_error, ErrorCode.timeout, ErrorCode.dependency_unavailable}


def backoff_delay_seconds(attempt: int, *, cap: float = 60.0, rnd: random.Random | None = None) -> float:
    """Exponential backoff + jitter: base 5s, factor 2, jitter [0,5), clamped to cap."""
    rng = rnd or random
    base = min(cap, 5.0 * (2 ** max(0, attempt - 1)))
    return min(cap, base + rng.uniform(0.0, 5.0))


def backoff_deadline(attempt: int, now: datetime | None = None, *, rnd: random.Random | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now + timedelta(seconds=backoff_delay_seconds(attempt, rnd=rnd))
