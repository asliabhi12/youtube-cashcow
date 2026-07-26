"""Agent Memory & Workflow Event Repository interface contract."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence

from app.models.agent_memory import AgentMemoryRecord, WorkflowEvent


class IMemoryRepository(ABC):
    """Encapsulates workflow event logs and AI agent memory records."""

    @abstractmethod
    def record_event(
        self,
        job_id: str,
        stage: str,
        status: str,
        finished_at: Optional[datetime] = None,
    ) -> WorkflowEvent:
        """Record a workflow pipeline execution event."""
        pass

    @abstractmethod
    def get_events(self, job_id: str) -> Sequence[WorkflowEvent]:
        """Fetch all workflow events for a job."""
        pass

    @abstractmethod
    def store_agent_memory(
        self,
        job_id: str,
        task: str,
        status: str,
        output_summary: Optional[str] = None,
        model: Optional[str] = None,
        artifact_path: Optional[str] = None,
    ) -> AgentMemoryRecord:
        """Store an agent memory execution record."""
        pass

    @abstractmethod
    def get_agent_memory(self, job_id: str, task: Optional[str] = None) -> Sequence[AgentMemoryRecord]:
        """Fetch agent memory records for a job and optional task filter."""
        pass
