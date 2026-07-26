"""Unit of Work atomic rollback & compensation action tests."""

import pytest
from app.infrastructure.unit_of_work import SQLiteUnitOfWork
from app.models.profile import Profile


def test_unit_of_work_atomic_commit():
    """Verify multi-repository writes commit atomically under single SQLite connection."""
    with SQLiteUnitOfWork() as uow:
        dest = uow.destinations.upsert_connected_channel(
            channel_title="Transaction Channel",
            channel_id="UC-tx-100",
            thumbnail="",
            description="",
            access_token="tx_token",
            refresh_token="tx_refresh",
            token_expires_at=None,
        )
        job = uow.jobs.create("https://youtube.example/watch?v=tx1", profile_id="cinematic")
        uow.jobs.record_upload_history(
            job_id=job.id,
            destination_id=dest.id,
            status="success",
            progress=100,
            video_id="tx_vid_1",
        )
        uow.commit()

    # Read back via fresh UoW
    with SQLiteUnitOfWork() as uow2:
        fetched_dest = uow2.destinations.get_by_id(dest.id)
        fetched_job = uow2.jobs.get_by_id(job.id)
        assert fetched_dest is not None
        assert fetched_dest.channel_title == "Transaction Channel"
        assert fetched_job is not None
        assert fetched_job.id == job.id


def test_unit_of_work_rollback_on_exception():
    """Verify failed operations roll back SQLite transaction and run compensation actions."""
    compensation_executed = []

    def rollback_handler():
        compensation_executed.append("reverted_external_file")

    with pytest.raises(RuntimeError, match="Simulated external upload failure"):
        with SQLiteUnitOfWork() as uow:
            uow.add_compensation_action(rollback_handler)
            uow.destinations.upsert_connected_channel(
                channel_title="Failed Channel",
                channel_id="UC-tx-fail",
                thumbnail="",
                description="",
                access_token="fail_tok",
                refresh_token="fail_ref",
                token_expires_at=None,
            )
            # Raise exception before commit
            raise RuntimeError("Simulated external upload failure")

    assert len(compensation_executed) == 1
    assert compensation_executed[0] == "reverted_external_file"

    # Verify SQLite rollback
    with SQLiteUnitOfWork() as uow2:
        dest = uow2.destinations.get_by_id("failed-channel")
        assert dest is None


def test_unit_of_work_compensation_order():
    """Verify compensation callbacks execute in reverse order (LIFO)."""
    calls = []

    with pytest.raises(ValueError):
        with SQLiteUnitOfWork() as uow:
            uow.add_compensation_action(lambda: calls.append(1))
            uow.add_compensation_action(lambda: calls.append(2))
            uow.add_compensation_action(lambda: calls.append(3))
            raise ValueError("Test error")

    assert calls == [3, 2, 1]
