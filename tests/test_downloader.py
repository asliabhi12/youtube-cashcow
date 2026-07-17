"""Unit coverage for yt-dlp's reported final download paths."""

from pathlib import Path

import pytest

from src.config import (
    AppConfig,
    DownloadConfig,
    LoggingConfig,
    Settings,
    StorageConfig,
)
from src.downloader import Downloader


def _settings(tmp_path: Path, *, overwrite: bool = False) -> Settings:
    return Settings(
        app=AppConfig(name="Test", version="1", debug=False),
        logging=LoggingConfig(log_dir=str(tmp_path / "logs"), file_output=False),
        storage=StorageConfig(),
        download=DownloadConfig(
            output_directory=str(tmp_path / "downloads"),
            overwrite=overwrite,
        ),
    )


class FakeYoutubeDL:
    """Small yt-dlp double that returns post-download metadata."""

    def __init__(self, options, info):
        self.options = options
        self.info = info
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def extract_info(self, url, download=False):
        self.calls.append((url, download))
        return self.info

    def prepare_filename(self, info):
        return info["_prepared_path"]


def _install_ydl(monkeypatch, info):
    import src.downloader as downloader_module

    instances = []

    def factory(options):
        response = info[min(len(instances), len(info) - 1)] if isinstance(info, list) else info
        instance = FakeYoutubeDL(options, response)
        instances.append(instance)
        return instance

    monkeypatch.setattr(downloader_module.yt_dlp, "YoutubeDL", factory)
    return instances


@pytest.mark.parametrize("extension", ["mp4", "webm", "mp3"])
def test_download_uses_yt_dlp_final_filepath(tmp_path, monkeypatch, extension):
    media_path = tmp_path / "downloads" / f"actual.{extension}"
    media_path.parent.mkdir()
    media_path.write_bytes(b"media")
    info = {
        "title": "Actual output",
        "filepath": str(media_path),
        "requested_downloads": [{"filepath": str(tmp_path / "downloads" / "source.webm")}],
        "_prepared_path": str(tmp_path / "downloads" / "predicted.mp4"),
    }
    instances = _install_ydl(monkeypatch, info)

    result = Downloader(_settings(tmp_path)).download_video("https://example.com/video")

    assert result.success is True
    assert result.file_path == str(media_path)
    assert result.file_size == 5
    assert media_path.with_suffix(".json").exists()
    assert instances[0].calls == [("https://example.com/video", True)]


def test_download_prefers_merged_filepath_over_requested_stream(tmp_path, monkeypatch):
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()
    merged_path = output_dir / "merged.mkv"
    merged_path.write_bytes(b"merged")
    info = {
        "title": "Merged",
        "filepath": str(merged_path),
        "requested_downloads": [{"filepath": str(output_dir / "video.webm")}],
        "_prepared_path": str(output_dir / "video.webm"),
    }
    _install_ydl(monkeypatch, info)

    result = Downloader(_settings(tmp_path)).download_video("https://example.com/video")

    assert result.success is True
    assert result.file_path == str(merged_path)


def test_no_overwrite_returns_existing_file_reported_by_yt_dlp(tmp_path, monkeypatch):
    existing_path = tmp_path / "downloads" / "existing.webm"
    existing_path.parent.mkdir()
    existing_path.write_bytes(b"existing")
    info = {"title": "Existing", "filepath": str(existing_path), "_prepared_path": str(existing_path)}
    instances = _install_ydl(monkeypatch, info)

    result = Downloader(_settings(tmp_path, overwrite=False)).download_video("https://example.com/video")

    assert result.success is True
    assert result.file_path == str(existing_path)
    assert instances[0].options["overwrites"] is False


def test_archive_skip_falls_back_to_actual_extension_from_reported_stem(tmp_path, monkeypatch):
    existing_path = tmp_path / "downloads" / "archived.webm"
    existing_path.parent.mkdir()
    existing_path.write_bytes(b"archived")
    info = {
        "title": "Archived",
        "_prepared_path": str(existing_path.with_suffix(".mp4")),
    }
    _install_ydl(monkeypatch, info)

    result = Downloader(_settings(tmp_path)).download_video("https://example.com/video")

    assert result.success is True
    assert result.file_path == str(existing_path)


def test_archive_skip_retries_without_archive_and_returns_actual_file(tmp_path, monkeypatch):
    media_path = tmp_path / "downloads" / "restored.webm"
    media_path.parent.mkdir()
    media_path.write_bytes(b"restored")
    instances = _install_ydl(monkeypatch, [None, {
        "title": "Restored",
        "filepath": str(media_path),
        "_prepared_path": str(media_path),
    }])

    result = Downloader(_settings(tmp_path)).download_video("https://example.com/video")

    assert result.success is True
    assert result.file_path == str(media_path)
    assert instances[0].calls == [("https://example.com/video", True)]
    assert "download_archive" not in instances[1].options


def test_download_fails_cleanly_when_output_directory_is_deleted(tmp_path, monkeypatch):
    output_dir = tmp_path / "downloads"
    info = {
        "title": "Missing",
        "filepath": str(output_dir / "missing.mp4"),
        "_prepared_path": str(output_dir / "missing.mp4"),
    }
    _install_ydl(monkeypatch, info)
    downloader = Downloader(_settings(tmp_path))
    output_dir.rmdir()

    result = downloader.download_video("https://example.com/video")

    assert result.success is False
    assert "could not find a non-empty media file" in result.error


def test_download_rejects_invalid_url_without_calling_yt_dlp(tmp_path, monkeypatch):
    info = {"title": "Unused", "_prepared_path": str(tmp_path / "unused.mp4")}
    instances = _install_ydl(monkeypatch, info)

    result = Downloader(_settings(tmp_path)).download_video("ftp://example.com/video")

    assert result.success is False
    assert "Invalid URL" in result.error
    assert instances == []
