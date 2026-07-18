"""Job CRUD routes.

Accepts a URL, creates an in-memory job, and returns it. No processing is
triggered here; that is wired up in a later phase.
"""

from fastapi import APIRouter, HTTPException, status

from app.models.job import Job, JobCreate
from app.services.jobs import job_store
from app.services.workflow import start_workflow

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=Job, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate) -> Job:
    """Create a pending job and start its workflow in the background.

    Returns immediately with the created job; processing runs asynchronously
    and updates the job's status as the workflow progresses.
    """
    job = job_store.create(payload.url)
    start_workflow(job.id, job.url)
    return job


@router.get("", response_model=list[Job])
def list_jobs() -> list[Job]:
    """Return all jobs in creation order."""
    return job_store.list()


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    """Return a single job, or 404 if it does not exist."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str) -> None:
    """Delete a job, or 404 if it does not exist."""
    if not job_store.delete(job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
