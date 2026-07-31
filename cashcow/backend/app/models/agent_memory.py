"""Agent Memory and Workflow Event models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class WorkflowEvent:
    id: Optional[int]
    job_id: str
    stage: str
    status: str
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class AgentMemoryRecord:
    id: Optional[int]
    job_id: str
    task: str
    status: str
    output_summary: Optional[str] = None
    model: Optional[str] = None
    artifact_path: Optional[str] = None
    created_at: Optional[datetime] = None
