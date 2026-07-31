"""Unit test suite for AI metadata generation layer in CashCow."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.llm.base import LLMProvider, LLMResponse
from app.llm.factory import get_llm_provider
from app.llm.openai_oauth import OpenAIOAuthProvider
from app.models.metadata import VideoMetadata
from app.prompts.metadata import PROMPT_VERSION, SYSTEM_PROMPT
from app.services.jobs import job_store
from app.services.metadata import GeneratedMetadata, MetadataService, parse_json_response


class MockLLMProvider(LLMProvider):
    """Mock LLM Provider for testing."""

    def __init__(self, response_content: str | None = None, should_fail: bool = False):
        self.response_content = response_content or json.dumps({
            "title": "AI Generated Title",
            "description": "AI Generated Description with summary and #hashtags",
            "tags": ["tag1", "tag2"],
            "hashtags": ["#tag1", "#tag2"],
            "thumbnail_prompt": "Thumbnail prompt sample",
            "language": "en",
        })
        self.should_fail = should_fail
        self.calls = []

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        if self.should_fail:
            raise RuntimeError("LLM service unreachable")
        return LLMResponse(
            content=self.response_content,
            model="gpt-5.6-sol",
            duration_seconds=0.12,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )


class TestLLMProvider:
    """✓ Test 1: Provider unit tests."""

    @patch("urllib.request.urlopen")
    def test_openai_oauth_provider_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{"message": {"content": '{"title": "Test Title", "description": "Test Desc"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        provider = OpenAIOAuthProvider(base_url="http://127.0.0.1:10531/v1", model="gpt-5.6-sol", max_retries=0)
        res = provider.generate("Generate metadata prompt")

        assert isinstance(res, LLMResponse)
        assert '{"title": "Test Title"' in res.content
        assert res.model == "gpt-5.6-sol"
        assert res.total_tokens == 15

    @patch("urllib.request.urlopen")
    def test_openai_oauth_provider_retries_and_failure(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")
        provider = OpenAIOAuthProvider(base_url="http://127.0.0.1:10531/v1", model="gpt-5.6-sol", max_retries=1)

        with pytest.raises(RuntimeError, match="OpenAI OAuth provider failed after 1 retries"):
            provider.generate("Prompt")

    def test_llm_factory_returns_configured_provider(self):
        provider = get_llm_provider("openai-oauth")
        assert isinstance(provider, OpenAIOAuthProvider)


class TestJSONParsing:
    """✓ Test 2: JSON parsing unit tests."""

    def test_parse_json_clean_string(self):
        raw = '{"title": "My Title", "description": "My Desc"}'
        result = parse_json_response(raw)
        assert result["title"] == "My Title"

    def test_parse_json_wrapped_in_markdown_code_fence(self):
        raw = """```json
{
  "title": "Markdown Title",
  "description": "Markdown Desc",
  "tags": ["a", "b"]
}
```"""
        result = parse_json_response(raw)
        assert result["title"] == "Markdown Title"
        assert result["tags"] == ["a", "b"]

    def test_parse_json_with_surrounding_whitespace_and_text(self):
        raw = """Here is the generated metadata:
{
  "title": "Extracted Title",
  "description": "Extracted Description"
}
Hope this helps!"""
        result = parse_json_response(raw)
        assert result["title"] == "Extracted Title"


class TestMalformedAIResponse:
    """✓ Test 3: Malformed AI response handling tests."""

    def test_malformed_json_raises_value_error(self):
        raw = "This is not json at all."
        with pytest.raises(ValueError):
            parse_json_response(raw)

    def test_missing_required_fields_in_ai_response(self):
        service = MetadataService()
        job = job_store.create("https://youtube.com/watch?v=12345678901")
        mock_provider = MockLLMProvider(response_content='{"tags": ["tag1"]}')

        metadata = service.generate(job.id, llm_provider=mock_provider, fallback=True)
        assert metadata is not None
        assert metadata.provider == "fallback"


class TestMetadataService:
    """✓ Test 4 & 5: Metadata service & fallback metadata unit tests."""

    def test_metadata_service_successful_generation(self):
        service = MetadataService()
        job = job_store.create("https://youtube.com/watch?v=12345678901")

        service.store_video_context(job.id, transcript="This video covers AI tech and python.", video_duration=120.0)
        mock_provider = MockLLMProvider()

        metadata = service.generate(job.id, llm_provider=mock_provider)

        assert isinstance(metadata, VideoMetadata)
        assert metadata.title == "AI Generated Title"
        assert metadata.description == "AI Generated Description with summary and #hashtags"
        assert service.get(job.id) == metadata

    def test_metadata_service_fallback_on_llm_error(self):
        service = MetadataService()
        job = job_store.create("https://youtube.com/watch?v=12345678901")
        mock_failing_provider = MockLLMProvider(should_fail=True)

        metadata = service.generate(job.id, llm_provider=mock_failing_provider, fallback=True)

        assert metadata is not None
        assert metadata.provider == "fallback"

    def test_manual_regeneration(self):
        service = MetadataService()
        job = job_store.create("https://youtube.com/watch?v=12345678901")
        mock_provider = MockLLMProvider()

        meta1 = service.generate(job.id, llm_provider=mock_provider)
        assert meta1 is not None

        meta2 = service.regenerate(job.id)
        assert meta2 is not None


class TestWorkflowIntegration:
    """✓ Test 6: Workflow integration tests."""

    def test_workflow_runs_metadata_step_and_persists_to_job(self):
        from app.services.workflow import _execute
        from src.config import load_config
        from src.pipeline import WorkflowDefinition, WorkflowStep
        from src.pipeline.runner import PipelineResult

        job = job_store.create("https://youtube.com/watch?v=12345678901")
        dummy_workflow = WorkflowDefinition(
            name="test_wf",
            version="1.0",
            description="test",
            steps=[WorkflowStep(name="download", action="download")],
        )
        settings = load_config(str(_REPO_ROOT / "settings.yaml"))

        mock_runner = MagicMock()
        mock_runner.run.return_value = PipelineResult(
            name="test_wf",
            workspace=Path("/tmp"),
            history=[],
            output_file=None,
            success=True,
            metadata={"download": {"title": "Test Video Title", "subtitles": {}}},
        )

        with patch("app.services.workflow._build_runner", return_value=mock_runner):
            _execute(job.id, dummy_workflow, settings)

        stored_job = job_store.get(job.id)
        assert stored_job.metadata_status == "available"
