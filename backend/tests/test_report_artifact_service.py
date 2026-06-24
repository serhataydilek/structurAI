from datetime import datetime, timezone
import hashlib

from app.services.report_artifact_service import build_report_markdown


def test_builds_utf8_markdown_with_identity_and_metadata():
    content, metadata = build_report_markdown(
        {"projectName": "North Tower", "projectId": "project-1", "processingStatus": "Ready", "uploadedMediaCount": 12},
        {"ready": True, "projectId": "project-1", "items": []},
        {"id": "package-1", "version": 3, "filename": "north-tower-v3.zip"},
        datetime(2026, 6, 24, 10, 30, tzinfo=timezone.utc),
    )

    markdown = content.decode("utf-8")
    assert isinstance(content, bytes)
    assert metadata == {
        "filename": "report.md",
        "format": "md",
        "contentType": "text/markdown; charset=utf-8",
        "sizeBytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    assert "North Tower" in markdown
    assert "project-1" in markdown
    assert "package-1" in markdown
    assert "Package version: 3" in markdown
    assert "2026-06-24T10:30:00+00:00" in markdown


def test_includes_manifest_model_quality_and_report_details():
    content, _ = build_report_markdown(
        {
            "projectName": "Model project",
            "captureMetadata": {"imageCount": 8, "videoCount": 1, "extractedFrameCount": 16},
            "reconstructionMetadata": {"status": "Complete", "sparseQualityLabel": "Good", "registeredImageCount": 7, "sparsePointCount": 2000},
        },
        {
            "ready": False,
            "missingRequired": ["final_model"],
            "items": [{"kind": "final_model", "ready": False, "required": True, "filename": "final.glb", "format": "glb", "sizeBytes": 42}],
            "metadataPreview": {"finalModel": {"filename": "final.glb", "format": "glb", "source": "uploaded", "sizeBytes": 42}},
            "finalModelQuality": {"status": "warning", "packageReady": True, "warnings": ["Texture is large"], "blockers": ["Review model"]},
        },
        {},
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    markdown = content.decode("utf-8")
    assert "Ready: False" in markdown
    assert "Missing required items:" in markdown
    assert "final\\_model" in markdown
    assert "final.glb" in markdown
    assert "42 bytes" in markdown
    assert "Status: warning" in markdown
    assert "Texture is large" in markdown
    assert "Review model" in markdown
    assert "Capture images: 8" in markdown
    assert "Sparse quality: Good" in markdown


def test_safely_renders_user_text_and_handles_missing_optional_fields():
    content, _ = build_report_markdown(
        {
            "projectName": "# Heading\r\n[link](https://example.test)",
            "annotations": [{"text": "- injected\r\n## Different heading\n`code`"}],
            "limitations": ["Use <care> & review"],
        },
        {"ready": True, "items": [], "notes": [], "metadataPreview": {"finalModel": {"format": "glb"}}},
        {},
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    markdown = content.decode("utf-8")
    assert "# Delivery Report: \\# Heading \\[link\\]\\(https://example.test\\)" in markdown
    assert "- \\- injected \\#\\# Different heading \\`code\\`" in markdown
    assert "<care>" not in markdown
    assert "\\<care\\>" in markdown
    assert "\r" not in markdown
