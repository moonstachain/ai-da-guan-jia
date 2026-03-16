from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ontology.router import SkillManifest, route_task


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "artifacts"
MANIFEST_PATH = REPO_ROOT / "skill-manifest.json"


def _artifacts_root() -> Path:
    override = os.environ.get("AI_DA_GUAN_JIA_ARTIFACTS_DIR")
    return Path(override).expanduser().resolve() if override else DEFAULT_ARTIFACTS_DIR


def _normalize_artifact_path(raw_path: str) -> tuple[Path | None, str | None]:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None, "path is required"
    if "\x00" in raw_path:
        return None, "path contains invalid characters"

    normalized = raw_path.strip().replace("\\", "/")
    if normalized.startswith("/"):
        return None, "absolute paths are not allowed"
    if normalized.startswith("artifacts/"):
        normalized = normalized[len("artifacts/") :]
    if normalized == "artifacts":
        normalized = ""

    parts = [part for part in normalized.split("/") if part]
    if any(part == ".." for part in parts):
        return None, "path traversal is not allowed"

    candidate = _artifacts_root()
    for part in parts:
        candidate = candidate / part

    try:
        candidate.relative_to(_artifacts_root())
    except ValueError:
        return None, "path must stay within artifacts/"

    return candidate, None


def _to_artifact_relative(path: Path) -> str:
    return f"artifacts/{path.relative_to(_artifacts_root()).as_posix()}"


def read_artifact(params: dict[str, Any]) -> dict[str, Any]:
    """
    读取本地 canonical artifact。
    """
    try:
        target_path, error = _normalize_artifact_path(params["path"])
        if error:
            return {"content": None, "exists": False, "error": error}
        assert target_path is not None
        if not target_path.exists() or not target_path.is_file():
            return {"content": None, "exists": False, "error": "file does not exist"}
        return {"content": target_path.read_text(encoding="utf-8"), "exists": True}
    except KeyError:
        return {"content": None, "exists": False, "error": "missing required parameter: path"}
    except FileNotFoundError:
        return {"content": None, "exists": False, "error": "file does not exist"}
    except OSError as exc:
        return {"content": None, "exists": False, "error": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive
        return {"content": None, "exists": False, "error": f"unexpected error: {exc}"}


def write_artifact(params: dict[str, Any]) -> dict[str, Any]:
    """
    写入本地 canonical artifact。
    """
    try:
        target_path, error = _normalize_artifact_path(params["path"])
        if error:
            return {"success": False, "error": error}
        assert target_path is not None
        content = params["content"]
        if not isinstance(content, str):
            return {"success": False, "error": "content must be a string"}
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        return {"success": True, "path": _to_artifact_relative(target_path)}
    except KeyError as exc:
        return {"success": False, "error": f"missing required parameter: {exc.args[0]}"}
    except OSError as exc:
        return {"success": False, "error": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive
        return {"success": False, "error": f"unexpected error: {exc}"}


def list_artifacts(params: dict[str, Any]) -> dict[str, Any]:
    """
    列出 artifacts 目录下的文件。
    """
    try:
        prefix_value = str(params.get("prefix", "") or "").strip()
        max_depth = int(params.get("max_depth", 3) or 3)
        if max_depth < 0:
            return {"files": [], "count": 0, "error": "max_depth must be non-negative"}

        normalized_prefix = prefix_value.replace("\\", "/")
        if normalized_prefix.startswith("artifacts/"):
            normalized_prefix = normalized_prefix[len("artifacts/") :]
        prefix_parts = [part for part in normalized_prefix.split("/") if part]
        if any(part == ".." for part in prefix_parts):
            return {"files": [], "count": 0, "error": "path traversal is not allowed"}

        root = _artifacts_root()
        if not root.exists():
            return {"files": [], "count": 0}

        files: list[str] = []
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(root)
            if len(relative.parts) > max_depth:
                continue
            relative_str = relative.as_posix()
            if normalized_prefix and not relative_str.startswith(normalized_prefix):
                continue
            files.append(f"artifacts/{relative_str}")

        files.sort()
        return {"files": files, "count": len(files)}
    except (TypeError, ValueError):
        return {"files": [], "count": 0, "error": "max_depth must be an integer"}
    except OSError as exc:
        return {"files": [], "count": 0, "error": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive
        return {"files": [], "count": 0, "error": f"unexpected error: {exc}"}


def list_skills(params: dict[str, Any]) -> dict[str, Any]:
    """
    查询 skill manifest。
    """
    try:
        manifest = SkillManifest(str(MANIFEST_PATH))
        skills = manifest.list_skills(
            tier=params.get("tier"),
            status=params.get("status"),
        )
        component_domain = params.get("component_domain")
        control_level = params.get("control_level")

        if component_domain is not None:
            skills = [
                skill
                for skill in skills
                if component_domain in skill.get("component_domains", [])
            ]
        if control_level is not None:
            skills = [
                skill
                for skill in skills
                if control_level in skill.get("control_levels", [])
            ]

        return {"skills": skills, "count": len(skills)}
    except FileNotFoundError:
        return {"skills": [], "count": 0, "error": "skill manifest not found"}
    except Exception as exc:  # pragma: no cover - defensive
        return {"skills": [], "count": 0, "error": f"unexpected error: {exc}"}


def route_task_tool(params: dict[str, Any]) -> dict[str, Any]:
    """
    对任务描述做路由推荐。
    """
    try:
        task_description = str(params.get("task_description", "") or "").strip()
        if not task_description:
            return {
                "recommended_skills": [],
                "routing_rationale": "缺少 task_description，无法做路由推荐",
                "human_boundary_needed": False,
                "error": "task_description is required",
            }

        manifest = SkillManifest(str(MANIFEST_PATH))
        context = {
            key: params[key]
            for key in ("component_domain", "control_level")
            if params.get(key) is not None
        }
        result = route_task(task_description, manifest, context=context)
        return {
            "recommended_skills": result.get("recommended_skills", []),
            "routing_rationale": result.get("routing_rationale", ""),
            "human_boundary_needed": result.get("human_boundary_needed", False),
            "warnings": result.get("warnings", []),
        }
    except FileNotFoundError:
        return {
            "recommended_skills": [],
            "routing_rationale": "",
            "human_boundary_needed": False,
            "error": "skill manifest not found",
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "recommended_skills": [],
            "routing_rationale": "",
            "human_boundary_needed": False,
            "error": f"unexpected error: {exc}",
        }

