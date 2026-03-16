from __future__ import annotations

import json
from pathlib import Path

from mcp_server.tools import (
    list_artifacts,
    list_skills,
    read_artifact,
    route_task_tool,
    write_artifact,
)


def test_read_artifact_existing_file_returns_content(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_DA_GUAN_JIA_ARTIFACTS_DIR", str(tmp_path))
    target = tmp_path / "notes" / "sample.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("hello", encoding="utf-8")

    result = read_artifact({"path": "artifacts/notes/sample.txt"})

    assert result == {"content": "hello", "exists": True}


def test_read_artifact_missing_file_returns_exists_false(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_DA_GUAN_JIA_ARTIFACTS_DIR", str(tmp_path))

    result = read_artifact({"path": "artifacts/missing.txt"})

    assert result["exists"] is False
    assert result["content"] is None


def test_read_artifact_rejects_path_traversal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_DA_GUAN_JIA_ARTIFACTS_DIR", str(tmp_path))

    result = read_artifact({"path": "../secret.txt"})

    assert result["exists"] is False
    assert "traversal" in result["error"]


def test_write_artifact_writes_new_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_DA_GUAN_JIA_ARTIFACTS_DIR", str(tmp_path))

    result = write_artifact({"path": "artifacts/output.json", "content": '{"ok": true}'})

    assert result["success"] is True
    assert (tmp_path / "output.json").read_text(encoding="utf-8") == '{"ok": true}'


def test_write_artifact_creates_intermediate_directories(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_DA_GUAN_JIA_ARTIFACTS_DIR", str(tmp_path))

    result = write_artifact({"path": "nested/deep/file.txt", "content": "created"})

    assert result["success"] is True
    assert (tmp_path / "nested" / "deep" / "file.txt").exists()


def test_write_artifact_rejects_path_traversal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_DA_GUAN_JIA_ARTIFACTS_DIR", str(tmp_path))

    result = write_artifact({"path": "../../escape.txt", "content": "nope"})

    assert result["success"] is False
    assert "traversal" in result["error"]


def test_list_artifacts_empty_directory_returns_empty_list(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_DA_GUAN_JIA_ARTIFACTS_DIR", str(tmp_path))

    result = list_artifacts({})

    assert result == {"files": [], "count": 0}


def test_list_artifacts_returns_expected_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_DA_GUAN_JIA_ARTIFACTS_DIR", str(tmp_path))
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    nested = tmp_path / "one" / "two.json"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("{}", encoding="utf-8")

    result = list_artifacts({"max_depth": 3})

    assert result["count"] == 2
    assert result["files"] == ["artifacts/a.txt", "artifacts/one/two.json"]


def test_list_artifacts_prefix_filter_works(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_DA_GUAN_JIA_ARTIFACTS_DIR", str(tmp_path))
    alpha = tmp_path / "alpha" / "a.json"
    beta = tmp_path / "beta" / "b.json"
    alpha.parent.mkdir(parents=True, exist_ok=True)
    beta.parent.mkdir(parents=True, exist_ok=True)
    alpha.write_text("{}", encoding="utf-8")
    beta.write_text("{}", encoding="utf-8")

    result = list_artifacts({"prefix": "alpha"})

    assert result == {"files": ["artifacts/alpha/a.json"], "count": 1}


def test_list_skills_without_filters_returns_all_skills() -> None:
    result = list_skills({})

    assert result["count"] >= 13
    assert any(skill["id"] == "route" for skill in result["skills"])


def test_list_skills_core_filter_returns_only_core() -> None:
    result = list_skills({"tier": "core"})

    assert result["count"] == 5
    assert all(skill["tier"] == "core" for skill in result["skills"])


def test_list_skills_component_domain_filter_returns_subset() -> None:
    result = list_skills({"component_domain": "clone"})

    assert result["count"] >= 1
    assert all("clone" in skill["component_domains"] for skill in result["skills"])


def test_route_task_tool_recommends_close_task_for_closure_description() -> None:
    result = route_task_tool({"task_description": "帮我把这件事闭环"})

    recommended_ids = [item["skill_id"] for item in result["recommended_skills"]]
    assert "close-task" in recommended_ids


def test_route_task_tool_returns_expected_structure() -> None:
    result = route_task_tool({"task_description": "帮我路由一个任务"})

    assert "recommended_skills" in result
    assert "routing_rationale" in result
    assert "human_boundary_needed" in result


def test_route_task_tool_handles_empty_description_without_raising() -> None:
    result = route_task_tool({"task_description": ""})

    assert result["recommended_skills"] == []
    assert result["human_boundary_needed"] is False
    assert result["error"] == "task_description is required"
